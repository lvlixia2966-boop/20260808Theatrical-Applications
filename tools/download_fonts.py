# -*- coding: utf-8 -*-
"""一次性脚本：从 npmmirror files API 按需拉取 @fontsource 字体文件（国内可直连），
提取 Noto Serif SC 700/900 + Outfit 400/600/800 的 woff2 子集与 CSS，
落到 frontend/assets/fonts/（fonts.css + files/*.woff2）。
Ma Shan Zheng 使用项目已有 MaShanZheng-Regular.ttf，无需下载。
运行：C:\\Python311\\python.exe tools\\download_fonts.py
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "frontend" / "assets" / "fonts"
FILES_DIR = FONT_DIR / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

WANTED = {
    "@fontsource/outfit": ["400", "600", "800"],
    "@fontsource/noto-serif-sc": ["700", "900"],
}


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8")


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


css_out = []
total = 0
for pkg, weights in WANTED.items():
    ver = json.loads(fetch_text(f"https://registry.npmmirror.com/{pkg}/latest"))["version"]
    base = f"https://registry.npmmirror.com/{pkg}/{ver}/files"
    name = pkg.split("/")[-1]
    for w in weights:
        css = fetch_text(f"{base}/{w}.css")
        files = sorted(set(re.findall(r"\.{1,2}/files/([\w.-]+\.woff2)", css)))
        for f in files:
            target = FILES_DIR / f
            if not target.exists():
                blob = fetch_bytes(f"{base}/files/{f}")
                target.write_bytes(blob)
                total += len(blob)
        css = css.replace("./files/", "files/").replace("../files/", "files/")
        css_out.append(f"/* {name} w{w} */\n{css}")
        print(f"{name} w{w}: {len(files)} 个 woff2")

(FONT_DIR / "fonts.css").write_text("\n".join(css_out), encoding="utf-8")
print(f"完成：本次下载 {total // 1024} KB，files 总计 {sum(f.stat().st_size for f in FILES_DIR.glob('*.woff2')) // 1024} KB")
