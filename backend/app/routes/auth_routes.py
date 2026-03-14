"""注册、登录相关路由"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasicCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import authenticate_user, hash_password, create_token, security
from ..schemas import RegisterRequest, LoginResponse

router = APIRouter()


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        public_key=req.public_key
    )
    db.add(user)
    db.commit()
    return {"message": "注册成功", "username": req.username}


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """用户登录（HTTP Basic认证）"""
    user = authenticate_user(credentials, db)
    token = create_token(user.username)
    return LoginResponse(
        token=token, username=user.username,
        role=user.role, message="登录成功"
    )
