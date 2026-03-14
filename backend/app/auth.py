import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
import bcrypt

from .database import get_db
from .models import User

logger = logging.getLogger(__name__)
security = HTTPBasic()

# Token存储：支持Redis或内存
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None

if REDIS_URL:
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Redis连接成功，Token将持久化存储")
    except Exception as e:
        logger.warning(f"Redis连接失败，回退到内存存储: {e}")
        redis_client = None

# 内存Token存储（Redis不可用时使用）
active_tokens: dict[str, dict] = {}
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))


def hash_password(password: str) -> str:
    """使用bcrypt哈希密码"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证bcrypt密码"""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        # 兼容旧的sha256哈希（迁移期间）
        import hashlib
        return hashlib.sha256(plain.encode()).hexdigest() == hashed


def create_token(username: str) -> str:
    """创建Token，优先存储到Redis"""
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    
    if redis_client:
        try:
            redis_client.hset(f"token:{token}", mapping={
                "username": username,
                "expires": expires.isoformat()
            })
            redis_client.expire(f"token:{token}", TOKEN_EXPIRE_HOURS * 3600)
            logger.debug(f"Token已存储到Redis: {username}")
        except Exception as e:
            logger.error(f"Redis存储Token失败: {e}")
            active_tokens[token] = {"username": username, "expires": expires}
    else:
        active_tokens[token] = {"username": username, "expires": expires}
    
    return token


def verify_token(token: str) -> Optional[str]:
    """验证Token，优先从Redis读取"""
    if redis_client:
        try:
            data = redis_client.hgetall(f"token:{token}")
            if data:
                expires = datetime.fromisoformat(data["expires"])
                if expires > datetime.utcnow():
                    return data["username"]
                redis_client.delete(f"token:{token}")
        except Exception as e:
            logger.error(f"Redis验证Token失败: {e}")
    
    # 回退到内存存储
    if token in active_tokens:
        data = active_tokens[token]
        if data["expires"] > datetime.utcnow():
            return data["username"]
        del active_tokens[token]
    
    return None


def revoke_token(token: str) -> bool:
    """撤销Token"""
    if redis_client:
        try:
            redis_client.delete(f"token:{token}")
        except Exception as e:
            logger.error(f"Redis撤销Token失败: {e}")
    
    if token in active_tokens:
        del active_tokens[token]
        return True
    return False


def authenticate_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """认证用户"""
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁，请联系管理员",
        )
    return user


def init_test_users(db: Session):
    """初始化测试用户（使用bcrypt）"""
    test_users = [
        ("admin", "admin123", "admin"),
        ("user1", "password1", "user"),
        ("user2", "password2", "user"),
    ]
    for username, password, role in test_users:
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            user = User(username=username, password_hash=hash_password(password), role=role)
            db.add(user)
        elif existing.role != role:
            existing.role = role
    db.commit()


def get_user_role(username: str, db: Session) -> str:
    """获取用户角色"""
    user = db.query(User).filter(User.username == username).first()
    return user.role if user else "user"


def require_admin(username: str, db: Session):
    """校验管理员权限，非管理员抛出403"""
    user = db.query(User).filter(User.username == username).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
