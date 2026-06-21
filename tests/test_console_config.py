"""配置读取模块测试。"""
from console.config import parse_env, read_bot_config
from console.bots import Bot


def test_parse_env_basic():
    text = "# 注释\nDEFAULT_MODEL=claude-opus-4-8[1m]\n\nFEISHU_APP_SECRET=qVPluZsMcTw6\n"
    d = parse_env(text)
    assert d["DEFAULT_MODEL"] == "claude-opus-4-8[1m]"
    assert d["FEISHU_APP_SECRET"] == "qVPluZsMcTw6"


def test_parse_env_strips_quotes():
    assert parse_env('DEFAULT_CWD="/Users/x"\n')["DEFAULT_CWD"] == "/Users/x"


def test_read_bot_config_masks_secret(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("DEFAULT_MODEL=m1\nFEISHU_APP_SECRET=supersecretvalue\n")
    bot = Bot("bot1", "lbl", "/repo", "/log", "/sd", "env", str(envf))
    cfg = read_bot_config(bot)
    assert cfg["DEFAULT_MODEL"] == "m1"
    assert cfg["FEISHU_APP_SECRET"] == "****alue"
    assert "supersecret" not in cfg["FEISHU_APP_SECRET"]
