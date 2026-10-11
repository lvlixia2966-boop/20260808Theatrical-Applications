"""AI 伴游对话引擎：知识库检索 + 位置上下文 + 意图路由 + 富卡片（+ 可选豆包 LLM 兜底）。

设计：
- 知识库即业务库：景区/点位讲解稿、贴士、路线、门票开放时间等信息全部就地取材，
  不需要单独维护一套语料。
- 位置上下文：每次请求带经纬度，服务端计算最近点位/所属景区/路线进度，
  回答时「知道你在哪」；到站主动播报由前端按 radius 判定触发。
- 富卡片：应答除文本外可携带美景卡片（点位/景区，带实拍图）与购物卡片（文创商品），
  前端在气泡下方渲染横向卡片栏，点卡片继续对话或直达选购。
- 规则引擎优先（零外部依赖、离线可用）；配置了 ARK_API_KEY 时自动升级为
  LLM 组织语言（检索内容作为唯一事实来源，防编造），失败自动回退规则引擎。
"""
import difflib
import json
import urllib.request

from app.config import settings
from app.models.content import RouteStop, ScenicArea, Spot, TourRoute
from app.models.product import Product
from app.services.geo import bearing_deg, haversine_m

_BEARINGS = ["正北", "东北", "正东", "东南", "正南", "西南", "正西", "西北"]

_INTENTS = [
    ("greet", ("你好", "您好", "在吗", "hi", "hello", "嗨")),
    ("thanks", ("谢谢", "感谢", "辛苦")),
    ("nav", ("下一站", "怎么走", "还有多远", "多远", "导航", "往哪", "路线怎么")),
    ("ticket", ("门票", "票价", "收费", "多少钱", "免费吗", "优惠")),
    ("open", ("几点", "开放", "关门", "闭馆", "开馆", "营业")),
    ("toilet", ("厕所", "洗手间", "卫生间", "wc")),
    ("food", ("吃", "美食", "小吃", "餐厅", "午饭", "晚饭", "饿了", "烧烤")),
    ("season", ("季节", "什么时候来", "花期", "红叶", "最佳", "雪")),
    ("shop", ("买", "文创", "纪念品", "好物", "礼物", "特产", "购物")),
    ("recommend", ("推荐", "必去", "值得", "好玩", "攻略", "怎么玩", "行程")),
]

_NARRATION_HINTS = ("讲", "介绍", "故事", "历史", "文化", "来历", "为什么", "讲究", "说", "聊聊")


def _bearing_name(deg: float) -> str:
    return _BEARINGS[int(((deg + 22.5) % 360) // 45)]


def _first_sentence(text: str, limit: int = 60) -> str:
    for sep in ("。", "！", "？", ";"):
        at = text.find(sep)
        if 0 < at <= limit:
            return text[: at + 1]
    return text[:limit]


def _ser_spot_min(s: Spot) -> dict:
    return {"id": s.id, "name": s.name, "category": s.category,
            "lat": s.lat, "lng": s.lng, "stay_minutes": s.stay_minutes}


def _load_areas(db) -> dict[int, ScenicArea]:
    return {a.id: a for a in db.query(ScenicArea).filter(ScenicArea.status == 1).all()}


def _match_spot(query: str, spots: list[Spot]) -> Spot | None:
    """按名称提及匹配点位：子串直接命中，否则按字符相似度取最优。"""
    q = query.strip().lower()
    best, best_score = None, 0.0
    for s in spots:
        name = s.name.lower()
        short = name.split("·")[0]
        if name in q or short in q or q in name:
            return s
        score = max(difflib.SequenceMatcher(None, q, name).ratio(),
                    difflib.SequenceMatcher(None, q, short).ratio())
        if score > best_score:
            best, best_score = s, score
    return best if best_score >= 0.62 else None


# ── 对话内富卡片：美景卡片（点位/景区）与购物卡片（文创商品） ──

def _spot_card(spot: Spot, area: ScenicArea | None = None) -> dict:
    """美景卡片：图片优先级 点位图 > 景区封面（美景实拍）> 空（前端渐变占位）。"""
    return {
        "type": "spot", "id": spot.id, "title": spot.name,
        "subtitle": f"{spot.category} · 建议停留 {spot.stay_minutes} 分钟",
        "image_url": spot.image_url or (area.cover_url if area else ""),
        "desc": _first_sentence((spot.narration or {}).get("zh") or "", 50),
    }


def _area_card(area: ScenicArea) -> dict:
    return {
        "type": "area", "id": area.id, "title": area.name,
        "subtitle": f"{area.city} · {area.level}" if area.level else area.city,
        "image_url": area.cover_url,
        "desc": _first_sentence(area.short_intro or "", 50),
    }


def _product_cards(db, area_id: int | None, limit: int = 4) -> list[dict]:
    """购物卡片：优先关联景区的商品，不足补全域好物。"""
    rows = db.query(Product).filter(Product.status == 1).order_by(Product.sort, Product.id).all()
    if area_id:
        ranked = [p for p in rows if p.scenic_area_id == area_id] + \
                 [p for p in rows if p.scenic_area_id is None]
    else:
        ranked = rows
    out = []
    for p in ranked[:limit]:
        out.append({
            "type": "product", "id": p.id, "title": p.name,
            "subtitle": f"¥{p.price:g}",
            "image_url": p.image_url, "desc": _first_sentence(p.desc or "", 40),
            "price": p.price,
        })
    return out


def build_context(db, lat: float | None, lng: float | None,
                  area_id: int | None, route_id: int | None) -> dict:
    """位置与行程上下文：最近点位 / 所属景区 / 路线下一站。

    显式指定景区时（从对话锁定），「最近点位」只在该景区内取——
    「这里」永远指用户正在游览的景区，而不是全局几何最近。
    """
    areas = _load_areas(db)
    area = areas.get(area_id) if area_id else None

    nearest, nearest_d = None, None
    if lat is not None and lng is not None:
        if area is not None:
            spots = [s for s in area.spots if s.status == 1 and s.lat]
        else:
            spots = [s for s in db.query(Spot).filter(Spot.status == 1).all() if s.lat]
        if spots:
            nearest = min(spots, key=lambda s: haversine_m(lat, lng, s.lat, s.lng))
            nearest_d = round(haversine_m(lat, lng, nearest.lat, nearest.lng))

    # 景区归属：显式指定 > 最近点位所属
    if area is None and nearest is not None:
        area = areas.get(nearest.scenic_area_id)

    # 路线与下一站
    route, next_stop = None, None
    if route_id:
        route = db.get(TourRoute, route_id)
    elif area is not None:
        route = (
            db.query(TourRoute)
            .filter(TourRoute.scenic_area_id == area.id, TourRoute.status == 1)
            .order_by(TourRoute.sort, TourRoute.id).first()
        )
    if route is not None and lat is not None and lng is not None:
        stops = (
            db.query(RouteStop).filter(RouteStop.route_id == route.id)
            .order_by(RouteStop.seq).all()
        )
        stops = [st for st in stops if st.spot.status == 1]
        if stops:
            dists = [haversine_m(lat, lng, st.spot.lat, st.spot.lng) for st in stops]
            cur = dists.index(min(dists))
            nxt = stops[cur + 1] if cur + 1 < len(stops) else None
            if nxt is not None:
                nd = haversine_m(lat, lng, nxt.spot.lat, nxt.spot.lng)
                b = bearing_deg(lat, lng, nxt.spot.lat, nxt.spot.lng)
                next_stop = {"seq": nxt.seq, "spot": _ser_spot_min(nxt.spot),
                             "distance_m": round(nd), "bearing": _bearing_name(b),
                             "walk_minutes": max(1, round(nd / 80))}
    nearest_info = None
    if nearest is not None:
        nearest_info = {**_ser_spot_min(nearest), "distance_m": nearest_d,
                        "arrived": nearest_d <= max(nearest.radius, 50)}
    return {
        "area": {"id": area.id, "name": area.name, "city": area.city} if area else None,
        "nearest_spot": nearest_info,
        "route": {"id": route.id, "name": route.name} if route else None,
        "next_stop": next_stop,
    }


def _suggestions(ctx: dict) -> list[str]:
    out = []
    if ctx.get("next_stop"):
        out.append("下一站怎么走")
    if ctx.get("nearest_spot"):
        out.append("讲讲这里的故事")
    out += ["门票多少钱", "有什么必去的", "有什么好物"]
    return out[:4]


# ── 意图应答（文本 + 引用 + 卡片） ──

def _answer_nav(db, query: str, ctx: dict, nearest: Spot | None, area: ScenicArea | None = None):
    nxt = ctx.get("next_stop")
    if nxt:
        s = nxt["spot"]
        nxt_spot = db.get(Spot, s["id"])
        cards = [_spot_card(nxt_spot, area)] if nxt_spot else []
        return (f"下一站是第 {nxt['seq']} 站「{s['name']}」，在您{nxt['bearing']}方向，"
                f"直线约 {nxt['distance_m']}m，步行约 {nxt['walk_minutes']} 分钟。"
                f"沿主步道走即可，到达后我会自动为您讲解。",
                "nav", [{"type": "spot", "id": s["id"], "name": s["name"]}], cards)
    if ctx.get("route"):
        rname = ctx["route"]["name"]
        if nearest is not None:
            return (f"您已经走到「{rname}」的最后一站「{nearest.name}」附近了，走完全程🎉"
                    " 可以在设置里看看我的订单，或点「好物」带点凉山风物回家。",
                    "nav", [{"type": "spot", "id": nearest.id, "name": nearest.name}],
                    [_spot_card(nearest, area)])
        return (f"「{rname}」的站点已走完，恭喜完成伴游🎉", "nav", [], [])
    if nearest is not None:
        d = ctx["nearest_spot"]["distance_m"]
        return (f"当前没有进行中的路线。离您最近的是「{nearest.name}」，"
                f"约 {d}m，建议停留 {nearest.stay_minutes} 分钟，要我先讲讲它吗？",
                "nav", [{"type": "spot", "id": nearest.id, "name": nearest.name}],
                [_spot_card(nearest, area)])
    return "开启定位后我就能为您指路啦；到了景区附近我会自动为您讲解。", "nav", [], []


def _answer_food(spots: list[Spot], nearest: Spot | None, area: ScenicArea | None = None):
    food_words = ("吃", "美食", "烧烤", "鱼", "茶", "小吃", "餐")
    hits = []
    for s in spots:
        text = (s.narration or {}).get("zh", "") + s.tips
        if any(w in text for w in food_words):
            hits.append(s)
    if not hits and nearest is not None:
        hits = [nearest]
    if hits:
        names = "、".join(f"「{s.name}」" for s in hits[:2])
        detail = hits[0]
        line = _first_sentence((detail.narration or {}).get("zh", ""))
        return (f"推荐去{names}：{line} 具体店铺沿步道标识走就好。", "info",
                [{"type": "spot", "id": s.id, "name": s.name} for s in hits[:2]],
                [_spot_card(s, area) for s in hits[:2]])
    return "沿线都有本地风味；也可以出景区后问我，帮您想想吃什么。", "info", [], []


def _answer_recommend(area: ScenicArea | None, spots: list[Spot]):
    if area is None:
        return "开启定位告诉我您的位置，我来帮您安排玩法～", "info", [], []
    picks = spots[:3]
    lines = "、".join(f"「{s.name}」" for s in picks) if picks else "各主要点位"
    route = next((r for r in area.routes if r.status == 1), None)
    route_line = f" 时间紧就走官方路线「{route.name}」（约 {round(route.duration_minutes / 60)} 小时），一步不落。" if route else ""
    return (f"{area.name}必看：{lines}。{route_line} "
            f"最佳季节是{area.best_season or '四季皆宜'}。", "info",
            [{"type": "spot", "id": s.id, "name": s.name} for s in picks[:2]],
            [_spot_card(s, area) for s in picks])


def _retrieve(db, query: str, ctx: dict) -> tuple[str, str, list[dict], list[dict]]:
    """规则引擎：返回 (回复文本, 类型, 引用, 卡片)。"""
    area = None
    if ctx.get("area"):
        area = db.get(ScenicArea, ctx["area"]["id"])
    spots = []
    if area is not None:
        spots = [s for s in area.spots if s.status == 1]
    nearest = None
    if ctx.get("nearest_spot"):
        nearest = db.get(Spot, ctx["nearest_spot"]["id"])
    named = _match_spot(query, spots) if spots else None

    def area_card():
        return [_area_card(area)] if area is not None else []

    for intent, keywords in _INTENTS:
        if not any(k in query for k in keywords):
            continue
        if intent == "greet":
            where = f"{area.name}" if area else "凉山"
            return (f"您好！我是您的 AI 伴游讲解员，现在陪您游览{where}。"
                    "您可以让我讲景点故事、查门票开放时间、指路下一站，或者问吃什么买什么～",
                    "small", [], area_card())
        if intent == "thanks":
            return "不客气！旅途注意脚下安全，随时叫我～", "small", [], []
        if intent == "nav":
            return _answer_nav(db, query, ctx, nearest, area)
        if intent == "ticket":
            if area is not None and area.ticket_info:
                return f"{area.name}门票：{area.ticket_info}。", "info", [], []
            return "大部分凉山景区免费开放；泸沽湖、螺髻山等收费景区以现场公告为准。", "info", [], []
        if intent == "open":
            if area is not None and area.open_time:
                return f"{area.name}开放时间：{area.open_time}。", "info", [], []
            return "多数景区全天开放，博物馆类周一闭馆，具体以现场公告为准。", "info", [], []
        if intent == "toilet":
            near = f"离您最近的「{nearest.name}」附近" if nearest else "游览步道沿线"
            return f"沿步道标识牌走，{near}就有卫生间；游客中心内也都有。", "small", [], []
        if intent == "food":
            return _answer_food(spots, nearest, area)
        if intent == "season":
            if area is not None and area.best_season:
                return f"{area.name}最佳游览时间：{area.best_season}。", "info", [], []
            return "凉山四季皆可游：春看索玛杜鹃，夏天高原避暑，秋赏彩林，冬季晒太阳观候鸟。", "info", [], []
        if intent == "shop":
            cards = _product_cards(db, area.id if area else None)
            where = f"关于{area.name}" if area else "凉山"
            tip = "点击卡片可直接选购。" if cards else "点击右上角「好物」查看全部。"
            return (f"{where}的好物都在手边：彝族漆器、彝绣、摩梭手作这些最受欢迎。{tip}",
                    "shop", [], cards)
        if intent == "recommend":
            return _answer_recommend(area, spots)

    # 点位提及 / 泛讲解诉求 → 讲解稿
    target = named
    if target is None and any(k in query for k in _NARRATION_HINTS):
        if nearest is not None:
            target = nearest
        elif area is not None:
            # 无定位但知道在哪个景区：讲景区总介 + 景区美景卡片
            return (f"【{area.name}】{area.intro or area.short_intro}",
                    "narration", [{"type": "area", "id": area.id, "name": area.name}],
                    area_card())
    if target is not None:
        narr = (target.narration or {}).get("zh") or ""
        body = narr or f"「{target.name}」的讲解内容筹备中，先看看它的{target.category}看点吧。"
        tips = f" 小贴士：{target.tips}" if target.tips else ""
        return (f"【{target.name}】{body}{tips}", "narration",
                [{"type": "spot", "id": target.id, "name": target.name}],
                [_spot_card(target, area)])

    # 兜底：给最近点位的概览
    if nearest is not None and area is not None:
        return (f"这个问题我还在学习中～ 先带您看看脚下的「{nearest.name}」："
                f"{_first_sentence((nearest.narration or {}).get('zh') or area.short_intro)} "
                f"您也可以问我{('下一站怎么走、' if ctx.get('next_stop') else '')}这里的故事、门票开放时间。",
                "fallback", [{"type": "spot", "id": nearest.id, "name": nearest.name}],
                [_spot_card(nearest, area)])
    return ("告诉我您在哪个景区附近，或直接问我景点故事、门票、路线，我来安排～",
            "fallback", [], area_card())


def _knowledge_pack(db, ctx: dict) -> str:
    """检索知识包：供 LLM 组织语言的事实来源（防编造）。"""
    parts = []
    if ctx.get("area"):
        area = db.get(ScenicArea, ctx["area"]["id"])
        if area:
            parts.append(f"【景区】{area.name}：{area.short_intro} 开放：{area.open_time}；门票：{area.ticket_info}；最佳季节：{area.best_season}")
    if ctx.get("nearest_spot"):
        s = db.get(Spot, ctx["nearest_spot"]["id"])
        if s:
            narr = (s.narration or {}).get("zh", "")
            parts.append(f"【当前附近点位】{s.name}（{s.category}，建议停留 {s.stay_minutes} 分钟）：{narr} 贴士：{s.tips}")
    if ctx.get("next_stop"):
        s = ctx["next_stop"]["spot"]
        parts.append(f"【下一站】{s['name']}，{ctx['next_stop']['bearing']}方向约 {ctx['next_stop']['distance_m']}m")
    return "\n".join(parts)


def _llm_reply(query: str, history: list[dict], ctx: dict, knowledge: str) -> str | None:
    """豆包 LLM（OpenAI 兼容 REST）；未配置或失败返回 None（回退规则引擎）。"""
    if not settings.ark_api_key:
        return None
    where = ctx["area"]["name"] if ctx.get("area") else "凉山州景区"
    nearest_line = ""
    if ctx.get("nearest_spot"):
        ns = ctx["nearest_spot"]
        nearest_line = f"游客当前在「{ns['name']}」附近（约 {ns['distance_m']}m）。"
    system = (
        f"你是{where}的 AI 伴游讲解员，语气亲切口语化，每次回答不超过 150 字。"
        f"{nearest_line} 只使用下面给你的资料回答，资料里没有的就说明不确定并建议现场咨询，"
        f"禁止编造事实。\n资料：\n{knowledge}"
    )
    messages = [{"role": "system", "content": system}]
    messages += [
        {"role": h["role"], "content": h["content"]}
        for h in (history or [])[-6:] if h.get("role") in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": query})
    try:
        req = urllib.request.Request(
            f"{settings.ark_base_url}/chat/completions",
            data=json.dumps({
                "model": settings.ark_llm_model,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 400,
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.ark_api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=settings.ark_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return content.strip() or None
    except Exception:  # noqa: BLE001 网络异常/超时/限流一律回退规则引擎
        return None


def chat(db, *, message: str, lat: float | None, lng: float | None,
         area_id: int | None, route_id: int | None,
         history: list[dict] | None = None) -> dict:
    # 无定位 / 换景区时：从消息里识别景区名（「我在泸沽湖」），对话即上下文入口
    matched_area_by_name = False
    if area_id is None:
        # 1) 点位名全局提及（「给我讲讲走婚桥」）→ 推导所属景区
        m = _match_spot(message, db.query(Spot).filter(Spot.status == 1).all())
        if m is not None:
            area_id = m.scenic_area_id
        # 2) 景区名提及（「我在泸沽湖」）
        if area_id is None:
            areas = _load_areas(db)
            for a in areas.values():
                base = a.name.replace("景区", "").replace("风景区", "").replace("高原湿地", "")
                if a.name in message or (len(base) >= 3 and base in message):
                    area_id = a.id
                    matched_area_by_name = True
                    break

    ctx = build_context(db, lat, lng, area_id, route_id)

    if matched_area_by_name:
        area = db.get(ScenicArea, area_id)
        return {"reply": f"好嘞，现在陪您游「{area.name}」。{area.short_intro} "
                         "到了具体点位附近我会主动讲解；有什么想了解的，直接问我～",
                "kind": "small", "refs": [], "cards": [_area_card(area)],
                "context": ctx, "suggestions": _suggestions(ctx)}

    reply, kind, refs, cards = _retrieve(db, message, ctx)
    knowledge = _knowledge_pack(db, ctx)
    llm = _llm_reply(message, history or [], ctx, knowledge)
    if llm:
        reply, kind = llm, "llm"
    return {"reply": reply, "kind": kind, "refs": refs, "cards": cards,
            "context": ctx, "suggestions": _suggestions(ctx)}
