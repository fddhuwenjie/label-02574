"""极简聊天室 - 应用入口"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base, get_db
from .auth import init_test_users
from .tunnel import tunnel_manager
from .routes import auth_routes, messages, admin, websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    # 自动迁移：为已有表补充新增列
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(engine)
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "role" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"
                ))
                logger.info("数据库迁移：添加 users.role 列")
            if "is_banned" not in existing_cols:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0"
                ))
                logger.info("数据库迁移：添加 users.is_banned 列")

    db = next(get_db())
    init_test_users(db)
    logger.info("数据库初始化完成")

    tunnel_type = tunnel_manager.start_tunnel()
    if tunnel_type:
        logger.info(f"穿透服务已启动: {tunnel_type}")

    yield

    tunnel_manager.stop_tunnel()
    logger.info("应用已关闭")


app = FastAPI(
    title="极简聊天室",
    description="支持多人在线聊天的极简工具，包含私聊、消息撤回、加密传输功能",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_routes.router)
app.include_router(messages.router)
app.include_router(admin.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {
        "service": "极简聊天室",
        "version": "2.0.0",
        "tunnel_url": tunnel_manager.get_public_url(),
        "features": ["群聊", "私聊", "消息撤回", "加密传输"],
        "endpoints": {
            "注册": "POST /register",
            "登录": "POST /login",
            "聊天": "WebSocket /ws/chat?token=xxx",
            "在线用户": "GET /users/online",
            "历史消息": "GET /messages",
            "私聊记录": "GET /messages/private/{username}",
            "撤回消息": "POST /messages/revoke",
            "管理员": "/admin/*",
        }
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/tunnel")
def get_tunnel_info():
    return {
        "type": tunnel_manager.tunnel_type,
        "public_url": tunnel_manager.get_public_url(),
        "local_port": tunnel_manager.local_port
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
