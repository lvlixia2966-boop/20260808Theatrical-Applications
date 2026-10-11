"""初始化脚本：创建管理员账号与演示数据。

用法：
    python seed.py                 # 初始化管理员 + 演示节目/耳机
    python seed.py --reset         # 清空并重建后初始化
"""
import os
import secrets
import sys

from sqlalchemy import text

from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.models import AdminUser, Earphone, Product, Program


# 演示节目数据（川蜀大剧院 常驻剧目）
DEMO_PROGRAMS = [
    {
        "title": "川剧《变脸》选段",
        "subtitle": "川蜀大剧院 · 主剧场 · 下午场",
        "content_type": "full",
        "narrator": "李老师",
        "venue": "主剧场",
        "duration_min": 90,
        "price": 128.0,
        "sort_order": 1,
        "intro_zh": "变脸：演员折扇一遮脸谱瞬间变换，一眨眼连换数张，是川剧最负盛名的绝技。",
        "intro_en": "Face-changing: masks swap in the blink of an eye behind a flick of the fan — Sichuan Opera's most celebrated feat.",
        "text_content": (
            "「各位看官，今日咱们要摆的是川剧当中的一绝——变脸。」\n"
            "变脸这门手艺，分抹脸、吹脸、扯脸、运气变脸，历来都是川剧艺人的看家本领。\n"
            "您看这台上的演员，折扇一遮，脸就变了，快得很哦！\n"
            "一张脸、两张脸、三张脸...一眨眼就是九张脸，巴适得板！"
        ),
        "voice_content": (
            "各位观众，欢迎来到川蜀大剧院。今天我们要讲述的是川剧中的绝技——变脸。"
            "变脸这门技艺，分为抹脸、吹脸、扯脸、运气变脸，历来都是川剧艺人的看家本领。"
            "您看台上的演员，折扇一遮，脸就变了，非常快！一张、两张、三张，一眨眼就是九张脸，非常精彩！"
        ),
    },
    {
        "title": "川剧·吐火绝技",
        "subtitle": "川蜀大剧院 · 主剧场 · 下午场",
        "content_type": "voice",
        "narrator": "王师傅",
        "venue": "主剧场",
        "duration_min": 120,
        "price": 168.0,
        "sort_order": 2,
        "intro_zh": "吐火：演员口吐数尺烈焰，火光冲天，是勇气与呼吸法加持的真功夫。",
        "intro_en": "Fire-spitting: jets of real flame leap from the performer's mouth — a breathtaking feat of breath mastery.",
        "text_content": "吐火与变脸同为川剧「四大绝技」之一，演员以口中油料燃出烈焰，惊险热烈，极具川味张力。",
        "voice_content": "",
    },
    {
        "title": "盖碗茶评书",
        "subtitle": "川蜀大剧院 · 茶楼剧场 · 夜场",
        "content_type": "text",
        "narrator": "赵先生",
        "venue": "茶楼剧场",
        "duration_min": 60,
        "price": 88.0,
        "sort_order": 3,
        "intro_zh": "盖碗茶评书：醒木一拍，说尽巴蜀烟火故事，一盅盖碗茶配一场好戏。",
        "intro_en": "Gaiwan tea storytelling: with a slap of the gavel, tales of old Sichuan unfold over a cup of jasmine tea.",
        "text_content": "「一盅盖碗茶，一盏清心灯。」盖碗茶评书，说的都是巴蜀人最爱的烟火故事，醒木一拍，满堂喝彩。",
        "voice_content": "",
    },
    {
        "title": "蜀绣非遗展演",
        "subtitle": "川蜀大剧院 · 艺术展厅 · 夜场",
        "content_type": "full",
        "narrator": "陈老师",
        "venue": "艺术展厅",
        "duration_min": 75,
        "price": 98.0,
        "sort_order": 4,
        "intro_zh": "蜀绣：一针一线绣出花鸟山水，近距离观赏千年非遗的指尖艺术。",
        "intro_en": "Shu embroidery: flowers, birds and landscapes stitched thread by thread — a living 2,000-year craft.",
        "text_content": "蜀绣千丝万缕，是巴蜀千年的指尖艺术。一针一线，绣出花鸟山水，也绣出蜀人的温婉与坚韧。",
        "voice_content": "走进蜀绣展演，细赏蜀绣千丝万缕的指尖艺术，感受巴蜀千年匠心。",
    },
    {
        "title": "民乐·川江号子",
        "subtitle": "川蜀大剧院 · 音乐厅 · 夜场",
        "content_type": "full",
        "narrator": "周老师",
        "venue": "音乐厅",
        "duration_min": 150,
        "price": 198.0,
        "sort_order": 5,
        "intro_zh": "川江号子：船工在激流险滩间喊出的生命赞歌，一曲高亢如见江涛奔涌。",
        "intro_en": "Chuanjiang boatmen's chants: work songs once roared against raging rapids, now thundering on stage.",
        "text_content": "川江号子，是川江船工在激流险滩间喊出的生命赞歌。一曲高亢，如见江涛奔涌，荡气回肠。",
        "voice_content": "川江号子，是川江船工在激流险滩间喊出的生命赞歌，高亢回荡，荡气回肠。",
    },
]

# 演示耳机数据
DEMO_EARPHONES = [
    {
        "qr_code_id": "SY001",
        "name": "耳机A-01",
        "device_name": "Chuanshu-Guide-01",
        "serial_number": "SN-CHUANSHU-01",
        "status": "available",
        "bound_program_title": "川剧《变脸》选段",
    },
    {
        "qr_code_id": "SY002",
        "name": "耳机A-02",
        "device_name": "Chuanshu-Guide-02",
        "serial_number": "SN-CHUANSHU-02",
        "status": "available",
        "bound_program_title": "盖碗茶评书",
    },
    {
        "qr_code_id": "SY003",
        "name": "耳机B-01",
        "device_name": "Chuanshu-Guide-03",
        "serial_number": "SN-CHUANSHU-03",
        "status": "offline",
        "bound_program_title": "",
    },
]


def seed(db, reset: bool = False) -> None:
    if reset:
        if db.bind.dialect.name == "mysql":
            db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in ("reservations", "programs", "earphones", "admin_users"):
            db.execute(text(f"DELETE FROM {table}"))
        if db.bind.dialect.name == "mysql":
            db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()

    # 管理员（口令取环境变量 ADMIN_INIT_PASSWORD；未设置则随机生成并打印，仓库不留明文）
    if not db.query(AdminUser).filter_by(username="admin").first():
        init_password = os.environ.get("ADMIN_INIT_PASSWORD") or secrets.token_urlsafe(12)
        db.add(AdminUser(
            username="admin",
            password_hash=hash_password(init_password),
            display_name="系统管理员",
        ))
        print(f"已创建管理员账号：admin / {init_password}")

    # 文创旗舰店商品（商城后端化：静态卡数据迁入，仅表空时写入）
    if db.query(Product).count() == 0:
        SEED_PRODUCTS = [
            {"name": "武生靠旗背剑精锻工艺模型", "category": "accessory", "price_cents": 26800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_wusheng_sword.jpg",
             "description": "精锻武生拔剑靠旗，镀 24K 真金，配雕花木座与收藏编号。"},
            {"name": "蜀绣花旦水袖双面绣台画", "category": "embroidery", "price_cents": 32800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_shushi_tapestry.jpg",
             "description": "蜀绣大师针法手工绣制，呈现花旦水袖甩动流云质感。"},
            {"name": "非遗手绘川剧脸谱竹编扇", "category": "bamboo", "price_cents": 8800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_bamboo_fan.jpg",
             "description": "青城山慈竹手工细编，手绘关羽张飞包公非遗彩绘脸谱。"},
            {"name": "四川省川剧院定制彩绘盖碗茶具", "category": "accessory", "price_cents": 16800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_gaiwan_teaset.jpg",
             "description": "景德镇高白瓷浮雕脸谱，内赠蒙顶黄芽精装茶包品鉴。"},
            {"name": "朱红火凤与金枪漆器脸谱挂件", "category": "lacquer", "price_cents": 19800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_mask_pendant.jpg",
             "description": "天然大漆髹饰工艺，推光打磨朱红火凤与金枪图案。"},
            {"name": "古蜀雕花戏楼紫砂手工茶壶", "category": "lacquer", "price_cents": 45800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_opera_pottery.jpg",
             "description": "宜兴原矿紫砂泥雕刻古戏楼花窗与川剧脸谱图案。"},
            {"name": "藏红花金装川剧文房木盒", "category": "bamboo", "price_cents": 29800,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_saffron_box.jpg",
             "description": "四川名产藏红花伴手礼盒，烫金川剧艺术文字水墨书香。"},
            {"name": "蜀绣四大名旦手工刺绣画框", "category": "embroidery", "price_cents": 52000,
             "badge": "非遗工艺", "image_url": "./assets/products/furong_embroidery_frame.jpg",
             "description": "国家级非遗传承人领衔刺绣，挂画藏品级金丝实木框。"},
        ]
        for i, item in enumerate(SEED_PRODUCTS, 1):
            db.add(Product(sku=f"SHOP-{i:03d}", sort=i, status=1, **item))
        db.commit()
        print(f"已写入 {len(SEED_PRODUCTS)} 件文创旗舰店商品")

    # 演示节目
    if db.query(Program).count() == 0:
        for p in DEMO_PROGRAMS:
            db.add(Program(**p))
        print(f"已创建 {len(DEMO_PROGRAMS)} 个演示节目")

    # 演示耳机
    if db.query(Earphone).count() == 0:
        for e in DEMO_EARPHONES:
            db.add(Earphone(**e))
        print(f"已创建 {len(DEMO_EARPHONES)} 副演示耳机")

    db.commit()


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    init_db()
    db = SessionLocal()
    try:
        seed(db, reset=reset)
        print("初始化完成。")
    finally:
        db.close()