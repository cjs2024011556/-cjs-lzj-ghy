"""
阿里云百炼平台适配器（DashScope）
云端 LLM 模式默认实现 - 通过 dashscope SDK 调用

模型分类:
- 文本对话: qwen-plus / qwen-max / qwen-turbo → dashscope.Generation
- 多模态:   qwen-vl-max / qwen-vl-plus        → dashscope.MultiModalConversation
- 文本嵌入: text-embedding-v3                  → dashscope.TextEmbedding
- 文档 OCR: qwen-vl-ocr                        → MultiModalConversation

为什么用 SDK 而不是 OpenAI 兼容模式:
- 兼容模式对中文有 latin-1 ↔ UTF-8 双重编码 bug（产生乱码）
- SDK 是百炼官方推荐方式，参数、错误处理、限流都更完善
"""
from typing import List, Dict, Any, Union
import dashscope
from dashscope import Generation, MultiModalConversation, TextEmbedding, TextReRank
from dashscope.api_entities.dashscope_response import Message

from app.llm.base import (
    ModelAdapter, ChatRequest, ChatResponse, ChatMessage, MessageRole, ToolCall
)
from app.utils.images import encode_image_data_uri
from app.core.config import settings
from app.core.logger import logger


# 多模态视觉模型前缀（用于路由到 MultiModalConversation）
_VL_MODEL_PREFIXES = ("qwen-vl", "qwen2-vl")


def _is_vl_model(model: str) -> bool:
    return any(model.startswith(p) for p in _VL_MODEL_PREFIXES)


def _has_multimodal_content(messages: List[ChatMessage]) -> bool:
    """判断消息中是否包含图像/视频等多模态内容"""
    for msg in messages:
        if isinstance(msg.content, list):
            return True
    return False


def _parse_tool_calls(raw_tool_calls) -> List[ToolCall]:
    """从 dashscope 响应的 tool_calls 字段解析为 List[ToolCall]

    dashscope 格式（OpenAI 兼容）：
        [{"id": "call_xxx", "type": "function",
          "function": {"name": "search_kb", "arguments": "{...json...}"}}]
    """
    import json as _json
    out: List[ToolCall] = []
    if not raw_tool_calls:
        return out
    for tc in raw_tool_calls:
        try:
            # tc 可能是 dict 或对象
            if isinstance(tc, dict):
                tc_id = tc.get("id", f"call_{len(out)}")
                tc_type = tc.get("type", "function")
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
            else:
                tc_id = getattr(tc, "id", f"call_{len(out)}") or f"call_{len(out)}"
                tc_type = getattr(tc, "type", "function")
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                fn_name = getattr(fn, "name", "")
                raw_args = getattr(fn, "arguments", "{}")
            # arguments 通常是 JSON 字符串
            if isinstance(raw_args, str):
                try:
                    args_dict = _json.loads(raw_args) if raw_args.strip() else {}
                except _json.JSONDecodeError:
                    args_dict = {"_raw": raw_args}
            elif isinstance(raw_args, dict):
                args_dict = raw_args
            else:
                args_dict = {}
            out.append(ToolCall(id=str(tc_id), name=str(fn_name), arguments=args_dict))
        except Exception as e:
            logger.debug(f"tool_call 解析失败跳过: {e}")
    return out


class BailianAdapter(ModelAdapter):
    """阿里云百炼平台（DashScope）适配器"""

    def __init__(self):
        self.api_key = settings.CLOUD_LLM.api_key
        self.base_url = settings.CLOUD_LLM.base_url
        self.model = settings.CLOUD_LLM.model
        self.timeout = settings.CLOUD_LLM.timeout

        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY 未配置。请在 .env 中填入阿里云百炼平台的 API Key。"
            )

        # 全局配置（dashscope SDK 单例）
        dashscope.api_key = self.api_key
        if self.base_url and "compatible-mode" not in self.base_url:
            dashscope.base_http_api_url = self.base_url

    @property
    def mode(self) -> str:
        return "cloud"

    @property
    def model_name(self) -> str:
        return f"bailian/{self.model}"

    async def aclose(self) -> None:
        """dashscope SDK 无显式 client，无需关闭"""
        return None

    # ---- 流式文本对话（打字机效果）----
    async def chat_text_stream(self, request: ChatRequest):
        """流式调用 qwen-plus（仅文本）

        返回 AsyncIterator[str]，每段是 LLM 输出的增量文本
        基于 dashscope Generation.call(stream=True, incremental_output=True)
        """
        import asyncio
        from dashscope import Generation

        messages = self._build_text_messages(request)
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stream": True,               # 关键：开启流式
            "incremental_output": True,   # 关键：增量输出
            "result_format": "message",
        }

        loop = asyncio.get_event_loop()
        # dashscope 返回的是 sync generator，用 run_in_executor 桥接
        sync_gen = await loop.run_in_executor(
            None, lambda: Generation.call(**kwargs)
        )

        # 在线程池里迭代 sync generator，每次循环 yield 到事件循环
        # 用 asyncio.run_in_executor 包装 iter()，避免阻塞
        for chunk in sync_gen:
            if chunk.status_code != 200:
                raise RuntimeError(f"流式错误 {chunk.code}: {chunk.message}")
            try:
                if chunk.output and chunk.output.choices:
                    content = chunk.output.choices[0].message.content
                    if content:
                        # 让出事件循环，让前端能及时收到
                        await asyncio.sleep(0)
                        yield content
            except (AttributeError, KeyError):
                continue

    # ---- 内部：构建文本消息 ----
    def _build_text_messages(self, request: ChatRequest) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            content = m.content if isinstance(m.content, str) else self._flatten_content(m.content)
            msgs.append({"role": m.role.value, "content": content})
        return msgs

    def _flatten_content(self, content: List[Dict[str, Any]]) -> str:
        """将多模态 content 列表压平成纯文本（用于纯文本模型）"""
        parts = []
        for c in content:
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "image_url":
                parts.append("[图像]")
        return "\n".join(parts)

    # ---- 内部：构建多模态消息 ----
    def _build_multimodal_messages(self, request: ChatRequest) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": [{"text": request.system_prompt}]})
        for m in request.messages:
            if isinstance(m.content, str):
                msgs.append({"role": m.role.value, "content": [{"text": m.content}]})
            else:
                # m.content 已经是 OpenAI 风格的 [{type, text/image_url}, ...]
                # 转 dashscope 风格 [{text:...}] / [{image:...}]
                converted = []
                for c in m.content:
                    if c.get("type") == "text":
                        converted.append({"text": c["text"]})
                    elif c.get("type") == "image_url":
                        url = c.get("image_url", {}).get("url", "")
                        converted.append({"image": url})
                msgs.append({"role": m.role.value, "content": converted})
        return msgs

    # ---- 文本对话（Generation）----
    async def _chat_text(self, model: str, request: ChatRequest) -> ChatResponse:
        messages = self._build_text_messages(request)
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "result_format": "message",
        }
        # 聚群 C: 透传 tools
        if request.tools:
            kwargs["tools"] = request.tools
            if request.tool_choice is not None:
                kwargs["tool_choice"] = request.tool_choice
        # dashscope SDK 调用是同步的，放到线程池里跑避免阻塞事件循环
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: Generation.call(**kwargs)
        )

        if response.status_code != 200:
            logger.error(f"百炼 Generation 失败: {response.code} - {response.message}")
            raise RuntimeError(f"百炼 API 错误 {response.code}: {response.message}")

        message = response.output.choices[0].message
        content = message.content or ""
        tool_calls = _parse_tool_calls(getattr(message, "tool_calls", None))
        usage = {
            "prompt_tokens": response.usage.input_tokens if response.usage else 0,
            "completion_tokens": response.usage.output_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return ChatResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason=response.output.choices[0].finish_reason or "stop",
            raw=response,
            tool_calls=tool_calls,
        )

    # ---- 多模态对话（MultiModalConversation）----
    async def _chat_multimodal(self, model: str, request: ChatRequest) -> ChatResponse:
        messages = self._build_multimodal_messages(request)
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "vl_high_resolution_images": False,
        }
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: MultiModalConversation.call(**kwargs)
        )

        if response.status_code != 200:
            logger.error(f"百炼 MultiModal 失败: {response.code} - {response.message}")
            raise RuntimeError(f"百炼 API 错误 {response.code}: {response.message}")

        # 多模态返回可能是 list（content list）
        raw_content = response.output.choices[0].message.content
        if isinstance(raw_content, list):
            content = "".join(
                c.get("text", "") for c in raw_content if isinstance(c, dict) and "text" in c
            )
        else:
            content = raw_content

        usage = {
            "prompt_tokens": response.usage.input_tokens if response.usage else 0,
            "completion_tokens": response.usage.output_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return ChatResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason=response.output.choices[0].finish_reason or "stop",
            raw=response,
        )

    # ---- 对外：chat ----
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return await self._chat_with_model(self.model, request)

    async def _chat_with_model(self, model: str, request: ChatRequest) -> ChatResponse:
        """支持模型覆盖的内部调用（用于 OCR 等特殊场景）"""
        if _is_vl_model(model) or _has_multimodal_content(request.messages):
            return await self._chat_multimodal(model, request)
        return await self._chat_text(model, request)

    # ---- Embedding ----
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """调用百炼 Embedding 向量化（U1 自适应：按 EMBEDDING_MODEL 选 model + dim）

        错误必须 raise — 返回零向量会让 Milvus 检索污染。
        """
        import asyncio
        from app.constants.embedding_models import (
            get_model_dim, supports_custom_dim,
        )

        model_name = settings.EMBEDDING.model
        # 自定义 dim 仅 v3 系列支持；其他用固定 dim
        if supports_custom_dim(model_name):
            dim = settings.EMBEDDING.dim
        else:
            dim = get_model_dim(model_name, settings.EMBEDDING.dim)

        loop = asyncio.get_event_loop()

        def _do_embed():
            kwargs = {
                "model": model_name,
                "input": texts,
                "text_type": "document",
            }
            # 仅 v3 系列传 dimension 参数
            if supports_custom_dim(model_name):
                kwargs["dimension"] = dim
            return TextEmbedding.call(**kwargs)

        response = await loop.run_in_executor(None, _do_embed)

        if response.status_code != 200:
            raise RuntimeError(f"百炼 Embedding 失败: {response.code} - {response.message}")

        return [item["embedding"] for item in response.output["embeddings"]]

    # ---- Rerank（U2：用百炼 gte-rerank / qwen3-rerank 对 hits 重排序）----
    async def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        """返回 documents 按相关性降序的索引列表

        Args:
            query: 用户原始 query
            documents: 候选 doc 文本列表
            top_n: 保留前 N 个

        Returns:
            索引列表（按相关性降序）。如失败则返回原顺序 [0..min(len, top_n)]。
        """
        if not documents:
            return []
        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _do_rerank():
                return TextReRank.call(
                    model=settings.RERANK_MODEL or "gte-rerank",
                    query=query,
                    documents=documents,
                    top_n=min(top_n, len(documents)),
                )

            response = await loop.run_in_executor(None, _do_rerank)
            if response.status_code != 200:
                logger.warning(f"rerank 失败 ({response.status_code}): {response.message}，降级用原顺序")
                return list(range(min(len(documents), top_n)))

            # response.output.results = [{index, relevance_score}, ...] 按 score 降序
            return [r.index for r in response.output.results[:top_n]]
        except Exception as e:
            logger.warning(f"rerank 异常: {e}，降级用原顺序")
            return list(range(min(len(documents), top_n)))

    # ---- OCR 文档解析 ----
    async def parse_document(self, file_path: str) -> str:
        """用 qwen-vl-ocr 做文档识别（图文混排）"""
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        image_data = encode_image_data_uri(str(path))
        messages = [{
            "role": "user",
            "content": [
                {"image": image_data},
                {"text": "请识别并提取这张图中的所有文字内容，按原文结构以 Markdown 格式输出。"},
            ],
        }]

        import asyncio
        loop = asyncio.get_event_loop()

        # 优先 OCR 模型；失败时降级
        try:
            response = await loop.run_in_executor(
                None,
                lambda: MultiModalConversation.call(
                    model="qwen-vl-ocr",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=4096,
                ),
            )
            if response.status_code != 200:
                raise RuntimeError(response.message)
            raw = response.output.choices[0].message.content
            if isinstance(raw, list):
                return "".join(c.get("text", "") for c in raw if isinstance(c, dict))
            return raw
        except Exception as e:
            logger.warning(f"OCR 模型调用失败，使用主模型降级: {e}")
            response = await self._chat_multimodal(
                "qwen-vl-max",
                ChatRequest(
                    messages=[ChatMessage(
                        role=MessageRole.USER,
                        content=[
                            {"type": "image_url", "image_url": {"url": image_data}},
                            {"type": "text", "text": "请识别并提取这张图中的所有文字内容，按原文结构以 Markdown 格式输出。"},
                        ],
                    )],
                    temperature=0.1,
                    max_tokens=4096,
                ),
            )
            return response.content

    # ===================== 全模态 / 语音（5 模型全覆盖）=====================

    async def omni_chat(
        self,
        text: str = "",
        image_data_uri: str | None = None,
        audio_data_uri: str | None = None,
        system_prompt: str | None = None,
    ) -> ChatResponse:
        """qwen-omni-turbo 全模态对话（文本+图像+音频统一理解）

        赛题要求"全模态模型"。Omni 是 Qwen 系列目前最强大的跨模态模型，
        支持文本/图像/音频/视频输入，文本/音频输出。
        """
        content_list: List[Dict[str, Any]] = []
        if text:
            content_list.append({"text": text})
        if image_data_uri:
            content_list.append({"image": image_data_uri})
        if audio_data_uri:
            content_list.append({"audio": audio_data_uri})

        if not content_list:
            raise ValueError("omni_chat 至少需要文本/图像/音频其中一种输入")

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": [{"text": system_prompt}]})
        messages.append({"role": "user", "content": content_list})

        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: MultiModalConversation.call(
                model="qwen-omni-turbo",
                messages=messages,
                temperature=0.3,
                top_p=0.9,
                max_tokens=1500,
                modalities=["text"],  # 输出模态：仅文本
            ),
        )
        if response.status_code != 200:
            raise RuntimeError(f"Omni 模型错误 {response.code}: {response.message}")

        raw = response.output.choices[0].message.content
        content = "".join(c.get("text", "") for c in raw if isinstance(c, dict)) if isinstance(raw, list) else raw

        return ChatResponse(
            content=content,
            model="qwen-omni-turbo",
            usage={
                "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                "completion_tokens": response.usage.output_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.output.choices[0].finish_reason or "stop",
        )

    async def asr_recognize(
        self,
        audio_data_uri: str,
        language_hints: List[str] | None = None,
    ) -> Dict[str, Any]:
        """语音识别（ASR）— 通过 qwen-omni-turbo 处理音频输入

        设计取舍：百炼的 paraformer-v2 需要把音频上传到 OSS 才能用（API 仅接 file_urls）。
        为简化演示流程，直接用 qwen-omni-turbo 处理音频（它原生支持音频输入），
        并通过 prompt 让它只输出转写文字。
        """
        import asyncio
        loop = asyncio.get_event_loop()

        sys_prompt = (
            "你是一个高精度的语音转写助手。请将用户提供的音频准确转写成文字。"
            "只输出转写后的文本，不要做任何解释、标点修正或翻译。"
            "如果听不清，输出 [静音]。"
        )

        # 直接用 omni 的音频输入能力
        response = await self.omni_chat(
            text="请把这段音频转写成文字",
            audio_data_uri=audio_data_uri,
            system_prompt=sys_prompt,
        )
        text = response.content.strip()
        # 兜底：去掉 [静音] 等标记
        if text in ("[静音]", "[无声]", ""):
            text = ""

        return {
            "text": text,
            "sentences": [{"text": text, "begin_time": 0, "end_time": 0}] if text else [],
            "model": "qwen-omni-turbo (asr)",
            "language": (language_hints or ["zh"])[0],
        }

    async def tts_synthesize(
        self,
        text: str,
        voice: str = "Cherry",
        sample_rate: int = 22050,
    ) -> bytes:
        """语音合成（TTS）— qwen-tts

        输入：文本（≤ 500 字）
        输出：wav 字节流
        voice: Cherry(女)/Ethan(男)/Chelsie(女)/Serena(女) — 百炼 qwen-tts 支持的音色
        """
        import asyncio
        from dashscope.audio.qwen_tts import SpeechSynthesizer

        loop = asyncio.get_event_loop()

        def _do_tts() -> dict:
            return SpeechSynthesizer.call(
                model="qwen-tts",
                text=text,
                voice=voice,
            )

        response = await loop.run_in_executor(None, _do_tts)
        if not response or getattr(response, "status_code", 0) != 200:
            raise RuntimeError(f"qwen-tts 错误: {getattr(response, 'message', 'unknown')}")

        # 响应包含 output.audio.url（OSS 链接，wav 格式）
        audio_url = None
        if hasattr(response, "output") and response.output:
            audio_data = response.output.audio if hasattr(response.output, "audio") else None
            if isinstance(audio_data, dict):
                audio_url = audio_data.get("url")

        if not audio_url:
            raise RuntimeError("qwen-tts 未返回音频 URL")

        # 下载 OSS 音频到 bytes
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(audio_url)
            r.raise_for_status()
            return r.content

    # ---- 意图识别（轻量小模型）----
    async def classify_intent(
        self,
        text: str,
        candidate_intents: List[str] | None = None,
    ) -> Dict[str, Any]:
        """意图分类（用 qwen-flash 阿里云小模型）

        输入：用户消息
        输出：{"intent": str, "confidence": float, "reason": str}
        """
        import asyncio
        from dashscope import Generation

        if candidate_intents is None:
            candidate_intents = ["maintenance", "casual"]

        intents_desc = {
            "maintenance": "工业设备检修相关问题（设备故障、检修方法、SOP 操作、零部件更换、技术参数、保养维护等）",
            "casual": "日常闲聊、问候、闲聊、打招呼、问天气、问 AI 自身等与设备检修无关的话题",
        }
        intents_text = "\n".join(
            f"- {k}: {intents_desc.get(k, k)}" for k in candidate_intents
        )

        system_prompt = f"""你是一个意图分类器。根据用户输入，准确判断用户意图属于以下哪一类：

{intents_text}

只输出 JSON，不要输出任何其他内容。格式：
{{"intent": "<分类>", "confidence": 0.0-1.0, "reason": "<一句话解释>"}}"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: Generation.call(
                model="qwen-flash",  # 阿里云小模型，最快最便宜
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                top_p=0.9,
                max_tokens=200,
                result_format="message",
            ),
        )

        if response.status_code != 200:
            logger.warning(f"意图识别失败: {response.code} - {response.message}")
            # 兜底：默认 casual（避免误用 RAG 资源）
            return {
                "intent": "casual",
                "confidence": 0.0,
                "reason": f"意图识别失败（{response.message}），默认闲聊",
            }

        content = response.output.choices[0].message.content.strip()
        # 解析 JSON（容错：去掉 markdown 包裹）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        import json as json_mod
        try:
            result = json_mod.loads(content)
            intent = result.get("intent", "casual")
            if intent not in candidate_intents:
                intent = "casual"
            return {
                "intent": intent,
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", ""),
            }
        except Exception as e:
            logger.warning(f"意图 JSON 解析失败: {e}, content: {content[:100]}")
            return {
                "intent": "casual",
                "confidence": 0.0,
                "reason": "解析失败，默认闲聊",
            }

    # ---- 5 模型状态探测（供 /llm/status 用）----
    async def capabilities(self) -> Dict[str, Any]:
        """返回当前适配器支持的 5 种模型能力（用于前端徽章展示）"""
        caps = {
            "llm": {"available": True, "model": self.model, "provider": "bailian"},
            "vl": {"available": True, "model": "qwen-vl-ocr / qwen-vl-plus", "provider": "bailian"},
            "embedding": {"available": True, "model": "text-embedding-v3", "provider": "bailian"},
            "omni": {"available": False, "model": "qwen-omni-turbo", "provider": "bailian", "error": "未实现或未授权"},
            "asr": {"available": False, "model": "qwen-omni-turbo (ASR)", "provider": "bailian", "error": "未实现或未授权"},
            "tts": {"available": False, "model": "qwen-tts", "provider": "bailian", "error": "未实现或未授权"},
        }
        # 实际探测（每个都尝试 1 次轻量调用）
        try:
            # LLM 已经在 chat 里
            caps["llm"]["available"] = True
        except Exception as e:
            caps["llm"]["error"] = str(e)

        try:
            # Embedding 轻量探测
            await self.embed(["test"])
            caps["embedding"]["available"] = True
            caps["embedding"]["error"] = None
        except Exception as e:
            caps["embedding"]["available"] = False
            caps["embedding"]["error"] = str(e)[:100]

        try:
            # VL 探测：用 parse_document（OCR 路径已验证）
            import tempfile, base64
            tiny_png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            )
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(tiny_png)
                tmp = f.name
            await self.parse_document(tmp)
            caps["vl"]["available"] = True
            caps["vl"]["error"] = None
        except Exception as e:
            caps["vl"]["available"] = False
            caps["vl"]["error"] = str(e)[:100]

        try:
            # Omni 用纯文本探测（最轻量）
            await self.omni_chat(text="你好")
            caps["omni"]["available"] = True
            caps["omni"]["error"] = None
        except Exception as e:
            caps["omni"]["error"] = str(e)[:100]

        try:
            # 用真实的 WAV（1 秒静音）测 ASR
            import base64
            silence_wav = (
                "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
            )
            result = await self.asr_recognize(silence_wav)
            caps["asr"]["available"] = True
            caps["asr"]["error"] = None
        except Exception as e:
            caps["asr"]["error"] = str(e)[:100]

        try:
            await self.tts_synthesize("测试")
            caps["tts"]["available"] = True
            caps["tts"]["error"] = None
        except Exception as e:
            caps["tts"]["error"] = str(e)[:100]

        return caps
