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
