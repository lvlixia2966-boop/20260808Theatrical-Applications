# -*- coding: utf-8 -*-
"""一次性：从清华镜像下载 starlette 0.41.3 wheel（fastapi 0.115.6 兼容版）。"""
import re
import urllib.request

html = urllib.request.urlopen(
    "https://pypi.tuna.tsinghua.edu.cn/simple/starlette/", timeout=30
).read().decode()
links = re.findall(r'href="([^"]+\.whl)#sha256=', html)
cands = [h for h in links if "starlette-0.41.3-py3-none-any.whl" in h]
assert cands, "wheel 未找到"
url = "https://pypi.tuna.tsinghua.edu.cn/" + cands[-1].lstrip("./")
target = r"d:\dan\chuan\tools\wheels\starlette-0.41.3-py3-none-any.whl"
open(target, "wb").write(urllib.request.urlopen(url, timeout=60).read())
print("downloaded:", target)
