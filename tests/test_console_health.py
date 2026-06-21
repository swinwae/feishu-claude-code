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
