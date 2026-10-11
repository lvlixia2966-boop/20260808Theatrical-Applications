"""语音合成路由：音色列表 + 文本转音频，供前端扫码页调用。"""
from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.voices import default_voice
from app.schemas import ApiResponse, VoiceOut
from app.services import tts_service

router = APIRouter(prefix="/api/tts", tags=["语音合成"])


@router.get("/voices", response_model=ApiResponse[list[VoiceOut]])
def list_voices(lang: str | None = Query(None, description="按系统语言码过滤")):
    """返回可用的豆包音色列表；lang 非空时仅返回该语言音色。"""
    return ApiResponse(data=[VoiceOut(**v) for v in tts_service.list_voices(lang)])


@router.get("/synthesize")
async def synthesize(
    text: str = Query(..., description="待合成文本"),
    voice: str = Query("", description="音色 ID，留空则按 lang 取默认"),
    lang: str = Query("zh-CN", description="语言码，用于无 voice 时取默认音色"),
    rate: int = Query(0, ge=-50, le=50, description="语速百分比偏移"),
):
    """将文本合成为音频流返回（豆包 MP3）。未配置凭据时返回 503。"""
    voice_id = tts_service.resolve_voice(lang, voice)
    try:
        audio, mime = await tts_service.synthesize(text, voice_id, rate, lang_code=lang)
    except RuntimeError as exc:
        return Response(status_code=503, content=str(exc))
    if not audio:
        return Response(status_code=400, content="empty text")
    return Response(content=audio, media_type=mime)