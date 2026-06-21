"""脱敏工具：保证 secret / open_id 不以明文外泄。"""

# 含以下任一子串的 key 视为敏感（不分大小写）
SENSITIVE_PARTS = ("SECRET", "TOKEN", "PASSWORD")


def mask(value: str, keep: int = 4) -> str:
    """保留末 keep 位，其余打码；过短则全打码。"""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * 4 + value[-keep:]


def is_sensitive(key: str) -> bool:
    k = key.upper()
    return any(part in k for part in SENSITIVE_PARTS)


def mask_config(d: dict) -> dict:
    """对敏感 key 的值打码，其余原样返回。"""
    return {k: (mask(v) if is_sensitive(k) else v) for k, v in d.items()}


def mask_open_id(oid: str) -> str:
    """ou_xxxx...xxxx → ou_****后4位。"""
    if not oid:
        return ""
    if len(oid) <= 7:
        return "****"
    return oid[:3] + "****" + oid[-4:]
