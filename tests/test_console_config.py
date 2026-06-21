"""配置读取模块测试。"""
from console.config import parse_env, read_bot_config, read_plist_env
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


def test_read_plist_env_parses_multiline_with_dict_wrapper():
    """测试 read_plist_env 成功解析多行 KEY = VALUE，并正确跳过 Dict {} 包裹行。"""
    # 模拟 PlistBuddy 输出格式：Dict { ... }
    plist_output = """Dict {
    DEFAULT_MODEL = claude-opus-4-8[1m]
    SESSIONS_DIR = /Users/x/.feishu-claude-bot3
    ANOTHER_KEY = some_value
}"""

    def fake_run(cmd):
        # 返回成功状态码与模拟的 PlistBuddy 输出
        return 0, plist_output

    result = read_plist_env("/some/path/com.example.plist", run=fake_run)

    # 验证正确解析了三个键值对，跳过了 Dict { 和 }
    assert len(result) == 3
    assert result["DEFAULT_MODEL"] == "claude-opus-4-8[1m]"
    assert result["SESSIONS_DIR"] == "/Users/x/.feishu-claude-bot3"
    assert result["ANOTHER_KEY"] == "some_value"


def test_read_plist_env_returns_empty_on_failure():
    """测试 read_plist_env 在 run 返回非 0 returncode 时返回空 dict。"""
    def fake_run_failure(cmd):
        # 模拟命令失败
        return 1, ""

    result = read_plist_env("/nonexistent/path.plist", run=fake_run_failure)
    assert result == {}


def test_read_plist_env_handles_value_with_equals():
    """测试 read_plist_env 正确处理 value 本身含 = 的情况。"""
    # 模拟 PlistBuddy 输出，其中 value 包含等号
    plist_output = """Dict {
    TOKEN_THING = a=b=c
    NORMAL_KEY = normal_value
}"""

    def fake_run(cmd):
        return 0, plist_output

    result = read_plist_env("/some/path.plist", run=fake_run)

    # 验证按 " = " 只分割一次，value 保留了所有 =
    assert result["TOKEN_THING"] == "a=b=c"
    assert result["NORMAL_KEY"] == "normal_value"
