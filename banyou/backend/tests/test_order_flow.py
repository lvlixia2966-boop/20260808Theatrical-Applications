"""文创订单链路回归：下单（服务端计价）→ 沙盒支付 → 库存扣减 → 我的订单 → 数据复原。

零依赖可直跑（也可被 pytest 收集）。全程走开放 API 真实请求；
测试订单使用专用 visitor_id（regression-test），结束后清理订单行并复原库存，
不污染真实运营数据。

前置：被测服务已启动（默认 http://127.0.0.1:8300，可用环境变量 BANYOU_BASE 覆盖）。
"""

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("BANYOU_BASE", "http://127.0.0.1:8300")
VID = "regression-test-order"


def _req(path, method="GET", body=None):
    r = urllib.request.Request(BASE + "/api/v1" + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, data, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_order_flow_priced_paid_and_stock_decremented():
    # 1) 选一件在售商品并记录原始库存
    items = _req("/products")["items"]
    assert items, "无可售商品，请先跑 seed_liangshan.py"
    p = items[0]
    stock0 = p["stock"]

    # 2) 下单 qty=2：金额必须按服务端价格计算
    qty = 2
    order = _req("/orders", "POST", {
        "visitor_id": VID,
        "items": [{"product_id": p["id"], "qty": qty}],
    })
    assert order["status"] == "pending", order
    assert abs(order["total"] - p["price"] * qty) < 0.001, \
        f"服务端计价不符: {order['total']} != {p['price']}*{qty}"

    # 3) 沙盒支付 → 已支付
    paid = _req(f"/orders/{order['id']}/pay", "POST",
                {"visitor_id": VID, "channel": "wechat"})
    assert paid["status"] == "paid" and paid["channel"] == "wechat", paid

    # 4) 库存按支付数量扣减
    after = _req(f"/products/{p['id']}")
    assert after["stock"] == stock0 - qty, \
        f"库存未正确扣减: {after['stock']} != {stock0}-{qty}"

    # 5) 我的订单可查到该单
    mine = _req(f"/orders?vid={VID}")["items"]
    assert any(o["id"] == order["id"] for o in mine), "我的订单未查到该单"


def _cleanup():
    """清理测试订单并复原库存（DB 直连，仅动 regression-test 的数据）。"""
    sys_path = os.path.join(os.path.dirname(__file__), "..")
    import sys
    sys.path.insert(0, sys_path)
    from app.database import SessionLocal, init_db
    from app.models.product import Order, Product

    init_db()
    db = SessionLocal()
    try:
        orders = db.query(Order).filter(Order.visitor_id == VID).all()
        for o in orders:
            for item in o.items:
                p = db.get(Product, item["product_id"])
                if p is not None:
                    p.stock += item["qty"]  # 复原库存
            db.delete(o)
        db.commit()
        n = len(orders)
    finally:
        db.close()
    return n


def _main():
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=5)
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"被测服务不可达（{BASE}）：{e} —— 请先 cd backend && python run.py")
    try:
        test_order_flow_priced_paid_and_stock_decremented()
        print("PASS  test_order_flow_priced_paid_and_stock_decremented")
    except AssertionError as err:
        print(f"FAIL  test_order_flow_priced_paid_and_stock_decremented: {err}")
        raise SystemExit(1)
    finally:
        n = _cleanup()
        print(f"清理: 已删除测试订单 {n} 笔并复原库存")


if __name__ == "__main__":
    _main()
