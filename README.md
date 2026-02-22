# 极简个人聊天工具

## How to Run

### 一键启动（推荐）

```bash
# 赋予执行权限并启动
chmod +x start.sh
./start.sh
```

脚本会自动：
1. 检测并安装 Docker（如未安装）
2. 构建并启动服务
3. 运行 API 测试验证
4. 输出可用的 WebSocket 测试命令

### Docker 启动

```bash
# 构建并启动
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 本地启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Services

| 服务 | 地址 | 说明 |
|------|------|------|
| API文档 | http://localhost:8000/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | 服务状态 |
| WebSocket | ws://localhost:8000/ws/chat?token=xxx | 聊天连接 |

## 测试账号

| 用户名 | 密码 |
|--------|------|
| admin | admin123 |
| user1 | password1 |
| user2 | password2 |

## 题目内容

我想使用python搭建一个极简的个人聊天工具，支持多人在线聊天，用户名密码认证即可，需要在内网搭建服务，集成内外网穿透功能，请帮我详细设计需求并实现。

---

## 项目介绍

基于 Python FastAPI 的极简多人聊天工具，支持：

- WebSocket 实时通信
- 群聊和私聊功能
- 消息撤回（2分钟内）
- 消息加密传输（AES-256-GCM / RSA）
- 用户名密码认证
- 多数据库支持（SQLite/PostgreSQL）
- 内外网穿透（ngrok/cloudflared/frp）
- Docker 跨平台部署（ARM64/AMD64）

---

## API 接口详细文档

### 认证相关

#### POST /register - 用户注册

注册新用户账号。

请求体：
```json
{
  "username": "newuser",
  "password": "password123",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"  // 可选，端到端加密公钥
}
```

响应：
```json
{
  "message": "注册成功",
  "username": "newuser"
}
```

错误码：
- 400: 用户名已存在

#### POST /login - 用户登录

使用 HTTP Basic 认证登录。

请求头：
```
Authorization: Basic base64(username:password)
```

响应：
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "username": "admin",
  "message": "登录成功"
}
```

错误码：
- 401: 用户名或密码错误

### 用户相关

#### GET /users/online - 获取在线用户

响应：
```json
{
  "users": ["admin", "user1"],
  "count": 2
}
```

#### GET /users/{username}/public-key - 获取用户公钥

用于端到端加密时获取对方公钥。

响应：
```json
{
  "username": "user1",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
}
```

错误码：
- 404: 用户不存在或未设置公钥

### 消息相关

#### GET /messages - 获取群聊历史消息

参数：
- `limit`: 消息数量限制，默认 50
- `decrypt`: 是否解密服务端加密消息，默认 false

响应：
```json
[
  {
    "message_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "admin",
    "content": "Hello!",
    "is_encrypted": false,
    "time": "2024-01-15 10:30:00"
  }
]
```

#### GET /messages/private/{username} - 获取私聊记录

获取与指定用户的私聊历史。

参数：
- `token`: 认证令牌（必需）
- `limit`: 消息数量限制，默认 50
- `decrypt`: 是否解密，默认 false

响应：
```json
[
  {
    "message_id": "550e8400-e29b-41d4-a716-446655440001",
    "username": "admin",
    "recipient": "user1",
    "content": "私聊内容",
    "is_encrypted": false,
    "time": "2024-01-15 10:35:00"
  }
]
```

#### POST /messages/revoke - 撤回消息

撤回自己发送的消息（2分钟内有效）。

参数：
- `token`: 认证令牌（必需）

请求体：
```json
{
  "message_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

响应：
```json
{
  "message": "撤回成功",
  "message_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

错误码：
- 400: 消息已撤回 / 超过撤回时间限制
- 403: 只能撤回自己的消息
- 404: 消息不存在

### 加密相关

#### POST /crypto/generate-keypair - 生成密钥对

生成 RSA 密钥对用于端到端加密。

响应：
```json
{
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
}
```

### WebSocket 聊天

#### WS /ws/chat?token=xxx

WebSocket 实时聊天接口。

连接参数：
- `token`: 登录获取的认证令牌

**发送消息格式：**

群聊消息：
```json
{"content": "Hello everyone!"}
```

私聊消息：
```json
{
  "type": "private",
  "to": "user1",
  "content": "私密消息"
}
```

加密消息：
```json
{
  "content": "加密内容",
  "encrypted": true
}
```

撤回消息：
```json
{
  "type": "revoke",
  "message_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**接收消息格式：**

系统消息：
```json
{
  "type": "system",
  "content": "📢 admin 加入了聊天室",
  "time": "10:30:00"
}
```

群聊消息：
```json
{
  "type": "message",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "content": "Hello!",
  "is_encrypted": false,
  "time": "10:30:05"
}
```

私聊消息：
```json
{
  "type": "private",
  "message_id": "550e8400-e29b-41d4-a716-446655440001",
  "username": "admin",
  "recipient": "user1",
  "content": "私密消息",
  "is_encrypted": false,
  "time": "10:30:10"
}
```

撤回通知：
```json
{
  "type": "revoke",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "admin",
  "content": "admin 撤回了一条消息",
  "time": "10:30:15"
}
```

错误消息：
```json
{
  "type": "error",
  "message": "错误描述"
}
```

---

## 使用示例

### 1. 登录获取 Token

```bash
curl -X POST http://localhost:8000/login \
  -u admin:admin123
```

### 2. WebSocket 群聊

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat?token=YOUR_TOKEN');

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  console.log(`[${msg.type}] ${msg.username}: ${msg.content}`);
};

// 发送群聊消息
ws.send(JSON.stringify({content: 'Hello!'}));
```

### 3. 私聊

```javascript
// 发送私聊消息
ws.send(JSON.stringify({
  type: 'private',
  to: 'user1',
  content: '这是私聊消息'
}));
```

### 4. 撤回消息

```javascript
// 通过 WebSocket 撤回
ws.send(JSON.stringify({
  type: 'revoke',
  message_id: '550e8400-e29b-41d4-a716-446655440000'
}));

// 或通过 REST API 撤回
curl -X POST "http://localhost:8000/messages/revoke?token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

### 5. 加密消息

```javascript
// 发送服务端加密消息
ws.send(JSON.stringify({
  content: '这条消息会被加密存储',
  encrypted: true
}));
```

### 6. 命令行测试

```bash
# 安装 websocat
brew install websocat  # macOS
# 或 cargo install websocat

# 连接聊天
websocat "ws://localhost:8000/ws/chat?token=YOUR_TOKEN"

# 发送消息（输入后回车）
{"content": "Hello from CLI!"}

# 发送私聊
{"type": "private", "to": "user1", "content": "私聊测试"}
```

### 7. 快速测试脚本

启动服务后，可以用以下命令快速测试：

```bash
# 一键启动
./start.sh

# 测试 API
curl http://localhost:8000/health                        # 健康检查
curl -X POST http://localhost:8000/login -u admin:admin123  # 登录

# 获取 token 后测试 WebSocket
TOKEN=$(curl -s -X POST http://localhost:8000/login -u admin:admin123 | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
echo "Token: $TOKEN"

# 用 websocat 连接聊天室
websocat "ws://localhost:8000/ws/chat?token=$TOKEN"
```

Python 测试脚本：

```python
import asyncio, websockets, httpx, json

async def test():
    # 登录获取 token
    async with httpx.AsyncClient() as c:
        r = await c.post("http://localhost:8000/login", auth=("admin", "admin123"))
        token = r.json()["token"]
        print(f"Token: {token}")
    
    # 连接聊天
    async with websockets.connect(f"ws://localhost:8000/ws/chat?token={token}") as ws:
        await ws.send(json.dumps({"content": "Hello!"}))
        for _ in range(3):
            print(await ws.recv())

asyncio.run(test())
```

---

## 内外网穿透配置

### 方式一：ngrok

```bash
export TUNNEL_TYPE=ngrok
export NGROK_AUTH_TOKEN=your_token
docker-compose up -d
```

### 方式二：Cloudflare Tunnel

```bash
export TUNNEL_TYPE=cloudflared
docker-compose up -d
```

### 方式三：frp（自建服务器）

```bash
export TUNNEL_TYPE=frp
# 需要配置 frpc.ini
docker-compose up -d
```

---

## 使用 PostgreSQL

编辑 docker-compose.yml 取消 postgres 服务注释，然后：

```bash
export DATABASE_TYPE=postgresql
export DATABASE_URL=postgresql://chatuser:chatpass@postgres:5432/chatdb
docker-compose up -d
```

---

## 故障排查指南

### 常见问题

#### 1. 无法连接 WebSocket

**症状：** WebSocket 连接失败，返回 4001 错误码

**原因：** Token 无效或已过期

**解决方案：**
```bash
# 重新登录获取新 token
curl -X POST http://localhost:8000/login -u admin:admin123

# 使用新 token 连接
websocat "ws://localhost:8000/ws/chat?token=NEW_TOKEN"
```

#### 2. 消息撤回失败

**症状：** 撤回请求返回 400 错误

**可能原因：**
- 超过 2 分钟撤回时限
- 消息已被撤回
- 尝试撤回他人消息

**解决方案：**
- 确保在发送后 2 分钟内撤回
- 检查 message_id 是否正确
- 只能撤回自己发送的消息

#### 3. 私聊消息未送达

**症状：** 私聊消息发送成功但对方未收到

**原因：** 接收者不在线

**解决方案：**
- 消息已保存到数据库，对方上线后可通过 `/messages/private/{username}` 查看
- 系统会返回 `type: info` 提示用户不在线

#### 4. 加密消息无法解密

**症状：** 获取历史消息时显示 `[加密消息]`

**解决方案：**
```bash
# 使用 decrypt=true 参数获取解密后的消息
curl "http://localhost:8000/messages?decrypt=true"
```

#### 5. Docker 容器启动失败

**症状：** `docker-compose up` 后容器退出

**排查步骤：**
```bash
# 查看容器日志
docker-compose logs backend

# 检查端口占用
lsof -i :8000

# 重新构建镜像
docker-compose build --no-cache
docker-compose up -d
```

#### 6. 数据库连接失败

**症状：** 启动时报数据库连接错误

**SQLite 问题：**
```bash
# 检查文件权限
ls -la chat.db

# 删除损坏的数据库文件重新创建
rm chat.db
docker-compose restart backend
```

**PostgreSQL 问题：**
```bash
# 检查 PostgreSQL 容器状态
docker-compose ps postgres

# 检查连接参数
echo $DATABASE_URL

# 测试连接
docker-compose exec postgres psql -U chatuser -d chatdb -c "SELECT 1"
```

#### 7. 穿透服务无法启动

**ngrok 问题：**
```bash
# 检查 token 是否正确
echo $NGROK_AUTH_TOKEN

# 手动测试 ngrok
ngrok http 8000
```

**cloudflared 问题：**
```bash
# 检查 cloudflared 是否安装
which cloudflared

# 查看穿透状态
curl http://localhost:8000/tunnel
```

### 日志分析

```bash
# 查看实时日志
docker-compose logs -f backend

# 查看最近 100 行日志
docker-compose logs --tail=100 backend

# 过滤错误日志
docker-compose logs backend 2>&1 | grep -i error
```

### 性能问题

#### 连接数过多

**症状：** 服务响应变慢，内存占用高

**解决方案：**
```bash
# 检查在线用户数
curl http://localhost:8000/users/online

# 重启服务清理连接
docker-compose restart backend
```

#### 数据库查询慢

**症状：** 获取历史消息响应慢

**解决方案：**
```bash
# 限制查询数量
curl "http://localhost:8000/messages?limit=20"

# 定期清理旧消息（PostgreSQL）
docker-compose exec postgres psql -U chatuser -d chatdb \
  -c "DELETE FROM messages WHERE created_at < NOW() - INTERVAL '30 days'"
```

### 安全建议

1. **生产环境必须设置加密密钥：**
   ```bash
   export ENCRYPTION_KEY=$(python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())")
   ```

2. **使用 HTTPS/WSS：**
   - 配置反向代理（nginx）启用 SSL
   - 或使用穿透服务自带的 HTTPS

3. **定期更换 JWT 密钥：**
   ```bash
   export JWT_SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
   ```

4. **限制注册：**
   - 生产环境可关闭公开注册
   - 通过管理接口添加用户

---

## 开发相关

### 运行测试

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov
pytest -v --cov=app --cov-report=term-missing
```

### 代码结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py      # FastAPI 应用入口
│   ├── auth.py      # 认证模块
│   ├── chat.py      # WebSocket 聊天管理
│   ├── crypto.py    # 加密模块
│   ├── database.py  # 数据库配置
│   ├── models.py    # 数据模型
│   └── tunnel.py    # 穿透服务
├── tests/           # 测试文件
├── Dockerfile
└── requirements.txt
```
