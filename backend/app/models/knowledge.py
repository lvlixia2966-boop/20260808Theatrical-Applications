"""知识库模型：节点 / 知识单元 / 多语译文 / 实体关系图谱 / 向量 / 验收问集。

高内聚：知识域（报价单 #10/#11）的持久化结构统一在此模块。
低耦合：检索逻辑在 services/retrieval_service.py，模型只存数据与状态。

量级口径：基础包 10 节点、约 500 知识单元；扩展包（#25）追加节点与单元即可。
"""
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeNode(Base):
    """知识节点：景区/卖场/服务点位（如「正门」「戏台」「文创柜台」）。"""

    __tablename__ = "knowledge_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name_zh: Mapped[str] = mapped_column(String(64), nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeUnit(Base):
    """知识单元：一条可问答的知识（中文母稿），抽检通过后方可被 Agent 引用。"""

    __tablename__ = "knowledge_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content_zh: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # draft=待抽检 / checked=已抽检（检索时加权）
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeTranslation(Base):
    """知识单元多语译文（12 语种），供 Agent 按语言输出与人工抽检。"""

    __tablename__ = "knowledge_translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_units.id"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # draft=机翻待抽检 / checked=已抽检（报价单 #8 人工抽检流程）
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")


class KnowledgeEntity(Base):
    """知识实体：人物 / 剧目 / 绝技 / 行当 / 场地等（知识图谱节点）。"""

    __tablename__ = "knowledge_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # person / opera / stunt / role / venue / other
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class EntityRelation(Base):
    """实体关系：src --rel--> dst（如「白蛇传」--人物-->「白素贞」）。"""

    __tablename__ = "entity_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_entities.id"), nullable=False, index=True)
    dst_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_entities.id"), nullable=False, index=True)
    rel: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class UnitEntityLink(Base):
    """知识单元 ↔ 实体 多对多（检索时支持沿实体关系扩展召回）。"""

    __tablename__ = "unit_entity_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_units.id"), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_entities.id"), nullable=False, index=True)


class KnowledgeVector(Base):
    """知识单元向量（豆包 embedding，float32 序列化 BLOB，纯 Python 余弦检索）。"""

    __tablename__ = "knowledge_vectors"

    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_units.id"), primary_key=True)
    dim: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vec: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, default=b"")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EvalQuestion(Base):
    """验收问集：question -> 期望命中的单元（报价单 #11 交付物，供 /eval 命中率报告）。"""

    __tablename__ = "eval_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(String(255), nullable=False)
    expect_unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_units.id"), nullable=False)
