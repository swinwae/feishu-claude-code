# 运维控制台（Ops Console）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为三 bot 部署提供一个本机只读运维控制台（健康/日志/会话/配置）+ 网页化金丝雀发布。

**Architecture:** 独立 FastAPI 服务（主仓 `console/` 子包），绑 `127.0.0.1:9990`，自己一个 launchd。与 bot 解耦：以纯文件方式读 `sessions.json`/`.env`/plist，以 subprocess 跑 `launchctl`/git/发布脚本。可测的纯函数（脱敏、解析）与 I/O 接线分离。

**Tech Stack:** Python 3 + FastAPI + uvicorn（复用主仓 `.venv`），前端单 HTML（无构建），SSE 推送日志与发布输出。

## Global Constraints

- 仅写操作 = 发布（rollout/promote）；健康、日志、会话、配置一律**只读**。
- 服务绑 `127.0.0.1`，**无鉴权**。
- 任何含 `SECRET`/`TOKEN`/`PASSWORD`（不分大小写）的值**必须打码**，不回传明文；用户 open_id 也打码。
- 控制台**不得 import** bot 的 `bot_config`/`session_store`（会触发 `load_dotenv` 且依赖具体 bot env）。
- 发布脚本参数（promote message）必须以**参数数组**传递，**绝不拼 shell 字符串**。
- 中文：注释、commit message、UI 文案、错误提示用中文；变量/函数/key/CLI 参数用英文。
- commit 格式 `类型: 描述`（feat/fix/docs/test/refactor/chore）。
- 路径常量（核准于 2026-06-21）：
  - 主仓 `MAIN_REPO=/Users/wanlizhu/projects/feishu-claude-code`
  - bot3 副本 `BOT3_REPO=/Users/wanlizhu/projects/feishu-claude-code-bot3`
  - 三 bot 注册表见 Task 1。

---

## File Structure

- `console/__init__.py` — 空包标记
- `console/bots.py` — `Bot` 数据类 + `BOTS` 注册表 + `get_bot(name)`
- `console/security.py` — `mask`、`is_sensitive`、`mask_config`、`mask_open_id`
- `console/health.py` — `parse_pid`、`probe_bot`、`collect_health`
- `console/config.py` — `parse_env`、`read_plist_env`、`read_bot_config`
- `console/sessions.py` — `extract_sessions`、`read_bot_sessions`
- `console/logs.py` — `tail_log`（async SSE 生成器）
- `console/publish.py` — `build_rollout_cmd`、`build_promote_cmd`、`stream_script`、发布锁
- `console/server.py` — FastAPI app + 路由 + 静态页挂载
- `console/static/index.html` — 单页前端
- `deploy/com.feishu-claude.console.plist` — launchd 配置（模板，安装到 `~/Library/LaunchAgents/`）
- 测试：`tests/test_console_security.py`、`tests/test_console_health.py`、`tests/test_console_config.py`、`tests/test_console_sessions.py`、`tests/test_console_publish.py`、`tests/test_console_server.py`

---

### Task 1: 包骨架 + bots 注册表 + 脱敏工具

**Files:**
- Create: `console/__init__.py`（空）
- Create: `console/bots.py`
- Create: `console/security.py`
- Test: `tests/test_console_security.py`
- 依赖安装（一次性）：`fastapi`、`uvicorn`

**Interfaces:**
- Produces:
  - `bots.Bot`（dataclass，字段：`name:str, label:str, repo:str, log:str, sessions_dir:str, config_kind:str, config_path:str`），`config_kind ∈ {"env","plist"}`
  - `bots.BOTS: list[Bot]`，`bots.get_bot(name:str)->Bot|None`
  - `security.mask(value:str, keep:int=4)->str`
  - `security.is_sensitive(key:str)->bool`
  - `security.mask_config(d:dict)->dict`
  - `security.mask_open_id(oid:str)->str`

- [ ] **Step 1: 安装依赖（按 CLAUDE.md 手动装，不进发布流程）**

Run:
```bash
cd /Users/wanlizhu/projects/feishu-claude-code
.venv/bin/pip install fastapi uvicorn
.venv/bin/python -c "import fastapi, uvicorn; print('ok', fastapi.__version__)"
```
Expected: 打印 `ok <version>`，无报错。

- [ ] **Step 2: 写失败测试 `tests/test_console_security.py`**

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd /Users/wanlizhu/projects/feishu-claude-code && .venv/bin/python -m pytest tests/test_console_security.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'console'`）。

- [ ] **Step 4: 实现 `console/__init__.py`（空文件）与 `console/security.py`**

`console/security.py`:
```python
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
```

- [ ] **Step 5: 实现 `console/bots.py`**

```python
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
```

- [ ] **Step 6: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_security.py -v`
Expected: PASS（6 passed）。

- [ ] **Step 7: 提交**

```bash
git add console/__init__.py console/bots.py console/security.py tests/test_console_security.py
git commit -m "feat: 运维控制台包骨架与脱敏工具"
```

---

### Task 2: 健康探测

**Files:**
- Create: `console/health.py`
- Test: `tests/test_console_health.py`

**Interfaces:**
- Consumes: `bots.Bot`, `bots.BOTS`
- Produces:
  - `health.parse_pid(launchctl_output:str, label:str)->str|None`
  - `health.collect_health(run=...)->list[dict]`（每项：`{name,label,alive:bool,pid,version,dirty:bool,last_good,started}`）
  - 默认命令执行器 `health._run(cmd:list[str])->tuple[int,str]`（返回 `(returncode, stdout)`）

- [ ] **Step 1: 写失败测试 `tests/test_console_health.py`**

```python
from console.health import parse_pid, collect_health


def test_parse_pid_found():
    out = "12651\t0\tcom.feishu-claude.bot3\n13993\t0\tcom.feishu-claude.bot\n"
    assert parse_pid(out, "com.feishu-claude.bot3") == "12651"


def test_parse_pid_dash_means_not_running():
    out = "-\t0\tcom.feishu-claude.bot2\n"
    assert parse_pid(out, "com.feishu-claude.bot2") is None


def test_parse_pid_absent():
    assert parse_pid("12651\t0\tother\n", "com.feishu-claude.bot") is None


def test_collect_health_shape():
    # 注入假 run：launchctl 返回 pid，git 返回版本，其它空
    def fake_run(cmd):
        if cmd[0] == "launchctl":
            return 0, "999\t0\tcom.feishu-claude.bot\n"
        if "rev-parse" in cmd and "--short" in cmd and "HEAD" in cmd:
            return 0, "abc1234\n"
        if "diff" in cmd:
            return 0, ""          # 干净
        if "ps" in cmd[0]:
            return 0, "Sat Jun 21 10:00:00 2026\n"
        return 0, ""
    rows = collect_health(run=fake_run)
    assert len(rows) == 3
    bot1 = next(r for r in rows if r["name"] == "bot1")
    assert bot1["alive"] is True
    assert bot1["pid"] == "999"
    assert bot1["version"] == "abc1234"
    assert bot1["dirty"] is False
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_health.py -v`
Expected: FAIL（`No module named 'console.health'`）。

- [ ] **Step 3: 实现 `console/health.py`**

```python
"""健康探测：launchctl 存活、git 版本、进程启动时间。全部只读。"""
import subprocess

from console.bots import BOTS


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def parse_pid(launchctl_output: str, label: str) -> str | None:
    for line in launchctl_output.splitlines():
        cols = line.split()
        if len(cols) >= 3 and cols[2] == label:
            pid = cols[0]
            return None if pid in ("-", "") else pid
    return None


def collect_health(run=_run) -> list[dict]:
    _, lc = run(["launchctl", "list"])
    rows = []
    for b in BOTS:
        pid = parse_pid(lc, b.label)
        _, head = run(["git", "-C", b.repo, "rev-parse", "--short", "HEAD"])
        rc_diff, _ = run(["git", "-C", b.repo, "diff", "--quiet"])
        _, good = run(["git", "-C", b.repo, "rev-parse", "--short", "bot3-last-good"])
        started = ""
        if pid:
            _, ls = run(["ps", "-o", "lstart=", "-p", pid])
            started = ls.strip()
        rows.append({
            "name": b.name,
            "label": b.label,
            "alive": pid is not None,
            "pid": pid or "",
            "version": head.strip(),
            "dirty": rc_diff != 0,
            "last_good": good.strip(),
            "started": started,
        })
    return rows
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_health.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add console/health.py tests/test_console_health.py
git commit -m "feat: 控制台健康探测"
```

---

### Task 3: 配置读取（脱敏）

**Files:**
- Create: `console/config.py`
- Test: `tests/test_console_config.py`

**Interfaces:**
- Consumes: `bots.Bot`, `security.mask_config`
- Produces:
  - `config.parse_env(text:str)->dict`（忽略注释/空行，去引号）
  - `config.read_plist_env(path:str, run=...)->dict`
  - `config.read_bot_config(bot:Bot, run=...)->dict`（已脱敏）

- [ ] **Step 1: 写失败测试 `tests/test_console_config.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_config.py -v`
Expected: FAIL（`No module named 'console.config'`）。

- [ ] **Step 3: 实现 `console/config.py`**

```python
"""读取各 bot 启动配置（.env 或 plist EnvironmentVariables），脱敏后返回。只读。"""
import os
import subprocess

from console.bots import Bot
from console.security import mask_config


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def parse_env(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def read_plist_env(path: str, run=_run) -> dict:
    """用 PlistBuddy 读 :EnvironmentVariables，逐行解析 'KEY = VALUE'。"""
    rc, txt = run(["/usr/libexec/PlistBuddy", "-c", "Print :EnvironmentVariables", path])
    if rc != 0:
        return {}
    out = {}
    for line in txt.splitlines():
        line = line.strip()
        if " = " in line and not line.endswith("{") and not line.endswith("}"):
            k, v = line.split(" = ", 1)
            out[k.strip()] = v.strip()
    return out


def read_bot_config(bot: Bot, run=_run) -> dict:
    if bot.config_kind == "env":
        try:
            with open(os.path.expanduser(bot.config_path), encoding="utf-8") as f:
                raw = parse_env(f.read())
        except OSError:
            raw = {}
    else:
        raw = read_plist_env(bot.config_path, run=run)
    return mask_config(raw)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_config.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add console/config.py tests/test_console_config.py
git commit -m "feat: 控制台配置读取与脱敏"
```

---

### Task 4: 会话读取（只读，脱敏）

**Files:**
- Create: `console/sessions.py`
- Test: `tests/test_console_sessions.py`

**Interfaces:**
- Consumes: `bots.Bot`, `security.mask_open_id`
- Produces:
  - `sessions.extract_sessions(data:dict)->list[dict]`（每项：`{user, chat, model, permission_mode, cwd, workspace, session_id, started_at, preview}`，user 已打码）
  - `sessions.read_bot_sessions(bot:Bot)->list[dict]`（文件缺失/损坏返回 `[]`）

- [ ] **Step 1: 写失败测试 `tests/test_console_sessions.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_sessions.py -v`
Expected: FAIL（`No module named 'console.sessions'`）。

- [ ] **Step 3: 实现 `console/sessions.py`**

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_sessions.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add console/sessions.py tests/test_console_sessions.py
git commit -m "feat: 控制台会话读取与脱敏"
```

---

### Task 5: 发布命令构造与流式执行

**Files:**
- Create: `console/publish.py`
- Test: `tests/test_console_publish.py`

**Interfaces:**
- Produces:
  - `publish.build_rollout_cmd()->list[str]`
  - `publish.build_promote_cmd(message:str)->list[str]`
  - `publish.stream_script(cmd:list[str], cwd:str=MAIN_REPO)` — async 生成器，逐行 yield str
  - `publish.publish_lock` — `asyncio.Lock()`，全模块共享，发布互斥

- [ ] **Step 1: 写失败测试 `tests/test_console_publish.py`**

```python
import asyncio

from console.publish import build_rollout_cmd, build_promote_cmd, stream_script


def test_build_rollout_cmd():
    assert build_rollout_cmd() == ["bash", "rollout.sh"]


def test_build_promote_cmd_is_arg_array_no_shell():
    # 注入攻击式 message 必须作为单个参数，绝不拆解
    msg = "feat: x; rm -rf /"
    cmd = build_promote_cmd(msg)
    assert cmd == ["bash", "promote.sh", "feat: x; rm -rf /"]
    assert len(cmd) == 3


def test_stream_script_yields_lines():
    async def collect():
        out = []
        async for line in stream_script(["bash", "-c", "echo 行1; echo 行2"], cwd="/tmp"):
            out.append(line.rstrip("\n"))
        return out
    out = asyncio.run(collect())
    assert out == ["行1", "行2"]
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_publish.py -v`
Expected: FAIL（`No module named 'console.publish'`）。

- [ ] **Step 3: 实现 `console/publish.py`**

```python
"""发布操作：构造 rollout/promote 命令并流式执行。唯一写操作路径。"""
import asyncio

from console.bots import MAIN_REPO

# 全局发布锁：同一时刻只允许一个 rollout/promote 在跑
publish_lock = asyncio.Lock()


def build_rollout_cmd() -> list[str]:
    return ["bash", "rollout.sh"]


def build_promote_cmd(message: str) -> list[str]:
    # message 作为独立参数传入，绝不拼进 shell 字符串，防注入
    return ["bash", "promote.sh", message]


async def stream_script(cmd: list[str], cwd: str = MAIN_REPO):
    """逐行 yield 子进程合并输出（stdout+stderr）。"""
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        yield line.decode("utf-8", errors="replace")
    await proc.wait()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_publish.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add console/publish.py tests/test_console_publish.py
git commit -m "feat: 控制台发布命令构造与流式执行"
```

---

### Task 6: 日志 tail 生成器

**Files:**
- Create: `console/logs.py`
- Test: `tests/test_console_logs.py`

**Interfaces:**
- Produces: `logs.tail_log(path:str, lines:int=200)` — async 生成器，先吐尾部 lines 行再持续跟随

- [ ] **Step 1: 写失败测试 `tests/test_console_logs.py`**

```python
import asyncio


def test_tail_log_emits_existing_tail(tmp_path):
    from console.logs import tail_log
    f = tmp_path / "x.log"
    f.write_text("a\nb\nc\n", encoding="utf-8")

    async def collect():
        out = []
        gen = tail_log(str(f), lines=2)
        # 只取已有尾部两行就停（tail -F 会持续阻塞，故限量取）
        for _ in range(2):
            out.append((await gen.__anext__()).rstrip("\n"))
        await gen.aclose()
        return out

    assert asyncio.run(collect()) == ["b", "c"]
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_logs.py -v`
Expected: FAIL（`No module named 'console.logs'`）。

- [ ] **Step 3: 实现 `console/logs.py`**

```python
"""实时日志：tail -n N -F，逐行 yield。只读。"""
import asyncio


async def tail_log(path: str, lines: int = 200):
    proc = await asyncio.create_subprocess_exec(
        "tail", "-n", str(lines), "-F", path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert proc.stdout is not None
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace")
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_logs.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: 提交**

```bash
git add console/logs.py tests/test_console_logs.py
git commit -m "feat: 控制台实时日志生成器"
```

---

### Task 7: FastAPI 服务接线

**Files:**
- Create: `console/server.py`
- Test: `tests/test_console_server.py`

**Interfaces:**
- Consumes: 全部上述模块
- Produces: `server.app`（FastAPI 实例）
- 路由：
  - `GET /` → `static/index.html`
  - `GET /api/health` → `{ok, bots:[...]}`
  - `GET /api/config` → `{ok, configs:{bot1:{...},...}}`
  - `GET /api/sessions` → `{ok, sessions:{bot1:[...],...}}`
  - `GET /api/logs/stream?bot=bot1` → SSE
  - `POST /api/rollout` → SSE（被锁占用返回 409）
  - `POST /api/promote`（body `{message}`）→ SSE（message 空返回 400；被锁占用 409）

- [ ] **Step 1: 写失败测试 `tests/test_console_server.py`**

```python
from fastapi.testclient import TestClient

from console import server


def test_health_endpoint(monkeypatch):
    fake = [{"name": "bot1", "alive": True, "pid": "1", "version": "abc",
             "dirty": False, "last_good": "", "started": "", "label": "l"}]
    monkeypatch.setattr(server, "collect_health", lambda: fake)
    client = TestClient(server.app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["bots"][0]["name"] == "bot1"


def test_promote_rejects_empty_message():
    client = TestClient(server.app)
    r = client.post("/api/promote", json={"message": ""})
    assert r.status_code == 400


def test_config_endpoint_never_leaks_secret(monkeypatch):
    monkeypatch.setattr(server, "read_bot_config",
                        lambda bot: {"FEISHU_APP_SECRET": "****abcd", "DEFAULT_MODEL": "m"})
    client = TestClient(server.app)
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "****abcd" in r.text
    # 明文不应出现
    assert "supersecret" not in r.text
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_console_server.py -v`
Expected: FAIL（`No module named 'console.server'`）。

- [ ] **Step 3: 实现 `console/server.py`**

```python
"""运维控制台 FastAPI 服务。绑 127.0.0.1，只读 + 发布。"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from console.bots import BOTS, get_bot
from console.health import collect_health
from console.config import read_bot_config
from console.sessions import read_bot_sessions
from console.logs import tail_log
from console.publish import (
    build_rollout_cmd, build_promote_cmd, stream_script, publish_lock,
)

app = FastAPI(title="运维控制台")
_STATIC = os.path.join(os.path.dirname(__file__), "static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


@app.get("/api/health")
async def api_health():
    return {"ok": True, "bots": collect_health()}


@app.get("/api/config")
async def api_config():
    return {"ok": True, "configs": {b.name: read_bot_config(b) for b in BOTS}}


@app.get("/api/sessions")
async def api_sessions():
    return {"ok": True, "sessions": {b.name: read_bot_sessions(b) for b in BOTS}}


def _sse(gen):
    async def event_stream():
        async for chunk in gen:
            # SSE：每行一个 data 事件
            yield f"data: {chunk.rstrip(chr(10))}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/logs/stream")
async def api_logs(bot: str = "bot1"):
    b = get_bot(bot)
    if not b:
        return JSONResponse({"ok": False, "error": "未知 bot"}, status_code=404)
    return _sse(tail_log(b.log))


async def _run_publish(cmd):
    if publish_lock.locked():
        return JSONResponse({"ok": False, "error": "已有发布任务在执行"}, status_code=409)

    async def guarded():
        async with publish_lock:
            async for line in stream_script(cmd):
                yield line
    return _sse(guarded())


@app.post("/api/rollout")
async def api_rollout():
    return await _run_publish(build_rollout_cmd())


@app.post("/api/promote")
async def api_promote(req: Request):
    body = await req.json()
    message = (body or {}).get("message", "").strip()
    if not message:
        return JSONResponse({"ok": False, "error": "改动说明不能为空"}, status_code=400)
    return await _run_publish(build_promote_cmd(message))
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_console_server.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 全量回归**

Run: `.venv/bin/python -m pytest tests/test_console_*.py -v`
Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add console/server.py tests/test_console_server.py
git commit -m "feat: 控制台 FastAPI 服务接线"
```

---

### Task 8: 单页前端

**Files:**
- Create: `console/static/index.html`

**Interfaces:**
- Consumes: 全部 `/api/*` 接口
- 五个 tab：健康 / 日志 / 会话 / 配置 / 发布。中文 UI。

- [ ] **Step 1: 实现 `console/static/index.html`**

单文件（HTML+CSS+原生 JS），要点：
- 顶部 5 个 tab 按钮切换面板。
- **健康**：`fetch('/api/health')` 每 5s 轮询，渲染三 bot 卡片（存活灯、PID、版本、dirty 标记、last_good、启动时间）。
- **日志**：bot1/2/3 子 tab，`new EventSource('/api/logs/stream?bot=botN')`，追加到 `<pre>`，自动滚底，切 bot 时关旧 EventSource。
- **会话**：`fetch('/api/sessions')`，按 bot 分组表格（user/chat/model/mode/cwd/session_id/started_at/preview）。
- **配置**：`fetch('/api/config')`，三列并排对比，敏感值已是打码串。
- **发布**：【金丝雀发布】按钮 → `fetch('/api/rollout',{method:'POST'})` 读 SSE 流到日志区；流结束且出现成功标志（文案含 `金丝雀 bot1/bot2 已加载新代码`）→ 启用改动说明输入框 + 【升级 bot3】按钮 → `POST /api/promote {message}`。409 时提示"已有发布在执行"。

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>运维控制台</title>
<style>
  body { font-family: -apple-system, "PingFang SC", sans-serif; margin: 0; background: #f5f5f7; color: #1d1d1f; }
  header { background: #1d1d1f; color: #fff; padding: 12px 20px; font-size: 18px; }
  nav { display: flex; gap: 4px; padding: 8px 20px; background: #fff; border-bottom: 1px solid #ddd; }
  nav button { border: 0; background: #eee; padding: 8px 16px; border-radius: 8px; cursor: pointer; }
  nav button.active { background: #0071e3; color: #fff; }
  main { padding: 20px; }
  .panel { display: none; }
  .panel.active { display: block; }
  .card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  .dot.on { background: #34c759; } .dot.off { background: #ff3b30; }
  pre { background: #111; color: #ddd; padding: 12px; border-radius: 8px; height: 60vh; overflow: auto; white-space: pre-wrap; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid #eee; padding: 6px 8px; text-align: left; }
  .cols { display: flex; gap: 12px; } .cols .card { flex: 1; }
  button.act { background: #0071e3; color: #fff; border: 0; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
  button.act:disabled { background: #999; cursor: not-allowed; }
  input { padding: 8px; border: 1px solid #ccc; border-radius: 6px; width: 60%; }
</style>
</head>
<body>
<header>🛠 运维控制台</header>
<nav>
  <button data-tab="health" class="active">健康</button>
  <button data-tab="logs">日志</button>
  <button data-tab="sessions">会话</button>
  <button data-tab="config">配置</button>
  <button data-tab="publish">发布</button>
</nav>
<main>
  <section id="health" class="panel active"></section>
  <section id="logs" class="panel">
    <div id="logTabs"></div>
    <pre id="logBox"></pre>
  </section>
  <section id="sessions" class="panel"></section>
  <section id="config" class="panel"></section>
  <section id="publish" class="panel">
    <div class="card">
      <button class="act" id="btnRollout">金丝雀发布（rollout）</button>
      <span id="rolloutHint"></span>
    </div>
    <div class="card">
      <input id="promoteMsg" placeholder="改动说明，如 feat: 新增 xxx" disabled>
      <button class="act" id="btnPromote" disabled>升级 bot3（promote）</button>
    </div>
    <pre id="pubBox"></pre>
  </section>
</main>
<script>
const $ = s => document.querySelector(s);
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  b.classList.add('active'); $('#' + b.dataset.tab).classList.add('active');
  if (b.dataset.tab === 'sessions') loadSessions();
  if (b.dataset.tab === 'config') loadConfig();
});

// 健康
async function loadHealth() {
  const r = await fetch('/api/health'); const d = await r.json();
  $('#health').innerHTML = d.bots.map(b => `
    <div class="card">
      <b><span class="dot ${b.alive ? 'on' : 'off'}"></span>${b.name}</b>（${b.label}）
      <div>PID: ${b.pid || '—'} ｜ 版本: ${b.version || '—'}${b.dirty ? ' ⚠️未提交改动' : ''}</div>
      <div>last-good: ${b.last_good || '—'} ｜ 启动: ${b.started || '—'}</div>
    </div>`).join('');
}
setInterval(() => { if ($('#health').classList.contains('active')) loadHealth(); }, 5000);
loadHealth();

// 日志
let logES = null;
function openLog(bot) {
  if (logES) logES.close();
  $('#logBox').textContent = '';
  logES = new EventSource('/api/logs/stream?bot=' + bot);
  logES.onmessage = e => { const p = $('#logBox'); p.textContent += e.data + '\n'; p.scrollTop = p.scrollHeight; };
}
$('#logTabs').innerHTML = ['bot1','bot2','bot3'].map(b => `<button onclick="openLog('${b}')">${b}</button>`).join(' ');
openLog('bot1');

// 会话
async function loadSessions() {
  const d = (await (await fetch('/api/sessions')).json()).sessions;
  $('#sessions').innerHTML = Object.entries(d).map(([bot, rows]) => `
    <div class="card"><b>${bot}</b>${rows.length ? `
      <table><tr><th>用户</th><th>chat</th><th>模型</th><th>模式</th><th>cwd</th><th>session</th><th>开始</th></tr>
      ${rows.map(r => `<tr><td>${r.user}</td><td>${r.chat}</td><td>${r.model}</td><td>${r.permission_mode}</td><td>${r.cwd}</td><td>${(r.session_id||'').slice(0,8)}</td><td>${r.started_at}</td></tr>`).join('')}
      </table>` : '<div>无会话</div>'}</div>`).join('');
}

// 配置
async function loadConfig() {
  const d = (await (await fetch('/api/config')).json()).configs;
  $('#config').innerHTML = '<div class="cols">' + Object.entries(d).map(([bot, cfg]) => `
    <div class="card"><b>${bot}</b>
    ${Object.entries(cfg).map(([k,v]) => `<div><code>${k}</code> = ${v}</div>`).join('')}
    </div>`).join('') + '</div>';
}

// 发布
function streamPost(url, body, onDone) {
  $('#pubBox').textContent = '';
  fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : null})
    .then(async resp => {
      if (resp.status === 409) { $('#pubBox').textContent = '已有发布任务在执行，请稍候。'; return; }
      if (resp.status === 400) { $('#pubBox').textContent = '改动说明不能为空。'; return; }
      const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = '';
      while (true) {
        const {value, done} = await reader.read(); if (done) break;
        buf += dec.decode(value, {stream:true});
        const parts = buf.split('\n\n'); buf = parts.pop();
        for (const p of parts) if (p.startsWith('data: ')) {
          $('#pubBox').textContent += p.slice(6) + '\n'; $('#pubBox').scrollTop = $('#pubBox').scrollHeight;
        }
      }
      onDone && onDone($('#pubBox').textContent);
    });
}
$('#btnRollout').onclick = () => streamPost('/api/rollout', null, txt => {
  if (txt.includes('金丝雀 bot1/bot2 已加载新代码')) {
    $('#promoteMsg').disabled = false; $('#btnPromote').disabled = false;
    $('#rolloutHint').textContent = ' ✅ 金丝雀通过，去飞书实测后再升级 bot3';
  } else {
    $('#rolloutHint').textContent = ' ❌ 未通过（见日志），已自动回滚';
  }
});
$('#btnPromote').onclick = () => streamPost('/api/promote', {message: $('#promoteMsg').value});
</script>
</body>
</html>
```

- [ ] **Step 2: 手动验证前端**

Run:
```bash
cd /Users/wanlizhu/projects/feishu-claude-code
.venv/bin/python -m uvicorn console.server:app --host 127.0.0.1 --port 9990 &
sleep 3 && curl -s localhost:9990/api/health | head -c 300; echo
curl -s localhost:9990/ | grep -q "运维控制台" && echo "HTML OK"
kill %1
```
Expected: `/api/health` 返回含三 bot 的 JSON；打印 `HTML OK`。浏览器开 `http://127.0.0.1:9990` 五个 tab 都能渲染。

- [ ] **Step 3: 提交**

```bash
git add console/static/index.html
git commit -m "feat: 控制台单页前端"
```

---

### Task 9: launchd 自启 + README + 手动验证清单

**Files:**
- Create: `deploy/com.feishu-claude.console.plist`
- Modify: `README.md`（新增"运维控制台"段落）

**Interfaces:** 无代码接口；交付自启配置与文档。

- [ ] **Step 1: 创建 `deploy/com.feishu-claude.console.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.feishu-claude.console</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/wanlizhu/projects/feishu-claude-code/.venv/bin/python</string>
    <string>-m</string><string>uvicorn</string>
    <string>console.server:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>9990</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/wanlizhu/projects/feishu-claude-code</string>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/feishu-claude-console.log</string>
  <key>StandardErrorPath</key><string>/tmp/feishu-claude-console.log</string>
</dict>
</plist>
```

- [ ] **Step 2: 安装并验证自启**

Run:
```bash
cp deploy/com.feishu-claude.console.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.feishu-claude.console.plist
sleep 4
launchctl list | grep console
curl -s localhost:9990/api/health | head -c 120; echo
```
Expected: `launchctl list` 见 `com.feishu-claude.console` 且 PID 非 `-`；curl 返回 JSON。

- [ ] **Step 3: README 增补"运维控制台"段落**

在 `README.md` 末尾追加：用途、启动方式（launchd 自启 / 手动 `uvicorn` 命令）、访问地址 `http://127.0.0.1:9990`、五面板说明、"仅本机只读、发布是唯一写操作、secret 全打码"的安全说明。

- [ ] **Step 4: 手动验证清单（人工执行，不自动化——会真重启线上 bot）**

逐项确认：
1. 浏览器开 `127.0.0.1:9990`，健康面板三 bot 全绿、版本正确。
2. 日志面板切 bot1/2/3 都能实时滚动。
3. 会话面板各 bot 列表正确，open_id 全打码。
4. 配置面板三列对比，`*_SECRET` 全为 `****xxxx`，无明文。
5. （需要时）在主仓造一处无害改动 → 点【金丝雀发布】→ 观察 SSE 日志走完 `[1/3]→[3/3]` → 通过后【升级 bot3】解锁。**实际 promote 仅在确有发布需求时点。**

- [ ] **Step 5: 提交**

```bash
git add deploy/com.feishu-claude.console.plist README.md
git commit -m "feat: 控制台自启配置与文档"
```

---

## Self-Review

**1. Spec coverage：**
- §3 架构（独立服务/解耦/端口/依赖/自启）→ Task 1(依赖) + Task 7(app) + Task 9(plist) ✓
- §4.1 健康 → Task 2 + Task 8 ✓
- §4.2 日志 → Task 6 + Task 8 ✓
- §4.3 会话 → Task 4 + Task 8 ✓
- §4.4 配置（脱敏） → Task 1(mask) + Task 3 + Task 8 ✓
- §4.5 发布（两步 + 锁 + 防注入） → Task 5 + Task 7(锁/路由) + Task 8(两步 UI) ✓
- §5 错误处理（文件缺失→空、409、SSE 重连） → Task 4/7/8 ✓
- §6 测试策略 → 各 Task 的 TDD + Task 9 手动清单 ✓

**2. Placeholder scan：** 无 TBD/TODO；每个代码步骤含完整代码。Task 8/9 的前端与文档为单文件交付，已给出完整 HTML 与 plist。

**3. Type consistency：** `Bot` 字段（name/label/repo/log/sessions_dir/config_kind/config_path）在 Task 1 定义，Task 2/3/4/7 一致使用；`collect_health`/`read_bot_config`/`read_bot_sessions`/`build_*_cmd`/`stream_script`/`tail_log`/`publish_lock` 在 server.py 的 import 与各模块定义一致。
