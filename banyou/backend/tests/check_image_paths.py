# 图片路径一致性核查：credits.json ↔ 磁盘文件 ↔ 数据库引用 ↔ 种子引用
# 兜底图一并纳入：点位美景卡的兜底 = 所属景区封面（area-*.jpg），同样要求登记。
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app.models.content import ScenicArea
from app.models.product import Product

ROOT = pathlib.Path(__file__).parent.parent  # backend/
IMG = ROOT / "uploads" / "images"
problems = []

# 1) credits.json 登记清单
credits = json.loads((IMG / "credits.json").read_text(encoding="utf-8"))
listed = {e["file"] for e in credits["items"]}
listed_products = {e["file"] for e in credits["items"] if "product" in e}
listed_areas = {e["file"] for e in credits["items"] if "area" in e}

# 2) 磁盘实际文件
disk = {f.name for f in IMG.glob("area-*")} | {f.name for f in IMG.glob("product-*")}

# 3) 数据库实际引用
init_db()
db = SessionLocal()
db_area_imgs = {a.cover_url.rsplit("/", 1)[-1] for a in db.query(ScenicArea).all() if a.cover_url}
db_product_imgs = {p.image_url.rsplit("/", 1)[-1] for p in db.query(Product).all() if p.image_url}
n_areas = db.query(ScenicArea).count()
n_products_with_img = len(db_product_imgs)
n_products = db.query(Product).count()
db.close()

# 4) 种子文件引用
seed_refs = set(re.findall(r"/uploads/images/([\w.-]+)", (ROOT / "seed_liangshan.py").read_text(encoding="utf-8")))

print("== credits.json ↔ 磁盘 ==")
for name in sorted(listed - disk):
    problems.append(f"credits 登记了但磁盘缺失: {name}")
for name in sorted(disk - listed):
    problems.append(f"磁盘存在但 credits 未登记: {name}")
print(f"credits 登记 {len(listed)} 项；磁盘 {len(disk)} 项；差异见问题清单")

print("== 数据库引用 ↔ credits（景区封面 + 商品图，双向） ==")
for name in sorted((db_area_imgs | db_product_imgs) - listed):
    problems.append(f"DB 引用但 credits 未登记: {name}")
for name in sorted(listed_products - db_product_imgs):
    problems.append(f"credits 商品图但 DB 未引用: {name}")
for name in sorted(listed_areas - db_area_imgs):
    problems.append(f"credits 景区封面但 DB 未引用: {name}")
print(f"DB 景区封面 {len(db_area_imgs)}/{n_areas}；DB 商品图 {n_products_with_img}/{n_products}")

print("== 种子引用 ↔ 磁盘/credits ==")
for name in sorted(seed_refs - disk):
    problems.append(f"种子引用但磁盘缺失: {name}")
for name in sorted(seed_refs - listed):
    problems.append(f"种子引用但 credits 未登记: {name}")
print(f"种子引用 {len(seed_refs)} 项")

# 5) 前后端代码中硬编码的 /uploads/images 引用（应无——图片路径一律数据驱动）
for js in list((ROOT.parent / "frontend" / "assets" / "js").rglob("*.js")) + \
          list((ROOT.parent / "admin" / "assets").glob("*.js")):
    hits = re.findall(r"/uploads/images/[\w.-]+", js.read_text(encoding="utf-8", errors="ignore"))
    if hits:
        problems.append(f"代码硬编码图片路径 {js.name}: {hits[:3]}")

print()
if problems:
    print("== 差异清单 ==")
    for p in problems:
        print(" -", p)
    raise SystemExit(1)
print("全部一致：credits / 磁盘 / 数据库 / 种子 / 代码引用 五方无差异（含兜底用的景区封面）")
