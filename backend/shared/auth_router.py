# backend/shared/auth_router.py
from fastapi import APIRouter, HTTPException, Depends
from .event_schemas import LoginRequest, TokenResponse
from .auth import authenticate_user, create_token, get_current_user

auth_router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

@auth_router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Đăng nhập hệ thống phân tán, nhận JWT Bearer Token theo Role"""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác")
    
    token = create_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@auth_router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Lấy thông tin người dùng đang đăng nhập"""
    return user
