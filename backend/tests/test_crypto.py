"""加密模块单元测试"""
import pytest
from app.crypto import (
    ServerEncryption, 
    E2EEncryption, 
    encrypt_message, 
    decrypt_message
)


class TestServerEncryption:
    """服务端加密测试"""
    
    def test_encrypt_returns_string(self):
        """测试加密返回字符串"""
        result = ServerEncryption.encrypt("Hello World")
        assert isinstance(result, str)
    
    def test_encrypt_different_each_time(self):
        """测试每次加密结果不同（因为随机nonce）"""
        text = "Same message"
        result1 = ServerEncryption.encrypt(text)
        result2 = ServerEncryption.encrypt(text)
        assert result1 != result2
    
    def test_decrypt_returns_original(self):
        """测试解密返回原文"""
        original = "Hello World 你好世界"
        encrypted = ServerEncryption.encrypt(original)
        decrypted = ServerEncryption.decrypt(encrypted)
        assert decrypted == original
    
    def test_encrypt_decrypt_empty_string(self):
        """测试空字符串加解密"""
        original = ""
        encrypted = ServerEncryption.encrypt(original)
        decrypted = ServerEncryption.decrypt(encrypted)
        assert decrypted == original
    
    def test_encrypt_decrypt_long_text(self):
        """测试长文本加解密"""
        original = "A" * 10000
        encrypted = ServerEncryption.encrypt(original)
        decrypted = ServerEncryption.decrypt(encrypted)
        assert decrypted == original
    
    def test_decrypt_invalid_data(self):
        """测试解密无效数据"""
        with pytest.raises(Exception):
            ServerEncryption.decrypt("invalid_base64_data!!!")


class TestE2EEncryption:
    """端到端加密测试"""
    
    def test_generate_keypair(self):
        """测试生成密钥对"""
        public_key, private_key = E2EEncryption.generate_keypair()
        
        assert "BEGIN PUBLIC KEY" in public_key
        assert "END PUBLIC KEY" in public_key
        assert "BEGIN PRIVATE KEY" in private_key
        assert "END PRIVATE KEY" in private_key
    
    def test_keypair_unique(self):
        """测试每次生成的密钥对不同"""
        pub1, priv1 = E2EEncryption.generate_keypair()
        pub2, priv2 = E2EEncryption.generate_keypair()
        
        assert pub1 != pub2
        assert priv1 != priv2
    
    def test_encrypt_with_public_key(self):
        """测试公钥加密"""
        public_key, _ = E2EEncryption.generate_keypair()
        encrypted = E2EEncryption.encrypt_with_public_key(public_key, "Secret")
        
        assert isinstance(encrypted, str)
        assert encrypted != "Secret"
    
    def test_decrypt_with_private_key(self):
        """测试私钥解密"""
        public_key, private_key = E2EEncryption.generate_keypair()
        original = "Secret message 秘密消息"
        
        encrypted = E2EEncryption.encrypt_with_public_key(public_key, original)
        decrypted = E2EEncryption.decrypt_with_private_key(private_key, encrypted)
        
        assert decrypted == original
    
    def test_wrong_private_key_fails(self):
        """测试错误私钥解密失败"""
        pub1, _ = E2EEncryption.generate_keypair()
        _, priv2 = E2EEncryption.generate_keypair()
        
        encrypted = E2EEncryption.encrypt_with_public_key(pub1, "Secret")
        
        with pytest.raises(Exception):
            E2EEncryption.decrypt_with_private_key(priv2, encrypted)


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_encrypt_message_with_server_encryption(self):
        """测试使用服务端加密"""
        original = "Hello"
        encrypted = encrypt_message(original, use_server_encryption=True)
        decrypted = decrypt_message(encrypted, use_server_encryption=True)
        
        assert decrypted == original
    
    def test_encrypt_message_without_encryption(self):
        """测试不加密"""
        original = "Hello"
        result = encrypt_message(original, use_server_encryption=False)
        
        assert result == original
    
    def test_decrypt_message_without_encryption(self):
        """测试不解密"""
        text = "Hello"
        result = decrypt_message(text, use_server_encryption=False)
        
        assert result == text
