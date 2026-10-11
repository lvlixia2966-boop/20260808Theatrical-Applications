# -*- coding: utf-8 -*-
"""一次性工具：用本地 CosyVoice3（agent_ 伴生项目 :9881）烘焙剧场介绍演示音频。

用途：222 生产容器豆包 TTS 凭据未配置（/api/tts/synthesize 返回 503）期间，
前端剧场介绍播放按钮兜底播放本脚本产出的预合成音频，保证演示链路可出声。

产出：
  frontend/assets/audio/intro_demo_zh.mp3  中文完整介绍（欢迎/声腔/绝技/礼仪/实用信息）
  frontend/assets/audio/intro_demo_en.mp3  英文完整介绍

运行前置：agent_ CosyVoice 服务已启动（python run_cosy.py -p 9881，需 GPU）。
"""
import json
import os
import subprocess
import urllib.request

API = "http://127.0.0.1:9881/synthesize"
OUT_DIR = r"d:\dan\chuan\frontend\assets\audio"
TMP = r"d:\dan\agent_\_intro_tmp.wav"

ITEMS = [
    dict(name="intro_demo_zh",
         # 川话版（2026-09-07 用户指定）：地道四川话欢迎词
         # 指令 ≤24 字，服务端会自动加英文系统前缀与 <|endofprompt|>
         instr="用地道四川话，像剧场主持人摆欢迎词，热络亲切。<|endofprompt|>",
         text="欢迎来到四川省川剧院。本剧院以传承和弘扬川剧艺术为己任，川剧融汇高腔、昆腔、胡琴、弹戏、灯调五种声腔流派，尤以变脸、吐火两大绝技闻名于世。今晚的演出，将带您领略巴蜀戏曲的独特魅力。观演期间，请将手机调至静音，请勿使用闪光灯拍照。在收听席页面选择您的语言，即可获得实时的多语言讲解字幕。本场演出约九十分钟，中场休息十五分钟。请提前三十分钟凭购票信息在售票厅取票。迟到观众请听从工作人员指引，于幕间入场。祝您观演愉快！"),
]


def synth(item):
    body = json.dumps({"text": item["text"], "instruction": item["instr"], "speed": 1.0}).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = resp.read()
    assert data.startswith(b"RIFF"), data[:120]
    with open(TMP, "wb") as f:
        f.write(data)
    mp3 = os.path.join(OUT_DIR, item["name"] + ".mp3")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", TMP,
                        "-codec:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-ar", "24000", mp3],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(mp3):
        raise RuntimeError("ffmpeg 失败: " + r.stderr[:300])
    print(item["name"], round(os.path.getsize(mp3) / 1024), "KB")


for it in ITEMS:
    synth(it)
os.remove(TMP)
print("ALL DONE")
