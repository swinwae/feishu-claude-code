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
