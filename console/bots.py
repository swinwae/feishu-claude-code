"""三 bot 事实注册表（核准于 2026-06-21），所有面板的唯一真相来源。"""
import os
from dataclasses import dataclass

MAIN_REPO = "/Users/wanlizhu/projects/feishu-claude-code"
BOT3_REPO = "/Users/wanlizhu/projects/feishu-claude-code-bot3"
_LA = os.path.expanduser("~/Library/LaunchAgents")


@dataclass(frozen=True)
class Bot:
    name: str          # bot1 / bot2 / bot3
    label: str         # launchd label
    repo: str          # 运行代码所在 git 仓
    log: str           # 日志文件
    sessions_dir: str  # SESSIONS_DIR（含 sessions.json）
    config_kind: str   # "env" | "plist"
    config_path: str   # .env 路径 或 plist 路径


BOTS = [
    Bot("bot1", "com.feishu-claude.bot", MAIN_REPO, "/tmp/feishu-claude.log",
        os.path.expanduser("~/wly-work/.feishu-claude"),
        "env", os.path.join(MAIN_REPO, ".env")),
    Bot("bot2", "com.feishu-claude.bot2", MAIN_REPO, "/tmp/feishu-claude-2.log",
        os.path.expanduser("~/zwl-work/.feishu-claude"),
        "plist", os.path.join(_LA, "com.feishu-claude.bot2.plist")),
    Bot("bot3", "com.feishu-claude.bot3", BOT3_REPO, "/tmp/feishu-claude-3.log",
        os.path.expanduser("~/.feishu-claude-bot3"),
        "plist", os.path.join(_LA, "com.feishu-claude.bot3.plist")),
]


def get_bot(name: str):
    for b in BOTS:
        if b.name == name:
            return b
    return None
