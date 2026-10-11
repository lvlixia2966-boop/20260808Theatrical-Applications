"""AI 伴游卡片回归测试：导航→下一站美景卡 三个边界用例 + 无定位点名讲解。

零依赖可直跑（内置简易 runner），也可被 pytest 自动收集：
    cd banyou/backend
    python tests/test_companion_cards.py     # 直跑
    python -m pytest tests/ -q               # pytest 收集（装了 pytest 时）

前置：被测服务已启动（默认 http://127.0.0.1:8300，可用环境变量 BANYOU_BASE 覆盖）。
"""

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("BANYOU_BASE", "http://127.0.0.1:8300")


def _chat(message, lat=None, lng=None):
    body = {"message": message}
    if lat is not None:
        body["lat"], body["lng"] = lat, lng
    r = urllib.request.Request(
        BASE + "/api/v1/companion/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(r, timeout=15).read())


def _cards_of(d):
    return [(c["type"], c["title"]) for c in d.get("cards", [])]


# ── 导航 → 下一站美景卡：三个边界用例 ──

def test_nav_mid_route_next_stop_card():
    """a) 路线中途（里格半岛=seq5）→ 指路下一站 seq6 且返回该站美景卡（带图）。"""
    d = _chat("下一站怎么走", 27.792, 100.772)
    assert d["kind"] == "nav", f"kind={d['kind']}"
    assert "格姆女神山索道" in d["reply"], d["reply"]
    cards = _cards_of(d)
    assert cards and cards[0] == ("spot", "格姆女神山索道"), cards
    assert d["cards"][0]["image_url"], "下一站美景卡应带图（景区封面兜底）"


def test_nav_last_stop_card():
    """b) 路线末站（走婚桥=seq9）→ 完成话术 + 走婚桥美景卡（带图）。"""
    d = _chat("下一站怎么走", 27.714, 100.747)
    assert d["kind"] == "nav", f"kind={d['kind']}"
    assert ("最后一站" in d["reply"]) or ("走完全程" in d["reply"]), d["reply"]
    cards = _cards_of(d)
    assert cards and cards[0] == ("spot", "走婚桥"), cards
    assert d["cards"][0]["image_url"], "末站美景卡应带图（景区封面兜底）"


def test_nav_without_position_empty_cards():
    """c) 完全无定位 → 引导开启定位，无卡片（无上下文无「下一站」）。"""
    d = _chat("下一站怎么走")
    assert d["kind"] == "nav", f"kind={d['kind']}"
    assert d.get("cards", []) == [], d.get("cards")
    assert "定位" in d["reply"], d["reply"]


# ── 关联回归：无定位点名讲解（权限缺失 / 权限拒绝 两分支参数化） ──
#
# 结论性约定（接口层）：定位权限「被拒绝」与「缺失」在请求线路上同形——
# 两种场景客户端都不携带可用坐标，服务端只看「有没有坐标」。
# 参数化的三组入参覆盖这一约定的全部线形：
#   1) 权限缺失：不携带 lat/lng 字段
#   2) 权限拒绝：同形不传（前端 geo:denied 后同样不传）
#   3) 显式 null：客户端显式传 lat=null/lng=null
# 预期：三组返回完全一致（讲解 + 景区封面美景卡 + 景区自动推导）。

NAMED_SPOT_SCENARIOS = [
    ("权限缺失-不传坐标字段", {}),
    ("权限拒绝-同形不传坐标", {}),
    ("显式null坐标", {"lat": None, "lng": None}),
]


def _post_body(body):
    r = urllib.request.Request(
        BASE + "/api/v1/companion/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(r, timeout=15).read())


def test_named_spot_scenarios():
    """参数化：权限缺失 / 权限拒绝 / 显式 null —— 三种线形应答一致。"""
    failures = []
    for label, extra in NAMED_SPOT_SCENARIOS:
        d = _post_body({"message": "给我讲讲走婚桥", **extra})
        try:
            assert d["kind"] == "narration", f"kind={d['kind']}"
            assert "走婚桥" in d["reply"], d["reply"]
            assert d["context"]["area"]["name"] == "泸沽湖景区", d["context"]["area"]
            cards = _cards_of(d)
            assert cards and cards[0] == ("spot", "走婚桥"), cards
            assert d["cards"][0]["image_url"], "美景卡应带图（景区封面兜底）"
        except AssertionError as err:
            failures.append(f"[{label}] {err}")
    assert not failures, "；".join(failures)


def _named_spot_scenario_labels():
    return [label for label, _extra in NAMED_SPOT_SCENARIOS]


# ── 直跑 runner ──

def _main():
    # 健康预检，服务未启动时给出明确提示
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=5)
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"被测服务不可达（{BASE}）：{e} —— 请先 cd backend && python run.py")

    tests = [
        test_nav_mid_route_next_stop_card,
        test_nav_last_stop_card,
        test_nav_without_position_empty_cards,
        test_named_spot_scenarios,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"PASS  {t.__name__}")
        except AssertionError as err:
            print(f"FAIL  {t.__name__}: {err}")
        except Exception as err:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {err}")
    if passed == len(tests):
        for label in _named_spot_scenario_labels():
            print(f"PASS      └ 参数化场景: {label}")
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    _main()
