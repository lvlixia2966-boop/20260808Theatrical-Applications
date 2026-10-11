"""冒烟：商城后端化链路（任务分解 T8 的部署后回归工具）。

用法：
    ADMIN_PASSWORD=管理员口令 python tools/smoke_shop.py [base_url] [--full]

    base_url 默认 http://127.0.0.1:8123（222 部署后填 http://192.168.0.222:8123）
    --full   追加真实下单校验（会在订单表留一条演示单，默认不跑）

无副作用检查：公开列表 / 管理端鉴权 / 下单防篡改拦截。
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

args = [a for a in sys.argv[1:]]
BASE = (next((a for a in args if not a.startswith("-")), "http://127.0.0.1:8123")).rstrip("/")
FULL = "--full" in args
PWD = os.environ.get("ADMIN_PASSWORD")

fails = []


def req(method, path, body=None, token=None, raw=False):
    r = urllib.request.Request(BASE + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json",
                                        **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
            return resp.status, payload
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def check(name, cond, detail=""):
    print(("  [OK]   " if cond else "  [FAIL] ") + name + ("" if cond else f"   <- {detail}"))
    if not cond:
        fails.append(name)


print(f"== 商城后端化冒烟 @ {BASE} ==")

# 1) 公开商品列表
code, body = req("GET", "/api/shop/products")
items = body.get("data") or []
check("公开商品列表 200", code == 200, f"code={code}")
check("商品非空且字段齐", bool(items) and all(
    {"sku", "name", "category", "price_cents", "image_url", "status"} <= set(i) for i in items),
    f"count={len(items)}")
check("仅含上架商品", all(i.get("status") == 1 for i in items))
first = items[0] if items else None

# 2) 管理端鉴权链
if not PWD:
    print("  [SKIP] 管理端检查（未设置 ADMIN_PASSWORD 环境变量）")
else:
    code, body = req("POST", "/api/auth/login", {"username": "admin", "password": PWD})
    token = (body.get("data") or {}).get("access_token", "")
    check("管理员登录 200", code == 200 and token, f"code={code}")
    if token:
        code, body = req("GET", "/api/admin/products", token=token)
        check("管理端全量列表 200(含下架)", code == 200 and len(body.get("data") or []) >= len(items),
              f"code={code}")

# 3) 下单防篡改（无副作用：拦截即不落库）
if first:
    bad = dict(id=first["sku"], name=first["name"], price_cents=first["price_cents"] + 1, qty=1)
    code, body = req("POST", "/api/payments/orders", {"channel": "wechat", "items": [bad]})
    check("篡改价格被拦截 400", code == 400, f"code={code} body={body.get('detail')}")

# 4) --full: 真实下单 + 订单查询（留一条演示单）
if FULL and first:
    ok_items = [dict(id=i["sku"], name=i["name"], price_cents=i["price_cents"], qty=1) for i in items[:2]]
    code, body = req("POST", "/api/payments/orders", {"channel": "wechat", "items": ok_items})
    order = (body.get("data") or {}).get("order") or {}
    order_no = order.get("order_no", "")
    check("正常下单 200", code == 200 and bool(order_no), f"code={code}")
    if order_no:
        code, body = req("GET", f"/api/payments/orders/{order_no}")
        check("订单查询 200", code == 200 and body.get("data", {}).get("order_no") == order_no, f"code={code}")

print(f"== 结果：{'全部通过' if not fails else f'{len(fails)} 项失败：{fails}'} ==")
sys.exit(1 if fails else 0)
