"""翻译服务：将讲解文本翻译为目标语言。

高内聚：翻译逻辑与提供商切换统一收敛在此模块。
低耦合：通过「提供商」抽象隔离外部翻译 API，业务层只依赖接口。

按报价单 #8/#16，翻译统一走豆包（方舟 chat completions）：
术语对照（glossary.TERMS）注入提示词做前置纠错；调用失败时门面保守回退原文，
保证讲解与字幕管线绝不中断。若目标语言与源语言一致则原样返回。
"""
from abc import ABC, abstractmethod

from app.core.languages import SOURCE_LANGUAGE
from app.services.doubao.ark_client import ark_client


class TranslationProvider(ABC):
    """翻译提供商抽象接口。"""

    @abstractmethod
    def translate(self, text: str, target: str, source: str) -> str:
        raise NotImplementedError


class DoubaoTranslateProvider(TranslationProvider):
    """基于豆包大模型（方舟）的翻译提供商。

    系统提示词约束「只输出译文」；源句命中的术语标准译名注入提示词，
    对应报价单「术语纠错」前置。失败抛异常由门面回退原文。
    """

    def translate(self, text: str, target: str, source: str) -> str:
        prompt = self._build_prompt(text, target)
        result = ark_client.chat_sync(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        if not result:
            raise RuntimeError("豆包翻译返回空文本")
        return result

    @staticmethod
    def _build_prompt(text: str, target: str) -> str:
        from app.core.languages import native_name

        lang_name = native_name(target)
        prompt = (
            f"你是川剧剧院的专业翻译。把用户给出的中文讲解翻译为{lang_name}（{target}）。"
            "只输出译文本身，不要任何解释、引号或注释；保留人名与剧目的拼音原名。"
        )
        # 术语纠错前置：源句命中的术语直接给出标准译名
        try:
            from app.services.glossary_service import TERMS

            hints = [
                f"{term} → {translation}"
                for term, translations in TERMS.items()
                if term in text and target in translations
            ]
            if hints:
                prompt += "\n术语必须使用以下标准译名：\n" + "\n".join(hints)
        except Exception:  # noqa: BLE001 - 术语注入失败降级为纯翻译
            pass
        return prompt


class TranslationService:
    """翻译服务门面：统一入口，负责参数校验与错误兜底。"""

    def __init__(self, provider: TranslationProvider | None = None):
        self.provider = provider or DoubaoTranslateProvider()

    def translate(self, text: str, target: str, source: str = SOURCE_LANGUAGE) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        # 目标语言与源语言一致（或目标为中文），无需翻译
        if not target or target == source or target.startswith("zh"):
            return text
        try:
            return self.provider.translate(text, target, source)
        except Exception:  # noqa: BLE001 - 翻译服务不可用时回退原文，保证讲解可继续
            return text


translation_service = TranslationService()
