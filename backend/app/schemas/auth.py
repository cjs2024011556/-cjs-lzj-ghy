"""
认证相关 Pydantic Schema
- 注册请求 / 响应
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=64, description="账号")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    confirm_password: str = Field(..., min_length=6, max_length=64, description="确认密码")
    full_name: str = Field(..., min_length=1, max_length=128, description="姓名")
    department: str = Field(default="", max_length=128, description="部门（可选）")
    role: Literal["admin", "engineer"] = Field(default="engineer", description="角色：系统管理员/普通用户")


class RegisterResponse(BaseModel):
    """用户注册响应"""
    success: bool
    message: str
    user: Optional[dict] = None