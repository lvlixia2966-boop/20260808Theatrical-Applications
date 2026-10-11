# -*- coding: utf-8 -*-
"""游客玩法扩展一键部署（川剧护照 / 观演竞答 / 购物点导览 / 准入页修复）。

部署范围（仅本次前端改动，后端无变更）：
  - frontend/index.html（新增 passport/quiz 挂载 + live-listen 版本号 + 头部移动端适配等）
  - frontend/assets/js/*.js（新增 passport.js / quiz.js；变更 shopping-spots / live-listen / ble-guard）

流程与 deploy_doubao_upgrade.py 一致：宿主备份 → SFTP 上传 → docker cp → 重启 → 探活。

运行：python tools\\deploy_visitor_play.py
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
BAK_SUFFIX = "bak-play"

SYNC_DIRS = [
    (r"frontend\assets\js", "frontend/assets/js", lambda name: name.endswith(".js")),
    (r"frontend\assets\vendor", "frontend/assets/vendor", lambda name: name.endswith(".js")),
    (r"frontend\assets\audio", "frontend/assets/audio", lambda name: name.endswith((".mp3", ".wav"))),
    (r"backend\app", "backend/app", lambda name: name.endswith(".py")),
    (r"frontend\redesign", "frontend/redesign", lambda name: name.endswith((".html", ".png", ".jpg"))),
]
SYNC_FILES = [
    r"frontend\index.html",
    r"frontend\index-v2.html",
    r"frontend\assets\mask-red-ai-transparent.png",
    r"frontend\assets\mask-gold-ai-transparent.png",
    r"frontend\assets\mask-blue-ai-transparent.png",
    r"frontend\assets\mask-green-ai-transparent.png",
    r"frontend\assets\mask-black-ai-transparent.png",
    r"frontend\assets\mask-white-ai-transparent.png",
    r"frontend\assets\theatre-silhouette.svg",
]


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, key_filename=KEY_FILE, timeout=15)
    return c


def run(c, cmd, t=300):
    _, out, err = c.exec_command(cmd, timeout=t)
    o, e = out.read().decode("utf-8", "ignore"), err.read().decode("utf-8", "ignore")
    return o + (("\n[stderr] " + e) if e.strip() else "")


def collect_tasks():
    import os

    tasks = []
    for local_dir, rel_dir, keep in SYNC_DIRS:
        base = ROOT + "\\" + local_dir
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                if not keep(name):
                    continue
                local = os.path.join(dirpath, name)
                sub = os.path.relpath(dirpath, base).replace("\\", "/")
                rel = posixpath.join(rel_dir, name) if sub == "." else posixpath.join(rel_dir, sub, name)
                tasks.append((local, rel))
    for rel in SYNC_FILES:
        tasks.append((ROOT + "\\" + rel, rel.replace("\\", "/")))
    return tasks


def main():
    tasks = collect_tasks()
    print(f"待同步 {len(tasks)} 个文件")
    c = connect()
    sftp = c.open_sftp()
    try:
        # ---- 1. 宿主备份 + 上传 ----
        t0 = time.time()
        for local, rel in tasks:
            remote = posixpath.join(HOST_ROOT, rel)
            run(c, f"mkdir -p $(dirname {remote})")
            run(c, f"cp -a {remote} {remote}.{BAK_SUFFIX} 2>/dev/null || true")
            sftp.put(local, remote)
        print(f"上传完成 {len(tasks)} 个文件（{time.time() - t0:.0f}s）")

        # ---- 2. docker cp 进容器 ----
        for _, rel in tasks:
            run(c, f"docker exec {CONTAINER} mkdir -p /app/$(dirname {rel})")
            run(c, f"docker cp {HOST_ROOT}/{rel} {CONTAINER}:/app/{rel}")
        print("docker cp 完成")

        # ---- 3. 重启容器 ----
        print(run(c, f"docker restart {CONTAINER}", t=180).strip())

        # ---- 4. 探活 + 新模块验证 ----
        time.sleep(3)
        print(run(c, "curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1:8123/api/health").strip())
        print(run(c, "curl -s http://127.0.0.1:8123/ | grep -c 'passport.js\\|quiz.js' "
                    "| xargs -I{} echo 'index.html 新脚本引用数: {}'").strip())
        print(run(c, "curl -s -o /dev/null -w 'passport.js: %{http_code} %{size_download}B\\n' "
                    "http://127.0.0.1:8123/assets/js/passport.js?v=20260906").strip())
        print(run(c, "curl -s -o /dev/null -w 'quiz.js: %{http_code} %{size_download}B\\n' "
                    "http://127.0.0.1:8123/assets/js/quiz.js?v=20260906").strip())
        print(run(c, f"docker logs {CONTAINER} --tail 5 2>&1").strip())
    finally:
        sftp.close()
        c.close()
    print("部署完成")


if __name__ == "__main__":
    sys.exit(main())
