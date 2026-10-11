"""知识库检索服务：向量 + 关键词混合召回与 RRF 融合（报价单 #10）。

高内聚：召回策略（BM25、余弦、融合、抽检/节点加权）统一在此。
低耦合：向量由豆包 embedding（ark_client.embed）产出，存储在 KnowledgeVector BLOB；
       留 `VectorBackend` 协议扩展点——知识量超出千级时替换 sqlite-vec 实现，
       调用方（Agent / admin 试查）无感。

量级口径：基础包约 500 知识单元，向量全量常驻内存 ≈ 数 MB，纯 Python 余弦即可，
无需 numpy / 向量库扩展（低内存占用优先）。未配置 ARK Key 时自动降级 BM25-only。
"""

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field

import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeNode, KnowledgeUnit, KnowledgeVector

logger = logging.getLogger("retrieval")


class _BM25Clamped(BM25Okapi):
    """IDF 下限为正的 BM25：小语料（冷启动/验收环境）时 rank_bm25 原生
    IDF 会出现负值（词出现在超半数文档），导致命中过滤 scores>0 全军覆没。"""

    _IDF_FLOOR = 0.01

    def _calc_idf(self, nd):
        super()._calc_idf(nd)
        self.idf = {word: max(value, self._IDF_FLOOR) for word, value in self.idf.items()}

# RRF 融合常数（标准取值）
RRF_K = 60
# 抽检通过 / 扫码节点命中的分数加成系数
CHECKED_BOOST = 0.25
NODE_BOOST = 0.25
QUERY_CACHE_TTL = 60.0


@dataclass
class RetrievedUnit:
    unit_id: int
    title: str
    content: str
    node_code: str
    node_name: str
    score: float = 0.0
    sources_meta: dict = field(default_factory=dict)


class VectorBackend:
    """向量检索扩展点：默认纯 Python 余弦；未来可替换 sqlite-vec 实现（同协议）。"""

    def search(self, query_vec: list[float], vectors: dict[int, list[float]], k: int) -> list[tuple[int, float]]:
        scored = [(unit_id, _cosine(query_vec, vec)) for unit_id, vec in vectors.items()]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _decode_vec(blob: bytes, dim: int) -> list[float]:
    if not blob or dim <= 0:
        return []
    return list(struct.unpack(f"<{dim}f", blob[: dim * 4]))


class RetrievalService:
    """混合召回服务（进程内单例）：BM25 索引与向量缓存惰性构建，变更时失效。"""

    def __init__(self):
        self._vector_backend = VectorBackend()
        self._bm25: _BM25Clamped | None = None
        self._corpus: list[dict] = []
        self._vectors: dict[int, list[float]] = {}
        self._dirty = True
        self._qcache: tuple[str, float, list[float]] | None = None

    # ── 索引管理 ────────────────────────────────────────────────

    def invalidate(self) -> None:
        """单元/向量变更后调用，下次检索自动重建 BM25 与向量缓存。"""
        self._dirty = True

    def _ensure_index(self, db: Session) -> None:
        if not self._dirty:
            return
        rows = (
            db.query(KnowledgeUnit, KnowledgeNode)
            .join(KnowledgeNode, KnowledgeUnit.node_id == KnowledgeNode.id)
            .filter(KnowledgeUnit.is_active.is_(True), KnowledgeNode.is_active.is_(True))
            .all()
        )
        self._corpus = [
            {
                "unit_id": unit.id,
                "title": unit.title,
                "content": unit.content_zh,
                "keywords": unit.keywords or "",
                "node_code": node.code,
                "node_name": node.name_zh,
                "checked": unit.review_status == "checked",
            }
            for unit, node in rows
        ]
        self._rebuild_bm25()
        self._load_vectors(db)
        self._dirty = False
        logger.info("检索索引就绪：%d 单元，%d 向量", len(self._corpus), len(self._vectors))

    def _rebuild_bm25(self) -> None:
        if not self._corpus:
            self._bm25 = None
            return
        self._bm25 = _BM25Clamped([self._tokenize(item) for item in self._corpus])

    def _load_vectors(self, db: Session) -> None:
        self._vectors = {}
        for row in db.query(KnowledgeVector).all():
            vec = _decode_vec(row.vec, row.dim)
            if vec:
                self._vectors[row.unit_id] = vec

    @staticmethod
    def _tokenize(item: dict) -> list[str]:
        text = f"{item['title']} {item['keywords']} {item['content']}"
        return [t for t in jieba.lcut(text) if t.strip()]

    # ── 检索 ────────────────────────────────────────────────────

    async def retrieve(self, db: Session, query: str, k: int = 5, node_code: str = "") -> list[RetrievedUnit]:
        """混合召回入口：BM25 关键词 + 向量余弦，RRF 融合；node_code 非空时该节点单元加权。"""
        query = (query or "").strip()
        if not query:
            return []
        self._ensure_index(db)
        if not self._corpus:
            return []

        # 两路召回候选（各取 k*3）
        bm25_rank = self._bm25_recall(query, k)
        qvec = await self._query_vector(query)
        vec_rank: dict[int, int] = {}
        if qvec and self._vectors:
            vec_rank = {uid: rank for rank, (uid, _s) in enumerate(
                self._vector_backend.search(qvec, self._vectors, k * 3))}
        return self._fuse(bm25_rank, vec_rank, k, node_code)

    def _bm25_recall(self, query: str, k: int) -> dict[int, int]:
        if self._bm25 is None:
            return {}
        scores = self._bm25.get_scores(self._tokenize({"title": query, "keywords": "", "content": query}))
        ranked = sorted(range(len(self._corpus)), key=lambda i: scores[i], reverse=True)[: k * 3]
        return {self._corpus[i]["unit_id"]: rank for rank, i in enumerate(ranked) if scores[i] > 0}

    async def _query_vector(self, query: str) -> list[float]:
        """查询向量：60s 内相同查询走缓存；embedding 失败降级 BM25-only（返回空）。"""
        now = time.monotonic()
        if self._qcache and self._qcache[0] == query and now - self._qcache[1] < QUERY_CACHE_TTL:
            return self._qcache[2]
        from app.services.doubao.ark_client import ark_client

        try:
            vec = (await ark_client.embed([query]))[0]
        except Exception:  # noqa: BLE001
            logger.warning("查询 embedding 失败，降级 BM25 召回")
            return []
        self._qcache = (query, now, vec)
        return vec

    def _fuse(self, bm25_rank: dict[int, int], vec_rank: dict[int, int], k: int, node_code: str) -> list[RetrievedUnit]:
        """RRF 融合两路名次，叠加抽检/节点加成后排序截断。"""
        fused: dict[int, float] = {}
        for unit_id, rank in bm25_rank.items():
            fused[unit_id] = fused.get(unit_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        for unit_id, rank in vec_rank.items():
            fused[unit_id] = fused.get(unit_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        by_id = {item["unit_id"]: item for item in self._corpus}
        results: list[RetrievedUnit] = []
        for unit_id, score in fused.items():
            item = by_id.get(unit_id)
            if item is None:
                continue
            boost = 1.0
            if item["checked"]:
                boost += CHECKED_BOOST
            if node_code and item["node_code"] == node_code:
                boost += NODE_BOOST
            results.append(RetrievedUnit(
                unit_id=unit_id, title=item["title"], content=item["content"],
                node_code=item["node_code"], node_name=item["node_name"], score=score * boost,
            ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]


retrieval_service = RetrievalService()
