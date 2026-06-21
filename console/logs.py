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
