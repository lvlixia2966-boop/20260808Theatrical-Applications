"""翻译与语音路由：语言清单 + 文本翻译，供前端扫码页调用。"""
from fastapi import APIRouter

from app.core.languages import LANGUAGES
from app.schemas import ApiResponse, LanguageOut, TranslateOut, TranslateRequest
from app.services.translation_service import translation_service

router = APIRouter(prefix="/api", tags=["翻译与语音"])


@router.get("/languages", response_model=ApiResponse[list[LanguageOut]])
def list_languages():
    """返回主流语言清单（按使用人数排序），供前端语言/语音选择。"""
    return ApiResponse(data=[LanguageOut(**item) for item in LANGUAGES])


@router.post("/translate", response_model=ApiResponse[TranslateOut])
def translate(payload: TranslateRequest):
    """将讲解文本翻译为目标语言。"""
    text = translation_service.translate(payload.text, payload.target, payload.source)
    return ApiResponse(
        data=TranslateOut(text=text, target=payload.target, source=payload.source)
    )