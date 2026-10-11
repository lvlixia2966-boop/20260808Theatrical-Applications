"""语音识别（ASR）引擎适配层：把会场收音的 PCM 音频流转为文字。

高内聚：引擎实现、可用性探测、断句策略统一收敛在此模块。
低耦合：对上只暴露 `AsrEngine` 抽象与 `create_asr_engine` 工厂，
       调用方（live_hub / RTC 网关）不感知具体引擎是豆包还是演示引擎。

引擎体系（对齐 TTS 的多引擎适配模式）：
  - DoubaoAsrEngine 豆包大模型流式 ASR（openspeech 云端，协议见 services/doubao/）
  - MockAsrEngine   演示引擎：无识别能力时按音频时长产出预设讲解词，
                    保证「收音→识别→翻译→广播→收听」全链路可演示

音频格式约定：PCM16LE / 单声道 / 16kHz（前端 AudioWorklet 采集即此格式）。
"""

import logging
import struct
from abc import ABC, abstractmethod

from app.config import settings

logger = logging.getLogger("asr")

# 句末标点：命中即切出一条最终字幕（识别引擎流式输出通常自带标点）
_SENTENCE_ENDINGS = ("。", "！", "？", "；", ".", "!", "?", ";")


class AsrResult:
    """一次喂入音频后的识别产出。"""

    __slots__ = ("partial", "finals")

    def __init__(self, partial: str = "", finals: list[str] | None = None):
        self.partial = partial  # 当前仍在进行中的句中片段（可随时间被改写）
        self.finals = finals or []  # 本次新确定的完整句子


class AsrEngine(ABC):
    """ASR 引擎抽象：输入 PCM 块，输出「部分句 + 完整句」。

    断句策略收敛在基类模板方法 `feed` 中：子引擎只需返回「当前段累积文本」，
    基类负责检测句末标点切出最终句，避免各引擎重复实现断句逻辑。
    """

    def feed(self, pcm: bytes, is_final: bool = False) -> AsrResult:
        """喂入一块 PCM 音频。

        Args:
            pcm: PCM16LE 单声道 16kHz 音频字节。
            is_final: 讲解停顿/结束时置 True，强制吐出段内剩余文本为最终句。
        """
        accumulated = self._recognize(pcm, is_final)
        finals, partial = self._split_finals(accumulated)
        if is_final:
            # 强制断句：段内剩余全部作为最终句，并重置引擎段状态
            if partial.strip():
                finals.append(partial.strip())
            partial = ""
            self.reset()
        return AsrResult(partial=partial, finals=finals)

    @abstractmethod
    def _recognize(self, pcm: bytes, is_final: bool) -> str:
        """识别一块音频，返回当前段累积文本（含句中未完部分）。"""

    @abstractmethod
    def reset(self) -> None:
        """重置段内状态（换讲/断句后调用）。"""

    @staticmethod
    def _split_finals(accumulated: str) -> tuple[list[str], str]:
        """按句末标点把累积文本切成 [完整句列表, 剩余部分句]。"""
        finals: list[str] = []
        buffer = accumulated
        while buffer:
            # 找最早的句末标点位置（含标点本身）
            cut = -1
            for i, ch in enumerate(buffer):
                if ch in _SENTENCE_ENDINGS:
                    cut = i + 1
                    break
            if cut <= 0:
                break
            sentence = buffer[:cut].strip()
            if sentence:
                finals.append(sentence)
            buffer = buffer[cut:]
        return finals, buffer


class DoubaoAsrEngine(AsrEngine):
    """豆包大模型流式 ASR 引擎（云端 openspeech）。

    引擎实例按会话创建（内含一条 WS 连接与段级状态，不可跨会话共享）；
    feed 节奏由调用方驱动（live 采集 200ms 块 / RTC 音频帧），
    每块发送后非阻塞拉取最新识别结果，返回当前段累积文本，
    断句由基类模板方法按句末标点完成。
    """

    def __init__(self):
        from app.services.doubao import DoubaoAsrConnection, speech_configured

        if not speech_configured():
            raise RuntimeError("豆包语音凭据未配置（doubao_speech_app_id / access_token）")
        self._conn = DoubaoAsrConnection()

    def _recognize(self, pcm: bytes, is_final: bool) -> str:
        return self._conn.send_audio(pcm, is_final)

    def reset(self) -> None:
        self._conn.reset()

    def close(self) -> None:
        """释放底层连接（RTC peer 断开时调用；live 会话随进程退出回收）。"""
        self._conn.close()


# 演示引擎预设讲解词：模拟剧场折子戏讲解，供全链路演示
_MOCK_SCRIPT = [
    "各位观众朋友，欢迎来到川蜀大剧院。",
    "今晚为大家呈现的是经典折子戏《秋江》。",
    "川剧历史悠久，融汇高腔、昆腔、胡琴、弹戏、灯调五种声腔。",
    "眼前这出《秋江》，讲的是陈妙常追赶潘必正的动人故事。",
    "请注意看演员的水袖功，行云流水，一气呵成。",
    "变脸是川剧的绝活之一，瞬息之间，气象万千。",
    "锣鼓点起，好戏马上开场，请大家静心欣赏。",
]

# 演示引擎每句之间的音频时长（秒）：约说一句话所需的时间
_MOCK_SECONDS_PER_LINE = 6.0
_SAMPLE_RATE = 16000
_BYTES_PER_SAMPLE = 2


class MockAsrEngine(AsrEngine):
    """演示引擎：不做真实识别，按喂入音频的时长逐句产出预设讲解词。

    用途：未部署豆包凭据的环境跑通「收音→字幕→翻译→广播」全链路，
    以及开发联调。真实部署时配置 openspeech 凭据即自动切换。
    """

    def __init__(self):
        self._heard_samples = 0  # 累计音频采样数（按 16kHz 折算时长）
        self._script_index = 0
        logger.warning("ASR 处于演示模式（MockAsrEngine）：按音频时长产出预设讲解词，不做真实识别")

    def _recognize(self, pcm: bytes, is_final: bool) -> str:
        samples = len(pcm) // _BYTES_PER_SAMPLE
        self._heard_samples += samples
        lines: list[str] = []
        threshold = int(_MOCK_SECONDS_PER_LINE * _SAMPLE_RATE)
        while self._heard_samples >= threshold and self._script_index < len(_MOCK_SCRIPT):
            self._heard_samples -= threshold
            lines.append(_MOCK_SCRIPT[self._script_index])
            self._script_index += 1
        return "".join(line for line in lines if line)

    def reset(self) -> None:
        pass


def create_asr_engine() -> AsrEngine:
    """按配置创建 ASR 引擎（auto 时优先豆包，凭据未配置回退演示引擎）。

    每次调用返回全新实例：引擎内含段级流式状态，须与会话一一对应。
    """
    name = settings.asr_engine.lower()
    if name in ("auto", "doubao"):
        try:
            return DoubaoAsrEngine()
        except Exception as exc:  # noqa: BLE001 - 探测失败需回退演示引擎
            logger.warning("豆包 ASR 引擎不可用（%s），回退演示模式", exc)
    return MockAsrEngine()


def pcm16_volume(pcm: bytes) -> float:
    """计算一块 PCM16 音频的平均振幅（0~1 估算），供音量可视化/静音检测。"""
    if not pcm:
        return 0.0
    count = len(pcm) // _BYTES_PER_SAMPLE
    if count == 0:
        return 0.0
    total = 0
    values = struct.unpack(f"<{count}h", pcm[: count * _BYTES_PER_SAMPLE])
    for v in values:
        total += abs(v)
    return total / (count * 32768.0)
