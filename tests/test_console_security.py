"""脱敏工具单测：确保任何 secret 都不会以明文出现。"""
from console.security import mask, is_sensitive, mask_config, mask_open_id


def test_mask_keeps_last_four():
    assert mask("USUkVkn4LhwcUcSUKbsSfeWALLrqn1gM") == "****n1gM"


def test_mask_short_value_fully_hidden():
    assert mask("abc") == "***"


def test_mask_empty():
    assert mask("") == ""


def test_is_sensitive_case_insensitive():
    assert is_sensitive("FEISHU_APP_SECRET")
    assert is_sensitive("api_token")
    assert is_sensitive("DB_PASSWORD")
    assert not is_sensitive("DEFAULT_MODEL")
    assert not is_sensitive("FEISHU_APP_ID")


def test_mask_config_only_masks_sensitive():
    src = {"FEISHU_APP_SECRET": "qVPluZsMcTw6Ysljz9z0TjBkx1144pDz",
           "DEFAULT_MODEL": "claude-opus-4-8[1m]"}
    out = mask_config(src)
    assert out["DEFAULT_MODEL"] == "claude-opus-4-8[1m]"
    assert out["FEISHU_APP_SECRET"] == "****4pDz"
    assert "qVPlu" not in out["FEISHU_APP_SECRET"]


def test_mask_open_id():
    assert mask_open_id("ou_5b56e365ed0dc4a9376ef8a1dc41e889") == "ou_****e889"
    assert mask_open_id("") == ""
