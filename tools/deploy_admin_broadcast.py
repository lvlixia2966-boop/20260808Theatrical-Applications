# -*- coding: utf-8 -*-
"""一次性脚本：向 192.168.0.222 部署管理后台推流功能与节目上下架修复。
1) SFTP 上传后端 4 文件 + admin/index.html → 宿主 /root/chuan/chuan/
2) docker cp 进 chuan-guide 容器 /app/
3) 重启容器（后端代码生效）
4) curl 验证
运行：C:\\Python311\\python.exe tools\\deploy_admin_broadcast.py deploy
"""
import os
import posixpath
import sys
import time

import paramiko

HOST, USER = "192.168.0.222", "root"
KEY_FILE = os.path.expanduser("~/.ssh/chuan_222")  # SSH 密钥登录（222 已禁用密码登录）
ROOT = r"d:\dan\chuan"
HOST_ROOT = "/root/chuan/chuan"
CONTAINER = "chuan-guide"

FILES = [
    (ROOT + r"\backend\app\services\live_hub.py", "backend/app/services/live_hub.py"),
    (ROOT + r"\backend\app\api\live.py", "backend/app/api/live.py"),
    (ROOT + r"\backend\app\schemas\live.py", "backend/app/schemas/live.py"),
    (ROOT + r"\backend\app\schemas\__init__.py", "backend/app/schemas/__init__.py"),
    (ROOT + r"\admin\index.html", "admin/index.html"),
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
            remote = posixpath.join(HOST_ROOT, rel)
            run(c, f"mkdir -p $(dirname {remote})")
            run(c, f"cp -a {remote} {remote}.bak-broadcast 2>/dev/null || true")
            sftp.put(local, remote)
            print(f"上传 {rel} ({time.time()-t0:.0f}s)")

        # ---- 2. docker cp 进容器 ----
        for _, rel in FILES:
            print(run(c, f"docker cp {HOST_ROOT}/{rel} {CONTAINER}:/app/{rel}").strip())

        # ---- 3. 重启容器（后端代码生效）----
        print(run(c, f"docker restart {CONTAINER}", t=180).strip())

        # ---- 4. 验证 ----
        time.sleep(3)
        print(run(c, "curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1:8123/api/health"))
        print(run(c, "curl -s -o /dev/null -w 'admin页: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/admin/"))
        print(run(c, "curl -s -X POST http://127.0.0.1:8123/api/live/shows/1/broadcast -H 'Content-Type: application/json' -d '{}' -o - -w '\\n推流端点(未登录应401/403): %{http_code}\\n'"))
        print(run(c, f"docker logs {CONTAINER} --tail 5 2>&1"))
    finally:
        sftp.close()
        c.close()
    print("部署完成")


if __name__ == "__main__":
    sys.exit(main())
