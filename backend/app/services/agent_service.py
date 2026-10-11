"""Agent 伴游服务：多语言问答编排（报价单 #9/#12）。

高内聚：RAG 召回 → 提示词组装 → 豆包 LLM → 引用校验 → 安全降级，全流程在此。
低耦合：检索走 retrieval_service、LLM 走 ark_client、记忆持久化走模型层；
       扩展包 #26 的场景工具（路线/票务/投诉）以 tools 预留位接入，不改主链路。

安全边界：仅答川剧与院内服务；LLM 未配置/超时/异常时按语言降级为
「引导至人工服务台」话术（degraded=True），绝不吐内部错误。
"""

import asyncio
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agent import AgentMessage, AgentSession
from app.services.doubao.ark_client import ark_client
from app.services.usage_meter import record as record_usage

logger = logging.getLogger("agent")

CHAT_TIMEOUT = 8.0        # 报价单 #19 性能口径内的会话上限
MEMORY_TURNS = 8          # 近 N 条消息作为会话记忆
MAX_SOURCES = 5

# 按语言的降级话术（人工服务台引导）
FALLBACK_TEXT = {
    "zh-CN": "抱歉，我暂时无法回答。请您前往服务台或咨询现场工作人员，我们会尽快为您解答。",
    "en": "Sorry, I can't answer right now. Please visit the service desk or ask our on-site staff.",
    "ja": "申し訳ありません、ただいま回答できません。サービスカウンターまたは係員にお尋ねください。",
    "ko": "죄송합니다. 지금은 답변할 수 없습니다. 서비스 데스크나 현장 직원에게 문의해 주세요.",
    "es": "Lo siento, no puedo responder ahora. Acuda al mostrador de información o al personal.",
    "fr": "Désolé, je ne peux pas répondre pour l'instant. Veuillez vous adresser au comptoir d'accueil.",
    "de": "Entschuldigung, ich kann gerade nicht antworten. Bitte wenden Sie sich an den Servicetresen.",
    "ru": "Извините, сейчас я не могу ответить. Обратитесь к сотруднику или на стойку информации.",
    "hi": "क्षमा करें, मैं अभी उत्तर नहीं दे सकता। कृपया सेवा डेस्क से संपर्क करें।",
    "th": "ขออภัย ตอนนี้ฉันตอบไม่ได้ กรุณาสอบถามที่เคาน์เตอร์บริการ",
    "vi": "Xin lỗi, tôi chưa thể trả lời lúc này. Vui lòng hỏi quầy dịch vụ.",
    "id": "Maaf, saya belum bisa menjawab. Silakan tanyakan di meja layanan.",
}


@dataclass
class AgentReply:
    text: str
    sources: list[dict] = field(default_factory=list)
    degraded: bool = False


def _lang_of(lang: str) -> str:
    """降级话术命中语言；未收录语言回退英文。"""
    return lang if lang in FALLBACK_TEXT else "en"


class AgentService:
    """伴游问答编排（进程内单例）。"""

    # ── 会话管理 ────────────────────────────────────────────────

    def create_session(self, db: Session, lang: str = "zh-CN", node_code: str = "") -> AgentSession:
        row = AgentSession(token=secrets.token_urlsafe(16), lang=lang or "zh-CN", node_code=node_code or "")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def get_session(self, db: Session, token: str) -> AgentSession | None:
        row = db.query(AgentSession).filter(AgentSession.token == (token or "").strip()).first()
        if row and row.is_active:
            row.last_active_at = datetime.now()
            db.commit()
            return row
        return None

    # ── 问答 ────────────────────────────────────────────────────

    async def chat(self, db: Session, session: AgentSession, text: str) -> AgentReply:
        text = (text or "").strip()
        if not text:
            return AgentReply(text=FALLBACK_TEXT[_lang_of(session.lang)], degraded=True)
        db.add(AgentMessage(session_id=session.id, role="user", content=text))
        db.commit()

        reply = await self._generate(db, session, text)
        db.add(AgentMessage(
            session_id=session.id, role="assistant", content=reply.text,
            sources_json=json.dumps(reply.sources, ensure_ascii=False), degraded=reply.degraded,
        ))
        db.commit()
        return reply

    async def _generate(self, db: Session, session: AgentSession, text: str) -> AgentReply:
        if not ark_client.is_configured():
            return AgentReply(text=FALLBACK_TEXT[_lang_of(session.lang)], degraded=True)

        # 1) RAG 召回
        from app.services.retrieval_service import retrieval_service

        try:
            units = await retrieval_service.retrieve(db, text, k=MAX_SOURCES, node_code=session.node_code)
        except Exception:  # noqa: BLE001 - 检索失败不阻断问答
            logger.exception("Agent 检索异常")
            units = []

        # 2) 组装消息：系统提示 + 会话记忆 + 上下文
        messages = [{"role": "system", "content": self._system_prompt(session, units)}]
        history = (
            db.query(AgentMessage)
            .filter(AgentMessage.session_id == session.id)
            .order_by(AgentMessage.id.desc())
            .limit(MEMORY_TURNS)
            .all()
        )
        for msg in reversed(history):
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": text})

        # 3) 豆包 LLM（超时/异常 → 降级）
        try:
            answer = await asyncio.wait_for(
                ark_client.chat(messages, temperature=0.5), timeout=CHAT_TIMEOUT
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent LLM 调用失败（%s），降级", exc)
            return AgentReply(text=FALLBACK_TEXT[_lang_of(session.lang)], degraded=True)

        record_usage("llm", _estimate_tokens(messages, answer), session_ref=f"agent:{session.token[:8]}")

        # 4) 引用校验：剔除无来源编号，返回实际命中的来源
        sources = self._source_list(units)
        answer = self._validate_citations(answer, sources)
        return AgentReply(text=answer, sources=sources)

    def _system_prompt(self, session: AgentSession, units) -> str:
        from app.core.languages import native_name

        lang_name = native_name(session.lang)
        prompt = (
            "你是四川省川剧院的伴游讲解员「川川」。只回答与川剧艺术、剧院参观、"
            "院内服务相关的问题；无关话题礼貌拒绝。回答必须使用"
            f"{lang_name}（{session.lang}）。风格亲切、简洁，控制在 150 字以内。"
        )
        if units:
            prompt += "\n\n以下是剧院知识库片段（回答时用句末 [编号] 标注来源；编号之外的来源不可编造）："
            for idx, u in enumerate(units, start=1):
                prompt += f"\n[{idx}] {u.node_name}·{u.title}：{u.content}"
        if session.node_code:
            prompt += f"\n游客当前所在节点：{session.node_code}，回答可优先结合该点位。"
        return prompt

    @staticmethod
    def _source_list(units) -> list[dict]:
        return [
            {"n": idx, "title": u.title, "node": u.node_name, "unit_id": u.unit_id}
            for idx, u in enumerate(units, start=1)
        ]

    @staticmethod
    def _validate_citations(answer: str, sources: list[dict]) -> str:
        """剔除指向不存在来源的编号（防幻觉引用），合法编号保留。"""
        valid = {s["n"] for s in sources}
        if not valid:
            answer = re.sub(r"\s*\[\d+\]", "", answer)
            return answer

        def _keep(match: re.Match) -> str:
            return match.group(0) if int(match.group(1)) in valid else ""

        return re.sub(r"\[(\d+)\]", _keep, answer)


def _estimate_tokens(messages: list[dict], answer: str) -> int:
    """粗估 token 数（中文约 1.5 字/token），供用量计量。"""
    chars = sum(len(m.get("content", "")) for m in messages) + len(answer)
    return max(1, int(chars / 1.5))


agent_service = AgentService()
