# 运维控制台（Ops Console）设计文档

日期：2026-06-21
状态：待评审

## 1. 目标与边界

为 feishu-claude-code 的三 bot 部署提供一个**本机 web 可视化界面**，把日常运维从「终端 + 飞书卡片」搬到一个网页上：看健康、看日志、看会话、看配置，并以网页流程执行金丝雀发布。

**核心边界（已与用户确认）：**
- **独立服务**：不嵌入任何 bot。它要能重启包括 bot3 在内的所有 bot，自身生命周期必须独立。
- **唯一写操作 = 发布**（`rollout.sh` / `promote.sh`）。其余四块（健康、日志、会话、配置）**全部只读**。
- **免登录**：绑定 `127.0.0.1`，仅本机访问，不设密码。
- **绝不显示任何 secret**：读到 `*_SECRET` / `*_TOKEN` 一律打码（如 `cli_****b6`），不经接口回传明文。

**非目标（本期不做）：** 配置写入/编辑、停止单个用户会话、远程访问、多用户鉴权。这些留作后续可选开关。

## 2. 三 bot 事实清单（核准于 2026-06-21）

| bot | launchd label | 运行代码（git 仓） | 日志文件 | SESSIONS_DIR | 启动配置来源 |
|-----|---------------|-------------------|----------|--------------|--------------|
| bot1 | `com.feishu-claude.bot` | 主仓 `~/projects/feishu-claude-code` | `/tmp/feishu-claude.log` | `~/wly-work/.feishu-claude` | 主仓 `.env` |
| bot2 | `com.feishu-claude.bot2` | 主仓（同 working tree） | `/tmp/feishu-claude-2.log` | `~/zwl-work/.feishu-claude` | plist `EnvironmentVariables` |
| bot3 | `com.feishu-claude.bot3` | 副本 `~/projects/feishu-claude-code-bot3`（bot3-stable） | `/tmp/feishu-claude-3.log` | `~/.feishu-claude-bot3` | plist `EnvironmentVariables` |

要点：
- bot1/bot2 共跑主仓 working tree，git 版本一致（= 主仓 HEAD）；bot3 跑副本 HEAD。
- `git tag bot3-last-good`（在主仓）指向 bot3 当前已验证版本。
- 某些 `sessions.json` 可能不存在（如该 bot 尚无会话）→ 必须优雅处理为"无会话"。

这份清单集中放在后端一个 `BOTS` 注册表常量里，是全部面板的唯一数据源真相。

## 3. 架构

```
浏览器 (127.0.0.1:9990)
        │  HTTP / SSE
        ▼
console/server.py  (FastAPI + uvicorn, 独立 launchd: com.feishu-claude.console)
        ├── GET  /                  → 返回 console/static/index.html
        ├── GET  /api/health        → 三 bot 存活/PID/版本/tag（轮询，JSON）
        ├── GET  /api/logs/stream   → ?bot=1|2|3，SSE 实时 tail 日志
        ├── GET  /api/sessions      → 读各 bot sessions.json，脱敏后 JSON
        ├── GET  /api/config        → 读各 bot 启动配置，secret 打码后 JSON
        ├── POST /api/rollout       → 跑 rollout.sh，SSE 流式输出
        └── POST /api/promote       → 跑 promote.sh（带 message），SSE 流式输出
```

**代码位置**：主仓新增 `console/` 子目录（`server.py` + `static/index.html` + `bots.py` 注册表）。
- 影响评估：`rollout.sh` 用 `git ls-files '*.py' | grep -v '^tests/'` 做 py_compile，会把 `console/*.py` 纳入语法预检（无害，保持语法正确即可）；`promote.sh` 把主仓同步进 bot3 副本，`console/` 也会落到副本（bot3 不运行它，无害）。
- 控制台**不 import** bot 的 `bot_config`/`session_store`（那些模块依赖具体 bot 的 env，且会触发 `load_dotenv`）。控制台保持**解耦**：直接以纯文件方式读 `sessions.json`、`.env`、plist，以 subprocess 方式跑 `launchctl`/脚本。

**技术栈**：复用主仓 `.venv`，新增依赖 `fastapi` + `uvicorn`。
- 按 CLAUDE.md：改依赖需手动 `\.venv/bin/pip install fastapi uvicorn` 并重新验证；`promote` 只同步代码不碰依赖，故三 bot 不受影响（它们不依赖这两个包）。

**自启**：新增 `~/Library/LaunchAgents/com.feishu-claude.console.plist`，`KeepAlive=true`，启动命令 `\.venv/bin/python -m uvicorn console.server:app --host 127.0.0.1 --port 9990`，工作目录主仓。控制台日志 `/tmp/feishu-claude-console.log`。

## 4. 各面板设计

### 4.1 健康总览（只读，自动刷新）
数据来自 `GET /api/health`，前端每 5s 轮询。每 bot 展示：
- **存活/PID**：`launchctl list | awk '$3==label{print $1}'`，PID 为空或 `-` → 离线。
- **当前版本**：bot1/bot2 取主仓 `git rev-parse --short HEAD`；bot3 取副本。附 working tree 是否有未提交改动（`git diff --quiet`）。
- **最近重启**：以进程启动时间为准 `ps -o lstart= -p PID`；PID 不存在时回退为日志文件 mtime。
- **bot3-last-good**：主仓 `git rev-parse --short bot3-last-good`。
- 顶部一个总状态灯（三 bot 全绿/有离线）。

### 4.2 实时日志（只读）
`GET /api/logs/stream?bot=N`，后端用 `tail -F` 子进程或异步读文件增量，SSE 推送新行。前端 tab 切换 bot1/2/3，自动滚动到底，可暂停滚动。日志可能含路径但不含 secret（bot 自身不打印 secret）。

### 4.3 会话总览（只读）
`GET /api/sessions` 读三 bot 的 `sessions.json`。结构：`user_open_id → chat_key(private/群) → {current:{session_id, model, cwd, permission_mode, started_at, preview, workspace}, history:[...]}`。
- 按 bot 分组，列出每个用户每个 chat 的 `current`：模型、权限模式、cwd/workspace、session_id（短）、started_at、preview。
- open_id **打码**展示（如 `ou_****e889`）。
- 文件缺失/损坏 → 显示"该 bot 无会话"。

### 4.4 配置查看（只读）
`GET /api/config` 读各 bot 启动配置：bot1 读主仓 `.env`；bot2/bot3 用 `PlistBuddy -c "Print :EnvironmentVariables"` 读各自 plist。
- 展示 `DEFAULT_MODEL`、`PERMISSION_MODE`、`DEFAULT_CWD`、`SESSIONS_DIR`、`CALLBACK_PORT` 等。
- **任何 key 含 `SECRET`/`TOKEN`/`PASSWORD`（不分大小写）→ 打码**，例如只显示后 4 位。
- 并排三列方便对比三 bot 差异。

### 4.5 发布操作（唯一写操作）
两步流程，编码 CLAUDE.md 的发布纪律：
1. **金丝雀发布**：`POST /api/rollout` → 后端 `bash rollout.sh`，stdout/stderr 行级 SSE 推到页面日志区。
   - 脚本退出码 0 且输出含成功标志 → 前端解锁第 2 步【升级 bot3】。
   - 失败 → 展示脚本自己打印的自动回滚结果，第 2 步保持禁用。
2. **升级 bot3**：解锁后出现一个**改动说明输入框** + 【升级 bot3】按钮 → `POST /api/promote {message}` → 后端 `bash promote.sh "<message>"`，SSE 流式。
   - `promote.sh` 已处理"重启自己"竞态（异步延迟 kickstart + KeepAlive 兜底）；控制台是独立进程，不受 bot3 重启影响，能稳定收完输出。
   - 安全约束：`message` 仅作为单个参数传给脚本（用参数数组、不拼 shell），防注入。

并发保护：同一时刻只允许一个发布任务（rollout/promote）在跑，后端用一个 asyncio 锁；占用时其他发布请求返回 409。

## 5. 错误处理

- **launchctl/git/脚本** 调用失败 → 接口返回结构化错误 `{ok:false, error}`，前端 toast，不崩页面。
- **SSE 断线** → 前端自动重连（EventSource 默认重连）。
- **文件缺失**（sessions.json / 日志 / .env）→ 视为空数据，面板显示占位，不报错。
- **发布脚本非零退出** → 完整输出照样展示给用户判断，前端标红。
- **端口被占用** → uvicorn 启动失败，记 `/tmp/feishu-claude-console.log`，KeepAlive 会重试。

## 6. 测试策略

- **后端单测**（pytest，放 `tests/`）：
  - 健康解析：mock `launchctl list` / `git` 输出 → 断言状态结构。
  - 脱敏：含 `FEISHU_APP_SECRET` 的 dict/config → 断言输出已打码、无明文。
  - sessions 解析：喂样例 `sessions.json` → 断言提取的 current 字段；喂缺失文件 → 断言"无会话"。
  - promote 参数安全：断言 message 经参数数组传递、特殊字符不触发 shell。
- **发布流程**不写自动化测试（会真重启线上 bot）；改为手动验证清单（先在本机点 rollout 看金丝雀，再实测，再 promote）。
- 控制台是独立服务，**不经过** rollout/promote 自身的发布流程即可迭代（它不影响 bot 运行）；但其代码在主仓内，提交仍走功能分支。

## 7. 实现顺序（建议）

1. `console/bots.py` 注册表 + `server.py` 骨架 + `/api/health` + 最简 `index.html`（健康面板）。
2. 配置查看（脱敏）+ 会话总览（只读）。
3. 实时日志 SSE。
4. 发布操作（rollout → promote 两步流程 + 并发锁）。
5. launchd plist + 手动验证清单 + README 段落。

## 8. 未决/后续可选

- 配置**写入**与「保存并重启」按钮（本期只读）。
- 会话面板的「停止某用户任务」操作。
- 控制台基础鉴权（若日后需非本机访问）。
