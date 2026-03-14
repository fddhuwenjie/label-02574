"""消息查询、撤回相关路由"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Message
from ..auth import verify_token, get_user_role
from ..chat import manager, can_revoke_message
from ..crypto import decrypt_message, E2EEncryption
from ..schemas import RevokeRequest, KeyPairResponse

router = APIRouter()


@router.get("/users/online")
def get_online_users():
    """获取在线用户列表"""
    users = manager.get_online_users()
    return {"users": users, "count": len(users)}


@router.get("/users/{username}/public-key")
def get_user_public_key(username: str, db: Session = Depends(get_db)):
    """获取用户公钥（用于端到端加密）"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.public_key:
        raise HTTPException(status_code=404, detail="用户未设置公钥")
    return {"username": username, "public_key": user.public_key}


@router.post("/crypto/generate-keypair", response_model=KeyPairResponse)
def generate_keypair():
    """生成端到端加密密钥对"""
    public_key, private_key = E2EEncryption.generate_keypair()
    return KeyPairResponse(public_key=public_key, private_key=private_key)


@router.get("/messages")
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


@router.get("/messages/private/{username}")
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


@router.post("/messages/revoke")
def revoke_message(
    req: RevokeRequest,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """撤回消息（管理员可撤回任意消息，普通用户限2分钟内自己的消息）"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")

    message = db.query(Message).filter(Message.message_id == req.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    if message.is_revoked:
        raise HTTPException(status_code=400, detail="消息已撤回")

    is_admin = get_user_role(current_user, db) == "admin"

    if not is_admin:
        if message.username != current_user:
            raise HTTPException(status_code=403, detail="只能撤回自己的消息")
        if not can_revoke_message(message.created_at):
            raise HTTPException(status_code=400, detail="超过撤回时间限制（2分钟）")

    message.is_revoked = True
    message.revoked_at = datetime.utcnow()
    db.commit()

    return {"message": "撤回成功", "message_id": req.message_id}
