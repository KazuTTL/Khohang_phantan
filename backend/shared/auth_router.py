# backend/shared/auth_router.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from .event_schemas import LoginRequest, TokenResponse
from .auth import authenticate_user, authenticate_user_db, create_token, get_current_user


def create_auth_router(get_db_dep=None, account_model=None) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

    if get_db_dep is not None and account_model is not None:
        @router.post("/login", response_model=TokenResponse)
        def login(req: LoginRequest, db: Session = Depends(get_db_dep)):
            """Đăng nhập từ bảng TAI_KHOAN cục bộ của Site, trả về JWT Bearer Token theo Role"""
            user = authenticate_user_db(db, account_model, req.username, req.password)
            if not user:
                raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác")
            token = create_token(user)
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": user
            }

        @router.get("/accounts")
        def list_local_accounts(db: Session = Depends(get_db_dep)):
            """Xem danh sách tài khoản được đồng bộ tại DB cục bộ của Site (ẩn chuỗi băm nhạy cảm)"""
            rows = db.query(account_model).all()
            return [
                {
                    "account_id": r.account_id,
                    "username": r.username,
                    "full_name": r.full_name,
                    "role": r.role,
                    "branch_code": r.branch_code,
                    "is_active": r.is_active,
                    "password_hashed": str(r.password_hash).startswith("pbkdf2_sha256$")
                }
                for r in rows
            ]
    else:
        @router.post("/login", response_model=TokenResponse)
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

    @router.get("/me")
    def get_me(user: dict = Depends(get_current_user)):
        """Lấy thông tin người dùng đang đăng nhập"""
        return user

    return router


auth_router = create_auth_router()
