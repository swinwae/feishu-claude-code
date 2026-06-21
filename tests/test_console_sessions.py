import json

from console.sessions import extract_sessions, read_bot_sessions
from console.bots import Bot


SAMPLE = {
    "ou_5b56e365ed0dc4a9376ef8a1dc41e889": {
        "private": {
            "current": {
                "session_id": "7d9242b3-5b30-4752-8d67-8f429094efdd",
                "model": "claude-opus-4-8[1m]",
                "cwd": "/Users/wanlizhu",
                "permission_mode": "bypassPermissions",
                "started_at": "2026-06-20T10:00:00",
                "preview": "你好",
                "workspace": "default",
            },
            "history": [{}],
        },
        "summaries": {"x": "y"},
    }
}


def test_extract_sessions_masks_user_and_picks_current():
    rows = extract_sessions(SAMPLE)
    assert len(rows) == 1
    r = rows[0]
    assert r["user"] == "ou_****e889"
    assert r["chat"] == "private"
    assert r["model"] == "claude-opus-4-8[1m]"
    assert r["permission_mode"] == "bypassPermissions"
    assert r["session_id"] == "7d9242b3-5b30-4752-8d67-8f429094efdd"


def test_extract_sessions_skips_non_chat_keys():
    # summaries 不是 chat，不应产出行
    rows = extract_sessions(SAMPLE)
    assert all(r["chat"] != "summaries" for r in rows)


def test_read_bot_sessions_missing_file(tmp_path):
    bot = Bot("bot1", "l", "/r", "/log", str(tmp_path), "env", "/e")
    assert read_bot_sessions(bot) == []


def test_read_bot_sessions_reads_file(tmp_path):
    (tmp_path / "sessions.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    bot = Bot("bot1", "l", "/r", "/log", str(tmp_path), "env", "/e")
    rows = read_bot_sessions(bot)
    assert rows[0]["user"] == "ou_****e889"


def test_read_bot_sessions_handles_non_dict_json(tmp_path):
    """sessions.json 是有效 JSON 但顶层不是 dict（如 list）时，应返回 [] 而非抛异常"""
    (tmp_path / "sessions.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    bot = Bot("bot1", "l", "/r", "/log", str(tmp_path), "env", "/e")
    assert read_bot_sessions(bot) == []
