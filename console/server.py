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


class _LockGuardedStream:
    """包裹一个异步生成器，保证发布锁在恰好一次的时机被释放。

    不能简单依赖 “async generator 内部 try/finally” 来释放锁：
    若生成器从未被迭代过就被 aclose()（例如调用方拿到响应后从不消费流），
    Python 不会运行尚未启动的 async generator 的 finally 块，锁会被永久泄漏。
    这里改用显式包装的异步迭代器，在 __anext__ 的正常结束/异常路径，
    以及 aclose() 路径上都主动释放一次，从而保证“已 acquire 但流未消费”
    的场景也能正确释放锁。
    """

    def __init__(self, agen):
        self._agen = agen
        self._released = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self._agen.__anext__()
        except StopAsyncIteration:
            self._release_once()
            raise
        except BaseException:
            self._release_once()
            raise

    async def aclose(self):
        await self._agen.aclose()
        self._release_once()

    def _release_once(self):
        if not self._released:
            self._released = True
            publish_lock.release()


async def _run_publish(cmd):
    if publish_lock.locked():
        return JSONResponse({"ok": False, "error": "已有发布任务在执行"}, status_code=409)
    # 关键修复：检测与获取之间不能有 await 挂起点。
    # locked() 是同步调用，锁空闲时 acquire() 不会挂起，
    # 二者之间没有切换点，因此在单线程事件循环里这一段是原子的，
    # 从而消除“两个请求都看到 locked()==False 然后都拿到 200”的 TOCTOU 竞态。
    await publish_lock.acquire()
    return _sse(_LockGuardedStream(stream_script(cmd)))


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
