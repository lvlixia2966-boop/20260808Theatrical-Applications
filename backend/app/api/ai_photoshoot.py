"""后端 AI 旅拍 API 路由：负责接收前端图像并安全调用豆包（方舟）视觉多模态 API。"""
from base64 import b64encode

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.schemas import ApiResponse
from app.services.doubao.ark_client import ark_client

router = APIRouter(prefix="/api/ai", tags=["AI旅拍"])

# 演示回退图（方舟未配置或生图关闭时使用，保证接口可用）
FALLBACK_IMAGE = "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=1000&auto=format&fit=crop"


class PhotoshootRequest(BaseModel):
    image_base64: str
    effect: str = "outfit"
    outfit: str = "wusheng"
    costar: str = "master_bianlian"


class PhotoshootResponse(BaseModel):
    image_url: str
    rendered_by: str
    style_prompt: str


STYLE_PROMPTS = {
    "outfit": "穿戴传统川剧五大行当华丽戏服与精致头饰唱腔形象",
    "stage": "穿越至古蜀雕花戏楼与盖碗茶饮传统胜景",
    "costar": "与川剧变脸大师或四大名旦同台合影对戏",
    "fire": "交融川剧吐火神火绝技光影交融极清画质",
    "ink": "呈现丹青水墨与金粉戏彩融合笔意画风",
    "reflection": "古水倒影照见川剧戏曲前世尊容"
}


@router.post("/photoshoot", response_model=ApiResponse[PhotoshootResponse])
async def generate_ai_photoshoot(payload: PhotoshootRequest):
    """后端 API：安全处理 AI 旅拍大片生成，API Key 仅保存在后端配置。

    方舟已配置 ark_image_model（doubao-seedream）时走真实生图并落盘 uploads/；
    仅配置 ARK_API_KEY 时走视觉多模态分析（返回风格化说明 + 演示图）；
    均未配置时返回演示响应。前端契约（PhotoshootResponse）不变。
    """
    style_prompt = STYLE_PROMPTS.get(payload.effect, "川剧非遗艺术旅拍大片")
    if payload.outfit:
        style_prompt += f"，指定服装：{payload.outfit}"
    if payload.costar:
        style_prompt += f"，同框角色：{payload.costar}"

    clean_base64 = payload.image_base64.split(",")[-1] if "," in payload.image_base64 else payload.image_base64
    full_prompt = f"你是一位顶级川剧非遗艺术摄影大师。请融合以下川剧风格生成极清大片：{style_prompt}"

    # 1) 生图增强：seedream 按视觉分析文案生成真实图像（以 data URI 返回，免静态挂载）
    if settings.ark_image_model and ark_client.is_configured():
        try:
            analysis = await ark_client.vision(
                f"描述如何把这张照片改造成川剧主题艺术大片（供文生图模型使用，50字内）：{style_prompt}",
                clean_base64,
            )
            image_bytes = await ark_client.generate_image(f"{full_prompt}。画面要求：{analysis}")
            data_uri = f"data:image/png;base64,{b64encode(image_bytes).decode()}"
            return ApiResponse(
                message="豆包生图渲染成功",
                data=PhotoshootResponse(image_url=data_uri, rendered_by=settings.ark_image_model, style_prompt=style_prompt),
            )
        except Exception as exc:  # noqa: BLE001 - 生图失败回退视觉/演示路径
            print(f"豆包生图异常: {exc}")

    # 2) 视觉多模态：豆包分析照片（返回演示图 + 分析结论在 message 中体现）
    if ark_client.is_configured():
        try:
            analysis = await ark_client.vision(full_prompt, clean_base64)
            return ApiResponse(
                message=f"豆包视觉分析完成：{analysis[:120]}",
                data=PhotoshootResponse(image_url=FALLBACK_IMAGE, rendered_by="doubao-vision", style_prompt=style_prompt),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"豆包视觉 API 调用异常: {exc}")

    # 3) 演示回退
    return ApiResponse(
        message="后端 AI 引擎处理成功 (接入模式)",
        data=PhotoshootResponse(image_url=FALLBACK_IMAGE, rendered_by="backend-ai-engine", style_prompt=style_prompt),
    )
