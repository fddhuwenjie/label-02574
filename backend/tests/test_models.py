"""数据模型单元测试"""
import pytest
from datetime import datetime
from app.models import User, Message


class TestUserModel:
    """用户模型测试"""
    
    def test_create_user(self, db_session):
        """测试创建用户"""
        user = User(username="newuser", password_hash="hashed_password")
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == "newuser"
        assert user.created_at is not None
    
    def test_user_unique_username(self, db_session):
        """测试用户名唯一约束"""
        user1 = User(username="unique", password_hash="hash1")
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(username="unique", password_hash="hash2")
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
    
    def test_user_created_at_default(self, db_session):
        """测试创建时间默认值"""
        before = datetime.utcnow()
        user = User(username="timetest", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        after = datetime.utcnow()
        
        assert before <= user.created_at <= after


class TestMessageModel:
    """消息模型测试"""
    
    def test_create_message(self, db_session):
        """测试创建消息"""
        msg = Message(username="sender", content="Hello!")
        db_session.add(msg)
        db_session.commit()
        
        assert msg.id is not None
        assert msg.username == "sender"
        assert msg.content == "Hello!"
    
    def test_message_long_content(self, db_session):
        """测试长消息内容"""
        long_content = "A" * 10000
        msg = Message(username="user", content=long_content)
        db_session.add(msg)
        db_session.commit()
        
        retrieved = db_session.query(Message).filter(Message.id == msg.id).first()
        assert retrieved.content == long_content
    
    def test_message_ordering(self, db_session):
        """测试消息排序"""
        msg1 = Message(username="user", content="First")
        msg2 = Message(username="user", content="Second")
        db_session.add_all([msg1, msg2])
        db_session.commit()
        
        messages = db_session.query(Message).order_by(Message.created_at).all()
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
