# -*- coding: utf-8 -*-
"""一次性脚本：向 192.168.0.222 同步购物点导览模块（骨架）。
1) SFTP 上传 frontend/index.html + frontend/assets/js/shopping-spots.js
   → 宿主 /root/chuan/chuan/frontend/（保备份）
2) docker cp 两文件进 chuan-guide 容器 /app/frontend/
3) curl 验证 8123
运行：C:\\Python311\\python.exe tools\\deploy_shopping_spots.py deploy
"""
import os
import posixpath
import sys
import time

import paramiko

HOST, USER = "192.168.0.222", "root"
KEY_FILE = os.path.expanduser("~/.ssh/chuan_222")  # SSH 密钥登录（222 已禁用密码登录）
ROOT = r"d:\dan\chuan"
HOST_DIR = "/root/chuan/chuan/frontend"
CONTAINER = "chuan-guide"

FILES = [
    (ROOT + r"\frontend\index.html", "index.html"),
    (ROOT + r"\frontend\assets\js\shopping-spots.js", "assets/js/shopping-spots.js"),
]


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
        # ---- 1. 宿主备份 + 上传 ----
        t0 = time.time()
        for local, rel in FILES:
            remote = posixpath.join(HOST_DIR, rel)
            run(c, f"mkdir -p $(dirname {remote})")
            run(c, f"cp -a {remote} {remote}.bak-shopping 2>/dev/null || true")
            sftp.put(local, remote)
            print(f"上传 {rel} ({time.time()-t0:.0f}s)")
        run(c, f"chmod -R a+rX {HOST_DIR}/assets/js")

        # ---- 2. docker cp 进容器 ----
        for _, rel in FILES:
            print(run(c, f"docker cp {HOST_DIR}/{rel} {CONTAINER}:/app/frontend/{rel}").strip())

        # ---- 3. 验证 ----
        print(run(c, "curl -s -o /dev/null -w 'index.html: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/"))
        print(run(c, "curl -s -o /dev/null -w 'shopping-spots.js: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/assets/js/shopping-spots.js"))
        print(run(c, "curl -s http://127.0.0.1:8123/ | grep -c 'shopping-spots' || echo 'index中引用=0'"))
    finally:
        sftp.close()
        c.close()
    print("部署完成")


if __name__ == "__main__":
    sys.exit(main())
