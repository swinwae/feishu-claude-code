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
