"""认证相关模式。"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str = ""
    role: str = Field("super", description="super / ops / content，前端按角色装配界面")


class AdminUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool

    model_config = {"from_attributes": True}