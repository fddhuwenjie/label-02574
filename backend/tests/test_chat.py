"""聊天模块单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.chat import ConnectionManager


class TestConnectionManager:
    """连接管理器测试"""
    
    def setup_method(self):
        """每个测试前创建新的管理器"""
        self.manager = ConnectionManager()
    
    def test_initial_state(self):
        """测试初始状态"""
        assert len(self.manager.active_connections) == 0
        assert self.manager.get_online_users() == []
    
    @pytest.mark.asyncio
    async def test_connect(self):
        """测试用户连接"""
        mock_ws = AsyncMock()
        await self.manager.connect(mock_ws, "user1")
        
        assert "user1" in self.manager.active_connections
        mock_ws.accept.assert_called_once()
    
    def test_disconnect(self):
        """测试用户断开"""
        self.manager.active_connections["user1"] = MagicMock()
        self.manager.disconnect("user1")
        
        assert "user1" not in self.manager.active_connections
    
    def test_disconnect_nonexistent(self):
        """测试断开不存在的用户"""
        # 不应抛出异常
        self.manager.disconnect("nonexistent")
    
    def test_get_online_users(self):
        """测试获取在线用户列表"""
        self.manager.active_connections["user1"] = MagicMock()
        self.manager.active_connections["user2"] = MagicMock()
        
        users = self.manager.get_online_users()
        assert set(users) == {"user1", "user2"}
    
    @pytest.mark.asyncio
    async def test_broadcast(self):
        """测试广播消息"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        self.manager.active_connections["user1"] = mock_ws1
        self.manager.active_connections["user2"] = mock_ws2
        
        message = {"type": "test", "content": "hello"}
        await self.manager.broadcast(message)
        
        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        """测试广播时移除失败的连接"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send_json.side_effect = Exception("Connection closed")
        
        self.manager.active_connections["user1"] = mock_ws1
        self.manager.active_connections["user2"] = mock_ws2
        
        await self.manager.broadcast({"type": "test"})
        
        assert "user1" in self.manager.active_connections
        assert "user2" not in self.manager.active_connections
    
    @pytest.mark.asyncio
    async def test_broadcast_system(self):
        """测试广播系统消息"""
        mock_ws = AsyncMock()
        self.manager.active_connections["user1"] = mock_ws
        
        await self.manager.broadcast_system("System message")
        
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "system"
        assert call_args["content"] == "System message"
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """测试广播用户消息"""
        mock_ws = AsyncMock()
        self.manager.active_connections["user1"] = mock_ws
        
        await self.manager.broadcast_message("sender", "Hello!", "msg-123")
        
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "message"
        assert call_args["username"] == "sender"
        assert call_args["content"] == "Hello!"
        assert call_args["message_id"] == "msg-123"


    @pytest.mark.asyncio
    async def test_send_private_message(self):
        """测试发送私聊消息"""
        mock_ws_sender = AsyncMock()
        mock_ws_recipient = AsyncMock()
        self.manager.active_connections["sender"] = mock_ws_sender
        self.manager.active_connections["recipient"] = mock_ws_recipient
        
        result = await self.manager.send_private_message(
            "sender", "recipient", "Private hello!", "msg-456"
        )
        
        assert result is True
        # 接收者应该收到消息
        recipient_call = mock_ws_recipient.send_json.call_args[0][0]
        assert recipient_call["type"] == "private"
        assert recipient_call["username"] == "sender"
        assert recipient_call["recipient"] == "recipient"
        assert recipient_call["content"] == "Private hello!"
    
    @pytest.mark.asyncio
    async def test_send_private_message_offline_recipient(self):
        """测试发送私聊给离线用户"""
        mock_ws_sender = AsyncMock()
        self.manager.active_connections["sender"] = mock_ws_sender
        
        result = await self.manager.send_private_message(
            "sender", "offline_user", "Hello!", "msg-789"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_broadcast_revoke(self):
        """测试广播撤回通知"""
        mock_ws = AsyncMock()
        self.manager.active_connections["user1"] = mock_ws
        
        await self.manager.broadcast_revoke("msg-123", "sender")
        
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "revoke"
        assert call_args["message_id"] == "msg-123"
        assert call_args["username"] == "sender"
    
    def test_is_online(self):
        """测试检查用户是否在线"""
        self.manager.active_connections["user1"] = MagicMock()
        
        assert self.manager.is_online("user1") is True
        assert self.manager.is_online("user2") is False


class TestMessageHelpers:
    """消息辅助函数测试"""
    
    def test_generate_message_id(self):
        """测试生成消息ID"""
        from app.chat import generate_message_id
        
        id1 = generate_message_id()
        id2 = generate_message_id()
        
        assert isinstance(id1, str)
        assert len(id1) == 36  # UUID 格式
        assert id1 != id2
    
    def test_can_revoke_message_within_limit(self):
        """测试2分钟内可以撤回"""
        from app.chat import can_revoke_message
        from datetime import datetime, timedelta
        
        recent_time = datetime.utcnow() - timedelta(seconds=30)
        assert can_revoke_message(recent_time) is True
    
    def test_can_revoke_message_expired(self):
        """测试超过2分钟不能撤回"""
        from app.chat import can_revoke_message
        from datetime import datetime, timedelta
        
        old_time = datetime.utcnow() - timedelta(minutes=3)
        assert can_revoke_message(old_time) is False
