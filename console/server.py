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
