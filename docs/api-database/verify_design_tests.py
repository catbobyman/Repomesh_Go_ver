#!/usr/bin/env python3
"""verify_design.py 的失败用例测试。

在临时副本里注入清单、声明和受保护文件错误，断言校验器报出预期错误，而不是任意异常。
临时副本只包含合成章节与清单，不读写仓库正文；git 快照与迁移目录通过符号链接读取。

    python3 docs/api-database/verify_design_tests.py      全部用例通过时退出码 0
    KEEP=1 python3 docs/api-database/verify_design_tests.py  保留临时目录
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASELINE = REPO / "docs/development/2026-09-15-table-consolidation-01/baseline.json"
CHAPTERS = ("foundations.md",) + tuple(f"b{index:02d}.md" for index in range(12))
TMP_ROOTS: List[Path] = []
FAILURES: List[str] = []


def make_stage() -> Path:
    root = Path(tempfile.mkdtemp(prefix="verify-design-tests-"))
    TMP_ROOTS.append(root)
    api = root / "docs" / "api-database"
    api.mkdir(parents=True)
    (root / "docs" / "development").symlink_to(REPO / "docs" / "development")
    (root / "internal").symlink_to(REPO / "internal")
    (root / ".git").symlink_to(REPO / ".git")
    shutil.copy(HERE / "verify_design.py", api / "verify_design.py")
    manifest = json.loads((HERE / "table-manifest.json").read_text(encoding="utf-8"))
    write_chapters(api, manifest)
    write_index(api, manifest)
    save_manifest(api, manifest)
    return api


def write_chapters(api: Path, manifest: dict) -> None:
    (api / "foundations.md").write_text(
        "# 共同规则\n\n测试占位。\n\n| 字段 | 类型 |\n| --- | --- |\n| id | text |\n",
        encoding="utf-8",
    )
    for index in range(12):
        name = f"b{index:02d}.md"
        lines = [
            f"# {name.upper()} 测试占位",
            "",
            "| 字段 | 类型 |",
            "| --- | --- |",
            "| id | text |",
        ]
        for row in manifest.get("target_tables") or []:
            if row.get("chapter") == name:
                lines += ["", f"## {row['table']}", "", f"物理表：`{row['table']}`"]
        (api / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index(api: Path, manifest: dict) -> None:
    existing = manifest.get("existing") or {}
    manual = (existing.get("manual_baseline") or {}).get("expected_count", 0)
    scan = (existing.get("scan") or {}).get("expected_count", 0)
    design = len(manifest.get("target_tables") or [])
    stats = [
        ("已有数据库表（手册基线）", manual),
        ("扫描表（手册外）", scan),
        ("B05-B11 设计表", design),
        ("手册范围合计", manual + design),
        ("全仓含扫描合计", manual + scan + design),
        ("说明表格", len(CHAPTERS)),
    ]
    body = "".join(
        f'<div class="stat"><div class="n">{value}</div><div class="t">{label}</div></div>'
        for label, value in stats
    )
    (api / "index.html").write_text(
        f'<html><body><div class="stats">{body}</div></body></html>\n', encoding="utf-8"
    )


def load_manifest(api: Path) -> dict:
    return json.loads((api / "table-manifest.json").read_text(encoding="utf-8"))


def save_manifest(api: Path, data: dict) -> None:
    (api / "table-manifest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def append(api: Path, name: str, text: str) -> None:
    with (api / name).open("a", encoding="utf-8") as handle:
        handle.write(text)


def run(api: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(api / "verify_design.py"), *args],
        capture_output=True,
        text=True,
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect(result: subprocess.CompletedProcess, needle: str) -> None:
    output = result.stdout + result.stderr
    check(result.returncode != 0, f"预期失败但退出码是 0: {output[:400]}")
    check(needle in output, f"缺少预期错误 {needle!r}: {output[:600]}")


def case_positive_control() -> None:
    api = make_stage()
    result = run(api)
    check(result.returncode == 0, f"合成清单应当通过: {result.stdout}{result.stderr}")
    check("OK:" in result.stdout, f"缺少 OK 输出: {result.stdout!r}")
    strict = run(api, "--strict")
    check(strict.returncode == 0, f"声明齐备时 --strict 应当通过: {strict.stdout}{strict.stderr}")


def case_missing_legacy_mapping() -> None:
    api = make_stage()
    data = load_manifest(api)
    removed = next(row for row in data["legacy_tables"] if row["batch"] == "b07")
    data["legacy_tables"].remove(removed)
    save_manifest(api, data)
    expect(run(api), "b07: legacy_count 写 1，实际 0")
    expect(run(api), "旧表总数应为 63，实际 62")


def case_duplicate_target() -> None:
    api = make_stage()
    data = load_manifest(api)
    data["target_tables"].append(dict(data["target_tables"][0]))
    save_manifest(api, data)
    expect(run(api), "target_tables 存在重复表名")


def case_duplicate_declaration() -> None:
    api = make_stage()
    data = load_manifest(api)
    table = next(row["table"] for row in data["target_tables"] if row["batch"] == "b09")
    append(api, "b09.md", f"物理表：`{table}`\n")
    expect(run(api), f"{table}: 声明重复")


def case_declaration_wrong_batch() -> None:
    api = make_stage()
    append(api, "b09.md", "物理表：`repomesh_execution.rounds`\n")
    expect(run(api), "repomesh_execution.rounds: 声明在 b09.md，清单要求 b10.md")


def case_orphan_declaration() -> None:
    api = make_stage()
    append(api, "b07.md", "物理表：`repomesh_issues.not_in_manifest`\n")
    expect(run(api), "repomesh_issues.not_in_manifest: 正文声明未在清单登记（孤立声明）")


def case_missing_policy_imports() -> None:
    api = make_stage()
    data = load_manifest(api)
    data["target_tables"] = [
        row for row in data["target_tables"] if row["table"] != "repomesh_sources.policy_imports"
    ]
    save_manifest(api, data)
    expect(
        run(api),
        "schema2_import_receipt: 目标 repomesh_sources.policy_imports 不在 target_tables",
    )


def case_missing_candidate_entity() -> None:
    api = make_stage()
    data = load_manifest(api)
    data["required_content"] = [
        row for row in data["required_content"] if row["role"] != "candidate_version"
    ]
    save_manifest(api, data)
    expect(run(api), "required_content 缺少必须显式登记的角色: ['candidate_version']")


def case_missing_business_plan_version() -> None:
    api = make_stage()
    data = load_manifest(api)
    data["required_content"] = [
        row for row in data["required_content"] if row["role"] != "business_plan_version"
    ]
    save_manifest(api, data)
    expect(run(api), "required_content 缺少必须显式登记的角色: ['business_plan_version']")


def case_missing_required_dependency_ref() -> None:
    api = make_stage()
    data = load_manifest(api)
    for row in data["target_tables"]:
        if row.get("origin") == "new_required_dependency":
            row.pop("design_ref", None)
    save_manifest(api, data)
    expect(run(api), "new_required_dependency 必须给出 design_ref")


def case_missing_declaration_strict() -> None:
    api = make_stage()
    data = load_manifest(api)
    table = next(row["table"] for row in data["target_tables"] if row["batch"] == "b10")
    text = (api / "b10.md").read_text(encoding="utf-8")
    (api / "b10.md").write_text(
        text.replace(f"物理表：`{table}`\n", "", 1), encoding="utf-8"
    )
    result = run(api)
    check(result.returncode == 0, f"进行中状态不应因待办失败: {result.stdout}{result.stderr}")
    check(f"待作者声明: b10.md 物理表：`{table}`" in result.stdout, f"缺少待办提示: {result.stdout}")
    expect(run(api, "--strict"), "FAIL:")


def case_protected_file_modified() -> None:
    api = make_stage()
    append(api, "b00.md", "\n被改动的受保护章节。\n")
    result = run(api, "--baseline", str(BASELINE))
    expect(result, "受保护文件 SHA-256 不匹配")
    check("docs/api-database/b00.md" in (result.stdout + result.stderr), "缺少被改文件路径")


CASES = (
    ("positive-control", case_positive_control),
    ("missing-legacy-mapping", case_missing_legacy_mapping),
    ("duplicate-target", case_duplicate_target),
    ("duplicate-declaration", case_duplicate_declaration),
    ("declaration-wrong-batch", case_declaration_wrong_batch),
    ("orphan-declaration", case_orphan_declaration),
    ("missing-policy-imports", case_missing_policy_imports),
    ("missing-candidate-entity", case_missing_candidate_entity),
    ("missing-business-plan-version", case_missing_business_plan_version),
    ("missing-required-dependency-ref", case_missing_required_dependency_ref),
    ("missing-declaration-strict", case_missing_declaration_strict),
    ("protected-file-modified", case_protected_file_modified),
)


def main() -> int:
    for name, function in CASES:
        try:
            function()
        except AssertionError as error:
            FAILURES.append(f"{name}: {error}")
            print(f"FAIL {name}: {error}")
        else:
            print(f"PASS {name}")
    if not os.environ.get("KEEP"):
        for root in TMP_ROOTS:
            shutil.rmtree(root, ignore_errors=True)
    print(f"\n{len(CASES) - len(FAILURES)}/{len(CASES)} 用例通过")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
