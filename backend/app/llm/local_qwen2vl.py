"""
本地 Qwen2-VL 适配器 - LoongArch 降级方案
使用 transformers 加载 Qwen2-VL-7B-Instruct
"""
import asyncio
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.llm.base import (
    ModelAdapter, ChatRequest, ChatResponse, ChatMessage, MessageRole
)
from app.core.config import settings
from app.core.logger import logger


class LocalQwen2VLAdapter(ModelAdapter):
    """本地 Qwen2-VL 多模态模型适配器

    用于 LoongArch 等无云端访问能力的场景
    注意: LoongArch 上需用 transformers 后端，vLLM 兼容性待验证
    """

    _instance: Optional["LocalQwen2VLAdapter"] = None
    _executor = ThreadPoolExecutor(max_workers=2)

    def __new__(cls, *args, **kwargs):
        """单例模式：模型很大，不重复加载"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.model_path = settings.LOCAL_LLM.model_path
        self.backend = settings.LOCAL_LLM.backend
        self.device = settings.LOCAL_LLM.device
        self.model = None
        self.processor = None
        self._initialized = True

        logger.info(f"本地 Qwen2-VL 适配器初始化: model={self.model_path}, backend={self.backend}, device={self.device}")

    @property
    def mode(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return f"local/{Path(self.model_path).name or 'qwen2-vl'}"

    def _ensure_loaded(self):
        """懒加载模型"""
        if self.model is not None:
            return

        model_path = Path(self.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"本地模型路径不存在: {self.model_path}\n"
                f"请从 HuggingFace 下载 Qwen2-VL-7B-Instruct: "
                f"https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct"
            )

        if self.backend == "vllm":
            self._load_vllm()
        else:
            self._load_transformers()

    def _load_transformers(self):
        """使用 transformers 加载"""
        try:
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
            import torch
        except ImportError:
            raise ImportError("请先安装 transformers 和 torch: pip install transformers torch")

        logger.info("正在加载 Qwen2-VL 模型（首次加载较慢）...")
        self.processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True)
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_path,
            torch_dtype=torch.float32 if self.device == "cpu" else torch.float16,
            device_map=self.device,
            trust_remote_code=True,
        )
        self.model.eval()
        logger.info("✅ Qwen2-VL 模型加载完成")

    def _load_vllm(self):
        """使用 vLLM 加载（性能更好，但 LoongArch 兼容性待验）"""
        try:
            from vllm import LLM, SamplingParams
        except ImportError:
            raise ImportError("请先安装 vllm: pip install vllm")

        logger.info("正在通过 vLLM 加载 Qwen2-VL 模型...")
        self.model = LLM(
            model=self.model_path,
            trust_remote_code=True,
            dtype="float16",
            gpu_memory_utilization=0.9,
        )
        logger.info("✅ vLLM 加载完成")

    def _build_messages(self, request: ChatRequest) -> list:
        """构建 transformers 输入格式"""
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        for msg in request.messages:
            if isinstance(msg.content, str):
                content = [{"type": "text", "text": msg.content}]
            else:
                content = msg.content
            messages.append({"role": msg.role.value, "content": content})
        return messages

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """本地推理（CPU 慢，建议仅作降级）"""
        self._ensure_loaded()
        messages = self._build_messages(request)

        def _run_inference():
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            # 解析多模态输入
            from qwen_vl_utils import process_vision_info
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(self.device)

            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=request.temperature > 0,
            )
            generated_ids_trimmed = [
                out_ids[len(in_ids):]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            output_text = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
            return output_text[0]

        # 在线程池中跑推理（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(self._executor, _run_inference)

        return ChatResponse(
            content=content,
            model=f"local/{self.model_path}",
            usage={"total_tokens": len(content)},  # 简化统计
            finish_reason="stop",
        )

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """本地 Embedding

        默认使用 sentence-transformers + BGE-M3
        注意: 这个方法无论 cloud/local 模式都用本地 BGE-M3（统一向量化）
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("请先安装 sentence-transformers: pip install sentence-transformers")

        if not hasattr(self, "_embedder") or self._embedder is None:
            model_name = settings.EMBEDDING.model
            self._embedder = SentenceTransformer(model_name, device=self.device)
            logger.info(f"✅ Embedding 模型加载: {model_name}")

        # sentence-transformers 支持 batch + 异步包装
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            self._executor,
            lambda: self._embedder.encode(
                texts,
                batch_size=settings.EMBEDDING.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist(),
        )
        return embeddings

    async def parse_document(self, file_path: str) -> str:
        """本地文档解析（多模态 OCR）

        直接用 Qwen2-VL 的图像理解能力做 OCR
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 把 PDF 转图像
        if path.suffix.lower() == ".pdf":
            images = self._pdf_to_images(path)
        else:
            images = [str(path)]

        all_text = []
        for img in images:
            messages = [ChatMessage(
                role=MessageRole.USER,
                content=[
                    {"type": "image", "image": img},
                    {"type": "text", "text": "请精确识别图中的所有文字内容，按原文排版以 Markdown 格式输出。保留章节结构、表格、公式。"},
                ],
            )]
            response = await self.chat(ChatRequest(
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
            ))
            all_text.append(response.content)
        return "\n\n---\n\n".join(all_text)

    def _pdf_to_images(self, pdf_path: Path) -> List[str]:
        """PDF 转图像列表"""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("请先安装 pdf2image: pip install pdf2image")
        images = convert_from_path(str(pdf_path), dpi=200)
        out_dir = pdf_path.parent / f".{pdf_path.stem}_pages"
        out_dir.mkdir(exist_ok=True)
        paths = []
        for i, img in enumerate(images):
            p = out_dir / f"page_{i+1}.png"
            img.save(p, "PNG")
            paths.append(str(p))
        return paths
