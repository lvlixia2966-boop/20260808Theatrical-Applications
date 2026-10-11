# -*- coding: utf-8 -*-
"""一次性脚本：向 192.168.0.222 部署自托管字体。
1) SFTP 上传 frontend/assets/fonts/ → 宿主 /root/chuan/chuan/frontend/assets/fonts/
2) 服务器 index.html 原位替换 Google Fonts 三行 → 本地 fonts.css（保备份）
3) docker cp fonts + index.html 进 chuan-guide 容器 /app/frontend/
4) curl 验证 8123
运行：C:\\Python311\\python.exe tools\\deploy_fonts.py deploy
"""
import io
import os
import posixpath
import sys
import time

import paramiko

HOST, USER = "192.168.0.222", "root"
KEY_FILE = os.path.expanduser("~/.ssh/chuan_222")  # SSH 密钥登录（222 已禁用密码登录）
ROOT = r"d:\dan\chuan"
LOCAL_FONT_DIR = ROOT + r"\frontend\assets\fonts"
HOST_DIR = "/root/chuan/chuan/frontend"
CONTAINER = "chuan-guide"

GOOGLE_BLOCK = """<!-- Google Fonts: 艺术厚重书法字体 Ma Shan Zheng & Noto Serif SC Black -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@700;900&family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">"""

LOCAL_BLOCK = """<!-- 字体：服务器自托管（现场网络无法访问 Google Fonts CDN）
       Ma Shan Zheng 书法体 / Noto Serif SC 700·900 / Outfit 400·600·800 -->
  <link href="./assets/fonts/fonts.css" rel="stylesheet">"""


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, key_filename=KEY_FILE, timeout=15)
    return c


def run(c, cmd, t=120):
    _, out, err = c.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8", "ignore"), err.read().decode("utf-8", "ignore")
    return o + (("\n[stderr] " + e) if e.strip() else "")


def main():
    c = connect()
    sftp = c.open_sftp()
    try:
        # ---- 1. 上传字体目录 ----
        import pathlib
        files = [pathlib.Path(LOCAL_FONT_DIR) / "fonts.css",
                 pathlib.Path(LOCAL_FONT_DIR) / "MaShanZheng-Regular.ttf"]
        files += sorted((pathlib.Path(LOCAL_FONT_DIR) / "files").glob("*.woff2"))
        print(f"待上传 {len(files)} 个文件")
        run(c, f"mkdir -p {HOST_DIR}/assets/fonts/files")
        t0 = time.time()
        for i, f in enumerate(files, 1):
            rel = f.name if f.parent.name == "fonts" else "files/" + f.name
            sftp.put(str(f), posixpath.join(HOST_DIR, "assets/fonts", rel))
            if i % 40 == 0 or i == len(files):
                print(f"  {i}/{len(files)} ({time.time()-t0:.0f}s)")
        run(c, f"chmod -R a+rX {HOST_DIR}/assets/fonts")

        # ---- 2. 服务器 index.html 原位替换（python3 无 sed 多行烦恼）----
        py = f"""
import pathlib
p = pathlib.Path('{HOST_DIR}/index.html')
s = p.read_text(encoding='utf-8')
old = '''{GOOGLE_BLOCK}'''
new = '''{LOCAL_BLOCK}'''
if new in s:
    print('ALREADY-PATCHED')
elif old in s:
    p.with_suffix('.html.bak-fonts').write_text(s, encoding='utf-8')
    p.write_text(s.replace(old, new), encoding='utf-8')
    print('PATCHED')
else:
    print('PATTERN-NOT-FOUND')
"""
        print(run(c, "python3 - <<'PYEOF'\n" + py + "\nPYEOF"))

        # ---- 3. docker cp 进容器 ----
        print(run(c, f"docker exec {CONTAINER} mkdir -p /app/frontend/assets/fonts/files"))
        print(run(c, f"docker cp {HOST_DIR}/assets/fonts/fonts.css {CONTAINER}:/app/frontend/assets/fonts/fonts.css"))
        print(run(c, f"docker cp {HOST_DIR}/assets/fonts/MaShanZheng-Regular.ttf {CONTAINER}:/app/frontend/assets/fonts/MaShanZheng-Regular.ttf"))
        print(run(c, f"docker cp {HOST_DIR}/assets/fonts/files/. {CONTAINER}:/app/frontend/assets/fonts/files/"))
        # 用宿主已打补丁的 index.html 覆盖容器内
        print(run(c, f"docker cp {HOST_DIR}/index.html {CONTAINER}:/app/frontend/index.html"))

        # ---- 4. 验证 ----
        print(run(c, "curl -s -o /dev/null -w 'fonts.css: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/assets/fonts/fonts.css"))
        print(run(c, "curl -s -o /dev/null -w 'ttf: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/assets/fonts/MaShanZheng-Regular.ttf"))
        print(run(c, "curl -s -o /dev/null -w 'woff2: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/assets/fonts/files/outfit-latin-400-normal.woff2"))
        print(run(c, "curl -s http://127.0.0.1:8123/ | grep -c 'fonts.googleapis' || echo 'google引用=0'"))
    finally:
        sftp.close()
        c.close()
    print("部署完成")


if __name__ == "__main__":
    sys.exit(main())
