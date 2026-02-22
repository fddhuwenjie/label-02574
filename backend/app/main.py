import os
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.security import HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .database import engine, Base, get_db
from .models import User, Message
from .auth import (
    authenticate_user, hash_password, verify_password, 
    create_token, verify_token, init_test_users, security
)
from .chat import manager, generate_message_id, can_revoke_message
from .tunnel import tunnel_manager
from .crypto import encrypt_message, decrypt_message, E2EEncryption

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    init_test_users(db)
    logger.info("数据库初始化完成")
    
    tunnel_type = tunnel_manager.start_tunnel()
    if tunnel_type:
        logger.info(f"穿透服务已启动: {tunnel_type}")
    
    yield
    
    tunnel_manager.stop_tunnel()
    logger.info("应用已关闭")


app = FastAPI(
    title="极简聊天室",
    description="支持多人在线聊天的极简工具，包含私聊、消息撤回、加密传输功能",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 数据模型 ==========
class RegisterRequest(BaseModel):
    username: str
    password: str
    public_key: Optional[str] = None  # 可选的端到端加密公钥


class LoginResponse(BaseModel):
    token: str
    username: str
    message: str


class RevokeRequest(BaseModel):
    message_id: str


class KeyPairResponse(BaseModel):
    public_key: str
    private_key: str


# ========== API接口 ==========
@app.get("/")
def root():
    return {
        "service": "极简聊天室",
        "version": "2.0.0",
        "tunnel_url": tunnel_manager.get_public_url(),
        "features": ["群聊", "私聊", "消息撤回", "加密传输"],
        "endpoints": {
            "注册": "POST /register",
            "登录": "POST /login",
            "聊天": "WebSocket /ws/chat?token=xxx",
            "在线用户": "GET /users/online",
            "历史消息": "GET /messages",
            "私聊记录": "GET /messages/private/{username}",
            "撤回消息": "POST /messages/revoke"
        }
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/tunnel")
def get_tunnel_info():
    return {
        "type": tunnel_manager.tunnel_type,
        "public_url": tunnel_manager.get_public_url(),
        "local_port": tunnel_manager.local_port
    }


@app.post("/register")
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


@app.post("/login", response_model=LoginResponse)
def login(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """用户登录（HTTP Basic认证）"""
    user = authenticate_user(credentials, db)
    token = create_token(user.username)
    return LoginResponse(token=token, username=user.username, message="登录成功")


@app.get("/users/online")
def get_online_users():
    """获取在线用户列表"""
    users = manager.get_online_users()
    return {"users": users, "count": len(users)}


@app.get("/users/{username}/public-key")
def get_user_public_key(username: str, db: Session = Depends(get_db)):
    """获取用户公钥（用于端到端加密）"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.public_key:
        raise HTTPException(status_code=404, detail="用户未设置公钥")
    return {"username": username, "public_key": user.public_key}


@app.post("/crypto/generate-keypair", response_model=KeyPairResponse)
def generate_keypair():
    """生成端到端加密密钥对"""
    public_key, private_key = E2EEncryption.generate_keypair()
    return KeyPairResponse(public_key=public_key, private_key=private_key)


@app.get("/messages")
def get_messages(
    limit: int = 50, 
    decrypt: bool = False,
    db: Session = Depends(get_db)
):
    """获取群聊历史消息"""
    messages = db.query(Message).filter(
        Message.is_private == False,
        Message.is_revoked == False
    ).order_by(Message.created_at.desc()).limit(limit).all()
    
    result = []
    for m in reversed(messages):
        content = m.content
        if decrypt and m.is_encrypted:
            try:
                content = decrypt_message(m.content)
            except:
                content = "[加密消息]"
        result.append({
            "message_id": m.message_id,
            "username": m.username,
            "content": content,
            "is_encrypted": m.is_encrypted,
            "time": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return result


@app.get("/messages/private/{username}")
def get_private_messages(
    username: str,
    token: str = Query(...),
    limit: int = 50,
    decrypt: bool = False,
    db: Session = Depends(get_db)
):
    """获取与指定用户的私聊记录"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    
    messages = db.query(Message).filter(
        Message.is_private == True,
        Message.is_revoked == False,
        (
            ((Message.username == current_user) & (Message.recipient == username)) |
            ((Message.username == username) & (Message.recipient == current_user))
        )
    ).order_by(Message.created_at.desc()).limit(limit).all()
    
    result = []
    for m in reversed(messages):
        content = m.content
        if decrypt and m.is_encrypted:
            try:
                content = decrypt_message(m.content)
            except:
                content = "[加密消息]"
        result.append({
            "message_id": m.message_id,
            "username": m.username,
            "recipient": m.recipient,
            "content": content,
            "is_encrypted": m.is_encrypted,
            "time": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return result


@app.post("/messages/revoke")
def revoke_message(
    req: RevokeRequest,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """撤回消息（2分钟内）"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    
    message = db.query(Message).filter(Message.message_id == req.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    if message.username != current_user:
        raise HTTPException(status_code=403, detail="只能撤回自己的消息")
    if message.is_revoked:
        raise HTTPException(status_code=400, detail="消息已撤回")
    if not can_revoke_message(message.created_at):
        raise HTTPException(status_code=400, detail="超过撤回时间限制（2分钟）")
    
    message.is_revoked = True
    message.revoked_at = datetime.utcnow()
    db.commit()
    
    return {"message": "撤回成功", "message_id": req.message_id}


# ========== WebSocket聊天 ==========
@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket聊天接口
    
    消息格式：
    - 群聊: {"content": "消息内容"}
    - 私聊: {"type": "private", "to": "用户名", "content": "消息内容"}
    - 撤回: {"type": "revoke", "message_id": "消息ID"}
    - 加密: {"content": "消息内容", "encrypted": true}
    """
    username = verify_token(token)
    if not username:
        await websocket.close(code=4001, reason="无效的token")
        return
    
    await manager.connect(websocket, username)
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
            except RuntimeError as e:
                logger.warning(f"WebSocket接收异常 [{username}]: {e}")
                break
            
            if not data.strip():
                continue
            
            try:
                msg_data = json.loads(data)
            except json.JSONDecodeError:
                # 兼容纯文本消息
                msg_data = {"content": data}
            
            msg_type = msg_data.get("type", "message")
            
            try:
                if msg_type == "revoke":
                    # 处理撤回请求
                    await handle_revoke(username, msg_data, db, websocket)
                elif msg_type == "private":
                    # 处理私聊消息
                    await handle_private_message(username, msg_data, db, websocket)
                else:
                    # 处理群聊消息
                    await handle_broadcast_message(username, msg_data, db, websocket)
            except Exception as e:
                logger.error(f"消息处理失败 [{username}]: {e}")
                db.rollback()
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"消息处理失败: {str(e)}"
                    })
                except:
                    break
                        
    except WebSocketDisconnect:
        logger.info(f"用户断开连接: {username}")
    except Exception as e:
        logger.error(f"WebSocket异常 [{username}]: {e}")
    finally:
        manager.disconnect(username)
        try:
            await manager.broadcast_system(f"📢 {username} 离开了聊天室")
        except Exception as e:
            logger.warning(f"广播离开消息失败: {e}")


async def handle_broadcast_message(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理群聊消息"""
    content = msg_data.get("content", "").strip()
    if not content:
        return
    
    use_encryption = msg_data.get("encrypted", False)
    message_id = generate_message_id()
    
    # 存储消息
    stored_content = encrypt_message(content) if use_encryption else content
    msg = Message(
        message_id=message_id,
        username=username, 
        content=stored_content,
        is_encrypted=use_encryption
    )
    db.add(msg)
    db.commit()
    
    # 广播消息（发送原文，客户端可选择加密显示）
    await manager.broadcast_message(username, content, message_id, use_encryption)


async def handle_private_message(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理私聊消息"""
    recipient = msg_data.get("to", "").strip()
    content = msg_data.get("content", "").strip()
    
    if not recipient or not content:
        await websocket.send_json({
            "type": "error",
            "message": "私聊消息需要指定接收者和内容"
        })
        return
    
    # 检查接收者是否存在
    if not db.query(User).filter(User.username == recipient).first():
        await websocket.send_json({
            "type": "error",
            "message": f"用户 {recipient} 不存在"
        })
        return
    
    use_encryption = msg_data.get("encrypted", False)
    message_id = generate_message_id()
    
    # 存储消息
    stored_content = encrypt_message(content) if use_encryption else content
    msg = Message(
        message_id=message_id,
        username=username,
        content=stored_content,
        recipient=recipient,
        is_private=True,
        is_encrypted=use_encryption
    )
    db.add(msg)
    db.commit()
    
    # 发送私聊消息
    online = await manager.send_private_message(username, recipient, content, message_id, use_encryption)
    
    if not online:
        await websocket.send_json({
            "type": "info",
            "message": f"用户 {recipient} 当前不在线，消息已保存"
        })


async def handle_revoke(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理消息撤回"""
    message_id = msg_data.get("message_id", "").strip()
    if not message_id:
        await websocket.send_json({
            "type": "error",
            "message": "撤回需要指定消息ID"
        })
        return
    
    message = db.query(Message).filter(Message.message_id == message_id).first()
    if not message:
        await websocket.send_json({
            "type": "error",
            "message": "消息不存在"
        })
        return
    
    if message.username != username:
        await websocket.send_json({
            "type": "error",
            "message": "只能撤回自己的消息"
        })
        return
    
    if message.is_revoked:
        await websocket.send_json({
            "type": "error",
            "message": "消息已撤回"
        })
        return
    
    if not can_revoke_message(message.created_at):
        await websocket.send_json({
            "type": "error",
            "message": "超过撤回时间限制（2分钟）"
        })
        return
    
    # 执行撤回
    message.is_revoked = True
    message.revoked_at = datetime.utcnow()
    db.commit()
    
    # 通知相关用户
    if message.is_private:
        await manager.notify_revoke_private(message_id, username, message.recipient)
    else:
        await manager.broadcast_revoke(message_id, username)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
