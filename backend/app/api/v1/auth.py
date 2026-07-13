"""
认证相关 API
- POST /api/v1/auth/register   用户注册（当前为 stub，待数据库连接后启用）
"""
import re
from fastapi import APIRouter, HTTPException

from app.schemas.auth import RegisterRequest, RegisterResponse

router = APIRouter()

# 用户名规则：字母开头，3-20 位字母/数字/下划线
_USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    """
    用户注册

    当前状态：stub（DB 未启用）
    前端已通过 localStorage 实现本地注册；本端点为后续接入 PostgreSQL 预留。
    """
    # 1. 校验密码一致性
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")

    # 2. 校验用户名格式
    if not _USERNAME_PATTERN.match(req.username):
        raise HTTPException(
            status_code=400,
            detail="账号必须以字母开头，仅含字母/数字/下划线，长度 3-20 位",
        )

    # 3. 角色白名单（与前端 UserInfo.role 对齐）
    if req.role not in ("admin", "engineer"):
        raise HTTPException(status_code=400, detail="非法角色")

    # 4. DB 未启用 → 返回 503（前端已使用 localStorage 完成注册流程）
    raise HTTPException(
        status_code=503,
        detail="用户注册功能待数据库连接后启用；当前由前端 localStorage 提供演示支持",
    )


@router.post("/login", response_model=RegisterResponse)
async def login_stub():
    """登录端点预留（前端 mock 模式）"""
    raise HTTPException(
        status_code=503,
        detail="登录功能当前由前端 mock 提供，待数据库连接后启用",
    )