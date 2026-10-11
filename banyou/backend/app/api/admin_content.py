"""管理后台内容 API：区域 / 景区 / 点位 / 路线 CRUD + 路线排点。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.admin import AdminUser
from app.models.content import Region, RouteStop, ScenicArea, Spot, TourRoute
from app.schemas.content import (
    RegionIn, RouteStopsIn, ScenicAreaIn, SpotIn, TourRouteIn,
)

router = APIRouter(dependencies=[Depends(require_admin)])


# ---------- 区域 ----------

@router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    rows = db.query(Region).order_by(Region.sort, Region.id).all()
    return {"items": [
        {"id": r.id, "code": r.code, "name": r.name, "sort": r.sort, "enabled": r.enabled}
        for r in rows
    ]}


@router.post("/regions")
def create_region(body: RegionIn, db: Session = Depends(get_db)):
    if db.query(Region).filter(Region.code == body.code).first():
        raise HTTPException(400, "区域 code 已存在")
    row = Region(code=body.code, name=body.name, sort=body.sort, enabled=body.enabled)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/regions/{region_id}")
def update_region(region_id: int, body: RegionIn, db: Session = Depends(get_db)):
    row = db.get(Region, region_id)
    if row is None:
        raise HTTPException(404, "区域不存在")
    row.code, row.name, row.sort, row.enabled = body.code, body.name, body.sort, body.enabled
    db.commit()
    return {"ok": True}


@router.delete("/regions/{region_id}")
def delete_region(region_id: int, db: Session = Depends(get_db)):
    row = db.get(Region, region_id)
    if row is None:
        raise HTTPException(404, "区域不存在")
    if row.areas:
        raise HTTPException(400, "区域下仍有景区，请先迁移或删除")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 景区 ----------

def _apply_area(row: ScenicArea, body: ScenicAreaIn) -> None:
    for key, value in body.model_dump().items():
        if key == "tags":
            row.tags = value
        else:
            setattr(row, key, value)


@router.get("/scenic-areas")
def list_areas(include_offline: bool = True, db: Session = Depends(get_db)):
    query = db.query(ScenicArea)
    if not include_offline:
        query = query.filter(ScenicArea.status == 1)
    rows = query.order_by(ScenicArea.sort, ScenicArea.id).all()
    return {"items": [
        {
            "id": r.id, "region_id": r.region_id, "name": r.name, "en_name": r.en_name,
            "city": r.city, "level": r.level, "address": r.address, "tel": r.tel,
            "open_time": r.open_time, "ticket_info": r.ticket_info,
            "suggested_hours": r.suggested_hours, "short_intro": r.short_intro,
            "intro": r.intro, "lat": r.lat, "lng": r.lng, "cover_url": r.cover_url,
            "tags": r.tags, "rating": r.rating, "best_season": r.best_season,
            "sort": r.sort, "status": r.status,
            "spot_count": len(r.spots), "route_count": len(r.routes),
        }
        for r in rows
    ]}


@router.post("/scenic-areas")
def create_area(body: ScenicAreaIn, db: Session = Depends(get_db)):
    row = ScenicArea()
    _apply_area(row, body)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/scenic-areas/{area_id}")
def update_area(area_id: int, body: ScenicAreaIn, db: Session = Depends(get_db)):
    row = db.get(ScenicArea, area_id)
    if row is None:
        raise HTTPException(404, "景区不存在")
    _apply_area(row, body)
    db.commit()
    return {"ok": True}


@router.delete("/scenic-areas/{area_id}")
def delete_area(area_id: int, db: Session = Depends(get_db)):
    row = db.get(ScenicArea, area_id)
    if row is None:
        raise HTTPException(404, "景区不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 点位 ----------

def _apply_spot(row: Spot, body: SpotIn) -> None:
    for key, value in body.model_dump().items():
        if key == "narration":
            row.narration = value
        else:
            setattr(row, key, value)


@router.get("/spots")
def list_spots(scenic_area_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Spot)
    if scenic_area_id:
        query = query.filter(Spot.scenic_area_id == scenic_area_id)
    rows = query.order_by(Spot.scenic_area_id, Spot.sort, Spot.id).all()
    return {"items": [
        {
            "id": s.id, "scenic_area_id": s.scenic_area_id, "name": s.name,
            "en_name": s.en_name, "category": s.category, "lat": s.lat, "lng": s.lng,
            "radius": s.radius, "stay_minutes": s.stay_minutes, "narration": s.narration,
            "audio_url": s.audio_url, "image_url": s.image_url, "tips": s.tips,
            "sort": s.sort, "status": s.status,
        }
        for s in rows
    ]}


@router.post("/spots")
def create_spot(body: SpotIn, db: Session = Depends(get_db)):
    if db.get(ScenicArea, body.scenic_area_id) is None:
        raise HTTPException(400, "所属景区不存在")
    row = Spot()
    _apply_spot(row, body)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/spots/{spot_id}")
def update_spot(spot_id: int, body: SpotIn, db: Session = Depends(get_db)):
    row = db.get(Spot, spot_id)
    if row is None:
        raise HTTPException(404, "点位不存在")
    _apply_spot(row, body)
    db.commit()
    return {"ok": True}


@router.delete("/spots/{spot_id}")
def delete_spot(spot_id: int, db: Session = Depends(get_db)):
    row = db.get(Spot, spot_id)
    if row is None:
        raise HTTPException(404, "点位不存在")
    used = db.query(RouteStop).filter(RouteStop.spot_id == spot_id).count()
    if used:
        raise HTTPException(400, f"该点位已被 {used} 条路线引用，请先在路线中移除")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- 路线 ----------

def _apply_route(row: TourRoute, body: TourRouteIn) -> None:
    for key, value in body.model_dump().items():
        setattr(row, key, value)


@router.get("/routes")
def list_routes(scenic_area_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(TourRoute)
    if scenic_area_id:
        query = query.filter(TourRoute.scenic_area_id == scenic_area_id)
    rows = query.order_by(TourRoute.scenic_area_id, TourRoute.sort, TourRoute.id).all()
    return {"items": [
        {
            "id": r.id, "scenic_area_id": r.scenic_area_id, "name": r.name,
            "theme": r.theme, "intro": r.intro, "cover_url": r.cover_url,
            "duration_minutes": r.duration_minutes, "distance_km": r.distance_km,
            "difficulty": r.difficulty, "mode": r.mode, "sort": r.sort, "status": r.status,
            "stop_ids": [stop.spot_id for stop in sorted(r.stops, key=lambda s: s.seq)],
            "stop_names": [stop.spot.name for stop in sorted(r.stops, key=lambda s: s.seq)],
        }
        for r in rows
    ]}


@router.post("/routes")
def create_route(body: TourRouteIn, db: Session = Depends(get_db)):
    if db.get(ScenicArea, body.scenic_area_id) is None:
        raise HTTPException(400, "所属景区不存在")
    row = TourRoute()
    _apply_route(row, body)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/routes/{route_id}")
def update_route(route_id: int, body: TourRouteIn, db: Session = Depends(get_db)):
    row = db.get(TourRoute, route_id)
    if row is None:
        raise HTTPException(404, "路线不存在")
    _apply_route(row, body)
    db.commit()
    return {"ok": True}


@router.delete("/routes/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    row = db.get(TourRoute, route_id)
    if row is None:
        raise HTTPException(404, "路线不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.put("/routes/{route_id}/stops")
def set_route_stops(route_id: int, body: RouteStopsIn, db: Session = Depends(get_db)):
    """重设路线点位顺序：整体替换，seq 按数组顺序 1..n。"""
    route = db.get(TourRoute, route_id)
    if route is None:
        raise HTTPException(404, "路线不存在")
    spots = db.query(Spot).filter(Spot.id.in_(body.spot_ids)).all()
    found = {s.id for s in spots}
    missing = [sid for sid in body.spot_ids if sid not in found]
    if missing:
        raise HTTPException(400, f"点位不存在: {missing}")
    db.query(RouteStop).filter(RouteStop.route_id == route_id).delete()
    for seq, spot_id in enumerate(body.spot_ids, start=1):
        db.add(RouteStop(route_id=route_id, spot_id=spot_id, seq=seq))
    db.commit()
    return {"ok": True, "stop_count": len(body.spot_ids)}
