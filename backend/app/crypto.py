"""
消息加密模块
支持两种加密方式：
1. 服务端加密（AES-256-GCM）- 消息在服务端加密存储
2. 端到端加密（RSA + AES）- 消息仅客户端可解密
"""
import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# 服务端加密密钥（从环境变量获取或生成）
_SERVER_KEY = os.getenv("ENCRYPTION_KEY")
if _SERVER_KEY:
    SERVER_KEY = base64.b64decode(_SERVER_KEY)
else:
    SERVER_KEY = secrets.token_bytes(32)  # 256-bit key


class ServerEncryption:
    """服务端加密（AES-256-GCM）"""
    
    @staticmethod
    def encrypt(plaintext: str) -> str:
        """加密消息，返回 base64 编码的密文"""
        aesgcm = AESGCM(SERVER_KEY)
        nonce = secrets.token_bytes(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        # 格式: nonce + ciphertext
        return base64.b64encode(nonce + ciphertext).decode('utf-8')
    
    @staticmethod
    def decrypt(encrypted: str) -> str:
        """解密消息"""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(SERVER_KEY)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')


class E2EEncryption:
    """端到端加密辅助类"""
    
    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """生成 RSA 密钥对，返回 (公钥, 私钥) PEM 格式"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return public_pem, private_pem
    
    @staticmethod
    def encrypt_with_public_key(public_key_pem: str, plaintext: str) -> str:
        """使用公钥加密消息"""
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        ciphertext = public_key.encrypt(
            plaintext.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')
    
    @staticmethod
    def decrypt_with_private_key(private_key_pem: str, encrypted: str) -> str:
        """使用私钥解密消息"""
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        ciphertext = base64.b64decode(encrypted)
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode('utf-8')


# 便捷函数
def encrypt_message(content: str, use_server_encryption: bool = True) -> str:
    """加密消息"""
    if use_server_encryption:
        return ServerEncryption.encrypt(content)
    return content


def decrypt_message(encrypted: str, use_server_encryption: bool = True) -> str:
    """解密消息"""
    if use_server_encryption:
        return ServerEncryption.decrypt(encrypted)
    return encrypted
