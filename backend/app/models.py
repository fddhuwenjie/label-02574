from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from datetime import datetime
import uuid
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    public_key = Column(Text, nullable=True)  # 用户公钥，用于端到端加密
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    recipient = Column(String(50), nullable=True, index=True)  # 私聊接收者，NULL表示群聊
    is_private = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)  # 是否加密消息
    is_revoked = Column(Boolean, default=False)  # 是否已撤回
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
