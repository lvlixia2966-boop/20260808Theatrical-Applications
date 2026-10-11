"""会场收音采集器：把剧场音源（服务器声卡线路输入）转为 PCM 块流。

高内聚：采集设备的选择、线程管理、回退策略统一收敛在此模块。
低耦合：对上只暴露 `AudioCapture` 抽象与 `create_capture` 工厂，
       产出统一为 PCM16LE / 单声道 / 16kHz 块，消费方（live_hub）不感知来源。

采集体系（对齐 ASR/TTS 的多引擎适配模式）：
  - SoundcardCapture 服务器声卡采集（调音台输出接入服务器输入设备，真实部署用）
  - MockCapture       演示采集器：定时产出带幅度的伪 PCM，
                      驱动演示 ASR 引擎产出预设讲解词，保证全链路无人值守可演示

真实部署接线：剧场调音台 AUX/Line-Out → 服务器声卡 Line-In，
            配置 capture_device 指定输入设备（默认取系统默认输入）。
"""
import asyncio
import logging
import math
import struct
import threading
import time
from abc import ABC, abstractmethod

from app.config import settings

logger = logging.getLogger("capture")

_SAMPLE_RATE = 16000
_BLOCK_MS = 200  # 每块时长：实时性与开销的平衡点
_SAMPLES_PER_BLOCK = _SAMPLE_RATE * _BLOCK_MS // 1000


class AudioCapture(ABC):
    """采集器抽象：start 开始产出 PCM 块并投递给回调，stop 停止。"""

    @abstractmethod
    def start(self, on_chunk: callable) -> None:
        """开始采集；on_chunk(bytes) 在采集线程中被调用（PCM16/16k/mono）。"""

    @abstractmethod
    def stop(self) -> None:
        """停止采集并释放设备。"""


class SoundcardCapture(AudioCapture):
    """服务器声卡采集器：sounddevice 输入流（PortAudio），独立线程回调。

    依赖 `pip install sounddevice`（wheel 自带 PortAudio，Windows 可用）。
    很多声卡不支持 16kHz 直采：按 16k → 48k → 44.1k 依次尝试打开，
    非 16k 采集时在回调内做最近邻抽取降采样（ASR 场景足够）。
    打开失败时由工厂回退演示采集器，不影响服务启动。
    """

    _CANDIDATE_RATES = (16000, 48000, 44100)

    def __init__(self, device=None):
        import sounddevice as sd  # 延迟导入：未安装不影响其他采集器

        self._sd = sd
        self._device = device if device is not None else settings.capture_device
        if self._device in ("", "-1", -1):
            self._device = None  # 系统默认输入
        self._stream = None

    def start(self, on_chunk: callable) -> None:
        last_error: Exception | None = None
        for rate in self._CANDIDATE_RATES:
            try:
                self._stream = self._sd.RawInputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="int16",
                    blocksize=rate * _BLOCK_MS // 1000,
                    device=self._device,
                    callback=self._make_callback(rate, on_chunk),
                )
                self._stream.start()
                logger.info("声卡采集已启动（设备=%s，采样率=%sHz）", self._device or "系统默认输入", rate)
                return
            except Exception as exc:  # noqa: BLE001 - 逐一尝试候选采样率
                last_error = exc
        raise last_error or RuntimeError("声卡采集启动失败")

    def _make_callback(self, rate: int, on_chunk: callable) -> callable:
        if rate == _SAMPLE_RATE:
            return lambda indata, _frames, _time, status: (
                logger.warning("采集状态告警：%s", status) if status else None,
                on_chunk(bytes(indata)),
            )

        # 非 16k 采集：最近邻抽取降采样（游标跨块连续，避免块边界丢样本）
        step = rate / _SAMPLE_RATE
        state = {"cursor": 0.0}

        def resample(indata, _frames, _time, status):
            if status:
                logger.warning("采集状态告警：%s", status)
            src = memoryview(indata).cast("h")
            cur = state["cursor"]
            out = []
            while cur < len(src):
                out.append(src[int(cur)])
                cur += step
            state["cursor"] = cur - len(src)
            if out:
                on_chunk(struct.pack(f"<{len(out)}h", *out))

        return resample

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
                logger.info("声卡采集已停止")


class MockCapture(AudioCapture):
    """演示采集器：独立线程每 200ms 产出一块带幅度的伪 PCM。

    幅度按正弦包络起伏模拟「有人在讲话」的电平；
    喂给演示 ASR 引擎（MockAsrEngine）即可按音频时长产出预设讲解词，
    实现「设置场次 → 到点自动开播 → 字幕/原声自动推送」的全链路无人值守演示。
    """

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, on_chunk: callable) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(on_chunk,), daemon=True)
        self._thread.start()
        logger.warning("采集处于演示模式（MockCapture）：定时产出伪 PCM，不做真实收音")

    def _run(self, on_chunk: callable) -> None:
        phase = 0.0
        while not self._stop_event.is_set():
            # 幅度包络：慢速正弦（约 20s 一周期）在 0.05~0.35 间起伏，模拟讲话电平
            envelope = 0.2 + 0.15 * math.sin(phase)
            phase += 0.1
            samples = []
            for i in range(_SAMPLES_PER_BLOCK):
                # 基频 220Hz + 幅度包络的「语音样」波形
                value = envelope * math.sin(2 * math.pi * 220 * i / _SAMPLE_RATE)
                samples.append(int(value * 32767))
            on_chunk(struct.pack(f"<{len(samples)}h", *samples))
            self._stop_event.wait(_BLOCK_MS / 1000.0)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


def create_capture() -> AudioCapture:
    """按配置创建采集器（auto 时优先声卡，不可用回退演示采集器）。"""
    name = settings.live_capture.lower()
    if name in ("auto", "soundcard"):
        try:
            capture = SoundcardCapture()
            # 试开即验：设备被占用/不存在时立即回退，不留到开播才发现
            probe = threading.Event()

            def _probe(_chunk):
                probe.set()

            capture.start(_probe)
            capture.stop()
            return capture
        except Exception as exc:  # noqa: BLE001 - 探测失败需回退演示采集器
            logger.warning("声卡采集不可用（%s），回退演示模式", exc)
    return MockCapture()


class CaptureWorker:
    """采集任务包装：把采集回调桥接到 asyncio 事件循环（调度器按场次启停）。

    采集回调运行在采集线程，此处经 loop.call_soon_threadsafe 转投递，
    保证 live_hub 的全异步管线不被跨线程调用破坏。
    """

    def __init__(self, on_chunk_async: callable):
        self._on_chunk_async = on_chunk_async  # 异步消费回调（live_hub 提供）
        self._capture: AudioCapture | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def running(self) -> bool:
        return self._capture is not None

    def start(self) -> None:
        if self._capture is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._capture = create_capture()
        self._capture.start(self._on_pcm)

    def stop(self) -> None:
        if self._capture is not None:
            try:
                self._capture.stop()
            finally:
                self._capture = None
                self._loop = None

    def _on_pcm(self, pcm: bytes) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._dispatch, pcm)

    def _dispatch(self, pcm: bytes) -> None:
        asyncio.ensure_future(self._on_chunk_async(pcm))
