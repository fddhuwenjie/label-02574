"""Pydantic 请求/响应模型"""
from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    password: str
    public_key: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    message: str


class RevokeRequest(BaseModel):
    message_id: str


class KeyPairResponse(BaseModel):
    public_key: str
    private_key: str
