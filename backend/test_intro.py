"""验证剧场介绍接口与 TTS。用后即删。"""
import json
import sys
import time
import urllib.parse

import requests

sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8000"

for lang in ["zh", "zh-CN", "en", "ja", "ko", "es", "fr", "de", "ru", "th", "xx"]:
    t0 = time.time()
    r = requests.get(f"{B}/api/live/intro?lang={lang}", timeout=30).json()
    dt = time.time() - t0
    data = r["data"]
    print(f"[{lang}] {dt:.1f}s -> lang={data['lang']} | {data['text'][:60]}")

text = requests.get(f"{B}/api/live/intro?lang=es", timeout=30).json()["data"]["text"][:40]
audio = requests.get(f"{B}/api/tts/synthesize?text={urllib.parse.quote(text)}&lang=es", timeout=60)
print("[tts es]", audio.status_code, audio.headers.get("content-type"), len(audio.content), "bytes")

text = requests.get(f"{B}/api/live/intro?lang=zh", timeout=30).json()["data"]["text"][:40]
audio = requests.get(f"{B}/api/tts/synthesize?text={urllib.parse.quote(text)}&lang=zh-CN", timeout=60)
print("[tts zh]", audio.status_code, audio.headers.get("content-type"), len(audio.content), "bytes")
