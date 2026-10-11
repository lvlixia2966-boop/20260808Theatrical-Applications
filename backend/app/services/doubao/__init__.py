"""豆包能力接入包：方舟 REST + openspeech 语音（ASR/TTS）协议细节单点收敛。

对外只暴露语义层：ark_client 单例、speech_configured()、流式/单发 ASR、流式 TTS。
"""
from app.services.doubao.ark_client import ArkClient, ArkError, ark_client
from app.services.doubao.asr_stream import DoubaoAsrConnection, speech_configured

__all__ = ["ArkClient", "ArkError", "ark_client", "DoubaoAsrConnection", "speech_configured"]
