"""读取各 bot 的 sessions.json，提取每用户每 chat 的当前会话，open_id 打码。只读。"""
import json
import os

from console.bots import Bot
from console.security import mask_open_id


def extract_sessions(data: dict) -> list[dict]:
    rows = []
    for user_id, chats in (data or {}).items():
        if not isinstance(chats, dict):
            continue
        for chat_key, payload in chats.items():
            if not isinstance(payload, dict):
                continue
            cur = payload.get("current")
            if not isinstance(cur, dict):
                continue  # 跳过 summaries 等非 chat 结构
            rows.append({
                "user": mask_open_id(user_id),
                "chat": chat_key,
                "model": cur.get("model", ""),
                "permission_mode": cur.get("permission_mode", ""),
                "cwd": cur.get("cwd", ""),
                "workspace": cur.get("workspace", ""),
                "session_id": cur.get("session_id", ""),
                "started_at": cur.get("started_at", ""),
                "preview": cur.get("preview", ""),
            })
    return rows


def read_bot_sessions(bot: Bot) -> list[dict]:
    path = os.path.join(os.path.expanduser(bot.sessions_dir), "sessions.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return extract_sessions(data)
