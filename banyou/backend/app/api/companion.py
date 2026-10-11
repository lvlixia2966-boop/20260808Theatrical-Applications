"""AI 伴游对话开放接口：知识库 + 位置上下文的纯对话伴游（含耳机语音链）。"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import companion, voice

router = APIRouter()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    lat: float | None = Query(None, ge=-90, le=90)
    lng: float | None = Query(None, ge=-180, le=180)
    area_id: int | None = None
    route_id: int | None = None
    history: list[dict[str, str]] = []


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    lang: str = "zh"
    rate: float = 1.0


@router.post("/companion/chat")
def companion_chat(body: ChatIn, db: Session = Depends(get_db)):
    """发一条消息，伴游讲解员结合「你此刻的位置 + 景区知识库」作答。"""
    return companion.chat(
        db, message=body.message.strip(),
        lat=body.lat, lng=body.lng,
        area_id=body.area_id, route_id=body.route_id,
        history=body.history,
    )


@router.get("/companion/locate")
def companion_locate(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """定位 → 知识锚点：最近点位、所属景区、是否已到站。"""
    return companion.build_context(db, lat, lng, None, None)


@router.get("/companion/voice-status")
def companion_voice_status():
    """前端语音能力探测：服务端 ASR/TTS 是否已配置（决定麦克风与播报链路）。"""
    return {"asr": voice.asr_ready(), "tts": voice.tts_ready()}


@router.post("/companion/asr")
async def companion_asr(audio: UploadFile):
    """录音 → 文本（豆包大模型 ASR；浏览器 MediaRecorder 的 webm/opus 均可）。"""
    if not voice.asr_ready():
        raise HTTPException(503, "语音识别未配置（DOUBAO_SPEECH_* 凭据缺失）")
    data = await audio.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "录音超过 8MB 限制")
    text = voice.asr_recognize(data)
    return {"text": text}


@router.post("/companion/tts")
def companion_tts(body: TtsIn):
    """文本 → MP3（豆包 TTS）；浏览器 Audio 播放时自动路由到已连接的蓝牙耳机。"""
    if not voice.tts_ready():
        raise HTTPException(503, "语音合成未配置（DOUBAO_SPEECH_* 凭据缺失）")
    try:
        mp3 = voice.tts_speak(body.text, body.lang, body.rate)
    except Exception as exc:  # noqa: BLE001 - 合成失败前端回退浏览器 TTS
        raise HTTPException(502, f"语音合成失败：{exc}") from exc
    if not mp3:
        raise HTTPException(502, "语音合成返回空音频")
    return Response(content=mp3, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
