from fastapi import WebSocket
from typing import Dict, Optional
from datetime import datetime, timedelta
import json
import uuid

# 消息撤回时间限制（分钟）
REVOKE_TIME_LIMIT = 2

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket
        await self.broadcast_system(f"📢 {username} 加入了聊天室")
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
    
    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """广播消息给所有在线用户"""
        disconnected = []
        for username, connection in self.active_connections.items():
            if exclude and username == exclude:
                continue
            try:
                await connection.send_json(message)
            except:
                disconnected.append(username)
        for username in disconnected:
            self.disconnect(username)
    
    async def send_personal(self, username: str, message: dict) -> bool:
        """发送私人消息给指定用户"""
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_json(message)
                return True
            except:
                self.disconnect(username)
        return False
    
    async def broadcast_system(self, content: str):
        """广播系统消息"""
        await self.broadcast({
            "type": "system",
            "content": content,
            "time": datetime.utcnow().strftime("%H:%M:%S")
        })
    
    async def broadcast_message(self, username: str, content: str, message_id: str, is_encrypted: bool = False):
        """广播用户消息"""
        await self.broadcast({
            "type": "message",
            "message_id": message_id,
            "username": username,
            "content": content,
            "is_encrypted": is_encrypted,
            "time": datetime.utcnow().strftime("%H:%M:%S")
        })
    
    async def send_private_message(self, sender: str, recipient: str, content: str, 
                                    message_id: str, is_encrypted: bool = False) -> bool:
        """发送私聊消息"""
        message = {
            "type": "private",
            "message_id": message_id,
            "username": sender,
            "recipient": recipient,
            "content": content,
            "is_encrypted": is_encrypted,
            "time": datetime.utcnow().strftime("%H:%M:%S")
        }
        # 发送给接收者
        sent_to_recipient = await self.send_personal(recipient, message)
        # 发送给发送者自己（确认）
        await self.send_personal(sender, message)
        return sent_to_recipient
    
    async def broadcast_revoke(self, message_id: str, username: str):
        """广播消息撤回通知"""
        await self.broadcast({
            "type": "revoke",
            "message_id": message_id,
            "username": username,
            "content": f"{username} 撤回了一条消息",
            "time": datetime.utcnow().strftime("%H:%M:%S")
        })
    
    async def notify_revoke_private(self, message_id: str, sender: str, recipient: str):
        """通知私聊消息撤回"""
        message = {
            "type": "revoke",
            "message_id": message_id,
            "username": sender,
            "content": f"{sender} 撤回了一条私聊消息",
            "time": datetime.utcnow().strftime("%H:%M:%S")
        }
        await self.send_personal(sender, message)
        await self.send_personal(recipient, message)
    
    def get_online_users(self) -> list:
        return list(self.active_connections.keys())
    
    def is_online(self, username: str) -> bool:
        return username in self.active_connections


def generate_message_id() -> str:
    """生成唯一消息ID"""
    return str(uuid.uuid4())


def can_revoke_message(created_at: datetime) -> bool:
    """检查消息是否可以撤回（2分钟内）"""
    return datetime.utcnow() - created_at < timedelta(minutes=REVOKE_TIME_LIMIT)


manager = ConnectionManager()
