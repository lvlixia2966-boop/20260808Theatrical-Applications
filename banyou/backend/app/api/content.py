"""开放 API（游客端 / 三方接入）：只读，全量内容经此输出。

约定：
- 一切内容来自数据库，后台改动实时生效（无缓存层，数据量小直查即可）。
- 序列化输出统一走 ser_* 函数，保证前后端字段契约稳定，三方接入同样吃这套契约。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content import Region, RouteStop, ScenicArea, Spot, TourRoute
from app.services import geo
from app.services.settings_service import get_public

router = APIRouter()


def ser_region(row: Region) -> dict:
    return {"id": row.id, "code": row.code, "name": row.name, "sort": row.sort}


def ser_area_summary(row: ScenicArea, spot_count: int = 0, route_count: int = 0) -> dict:
    return {
        "id": row.id, "name": row.name, "en_name": row.en_name, "city": row.city,
        "level": row.level, "short_intro": row.short_intro, "cover_url": row.cover_url,
        "tags": row.tags, "rating": row.rating, "lat": row.lat, "lng": row.lng,
        "suggested_hours": row.suggested_hours, "ticket_info": row.ticket_info,
        "best_season": row.best_season,
        "spot_count": spot_count, "route_count": route_count,
    }


def ser_spot(row: Spot) -> dict:
    return {
        "id": row.id, "scenic_area_id": row.scenic_area_id, "name": row.name,
        "en_name": row.en_name, "category": row.category, "lat": row.lat, "lng": row.lng,
        "radius": row.radius, "stay_minutes": row.stay_minutes, "narration": row.narration,
        "audio_url": row.audio_url, "image_url": row.image_url, "tips": row.tips,
        "sort": row.sort,
    }


def ser_route(row: TourRoute, with_stops: bool = False, db: Session | None = None) -> dict:
    data = {
        "id": row.id, "scenic_area_id": row.scenic_area_id, "name": row.name,
        "theme": row.theme, "intro": row.intro, "cover_url": row.cover_url,
        "duration_minutes": row.duration_minutes, "distance_km": row.distance_km,
        "difficulty": row.difficulty, "mode": row.mode,
        "stop_count": len(row.stops),
    }
    if with_stops and db is not None:
        stops = (
            db.query(RouteStop).filter(RouteStop.route_id == row.id)
            .order_by(RouteStop.seq).all()
        )
        data["stops"] = [
            {"seq": stop.seq, "spot": ser_spot(stop.spot)}
            for stop in stops if stop.spot.status == 1
        ]
    return data


def ser_area_detail(row: ScenicArea, db: Session) -> dict:
    spots = [s for s in row.spots if s.status == 1]
    routes = [r for r in row.routes if r.status == 1]
    data = ser_area_summary(row, spot_count=len(spots), route_count=len(routes))
    data.update({
        "intro": row.intro, "address": row.address, "tel": row.tel,
        "open_time": row.open_time,
        "spots": [ser_spot(s) for s in spots],
        "routes": [ser_route(r) for r in routes],
        "center": {"lat": row.lat, "lng": row.lng},
    })
    return data


@router.get("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    """应用冷启动一次拉全：公开设置 + 区域列表，减少首屏请求。"""
    regions = (
        db.query(Region).filter(Region.enabled == 1).order_by(Region.sort, Region.id).all()
    )
    return {"app": get_public(db), "regions": [ser_region(r) for r in regions]}


@router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    regions = (
        db.query(Region).filter(Region.enabled == 1).order_by(Region.sort, Region.id).all()
    )
    return {"items": [ser_region(r) for r in regions]}


@router.get("/scenic-areas")
def list_scenic_areas(
    region: str | None = Query(None, description="区域 code，如 liangshan"),
    city: str | None = Query(None, description="县市名过滤，如 盐源县"),
    keyword: str | None = Query(None, description="名称/简介/标签模糊搜索"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(ScenicArea)
        .join(Region, ScenicArea.region_id == Region.id)
        .filter(ScenicArea.status == 1, Region.enabled == 1)
    )
    if region:
        query = query.filter(Region.code == region)
    if city:
        query = query.filter(ScenicArea.city == city)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(
            ScenicArea.name.like(like),
            ScenicArea.short_intro.like(like),
            ScenicArea.tags_raw.like(like),
        ))
    rows = query.order_by(ScenicArea.sort, ScenicArea.rating.desc(), ScenicArea.id).all()
    return {"items": [ser_area_summary(r, len([s for s in r.spots if s.status == 1]),
                                  len([x for x in r.routes if x.status == 1])) for r in rows]}


@router.get("/scenic-areas/{area_id}")
def get_scenic_area(area_id: int, db: Session = Depends(get_db)):
    row = db.get(ScenicArea, area_id)
    if row is None or row.status != 1:
        raise HTTPException(404, "景区不存在或已下线")
    return ser_area_detail(row, db)


@router.get("/spots/{spot_id}")
def get_spot(spot_id: int, db: Session = Depends(get_db)):
    row = db.get(Spot, spot_id)
    if row is None or row.status != 1:
        raise HTTPException(404, "点位不存在或已下线")
    return ser_spot(row)


@router.get("/routes/{route_id}")
def get_route(route_id: int, db: Session = Depends(get_db)):
    row = db.get(TourRoute, route_id)
    if row is None or row.status != 1:
        raise HTTPException(404, "路线不存在或已下线")
    return ser_route(row, with_stops=True, db=db)


@router.get("/nearby")
def nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """按距离排序的景区列表（伴游首页「离我最近」）。"""
    rows = db.query(ScenicArea).filter(ScenicArea.status == 1).all()
    items = []
    for row in rows:
        if not row.lat or not row.lng:
            continue
        items.append({
            **ser_area_summary(row),
            "distance_m": round(geo.haversine_m(lat, lng, row.lat, row.lng)),
        })
    items.sort(key=lambda x: x["distance_m"])
    return {"items": items[:limit]}
