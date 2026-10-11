# 任务2：README 差异清单 ↔ 商品图来源清单（credits.json）同步核查
# 任务3：末站分支覆盖——单站点路线（单末站）实测 + 清理
import json
import pathlib
import sys
import urllib.request
import uuid

BASE = "http://127.0.0.1:8300"
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.content import ScenicArea  # noqa: E402
from app.models.product import Product  # noqa: E402

init_db()
db = SessionLocal()

print("== 任务2：差异清单同步核查 ==")
# DB 侧：已配图文件集合（应 12/12 全配）
products = db.query(Product).all()
withimg_files = {p.image_url.rsplit("/", 1)[-1] for p in products if p.image_url}
noimg = [p.name for p in products if not p.image_url]
# credits 侧：商品图登记集合 + note
IMG = pathlib.Path(__file__).parent.parent / "uploads" / "images"
credits = json.loads((IMG / "credits.json").read_text(encoding="utf-8"))
credit_files = {e["file"] for e in credits["items"] if "product" in e}
note = credits.get("note", "")
# README 侧：应声明「12 件全部配演示商品图」
readme = (pathlib.Path(__file__).parent.parent.parent / "README.md").read_text(encoding="utf-8")

diffs = []
if noimg:
    diffs.append(f"仍有 {len(noimg)} 件商品未配图: {noimg}")
if credit_files != withimg_files:
    diffs.append(f"credits 商品图 {sorted(credit_files)} ≠ DB 引用 {sorted(withimg_files)}")
if "商品图" not in note:
    diffs.append("credits note 未提及商品图")
if "12 件全部配" not in readme and "10 件配" in readme:
    diffs.append("README 仍为旧的 10/12 表述，请更新为 12/12")

print(f"DB 配图: {len(withimg_files)}/{len(products)} | credits 商品图 {len(credit_files)} 张")
if diffs:
    print("== 需更新条目 ==")
    for d in diffs:
        print(" -", d)
else:
    print("同步状态：已同步，无差异")

print()
print("== 任务3：单站点路线（单末站）末站分支实测 ==")
import os as _os

from app.models.content import RouteStop, ScenicArea, Spot, TourRoute  # noqa: E402

_admin_pwd = _os.environ.get("ADMIN_PASSWORD")
# 双模式：设置 ADMIN_PASSWORD 走管理 API（与线上操作路径一致）；
# 未设置则 DB 直连造数（免口令，本地回归默认）。两种模式的断言完全一致。


def chat(msg, lat=None, lng=None):
    body = {"message": msg}
    if lat is not None:
        body["lat"], body["lng"] = lat, lng
    r = urllib.request.Request(BASE + "/api/v1/companion/chat",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=15).read())


_token = {"v": None}
if _admin_pwd:
    _token["v"] = json.loads(urllib.request.urlopen(
        urllib.request.Request(BASE + "/api/admin/login", method="POST",
            data=json.dumps({"username": "admin", "password": _admin_pwd}).encode(),
            headers={"Content-Type": "application/json"}), timeout=8).read())["token"]


def admin(path, method="GET", body=None):
    r = urllib.request.Request(BASE + "/api/admin" + path, method=method)
    r.add_header("Authorization", "Bearer " + _token["v"])
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, data, timeout=10) as resp:
        return json.loads(resp.read())


area_id = None
try:
    if _admin_pwd:
        # 管理 API 造数
        region = admin("/regions")["items"][0]
        area_id = admin("/scenic-areas", "POST", {
            "region_id": region["id"], "name": "验证用单站景区", "city": "验证",
            "level": "test", "lat": 28.0, "lng": 102.5, "status": 1,
            "short_intro": "回归测试造数", "intro": "回归测试造数", "suggested_hours": 1,
        })["id"]
        spot_id = admin("/spots", "POST", {
            "scenic_area_id": area_id, "name": "验证单站点", "category": "观景",
            "lat": 28.0, "lng": 102.5, "radius": 50, "status": 1,
            "narration": {"zh": "这是回归测试用的单站点。"},
        })["id"]
        route_id = admin("/routes", "POST", {
            "scenic_area_id": area_id, "name": "验证单站路线", "status": 1,
            "duration_minutes": 30, "distance_km": 0.5,
        })["id"]
        admin(f"/routes/{route_id}/stops", "PUT", {"spot_ids": [spot_id]})
    else:
        # DB 直连造数（免口令）
        area = ScenicArea(region_id=db.query(ScenicArea).first().region_id,
                          name="验证用单站景区", city="验证", level="test",
                          lat=28.0, lng=102.5, status=1,
                          short_intro="回归测试造数", intro="回归测试造数", suggested_hours=1)
        db.add(area)
        db.flush()
        spot = Spot(scenic_area_id=area.id, name="验证单站点", category="观景",
                    lat=28.0, lng=102.5, radius=50, status=1)
        spot.narration = {"zh": "这是回归测试用的单站点。"}
        db.add(spot)
        db.flush()
        route = TourRoute(scenic_area_id=area.id, name="验证单站路线", status=1,
                          duration_minutes=30, distance_km=0.5)
        db.add(route)
        db.flush()
        db.add(RouteStop(route_id=route.id, spot_id=spot.id, seq=1))
        db.commit()
        area_id = area.id

    # 站在唯一站点上问导航 → 应命中末站分支：完成话术 + 该点位美景卡
    d = chat("下一站怎么走", 28.0, 102.5)
    cards = [(c["type"], c["title"], c["image_url"] or "-") for c in d.get("cards", [])]
    print("模式:", "管理API" if _admin_pwd else "DB直连", "| kind:", d["kind"], "| cards:", cards)
    print("reply:", d["reply"][:60])
    ok_branch = ("最后一站" in d["reply"] or "走完全程" in d["reply"] or "已走完" in d["reply"])
    ok_card = cards and cards[0][0] == "spot" and "验证单站点" in cards[0][1]
    print("覆盖判定:", "PASS（单末站命中末站分支且返回美景卡）" if ok_branch and ok_card else "FAIL")
    # 无图景区的美景卡 image_url 为空 → 前端渐变占位（与商品卡同约定）
finally:
    # 清理造数（级联删除路线与点位）
    if area_id is not None:
        if _admin_pwd:
            try:
                admin(f"/scenic-areas/{area_id}", "DELETE")
                print("清理造数: 已删除验证景区及其点位/路线")
            except Exception as e:  # noqa: BLE001
                print("清理失败，请手动删除:", e)
        else:
            a = db.get(ScenicArea, area_id)
            if a is not None:
                db.delete(a)
                db.commit()
                print("清理造数: 已删除（DB 直连，级联点位/路线）")
    db.close()
