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
