"""WebSocket集成测试"""
import pytest
from fastapi.testclient import TestClient
from app.auth import create_token, active_tokens


class TestWebSocketChat:
    """WebSocket聊天测试"""
    
    def setup_method(self):
        """每个测试前清空token"""
        active_tokens.clear()
    
    def test_websocket_invalid_token(self, client):
        """测试无效token连接"""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/chat?token=invalid"):
                pass
    
    def test_websocket_missing_token(self, client):
        """测试缺少token"""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/chat"):
                pass
    
    def test_websocket_connect_with_valid_token(self, client, test_user):
        """测试有效token连接"""
        token = create_token(test_user.username)
        
        with client.websocket_connect(f"/ws/chat?token={token}") as ws:
            # 连接成功后应收到加入消息
            data = ws.receive_json()
            assert data["type"] == "system"
            assert test_user.username in data["content"]
    
    def test_websocket_send_message(self, client, test_user):
        """测试发送消息"""
        token = create_token(test_user.username)
        
        with client.websocket_connect(f"/ws/chat?token={token}") as ws:
            # 跳过加入消息
            ws.receive_json()
            
            # 发送消息
            ws.send_text("Hello, everyone!")
            
            # 接收广播的消息
            data = ws.receive_json()
            assert data["type"] == "message"
            assert data["username"] == test_user.username
            assert data["content"] == "Hello, everyone!"
    
    def test_websocket_empty_message_ignored(self, client, test_user):
        """测试空消息被忽略"""
        token = create_token(test_user.username)
        
        with client.websocket_connect(f"/ws/chat?token={token}") as ws:
            ws.receive_json()  # 跳过加入消息
            
            # 发送空消息
            ws.send_text("   ")
            
            # 发送正常消息
            ws.send_text("Real message")
            
            # 应该只收到正常消息
            data = ws.receive_json()
            assert data["content"] == "Real message"
