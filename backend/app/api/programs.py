"""节目路由：后台管理 + 前端公开查询。"""
from fastapi import APIRouter, Query

from app.api.deps import AdminDep, DbDep
from app.core.languages import is_supported
from app.schemas import ApiResponse, PageResult, ProgramCreate, ProgramOut, ProgramUpdate
from app.services import program_service

router = APIRouter(prefix="/api/programs", tags=["节目"])


# —— 公开接口（前端用户无需登录）——
@router.get("/public", response_model=ApiResponse[PageResult])
def list_public_programs(
    db: DbDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    lang: str = Query("", description="界面语言码；按 请求语言→en→zh 回退解析 intro 字段"),
):
    """前端展示：仅返回已上架节目；附按语言回退的「一句话简介」intro。"""
    total, items = program_service.list_programs(db, page, page_size, only_online=True)
    # lang 白名单校验：脏参数按无语言处理（走 en→zh 回退）。
    # 注意语言表中文登记为 zh-CN，须先归一化 zh* → zh 再查表（同 intro_service）
    lang = (lang or "").strip()
    if lang.startswith("zh"):
        lang = "zh"
    if lang and lang != "zh" and not is_supported(lang):
        lang = ""
    out = []
    for p in items:
        data = ProgramOut.model_validate(p).model_dump()
        data["intro"] = _resolve_intro(p, lang)
        out.append(data)
    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=out))


def _resolve_intro(p, lang: str) -> str:
    """简介回退链：请求语言(zh) → en → zh → 空。"""
    if lang.startswith("zh") and (p.intro_zh or "").strip():
        return p.intro_zh.strip()
    if (p.intro_en or "").strip():
        return p.intro_en.strip()
    return (p.intro_zh or "").strip()


# —— 后台管理接口（需登录）——
@router.get("", response_model=ApiResponse[PageResult[ProgramOut]])
def list_programs(
    db: DbDep,
    _: AdminDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, items = program_service.list_programs(db, page, page_size)
    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.post("", response_model=ApiResponse[ProgramOut])
def create_program(payload: ProgramCreate, db: DbDep, _: AdminDep):
    program = program_service.create_program(db, payload)
    return ApiResponse(message="新增成功", data=program)


@router.put("/{program_id}", response_model=ApiResponse[ProgramOut])
def update_program(program_id: int, payload: ProgramUpdate, db: DbDep, _: AdminDep):
    program = program_service.update_program(db, program_id, payload)
    return ApiResponse(message="更新成功", data=program)


@router.delete("/{program_id}", response_model=ApiResponse)
def delete_program(program_id: int, db: DbDep, _: AdminDep):
    program_service.delete_program(db, program_id)
    return ApiResponse(message="删除成功")