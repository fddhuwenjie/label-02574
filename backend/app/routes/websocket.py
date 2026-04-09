"""WebSocket 聊天路由及消息处理"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Message
from ..auth import verify_token, get_user_role
from ..chat import manager, generate_message_id, can_revoke_message
from ..crypto import encrypt_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/chat")
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

    user = db.query(User).filter(User.username == username).first()
    if user and user.is_banned:
        await websocket.close(code=4003, reason="账号已被封禁")
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
                msg_data = {"content": data}

            msg_type = msg_data.get("type", "message")

            try:
                if msg_type == "revoke":
                    await _handle_revoke(username, msg_data, db, websocket)
                elif msg_type == "private":
                    await _handle_private_message(username, msg_data, db, websocket)
                else:
                    await _handle_broadcast_message(username, msg_data, db, websocket)
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


async def _handle_broadcast_message(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理群聊消息"""
    content = msg_data.get("content", "").strip()
    if not content:
        return

    use_encryption = msg_data.get("encrypted", False)
    message_id = generate_message_id()

    stored_content = encrypt_message(content) if use_encryption else content
    msg = Message(
        message_id=message_id,
        username=username,
        content=stored_content,
        is_encrypted=use_encryption
    )
    db.add(msg)
    db.commit()

    await manager.broadcast_message(username, content, message_id, use_encryption)


async def _handle_private_message(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理私聊消息"""
    recipient = msg_data.get("to", "").strip()
    content = msg_data.get("content", "").strip()

    if not recipient or not content:
        await websocket.send_json({
            "type": "error",
            "message": "私聊消息需要指定接收者和内容"
        })
        return

    if not db.query(User).filter(User.username == recipient).first():
        await websocket.send_json({
            "type": "error",
            "message": f"用户 {recipient} 不存在"
        })
        return

    use_encryption = msg_data.get("encrypted", False)
    message_id = generate_message_id()

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

    online = await manager.send_private_message(username, recipient, content, message_id, use_encryption)

    if not online:
        await websocket.send_json({
            "type": "info",
            "message": f"用户 {recipient} 当前不在线，消息已保存"
        })


async def _handle_revoke(username: str, msg_data: dict, db: Session, websocket: WebSocket):
    """处理消息撤回（管理员可撤回任意消息）"""
    message_id = msg_data.get("message_id", "").strip()
    if not message_id:
        await websocket.send_json({
            "type": "error",
            "message": "撤回需要指定消息ID"
        })
        return

    message = db.query(Message).filter(Message.message_id == message_id).first()
    if not message:
        await websocket.send_json({"type": "error", "message": "消息不存在"})
        return

    if message.is_revoked:
        await websocket.send_json({"type": "error", "message": "消息已撤回"})
        return

    is_admin = get_user_role(username, db) == "admin"

    if not is_admin:
        if message.username != username:
            await websocket.send_json({"type": "error", "message": "只能撤回自己的消息"})
            return
        if not can_revoke_message(message.created_at):
            await websocket.send_json({"type": "error", "message": "超过撤回时间限制（2分钟）"})
            return

    message.is_revoked = True
    message.revoked_at = datetime.utcnow()
    db.commit()

    revoke_by = username if message.username == username else f"管理员{username}"

    if message.is_private:
        await manager.notify_revoke_private(message_id, message.username, message.recipient, revoke_by)
    else:
        await manager.broadcast_revoke(message_id, revoke_by)
