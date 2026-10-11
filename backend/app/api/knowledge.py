"""知识库路由：节点 / 知识单元 / 译文 / 实体图谱 / 验收问集 / 试查 / 向量生成（报价单 #10/#11）。

高内聚：知识域的 CRUD 与运营操作收敛在此；召回策略在 retrieval_service。
低耦合：路由只做鉴权、参数装配与响应装配；向量经 ark_client 产出后落 KnowledgeVector，
       任何数据变更后调用 retrieval_service.invalidate() 让索引自动重建。
"""
import logging
import struct
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import DbDep, require_role
from app.models import AdminUser
from app.models.knowledge import (
    EntityRelation,
    EvalQuestion,
    KnowledgeEntity,
    KnowledgeNode,
    KnowledgeTranslation,
    KnowledgeUnit,
    KnowledgeVector,
    UnitEntityLink,
)
from app.schemas import ApiResponse
from app.schemas.knowledge import (
    EmbedResultOut,
    EntityRelationIn,
    EntityRelationOut,
    EvalQuestionIn,
    EvalQuestionOut,
    KnowledgeEntityIn,
    KnowledgeEntityOut,
    KnowledgeNodeIn,
    KnowledgeNodeOut,
    KnowledgeTranslationIn,
    KnowledgeTranslationOut,
    KnowledgeUnitIn,
    KnowledgeUnitOut,
    SearchPreviewOut,
    UnitEntityLinkIn,
)
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger("knowledge")

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])

BATCH_EMBED_SIZE = 16

# 知识域权限：内容（content）/运营（ops）/超管（super）可操作，普通账号只读受限
ContentDep = Annotated[AdminUser, Depends(require_role("content", "ops"))]


# ── 知识节点 ─────────────────────────────────────────────────────


def _node_out(db, row: KnowledgeNode) -> KnowledgeNodeOut:
    count = db.query(KnowledgeUnit).filter(KnowledgeUnit.node_id == row.id).count()
    return KnowledgeNodeOut(
        id=row.id, code=row.code, name_zh=row.name_zh, name_en=row.name_en,
        description=row.description, sort=row.sort, is_active=row.is_active,
        unit_count=count,
    )


@router.get("/nodes", response_model=ApiResponse[list[KnowledgeNodeOut]])
def list_nodes(db: DbDep, _: ContentDep):
    """节点列表（含单元计数）。"""
    rows = db.query(KnowledgeNode).order_by(KnowledgeNode.sort, KnowledgeNode.id).all()
    return ApiResponse(data=[_node_out(db, r) for r in rows])


@router.post("/nodes", response_model=ApiResponse[KnowledgeNodeOut])
def create_node(payload: KnowledgeNodeIn, db: DbDep, _: ContentDep):
    if db.query(KnowledgeNode).filter(KnowledgeNode.code == payload.code).first():
        raise HTTPException(status_code=409, detail="节点码已存在")
    row = KnowledgeNode(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiResponse(data=_node_out(db, row))


@router.put("/nodes/{node_id}", response_model=ApiResponse[KnowledgeNodeOut])
def update_node(node_id: int, payload: KnowledgeNodeIn, db: DbDep, _: ContentDep):
    row = db.get(KnowledgeNode, node_id)
    if row is None:
        raise HTTPException(status_code=404, detail="节点不存在")
    dup = db.query(KnowledgeNode).filter(KnowledgeNode.code == payload.code, KnowledgeNode.id != node_id).first()
    if dup:
        raise HTTPException(status_code=409, detail="节点码已存在")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    retrieval_service.invalidate()
    return ApiResponse(data=_node_out(db, row))


@router.delete("/nodes/{node_id}", response_model=ApiResponse[dict])
def delete_node(node_id: int, db: DbDep, _: ContentDep):
    """删除节点：其下单元一并停用（保留记录，向量与索引随之失效）。"""
    row = db.get(KnowledgeNode, node_id)
    if row is None:
        raise HTTPException(status_code=404, detail="节点不存在")
    db.query(KnowledgeUnit).filter(KnowledgeUnit.node_id == node_id).update({"is_active": False})
    row.is_active = False
    db.commit()
    retrieval_service.invalidate()
    return ApiResponse(message="节点已停用（其下单元一并停用）", data={"id": node_id, "is_active": False})


# ── 知识单元 ─────────────────────────────────────────────────────


def _unit_out(db, row: KnowledgeUnit) -> KnowledgeUnitOut:
    node = db.get(KnowledgeNode, row.node_id)
    has_vec = db.get(KnowledgeVector, row.id) is not None
    return KnowledgeUnitOut(
        id=row.id, node_id=row.node_id,
        node_code=node.code if node else "", node_name=node.name_zh if node else "",
        title=row.title, content_zh=row.content_zh, keywords=row.keywords,
        is_active=row.is_active, review_status=row.review_status,
        has_vector=has_vec, created_at=row.created_at,
    )


@router.get("/units", response_model=ApiResponse[list[KnowledgeUnitOut]])
def list_units(
    db: DbDep, _: ContentDep,
    node_id: int | None = Query(None), q: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """单元列表（可按节点过滤 / 标题与内容模糊搜索）。"""
    query = db.query(KnowledgeUnit)
    if node_id is not None:
        query = query.filter(KnowledgeUnit.node_id == node_id)
    if q:
        like = f"%{q}%"
        query = query.filter(KnowledgeUnit.title.like(like) | KnowledgeUnit.content_zh.like(like))
    rows = query.order_by(KnowledgeUnit.id.desc()).limit(limit).all()
    return ApiResponse(data=[_unit_out(db, r) for r in rows])


@router.post("/units", response_model=ApiResponse[KnowledgeUnitOut])
def create_unit(payload: KnowledgeUnitIn, db: DbDep, _: ContentDep):
    if db.get(KnowledgeNode, payload.node_id) is None:
        raise HTTPException(status_code=404, detail="所属节点不存在")
    row = KnowledgeUnit(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    retrieval_service.invalidate()
    return ApiResponse(data=_unit_out(db, row))


@router.put("/units/{unit_id}", response_model=ApiResponse[KnowledgeUnitOut])
def update_unit(unit_id: int, payload: KnowledgeUnitIn, db: DbDep, _: ContentDep):
    row = db.get(KnowledgeUnit, unit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="单元不存在")
    if db.get(KnowledgeNode, payload.node_id) is None:
        raise HTTPException(status_code=404, detail="所属节点不存在")
    content_changed = (
        row.title != payload.title or row.content_zh != payload.content_zh
        or row.keywords != payload.keywords
    )
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    if content_changed:
        # 母稿变更：旧向量作废，待重新生成
        db.query(KnowledgeVector).filter(KnowledgeVector.unit_id == unit_id).delete()
    db.commit()
    db.refresh(row)
    retrieval_service.invalidate()
    return ApiResponse(data=_unit_out(db, row))


@router.delete("/units/{unit_id}", response_model=ApiResponse[dict])
def delete_unit(unit_id: int, db: DbDep, _: ContentDep):
    row = db.get(KnowledgeUnit, unit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="单元不存在")
    db.query(KnowledgeVector).filter(KnowledgeVector.unit_id == unit_id).delete()
    db.query(KnowledgeTranslation).filter(KnowledgeTranslation.unit_id == unit_id).delete()
    db.query(UnitEntityLink).filter(UnitEntityLink.unit_id == unit_id).delete()
    db.query(EvalQuestion).filter(EvalQuestion.expect_unit_id == unit_id).delete()
    db.delete(row)
    db.commit()
    retrieval_service.invalidate()
    return ApiResponse(message="单元已删除", data={"id": unit_id})


# ── 译文（12 语种，人工抽检流程）─────────────────────────────────


@router.get("/units/{unit_id}/translations", response_model=ApiResponse[list[KnowledgeTranslationOut]])
def list_translations(unit_id: int, db: DbDep, _: ContentDep):
    rows = db.query(KnowledgeTranslation).filter(KnowledgeTranslation.unit_id == unit_id).all()
    return ApiResponse(data=[KnowledgeTranslationOut(
        id=r.id, unit_id=r.unit_id, lang=r.lang, content=r.content, review_status=r.review_status,
    ) for r in rows])


@router.put("/units/{unit_id}/translations", response_model=ApiResponse[KnowledgeTranslationOut])
def upsert_translation(unit_id: int, payload: KnowledgeTranslationIn, db: DbDep, _: ContentDep):
    """写入/更新某语种译文（机翻预填或人工修订，review_status 标记抽检状态）。"""
    if db.get(KnowledgeUnit, unit_id) is None:
        raise HTTPException(status_code=404, detail="单元不存在")
    if payload.unit_id != unit_id:
        raise HTTPException(status_code=400, detail="unit_id 与路径不一致")
    row = (
        db.query(KnowledgeTranslation)
        .filter(KnowledgeTranslation.unit_id == unit_id, KnowledgeTranslation.lang == payload.lang)
        .first()
    )
    if row is None:
        row = KnowledgeTranslation(unit_id=unit_id, lang=payload.lang, content=payload.content,
                                   review_status=payload.review_status)
        db.add(row)
    else:
        row.content = payload.content
        row.review_status = payload.review_status
    db.commit()
    db.refresh(row)
    return ApiResponse(data=KnowledgeTranslationOut(
        id=row.id, unit_id=row.unit_id, lang=row.lang, content=row.content, review_status=row.review_status,
    ))


# ── 实体图谱 ─────────────────────────────────────────────────────


@router.get("/entities", response_model=ApiResponse[list[KnowledgeEntityOut]])
def list_entities(db: DbDep, _: ContentDep):
    rows = db.query(KnowledgeEntity).order_by(KnowledgeEntity.type, KnowledgeEntity.name).all()
    return ApiResponse(data=[KnowledgeEntityOut(id=r.id, name=r.name, type=r.type, note=r.note) for r in rows])


@router.post("/entities", response_model=ApiResponse[KnowledgeEntityOut])
def create_entity(payload: KnowledgeEntityIn, db: DbDep, _: ContentDep):
    if db.query(KnowledgeEntity).filter(KnowledgeEntity.name == payload.name).first():
        raise HTTPException(status_code=409, detail="实体已存在")
    row = KnowledgeEntity(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiResponse(data=KnowledgeEntityOut(id=row.id, name=row.name, type=row.type, note=row.note))


@router.delete("/entities/{entity_id}", response_model=ApiResponse[dict])
def delete_entity(entity_id: int, db: DbDep, _: ContentDep):
    row = db.get(KnowledgeEntity, entity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="实体不存在")
    db.query(EntityRelation).filter(
        (EntityRelation.src_id == entity_id) | (EntityRelation.dst_id == entity_id)
    ).delete(synchronize_session=False)
    db.query(UnitEntityLink).filter(UnitEntityLink.entity_id == entity_id).delete()
    db.delete(row)
    db.commit()
    return ApiResponse(message="实体及其关系已删除", data={"id": entity_id})


@router.get("/relations", response_model=ApiResponse[list[EntityRelationOut]])
def list_relations(db: DbDep, _: ContentDep):
    src = db.query(KnowledgeEntity).all()
    names = {e.id: e.name for e in src}
    rows = db.query(EntityRelation).order_by(EntityRelation.id).all()
    return ApiResponse(data=[EntityRelationOut(
        id=r.id, src_id=r.src_id, src_name=names.get(r.src_id, ""),
        dst_id=r.dst_id, dst_name=names.get(r.dst_id, ""),
        rel=r.rel, note=r.note,
    ) for r in rows])


@router.post("/relations", response_model=ApiResponse[EntityRelationOut])
def create_relation(payload: EntityRelationIn, db: DbDep, _: ContentDep):
    for eid in (payload.src_id, payload.dst_id):
        if db.get(KnowledgeEntity, eid) is None:
            raise HTTPException(status_code=404, detail=f"实体 {eid} 不存在")
    row = EntityRelation(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    names = {e.id: e.name for e in db.query(KnowledgeEntity).all()}
    return ApiResponse(data=EntityRelationOut(
        id=row.id, src_id=row.src_id, src_name=names.get(row.src_id, ""),
        dst_id=row.dst_id, dst_name=names.get(row.dst_id, ""),
        rel=row.rel, note=row.note,
    ))


@router.put("/units/{unit_id}/entity-links", response_model=ApiResponse[dict])
def set_unit_links(unit_id: int, payload: UnitEntityLinkIn, db: DbDep, _: ContentDep):
    """全量替换单元的实体关联（供问答沿实体关系扩展召回）。"""
    if db.get(KnowledgeUnit, unit_id) is None:
        raise HTTPException(status_code=404, detail="单元不存在")
    db.query(UnitEntityLink).filter(UnitEntityLink.unit_id == unit_id).delete()
    for eid in set(payload.entity_ids):
        if db.get(KnowledgeEntity, eid) is not None:
            db.add(UnitEntityLink(unit_id=unit_id, entity_id=eid))
    db.commit()
    return ApiResponse(data={"unit_id": unit_id, "entity_ids": payload.entity_ids})


# ── 验收问集（报价单 #11 交付物）─────────────────────────────────


@router.get("/eval-questions", response_model=ApiResponse[list[EvalQuestionOut]])
def list_eval_questions(db: DbDep, _: ContentDep):
    rows = db.query(EvalQuestion).order_by(EvalQuestion.id).all()
    return ApiResponse(data=[EvalQuestionOut(id=r.id, question=r.question, expect_unit_id=r.expect_unit_id)
                             for r in rows])


@router.post("/eval-questions", response_model=ApiResponse[EvalQuestionOut])
def add_eval_question(payload: EvalQuestionIn, db: DbDep, _: ContentDep):
    if db.get(KnowledgeUnit, payload.expect_unit_id) is None:
        raise HTTPException(status_code=404, detail="期望命中的单元不存在")
    row = EvalQuestion(question=payload.question, expect_unit_id=payload.expect_unit_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiResponse(data=EvalQuestionOut(id=row.id, question=row.question, expect_unit_id=row.expect_unit_id))


@router.delete("/eval-questions/{question_id}", response_model=ApiResponse[dict])
def delete_eval_question(question_id: int, db: DbDep, _: ContentDep):
    row = db.get(EvalQuestion, question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="问集条目不存在")
    db.delete(row)
    db.commit()
    return ApiResponse(message="已删除", data={"id": question_id})


@router.get("/eval-report", response_model=ApiResponse[dict])
async def eval_report(db: DbDep, _: ContentDep, top_k: int = Query(5, ge=1, le=20)):
    """验收报告：跑全部问集，报告 top-k 命中率。"""
    rows = db.query(EvalQuestion).all()
    if not rows:
        return ApiResponse(data={"total": 0, "hit": 0, "hit_rate": 0.0, "misses": []})
    hit = 0
    misses = []
    for row in rows:
        results = await retrieval_service.retrieve(db, row.question, k=top_k)
        ids = [r.unit_id for r in results]
        if row.expect_unit_id in ids:
            hit += 1
        else:
            misses.append({"question_id": row.id, "question": row.question,
                           "expect_unit_id": row.expect_unit_id, "got": ids})
    total = len(rows)
    return ApiResponse(data={"total": total, "hit": hit, "hit_rate": round(hit / total, 4), "misses": misses})


# ── 试查与向量 ───────────────────────────────────────────────────


@router.get("/search", response_model=ApiResponse[list[SearchPreviewOut]])
async def search_preview(db: DbDep, _: ContentDep, q: str = Query(..., min_length=1),
                         node_code: str = Query(""), k: int = Query(5, ge=1, le=20)):
    """知识试查：直通检索服务，供管理端验证召回质量。"""
    results = await retrieval_service.retrieve(db, q, k=k, node_code=node_code)
    return ApiResponse(data=[SearchPreviewOut(
        unit_id=r.unit_id, title=r.title, content=r.content,
        node_code=r.node_code, node_name=r.node_name, score=round(r.score, 6),
    ) for r in results])


@router.post("/embed", response_model=ApiResponse[EmbedResultOut])
async def embed_pending(db: DbDep, _: ContentDep):
    """为缺失/失效向量的单元批量生成豆包 embedding（未配置 Key 时跳过）。"""
    from app.services.doubao.ark_client import ark_client

    if not ark_client.is_configured():
        raise HTTPException(status_code=503, detail="方舟 API Key 未配置，无法生成向量")
    pending = (
        db.query(KnowledgeUnit)
        .outerjoin(KnowledgeVector, KnowledgeUnit.id == KnowledgeVector.unit_id)
        .filter(KnowledgeUnit.is_active.is_(True), KnowledgeVector.unit_id.is_(None))
        .all()
    )
    embedded = 0
    for start in range(0, len(pending), BATCH_EMBED_SIZE):
        batch = pending[start: start + BATCH_EMBED_SIZE]
        texts = [f"{u.title} {u.keywords} {u.content_zh}" for u in batch]
        try:
            vectors = await ark_client.embed(texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedding 批次失败：%s", exc)
            break
        for unit, vec in zip(batch, vectors):
            db.query(KnowledgeVector).filter(KnowledgeVector.unit_id == unit.id).delete()
            db.add(KnowledgeVector(
                unit_id=unit.id, dim=len(vec), vec=struct.pack(f"<{len(vec)}f", *vec),
            ))
            embedded += 1
        db.commit()
    retrieval_service.invalidate()
    return ApiResponse(data=EmbedResultOut(embedded=embedded, skipped=len(pending) - embedded))
