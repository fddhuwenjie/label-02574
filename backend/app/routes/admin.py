"""管理员接口路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import verify_token, require_admin
from ..chat import manager

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def admin_list_users(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """管理员：获取所有用户列表"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    require_admin(current_user, db)

    users = db.query(User).all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_banned": u.is_banned,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.put("/users/{username}/ban")
def admin_ban_user(
    username: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """管理员：封禁/解封用户"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    require_admin(current_user, db)

    if username == current_user:
        raise HTTPException(status_code=400, detail="不能封禁自己")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_banned = not user.is_banned
    db.commit()

    status_text = "已封禁" if user.is_banned else "已解封"
    return {"message": f"{username} {status_text}", "is_banned": user.is_banned}


@router.delete("/users/{username}")
def admin_delete_user(
    username: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """管理员：删除用户"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    require_admin(current_user, db)

    if username == current_user:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"message": f"用户 {username} 已删除"}


@router.put("/users/{username}/role")
def admin_set_role(
    username: str,
    role: str = Query(..., regex="^(admin|user)$"),
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """管理员：设置用户角色"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    require_admin(current_user, db)

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.role = role
    db.commit()
    return {"message": f"{username} 角色已设为 {role}", "role": role}


@router.post("/kick/{username}")
async def admin_kick_user(
    username: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """管理员：踢用户下线"""
    current_user = verify_token(token)
    if not current_user:
        raise HTTPException(status_code=401, detail="无效的token")
    require_admin(current_user, db)

    if username == current_user:
        raise HTTPException(status_code=400, detail="不能踢自己下线")

    if not manager.is_online(username):
        raise HTTPException(status_code=404, detail="用户不在线")

    ws = manager.active_connections.get(username)
    if ws:
        try:
            await ws.close(code=4003, reason="被管理员踢出")
        except Exception:
            pass
        manager.disconnect(username)
        await manager.broadcast_system(f"🚫 {username} 被管理员移出了聊天室")

    return {"message": f"{username} 已被踢出"}
