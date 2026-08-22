"""把 Locust CSV 汇总成一份便于阅读的中文报告。"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def read_aggregate(path: Path) -> dict[str, str] | None:
    rows = read_csv(path)
    for row in rows:
        if row.get("Name") == "Aggregated":
            return row
    return rows[-1] if rows else None


def number(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def integer(row: dict[str, str], key: str) -> int:
    return int(number(row, key))


def percentile(row: dict[str, str], name: str) -> int:
    return round(number(row, name))


def memory_to_mib(value: str) -> float:
    used = value.split("/", maxsplit=1)[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*([KMGT]?i?B)", used, re.IGNORECASE)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = match.group(2).lower()
    factors = {
        "b": 1 / (1024 * 1024),
        "kb": 1 / 1024,
        "kib": 1 / 1024,
        "mb": 1,
        "mib": 1,
        "gb": 1024,
        "gib": 1024,
        "tb": 1024 * 1024,
        "tib": 1024 * 1024,
    }
    return amount * factors.get(unit, 0)


def percentage(value: str) -> float:
    try:
        return float(value.strip().removesuffix("%"))
    except ValueError:
        return 0.0


def read_resource_peaks(results_dir: Path) -> dict[str, dict[str, dict[str, float]]]:
    peaks: dict[str, dict[str, dict[str, float]]] = {}
    for stats_path in sorted(results_dir.glob("*-docker-stats.csv")):
        prefix = stats_path.name.removesuffix("-docker-stats.csv")
        stage_peaks: dict[str, dict[str, float]] = {}
        for row in read_csv(stats_path):
            container_name = row.get("name", "")
            if "-backend-" in container_name:
                service = "backend"
            elif "-postgres-" in container_name:
                service = "postgres"
            elif "-redis-" in container_name:
                service = "redis"
            else:
                continue
            current = stage_peaks.setdefault(service, {"cpu": 0.0, "memory_mib": 0.0})
            current["cpu"] = max(
                current["cpu"],
                percentage(row.get("cpu") or ""),
            )
            current["memory_mib"] = max(
                current["memory_mib"],
                memory_to_mib(row.get("memory") or ""),
            )
        peaks[prefix] = stage_peaks
    return peaks


def stage_by_prefix(
    summaries: list[dict[str, object]],
    prefix: str,
) -> dict[str, object] | None:
    return next((item for item in summaries if item["prefix"] == prefix), None)


def stage_has_unfinished_tasks(results_dir: Path, prefix: str) -> bool:
    log_path = results_dir / f"{prefix}.log"
    if not log_path.exists():
        return False
    raw = log_path.read_bytes()
    try:
        log_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        log_text = raw.decode("gb18030", errors="replace")
    return "Not all users finished their tasks" in log_text


def build_conclusions(
    summaries: list[dict[str, object]],
    resource_peaks: dict[str, dict[str, dict[str, float]]],
    results_dir: Path,
) -> list[str]:
    if not summaries:
        return ["- 没有找到可分析的 Locust 汇总数据。"]

    total_requests = sum(int(item["requests"]) for item in summaries)
    total_failures = sum(int(item["failures"]) for item in summaries)
    conclusions = []
    if total_failures == 0:
        conclusions.append(
            f"- 共完成 {total_requests} 次请求，Locust 记录到 0 次失败。"
        )
    else:
        failure_rate = total_failures / total_requests * 100 if total_requests else 0.0
        conclusions.append(
            f"- 共完成 {total_requests} 次请求，其中 {total_failures} 次失败，"
            f"整体错误率为 {failure_rate:.2f}%。"
        )

    mixed = stage_by_prefix(summaries, "04-mixed")
    if mixed and int(mixed["p95"]) >= 5000:
        conclusions.append(
            f"- 复杂读写场景 P95 为 {int(mixed['p95']) / 1000:.1f} 秒，"
            "请求已经出现明显排队。"
        )

    peak = stage_by_prefix(summaries, "05-peak")
    if peak:
        users = peak["stage"].get("users", "?")  # type: ignore[union-attr]
        peak_p95 = int(peak["p95"])
        unfinished = stage_has_unfinished_tasks(results_dir, "05-peak")
        if unfinished:
            conclusions.append(
                f"- {users} 用户峰值场景 P95 为 {peak_p95 / 1000:.1f} 秒，"
                "停止时仍有任务未完成；这表示系统已经过载，不能解释为支持该并发量。"
            )
        elif peak_p95 >= 10000:
            conclusions.append(
                f"- {users} 用户峰值场景 P95 为 {peak_p95 / 1000:.1f} 秒，"
                "延迟已经很高，不能只根据 0 失败判断容量。"
            )

    auth_peaks = resource_peaks.get("02-auth", {}).get("backend", {})
    if auth_peaks:
        conclusions.append(
            "- 认证突发阶段 Backend 资源峰值为 "
            f"{auth_peaks.get('cpu', 0.0):.0f}% CPU、"
            f"{auth_peaks.get('memory_mib', 0.0) / 1024:.2f} GiB 内存；"
            "密码哈希是本轮最明显的资源峰值。"
        )

    chat = stage_by_prefix(summaries, "06-chat")
    if chat:
        conclusions.append(
            f"- 真实聊天完成 {chat['requests']} 次请求，失败 {chat['failures']} 次，"
            f"平均响应 {int(chat['average']) / 1000:.1f} 秒。"
        )

    conclusions.append("- 结果来自单机学习环境，不代表生产服务器容量。")
    return conclusions


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("用法：summarize.py <results_dir> <metadata.json> <report.md>")

    results_dir = Path(sys.argv[1])
    metadata = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    report_path = Path(sys.argv[3])
    stage_by_prefix = {
        stage["prefix"]: stage for stage in metadata.get("stages", [])
    }

    summaries = []
    for stats_path in sorted(results_dir.glob("*_stats.csv")):
        prefix = stats_path.name.removesuffix("_stats.csv")
        row = read_aggregate(stats_path)
        if not row:
            continue
        requests = integer(row, "Request Count")
        failures = integer(row, "Failure Count")
        summaries.append(
            {
                "prefix": prefix,
                "stage": stage_by_prefix.get(prefix, {}),
                "requests": requests,
                "failures": failures,
                "failure_rate": failures / requests * 100 if requests else 0.0,
                "rps": number(row, "Requests/s"),
                "average": round(number(row, "Average Response Time")),
                "p95": percentile(row, "95%"),
                "p99": percentile(row, "99%"),
                "maximum": round(number(row, "Max Response Time")),
            }
        )

    resource_peaks = read_resource_peaks(results_dir)
    git_dirty = metadata.get("git_dirty")
    if git_dirty is True:
        git_worktree = "有未提交修改"
    elif git_dirty is False:
        git_worktree = "干净"
    else:
        git_worktree = "未记录"

    lines = [
        "# V2 全面压测报告",
        "",
        f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## 测试环境",
        "",
        f"- Git 提交：`{metadata.get('git_commit', 'unknown')}`",
        f"- Git 工作区：{git_worktree}",
        f"- 目标地址：`{metadata.get('target', 'unknown')}`",
        f"- 测试配置：`{metadata.get('profile', 'unknown')}`",
        f"- CPU：{metadata.get('cpu', 'unknown')}",
        f"- 内存：{metadata.get('memory_gb', 'unknown')} GB",
        f"- 预置压测身份：{metadata.get('seeded_users', 'unknown')} 个",
        f"- 阶段冷却：{metadata.get('cooldown_seconds', 'unknown')} 秒",
        f"- 后端进程：{metadata.get('backend_workers', 'unknown')} 个 Uvicorn worker",
        "- 数据隔离：独立 PostgreSQL volume 和独立 Redis，不使用正式用户数据",
        "- 知识库：独立运行的 WeKnora，聊天场景调用真实模型与混合检索",
        "",
        "## 汇总",
        "",
        "| 场景 | 用户数 | 时长 | 请求数 | 失败数 | 错误率 | RPS | 平均 | P95 | P99 | 最大 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for item in summaries:
        stage = item["stage"]
        lines.append(
            "| {name} | {users} | {duration} | {requests} | {failures} | "
            "{failure_rate:.2f}% | {rps:.2f} | {average}ms | {p95}ms | "
            "{p99}ms | {maximum}ms |".format(
                name=stage.get("name", item["prefix"]),
                users=stage.get("users", "?"),
                duration=stage.get("duration", "?"),
                **item,
            )
        )

    lines.extend(["", "## 失败明细", ""])
    has_failures = False
    for failure_path in sorted(results_dir.glob("*_failures.csv")):
        failures = read_csv(failure_path)
        if not failures:
            continue
        has_failures = True
        lines.append(f"### {failure_path.name.removesuffix('_failures.csv')}")
        lines.append("")
        lines.append("| 接口 | 次数 | 错误 |")
        lines.append("| --- | ---: | --- |")
        for failure in failures:
            error = (failure.get("Error") or "").replace("|", "\\|")
            lines.append(
                f"| {failure.get('Name', '')} | {failure.get('Occurrences', '0')} | {error} |"
            )
        lines.append("")
    if not has_failures:
        lines.append("Locust 没有记录到请求失败。")

    lines.extend(
        [
            "",
            "## 容器资源峰值",
            "",
            "| 场景 | Backend CPU | Backend 内存 | PostgreSQL CPU | PostgreSQL 内存 | Redis CPU | Redis 内存 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in summaries:
        stage = item["stage"]
        peaks = resource_peaks.get(item["prefix"], {})
        backend = peaks.get("backend", {})
        postgres = peaks.get("postgres", {})
        redis = peaks.get("redis", {})
        lines.append(
            "| {name} | {backend_cpu:.2f}% | {backend_memory:.1f} MiB | "
            "{postgres_cpu:.2f}% | {postgres_memory:.1f} MiB | "
            "{redis_cpu:.2f}% | {redis_memory:.1f} MiB |".format(
                name=stage.get("name", item["prefix"]),
                backend_cpu=backend.get("cpu", 0.0),
                backend_memory=backend.get("memory_mib", 0.0),
                postgres_cpu=postgres.get("cpu", 0.0),
                postgres_memory=postgres.get("memory_mib", 0.0),
                redis_cpu=redis.get("cpu", 0.0),
                redis_memory=redis.get("memory_mib", 0.0),
            )
        )

    lines.extend(["", "## 测试结论", ""])
    lines.extend(build_conclusions(summaries, resource_peaks, results_dir))

    lines.extend(
        [
            "",
            "## 如何阅读",
            "",
            "- 错误率比单纯 RPS 更重要；先解决失败，再追求吞吐量。",
            "- P95 表示 95% 请求不超过该时间，P99 更能反映高峰抖动。",
            "- 基础接口和聊天接口不能直接比较：聊天还包含模型 API 与 WeKnora 延迟。",
            "- 业务场景使用预置 JWT，统计不包含注册和登录准备时间；认证突发单独统计。",
            "- 峰值场景使用更短等待时间，用来观察过载表现，不代表日常稳定容量。",
            "- 这是单机学习环境结果，不代表生产服务器容量。",
            "",
            "## 原始结果",
            "",
            f"CSV、HTML、日志保存在本机：`{results_dir}`",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
