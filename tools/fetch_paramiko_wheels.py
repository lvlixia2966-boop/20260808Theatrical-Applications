# -*- coding: utf-8 -*-
"""一次性脚本：绕过失效的系统代理，用 urllib 从 PyPI 镜像直接下载
paramiko 及其依赖的 Windows wheel，落盘 tools/wheels/ 供 pip 本地安装。
运行：C:\\Python311\\python.exe tools\\fetch_paramiko_wheels.py
"""
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "wheels"
OUT.mkdir(exist_ok=True)
INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"

PKGS = ["cffi", "pycparser", "bcrypt", "pynacl", "cryptography", "invoke", "paramiko"]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


for pkg in PKGS:
    html = fetch(f"{INDEX}/{pkg}/").decode("utf-8", "ignore")
    # 取版本号排序，选最新版本；html 链接形如 href="../packages/..../name-ver-....whl#sha256=..."
    links = re.findall(r'href="([^"]+\.whl)#sha256=([^"]+)"', html)
    # 链接是相对路径 ../packages/...，镜像根为 INDEX
    candidates = []
    for href, sha in links:
        fname = href.rsplit("/", 1)[-1]
        if "manylinux" in fname or fname.startswith(("pp", "cp3")) and not (
            "abi3-win_amd64" in fname or "cp311-cp311-win_amd64" in fname
        ):
            continue
        if "win_amd64" not in fname and "any" not in fname:
            continue
        if "py3-none-any" not in fname and not (
            "abi3-win_amd64" in fname or "cp311-cp311-win_amd64" in fname
        ):
            continue
        m = re.match(r"^(.*)-(\d+\.\d+[^-]*)-(.+)\.whl$", fname)
        if not m:
            continue
        ver = m.group(2)
        candidates.append((ver, fname, href, sha))
    if not candidates:
        print(f"{pkg}: 未找到可用 wheel！")
        continue
    # 简单版本排序（多数场景够用）
    def vkey(t):
        return [int(x) if x.isdigit() else 0 for x in re.split(r"[.ab]", t[0])]
    candidates.sort(key=vkey)
    ver, fname, href, sha = candidates[-1]
    url = href if href.startswith("http") else "https://pypi.tuna.tsinghua.edu.cn/" + href.lstrip("./")
    target = OUT / fname
    if target.exists():
        print(f"{pkg}: 已有 {fname}")
        continue
    blob = fetch(url)
    target.write_bytes(blob)
    print(f"{pkg} {ver}: {fname} ({len(blob)//1024} KB)")

print("全部完成 →", OUT)
