# -*- coding: utf-8 -*-
"""项目打包到桌面（健壮版：单文件读取带超时，阻塞即跳过并记录）"""
import os
import sys
import threading
import time
import zipfile

ROOT = r"D:\dan\chuan"
OUT = r"C:\Users\minihuz\Desktop\chuan_项目打包_20260929.zip"

EXCLUDE_DIRS = {'dist', '.trae', '.git', '_qa_shots', '.verify-shots', '.jwt_tmp', '.sid_tmp',
                '__pycache__', 'node_modules', 'shop_e2e_uploads', '.pytest_cache'}
EXCLUDE_FILES = {'.env'}
EXCLUDE_EXT = {'.db', '.pyc'}
READ_TIMEOUT = 10  # 单文件读取超时（秒）：并发工具持锁时跳过该文件


def read_with_timeout(path, timeout):
    """在工作线程读整个文件；超时抛 TimeoutError（线程留作后台，不阻塞主流程）。"""
    result = {}

    def worker():
        try:
            with open(path, 'rb') as f:
                result['data'] = f.read()
        except OSError as e:
            result['err'] = str(e)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        raise TimeoutError(f"读取超过 {timeout}s（文件被其他进程锁定？）")
    if 'err' in result:
        raise OSError(result['err'])
    return result['data']


t0 = time.time()
count = 0
skipped = []
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT)
        parts = set()
        cur = rel_dir
        while cur != '.':
            head, tail = os.path.split(cur)
            parts.add(tail if head else cur)
            cur = head
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if parts & EXCLUDE_DIRS:
            dirnames[:] = []
            continue
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if fn in EXCLUDE_FILES or ext in EXCLUDE_EXT or fn.endswith('.tmp'):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            try:
                data = read_with_timeout(full, READ_TIMEOUT)
            except TimeoutError as e:
                skipped.append(f"{rel}: {e}")
                print(f"  [跳过] {rel}  {e}", flush=True)
                continue
            except OSError as e:
                skipped.append(f"{rel}: {e}")
                continue
            z.writestr(rel, data)
            count += 1
            if count % 200 == 0:
                print(f"  ...{count} 文件  {time.time()-t0:.0f}s", flush=True)

size = os.path.getsize(OUT)
print(f"打包完成: {OUT}")
print(f"文件数 {count} | 体积 {size/1024/1024:.1f} MB | 耗时 {time.time()-t0:.1f}s")
if skipped:
    print(f"跳过 {len(skipped)} 个:")
    for x in skipped:
        print("  -", x)
sys.exit(0)
