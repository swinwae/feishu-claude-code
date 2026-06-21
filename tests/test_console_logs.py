import asyncio
from unittest.mock import patch, AsyncMock
from asyncio import subprocess as subproc_module


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


def test_tail_log_closes_subprocess_on_generator_aclose(tmp_path):
    """验证生成器 aclose() 后，子进程被杀死（不留孤儿）。"""
    from console.logs import tail_log
    import console.logs

    f = tmp_path / "x.log"
    f.write_text("a\nb\nc\n", encoding="utf-8")

    captured_proc = None

    async def run_test():
        nonlocal captured_proc

        # 用 patch 包裹 asyncio.create_subprocess_exec，记录返回的子进程对象
        original_create_subprocess_exec = asyncio.create_subprocess_exec

        async def patched_create_subprocess_exec(*args, **kwargs):
            nonlocal captured_proc
            captured_proc = await original_create_subprocess_exec(*args, **kwargs)
            return captured_proc

        with patch("asyncio.create_subprocess_exec", side_effect=patched_create_subprocess_exec):
            gen = tail_log(str(f), lines=2)

            # 取一行，确保子进程已启动
            line = await gen.__anext__()
            assert line.strip() == "b"
            assert captured_proc is not None

            # 此时子进程应该还在运行
            assert captured_proc.returncode is None, "子进程应该还在运行"

            # 关闭生成器，触发 finally 清理
            await gen.aclose()

            # 子进程应该已被 kill 并 wait，returncode 应该非 None
            assert captured_proc.returncode is not None, "子进程应该已被终止"

    asyncio.run(run_test())
