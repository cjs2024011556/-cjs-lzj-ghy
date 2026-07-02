"""
音频 API（5 模型全覆盖 - 语音能力）
- ASR：语音识别（paraformer-v2 / qwen-audio-asr）
- TTS：语音合成（cosyvoice-v2 / Sambert）
- Omni：全模态对话（qwen-omni-turbo）

赛题明文要求 5 种模型：大语言/视觉/全模态/语音/向量
"""
import base64
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.llm.factory import get_model_adapter
from app.core.logger import logger

router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="合成文本")
    voice: str = Field(default="Cherry", description="声音: Cherry(女)/Ethan(男)/Chelsie(女)/Serena(女)")
    sample_rate: int = Field(default=22050, ge=8000, le=48000)


class OmniRequest(BaseModel):
    text: str = Field(default="", description="文本输入")
    image_data_uri: Optional[str] = Field(default=None, description="图像 data URI（base64）")
    audio_data_uri: Optional[str] = Field(default=None, description="音频 data URI（base64）")
    system_prompt: Optional[str] = Field(default=None)


@router.post("/asr/recognize")
async def asr_recognize(audio: UploadFile = File(..., description="音频文件（wav/mp3/m4a）")):
    """语音识别（ASR）— 把录音转成文字

    现场检修师傅 → 说话提问 → 文字检索
    """
    try:
        # 读音频 bytes
        audio_bytes = await audio.read()
        mime = audio.content_type or "audio/wav"
        audio_data_uri = f"data:{mime};base64,{base64.b64encode(audio_bytes).decode()}"

        adapter = get_model_adapter()
        if not hasattr(adapter, "asr_recognize"):
            raise HTTPException(status_code=501, detail="当前适配器不支持 ASR（仅 Bailian 模式支持）")

        result = await adapter.asr_recognize(audio_data_uri)
        return {
            "text": result["text"],
            "sentences": result.get("sentences", []),
            "model": result.get("model"),
            "language": result.get("language", "zh"),
            "audio_size_kb": round(len(audio_bytes) / 1024, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts/synthesize")
async def tts_synthesize(req: TTSRequest):
    """语音合成（TTS）— 把文字转成 mp3

    SOP 步骤自动播报、检索答案朗读
    """
    try:
        adapter = get_model_adapter()
        if not hasattr(adapter, "tts_synthesize"):
            raise HTTPException(status_code=501, detail="当前适配器不支持 TTS")

        audio_bytes = await adapter.tts_synthesize(
            text=req.text,
            voice=req.voice,
            sample_rate=req.sample_rate,
        )
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="TTS 返回空音频")

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'inline; filename="tts_{req.voice}.wav"',
                "X-Audio-Size": str(len(audio_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/omni/chat")
async def omni_chat(req: OmniRequest):
    """全模态对话（qwen-omni-turbo）— 文本+图像+音频统一理解

    现场同时拍照+录音+提问 → 跨模态推理
    """
    try:
        adapter = get_model_adapter()
        if not hasattr(adapter, "omni_chat"):
            raise HTTPException(status_code=501, detail="当前适配器不支持 Omni")

        response = await adapter.omni_chat(
            text=req.text,
            image_data_uri=req.image_data_uri,
            audio_data_uri=req.audio_data_uri,
            system_prompt=req.system_prompt,
        )
        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Omni 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities")
async def get_capabilities():
    """探测 5 种模型能力（用于前端状态徽章）

    实际跑一遍轻量调用，避免只读配置而误判可用性
    """
    try:
        adapter = get_model_adapter()
        if not hasattr(adapter, "capabilities"):
            # 降级返回（local 模式只有 LLM + Embedding）
            return {
                "llm": {"available": True, "model": "local"},
                "embedding": {"available": True, "model": "BGE-M3"},
                "vl": {"available": False, "error": "本地模式不支持 VL"},
                "omni": {"available": False, "error": "本地模式不支持 Omni"},
                "asr": {"available": False, "error": "本地模式不支持 ASR"},
                "tts": {"available": False, "error": "本地模式不支持 TTS"},
            }
        return await adapter.capabilities()
    except Exception as e:
        logger.error(f"capabilities 探测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
