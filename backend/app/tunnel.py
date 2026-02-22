"""
内外网穿透模块
支持多种穿透方案：
1. ngrok - 第三方服务（推荐，使用pyngrok库）
2. cloudflared - Cloudflare Tunnel
3. frp - 需要自建服务器
"""
import os
import subprocess
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TunnelManager:
    """内外网穿透管理器"""
    
    def __init__(self):
        self.tunnel_type = os.getenv("TUNNEL_TYPE", "none")
        self.local_port = int(os.getenv("LOCAL_PORT", "8000"))
        self.process = None
        self.ngrok_tunnel = None
        self.public_url: Optional[str] = None
        self._log_thread: Optional[threading.Thread] = None
        self._running = False
    
    def start_tunnel(self) -> Optional[str]:
        """启动穿透服务"""
        if self.tunnel_type == "none":
            logger.info("未配置穿透服务，仅内网访问")
            return None
        
        self._running = True
        
        handlers = {
            "ngrok": self._start_ngrok,
            "cloudflared": self._start_cloudflared,
            "frp": self._start_frp,
        }
        
        handler = handlers.get(self.tunnel_type)
        if handler:
            return handler()
        
        logger.warning(f"未知穿透类型: {self.tunnel_type}")
        return None
    
    def _start_ngrok(self) -> Optional[str]:
        """启动ngrok穿透（使用pyngrok库）"""
        ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
        if not ngrok_token:
            logger.warning("未配置NGROK_AUTH_TOKEN，ngrok无法启动")
            return None
        
        try:
            from pyngrok import ngrok, conf
            
            # 配置ngrok
            conf.get_default().auth_token = ngrok_token
            conf.get_default().log_level = "info"
            
            # 启动隧道
            self.ngrok_tunnel = ngrok.connect(self.local_port, "http")
            self.public_url = self.ngrok_tunnel.public_url
            
            logger.info(f"✅ ngrok已启动")
            logger.info(f"📡 公网地址: {self.public_url}")
            logger.info(f"🔗 本地端口: {self.local_port}")
            
            return "ngrok"
        except ImportError:
            logger.error("pyngrok未安装，请运行: pip install pyngrok")
            return None
        except Exception as e:
            logger.error(f"❌ ngrok启动失败: {e}")
            return None
    
    def _start_cloudflared(self) -> Optional[str]:
        """启动Cloudflare Tunnel"""
        try:
            self.process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{self.local_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # 启动日志监控线程
            self._log_thread = threading.Thread(
                target=self._monitor_cloudflared_output,
                daemon=True
            )
            self._log_thread.start()
            
            logger.info(f"✅ cloudflared已启动，本地端口: {self.local_port}")
            logger.info("📡 等待获取公网地址...")
            
            return "cloudflared"
        except FileNotFoundError:
            logger.error("❌ cloudflared未安装，请先安装cloudflared")
            return None
        except Exception as e:
            logger.error(f"❌ cloudflared启动失败: {e}")
            return None
    
    def _monitor_cloudflared_output(self):
        """监控cloudflared输出，提取公网URL"""
        if not self.process or not self.process.stdout:
            return
        
        try:
            for line in self.process.stdout:
                if not self._running:
                    break
                line = line.strip()
                if line:
                    # 提取公网URL
                    if "trycloudflare.com" in line or "https://" in line:
                        import re
                        urls = re.findall(r'https://[^\s]+\.trycloudflare\.com', line)
                        if urls:
                            self.public_url = urls[0]
                            logger.info(f"📡 Cloudflare公网地址: {self.public_url}")
                    
                    # 记录重要日志
                    if any(kw in line.lower() for kw in ["error", "failed", "connected", "url"]):
                        logger.info(f"[cloudflared] {line}")
        except Exception as e:
            if self._running:
                logger.error(f"cloudflared日志监控异常: {e}")
    
    def _start_frp(self) -> Optional[str]:
        """启动frp客户端"""
        frp_config = os.getenv("FRP_CONFIG_PATH", "/etc/frp/frpc.ini")
        frp_server = os.getenv("FRP_SERVER_ADDR")
        
        if not os.path.exists(frp_config) and not frp_server:
            logger.warning("❌ FRP配置文件不存在且未配置FRP_SERVER_ADDR")
            return None
        
        try:
            self.process = subprocess.Popen(
                ["frpc", "-c", frp_config],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # 启动日志监控线程
            self._log_thread = threading.Thread(
                target=self._monitor_frp_output,
                daemon=True
            )
            self._log_thread.start()
            
            logger.info(f"✅ frp客户端已启动，配置: {frp_config}")
            return "frp"
        except FileNotFoundError:
            logger.error("❌ frpc未安装，请先安装frp客户端")
            return None
        except Exception as e:
            logger.error(f"❌ frp启动失败: {e}")
            return None
    
    def _monitor_frp_output(self):
        """监控frp输出"""
        if not self.process or not self.process.stdout:
            return
        
        try:
            for line in self.process.stdout:
                if not self._running:
                    break
                line = line.strip()
                if line:
                    level = "INFO"
                    if "error" in line.lower():
                        level = "ERROR"
                    elif "success" in line.lower() or "start" in line.lower():
                        level = "INFO"
                    
                    if level == "ERROR":
                        logger.error(f"[frp] {line}")
                    else:
                        logger.info(f"[frp] {line}")
        except Exception as e:
            if self._running:
                logger.error(f"frp日志监控异常: {e}")
    
    def get_public_url(self) -> Optional[str]:
        """获取公网访问地址"""
        return self.public_url
    
    def stop_tunnel(self):
        """停止穿透服务"""
        self._running = False
        
        # 停止ngrok
        if self.ngrok_tunnel:
            try:
                from pyngrok import ngrok
                ngrok.disconnect(self.ngrok_tunnel.public_url)
                ngrok.kill()
                logger.info("ngrok已停止")
            except Exception as e:
                logger.error(f"ngrok停止异常: {e}")
            self.ngrok_tunnel = None
        
        # 停止子进程
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("穿透服务进程已停止")
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("穿透服务进程被强制终止")
            except Exception as e:
                logger.error(f"停止穿透服务异常: {e}")
            self.process = None
        
        self.public_url = None


tunnel_manager = TunnelManager()
