"""蓝牙校验逻辑：判定前端上报的蓝牙设备是否与登记的耳机匹配。

识别策略（服务端侧）：
- 前端通过 Web Bluetooth API 扫描并连接到目标耳机，读取其「设备名」及
  「厂商自定义广播数据(mfgData)」后上报。
- 服务端将上报值与耳机登记信息比对，判定是否为预期设备。
- 说明：普通蓝牙耳机不暴露全局唯一硬件序列号，最常见的强标识是
  厂商自定义广播数据中的设备序列号；仅凭设备名无法区分同型号耳机。
"""
from app.config import settings
from app.models.earphone import Earphone


def normalize_device_name(value: str | None) -> str:
    return (value or "").strip().replace(" ", "")


def verify_earphone_device(
    earphone: Earphone,
    reported_device_name: str | None = None,
    reported_mfg_data: str | None = None,
) -> dict:
    """校验上报的蓝牙设备信息是否匹配耳机登记信息。

    返回结构：
      {"matched": bool, "reason": str, "verified": bool}
    verified=True 表示已完成强校验（读到了序列号/厂商数据）。
    """
    if not settings.bluetooth_verify_required:
        return {"matched": True, "reason": "蓝牙校验已关闭，跳过", "verified": False}

    # 1) 若能读到厂商自定义数据中的序列号，优先做强校验
    expected_serial = (earphone.serial_number or "").strip()
    if expected_serial:
        if reported_mfg_data and expected_serial.lower() in reported_mfg_data.lower():
            return {"matched": True, "reason": "厂商数据序列号匹配", "verified": True}
        return {
            "matched": False,
            "reason": "厂商数据序列号不匹配，请检查耳机的型号/序列号",
            "verified": True,
        }

    # 2) 退而求其次：设备名匹配（可区分不同型号，但同型号无法区分）
    expected_name = normalize_device_name(earphone.device_name)
    reported_name = normalize_device_name(reported_device_name)
    if expected_name:
        if reported_name and reported_name == expected_name:
            return {"matched": True, "reason": "蓝牙设备名匹配", "verified": False}
        return {"matched": False, "reason": "蓝牙设备名不匹配", "verified": False}

    # 3) 耳机未登记任何蓝牙标识，无法判定
    return {"matched": False, "reason": "该耳机未登记蓝牙标识，无法校验", "verified": False}