# -*- coding: utf-8 -*-
"""豆包化改造一键部署：向 192.168.0.222 同步代码 → docker cp → 重启 → 自检。

部署范围（豆包化改造全部交付物）：
  - backend/app/    全部 Python 源码（豆包引擎层 / RTC 网关 / 知识库 / Agent / 统计 / 用户权限）
  - backend/tools/  连通性自检工具
  - admin/index.html（统计 / 知识管理 / 用户权限页）
  - frontend/index.html + frontend/assets/js/*.js（实时翻译视图 / Agent 伴游）

流程：宿主备份 → SFTP 上传 → docker cp 进容器 → 重启 → health 探活 → 容器内跑连通性自检。

运行：python tools\\deploy_doubao_upgrade.py
前置：本机可访问 192.168.0.222；paramiko 已安装；容器内已安装 aiortc/websockets 等新依赖
     （新依赖首次部署需在容器内 pip install，见脚本末尾提示）。
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
BAK_SUFFIX = "bak-doubao"

# 同步清单：(本地目录, 容器内目录, 文件过滤)
SYNC_DIRS = [
    (r"backend\app", "backend/app", lambda name: name.endswith(".py")),
    (r"backend\tools", "backend/tools", lambda name: name.endswith(".py")),
    (r"frontend\assets\js", "frontend/assets/js", lambda name: name.endswith(".js")),
    # 静态音频资产（候场节目 mp3 等）；cosy_server 预烘焙 wav 一并覆盖
    (r"frontend\assets\audio", "frontend/assets/audio",
     lambda name: name.endswith((".mp3", ".wav"))),
]
SYNC_FILES = [
    r"backend\requirements.txt",
    r"admin\index.html",
    r"frontend\index.html",
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
    """汇总待上传任务：(本地绝对路径, 仓库相对路径)。目录递归遍历。"""
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

        # ---- 2. docker cp 进容器（先建父目录，避免单文件 cp 到不存在目录静默失败）----
        for _, rel in tasks:
            run(c, f"docker exec {CONTAINER} mkdir -p /app/$(dirname {rel})")
            run(c, f"docker cp {HOST_ROOT}/{rel} {CONTAINER}:/app/{rel}")
        print("docker cp 完成")

        # ---- 3. 容器内补装新依赖（幂等：已装则秒过）----
        print(run(c, "docker exec " + CONTAINER + " pip install -q -r /app/backend/requirements.txt "
                    "--no-warn-script-location -i https://pypi.tuna.tsinghua.edu.cn/simple", t=600).strip()
              or "依赖检查完成")

        # ---- 4. 重启容器 ----
        print(run(c, f"docker restart {CONTAINER}", t=180).strip())

        # ---- 5. 探活 ----
        time.sleep(3)
        print(run(c, "curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1:8123/api/health").strip())
        print(run(c, "curl -s -o /dev/null -w 'admin页: %{http_code} %{size_download}B\\n' http://127.0.0.1:8123/admin/").strip())

        # ---- 6. 容器内连通性自检（凭据取自容器 .env）----
        print(run(c, f"docker exec {CONTAINER} sh -c 'cd /app/backend && python tools/check_connectivity.py'", t=180).strip())
        print(run(c, f"docker logs {CONTAINER} --tail 5 2>&1").strip())
    finally:
        sftp.close()
        c.close()
    print("部署完成")


if __name__ == "__main__":
    sys.exit(main())
