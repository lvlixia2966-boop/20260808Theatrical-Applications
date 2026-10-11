"""API 路由总入口：统一注册各模块子路由。"""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.earphones import router as earphones_router
from app.api.programs import router as programs_router
from app.api.reservations import router as reservations_router
from app.api.translation import router as translation_router
from app.api.tts import router as tts_router
from app.api.ai_photoshoot import router as ai_photoshoot_router
from app.api.live import router as live_router
from app.api.payments import router as payments_router
from app.api.rtc import router as rtc_router
from app.api.knowledge import router as knowledge_router
from app.api.agent import router as agent_router
from app.api.stats import router as stats_router
from app.api.shop import shop_admin as shop_admin_router
from app.api.shop import shop_public as shop_public_router
from app.api.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(earphones_router)
api_router.include_router(programs_router)
api_router.include_router(reservations_router)
api_router.include_router(translation_router)
api_router.include_router(tts_router)
api_router.include_router(ai_photoshoot_router)
api_router.include_router(live_router)
api_router.include_router(payments_router)
api_router.include_router(rtc_router)
api_router.include_router(knowledge_router)
api_router.include_router(agent_router)
api_router.include_router(shop_public_router)
api_router.include_router(shop_admin_router)
api_router.include_router(stats_router)
api_router.include_router(users_router)
