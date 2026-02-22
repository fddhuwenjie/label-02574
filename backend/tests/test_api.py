"""API集成测试"""
import pytest
from base64 import b64encode
from app.auth import create_token, active_tokens, hash_password
from app.models import User, Message


class TestRootEndpoint:
    """根路径测试"""
    
    def test_root_returns_service_info(self, client):
        """测试根路径返回服务信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "极简聊天室"
        assert "endpoints" in data


class TestHealthEndpoint:
    """健康检查测试"""
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestRegisterEndpoint:
    """注册接口测试"""
    
    def test_register_success(self, client):
        """测试注册成功"""
        response = client.post("/register", json={
            "username": "newuser",
            "password": "password123"
        })
        assert response.status_code == 200
        assert response.json()["message"] == "注册成功"
    
    def test_register_duplicate_username(self, client, test_user):
        """测试重复用户名"""
        response = client.post("/register", json={
            "username": test_user.username,
            "password": "password123"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]
    
    def test_register_missing_fields(self, client):
        """测试缺少字段"""
        response = client.post("/register", json={"username": "user"})
        assert response.status_code == 422


class TestLoginEndpoint:
    """登录接口测试"""
    
    def test_login_success(self, client, test_user):
        """测试登录成功"""
        credentials = b64encode(b"testuser:testpass123").decode()
        response = client.post(
            "/login",
            headers={"Authorization": f"Basic {credentials}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["username"] == "testuser"
    
    def test_login_wrong_password(self, client, test_user):
        """测试密码错误"""
        credentials = b64encode(b"testuser:wrongpassword").decode()
        response = client.post(
            "/login",
            headers={"Authorization": f"Basic {credentials}"}
        )
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client):
        """测试不存在的用户"""
        credentials = b64encode(b"nonexistent:password").decode()
        response = client.post(
            "/login",
            headers={"Authorization": f"Basic {credentials}"}
        )
        assert response.status_code == 401


class TestOnlineUsersEndpoint:
    """在线用户接口测试"""
    
    def test_get_online_users_empty(self, client):
        """测试获取空的在线用户列表"""
        response = client.get("/users/online")
        assert response.status_code == 200
        data = response.json()
        assert data["users"] == []
        assert data["count"] == 0


class TestMessagesEndpoint:
    """消息接口测试"""
    
    def test_get_messages_empty(self, client):
        """测试获取空消息列表"""
        response = client.get("/messages")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_messages_with_data(self, client, test_message):
        """测试获取消息列表"""
        response = client.get("/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello, World!"
    
    def test_get_messages_limit(self, client, db_session):
        """测试消息数量限制"""
        # 创建多条消息
        for i in range(10):
            msg = Message(username="user", content=f"Message {i}")
            db_session.add(msg)
        db_session.commit()
        
        response = client.get("/messages?limit=5")
        assert response.status_code == 200
        assert len(response.json()) == 5


class TestTunnelEndpoint:
    """穿透服务接口测试"""
    
    def test_get_tunnel_info(self, client):
        """测试获取穿透信息"""
        response = client.get("/tunnel")
        assert response.status_code == 200
        data = response.json()
        assert "type" in data
        assert "public_url" in data
        assert "local_port" in data
