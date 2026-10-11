"""知识库 Schema：节点 / 知识单元 / 译文 / 实体关系 / 验收问集 / 试查（报价单 #10/#11）。

高内聚：知识域的数据契约统一收敛在此模块。
低耦合：仅定义纯数据结构，不依赖服务与路由实现。
"""
from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeNodeIn(BaseModel):
    """知识节点创建/修改请求。"""

    code: str = Field(..., min_length=1, max_length=32, description="节点码，如 gate/stage/wenchuang")
    name_zh: str = Field(..., min_length=1, max_length=64)
    name_en: str = Field("", max_length=64)
    description: str = Field("", max_length=255)
    sort: int = Field(0, ge=0, le=9999)
    is_active: bool = True


class KnowledgeNodeOut(BaseModel):
    """知识节点信息。"""

    id: int
    code: str
    name_zh: str
    name_en: str
    description: str
    sort: int
    is_active: bool
    unit_count: int = Field(0, description="该节点下知识单元数")


class KnowledgeUnitIn(BaseModel):
    """知识单元创建/修改请求（中文母稿）。"""

    node_id: int
    title: str = Field(..., min_length=1, max_length=128)
    content_zh: str = Field(..., min_length=1)
    keywords: str = Field("", max_length=255, description="逗号分隔的检索关键词")
    is_active: bool = True
    review_status: str = Field("draft", pattern="^(draft|checked)$")


class KnowledgeUnitOut(BaseModel):
    """知识单元信息。"""

    id: int
    node_id: int
    node_code: str = ""
    node_name: str = ""
    title: str
    content_zh: str
    keywords: str
    is_active: bool
    review_status: str
    has_vector: bool = Field(False, description="是否已生成向量")
    created_at: datetime | None = None


class KnowledgeTranslationIn(BaseModel):
    """译文写入/抽检请求。"""

    unit_id: int
    lang: str = Field(..., min_length=2, max_length=16)
    content: str = Field(..., min_length=1)
    review_status: str = Field("draft", pattern="^(draft|checked)$")


class KnowledgeTranslationOut(BaseModel):
    """译文信息。"""

    id: int
    unit_id: int
    lang: str
    content: str
    review_status: str


class KnowledgeEntityIn(BaseModel):
    """知识实体创建请求。"""

    name: str = Field(..., min_length=1, max_length=64)
    type: str = Field("other", pattern="^(person|opera|stunt|role|venue|other)$")
    note: str = Field("", max_length=255)


class KnowledgeEntityOut(BaseModel):
    """知识实体信息。"""

    id: int
    name: str
    type: str
    note: str


class EntityRelationIn(BaseModel):
    """实体关系创建请求。"""

    src_id: int
    dst_id: int
    rel: str = Field(..., min_length=1, max_length=32)
    note: str = Field("", max_length=255)


class EntityRelationOut(BaseModel):
    """实体关系信息。"""

    id: int
    src_id: int
    src_name: str = ""
    dst_id: int
    dst_name: str = ""
    rel: str
    note: str


class UnitEntityLinkIn(BaseModel):
    """知识单元关联实体请求。"""

    unit_id: int
    entity_ids: list[int] = Field(..., description="全量替换该单元的实体关联")


class EvalQuestionIn(BaseModel):
    """验收问集条目请求。"""

    question: str = Field(..., min_length=1, max_length=255)
    expect_unit_id: int


class EvalQuestionOut(BaseModel):
    """验收问集条目信息。"""

    id: int
    question: str
    expect_unit_id: int


class SearchPreviewOut(BaseModel):
    """知识试查结果（检索服务直通，供管理端验证召回质量）。"""

    unit_id: int
    title: str
    content: str
    node_code: str
    node_name: str
    score: float


class EmbedResultOut(BaseModel):
    """向量生成结果统计。"""

    embedded: int = Field(0, description="本次生成向量的单元数")
    skipped: int = Field(0, description="跳过数（已有向量或未配置 Key）")
