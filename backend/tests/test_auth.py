"""认证模块单元测试"""
import pytest
from datetime import datetime, timedelta
from app.auth import (
    hash_password, verify_password, create_token, verify_token,
    revoke_token, active_tokens
)


class TestPasswordHashing:
    """密码哈希测试"""
    
    def test_hash_password_returns_string(self):
        """测试哈希返回字符串"""
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """测试每次哈希结果不同（因为salt）"""
        hash1 = hash_password("same_password")
        hash2 = hash_password("same_password")
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "secure_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False
    
    def test_verify_password_empty(self):
        """测试空密码"""
        hashed = hash_password("password")
        assert verify_password("", hashed) is False


class TestTokenManagement:
    """Token管理测试"""
    
    def setup_method(self):
        """每个测试前清空token存储"""
        active_tokens.clear()
    
    def test_create_token_returns_string(self):
        """测试创建token返回字符串"""
        token = create_token("testuser")
        assert isinstance(token, str)
        assert len(token) > 20
    
    def test_create_token_unique(self):
        """测试每次创建的token唯一"""
        token1 = create_token("user1")
        token2 = create_token("user1")
        assert token1 != token2
    
    def test_verify_token_valid(self):
        """测试验证有效token"""
        token = create_token("testuser")
        username = verify_token(token)
        assert username == "testuser"
    
    def test_verify_token_invalid(self):
        """测试验证无效token"""
        username = verify_token("invalid_token_12345")
        assert username is None
    
    def test_verify_token_expired(self):
        """测试验证过期token"""
        token = create_token("testuser")
        # 手动设置过期时间为过去
        active_tokens[token]["expires"] = datetime.utcnow() - timedelta(hours=1)
        username = verify_token(token)
        assert username is None
    
    def test_revoke_token(self):
        """测试撤销token"""
        token = create_token("testuser")
        assert verify_token(token) == "testuser"
        revoke_token(token)
        assert verify_token(token) is None
    
    def test_revoke_nonexistent_token(self):
        """测试撤销不存在的token"""
        result = revoke_token("nonexistent_token")
        assert result is False
