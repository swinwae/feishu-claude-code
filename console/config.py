"""读取各 bot 启动配置（.env 或 plist EnvironmentVariables），脱敏后返回。只读。"""
import os
import subprocess

from console.bots import Bot
from console.security import mask_config


def _run(cmd: list[str]) -> tuple[int, str]:
    """运行命令，返回返回码与标准输出。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def parse_env(text: str) -> dict:
    """解析 .env 格式文本：忽略注释与空行，去除引号。"""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        # 跳过注释、空行、无等号的行
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        # 去除首尾空格与引号
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def read_plist_env(path: str, run=_run) -> dict:
    """用 PlistBuddy 读 plist 的 :EnvironmentVariables，逐行解析 'KEY = VALUE'。"""
    rc, txt = run(["/usr/libexec/PlistBuddy", "-c", "Print :EnvironmentVariables", path])
    if rc != 0:
        return {}
    out = {}
    for line in txt.splitlines():
        line = line.strip()
        # 跳过字典括号、空行
        if " = " in line and not line.endswith("{") and not line.endswith("}"):
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
    return out


def read_bot_config(bot: Bot, run=_run) -> dict:
    """读取 bot 配置，脱敏后返回。支持 .env 和 plist 两种形式。"""
    if bot.config_kind == "env":
        try:
            with open(os.path.expanduser(bot.config_path), encoding="utf-8") as f:
                raw = parse_env(f.read())
        except OSError:
            # 文件不存在或无权限，返回空配置
            raw = {}
    else:
        # plist 形式
        raw = read_plist_env(bot.config_path, run=run)
    return mask_config(raw)
