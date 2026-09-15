#!/usr/bin/env python3
"""B05-B11 物理合表清单与正文声明的独立校验。

    python3 docs/api-database/verify_design.py                 日常检查：清单、正文、来源与统计
    python3 docs/api-database/verify_design.py --strict        交付冻结：待办同样失败
    python3 docs/api-database/verify_design.py --baseline PATH 本轮范围保护审计：核对受保护文件 SHA
    python3 docs/api-database/verify_design.py --report PATH   写入机器可读摘要

只使用 Python 3 标准库。校验对象是 table-manifest.json、迁移源码事实、19cac6e 正文快照、
正文可见声明和 index.html 统计口径。默认不载入历史 baseline；本轮交付的受保护文件审计必须显式
给出 --baseline。它不执行数据库迁移，也不证明任何表已在 PostgreSQL 创建或任何数据库行为已验证。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MANIFEST_PATH = HERE / "table-manifest.json"
INDEX_PATH = HERE / "index.html"
MIGRATION_DIR = REPO / "internal/database/migrations"

SOURCES = ("foundations.md",) + tuple(f"b{index:02d}.md" for index in range(12))
PROTECTED_CHAPTERS = ("b00.md", "b01.md", "b02.md", "b03.md", "b04.md")
CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)
DECL_RE = re.compile(r"^物理表：`([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)`$")
DECL_NEAR_RE = re.compile(r"^\**\s*物理表\s*[:：]")
STAT_RE = re.compile(r'<div class="n">(\d+)</div><div class="t">([^<]+)</div>')

ORIGINS = ("legacy_merge", "new", "new_required_dependency")
LEGACY_DISPOSITIONS = ("active", "deferred")
EXISTING_GROUPS = ("manual_baseline", "scan", "decision_chain")
ROLES = (
    "schema2_import_receipt",
    "candidate_version",
    "combination_version",
    "business_plan_version",
)


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.pending: List[str] = []
        self.notes: List[str] = []
        self.counts: Dict[str, object] = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def todo(self, message: str) -> None:
        self.pending.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def load_manifest(report: Report) -> Optional[dict]:
    if not MANIFEST_PATH.is_file():
        report.error(f"缺少清单文件: {MANIFEST_PATH.relative_to(REPO)}")
        return None
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.error(f"清单不是合法 JSON: {error}")
        return None
    if not isinstance(data, dict):
        report.error("清单顶层必须是对象")
        return None
    for key in ("manifest_version", "status", "existing", "batches", "legacy_tables", "target_tables"):
        if key not in data:
            report.error(f"清单缺少字段: {key}")
    return data


def scan_migrations() -> List[dict]:
    rows: List[dict] = []
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for match in CREATE_TABLE_RE.finditer(text):
            rows.append(
                {
                    "table": match.group(1),
                    "migration": path.name,
                    "line": text[: match.start()].count("\n") + 1,
                }
            )
    return rows


def check_existing(manifest: dict, migrations: List[dict], report: Report) -> None:
    """按显式分组清单核对已有表与迁移事实。

    每张已有表必须由某个分组用明确的 migration 清单拥有：清单未登记的迁移整文件报错，
    不能沿用“不是 0007 就并入手册基线”的隐式归类，否则上游新增迁移会被静默算进旧基线。
    """
    existing = manifest.get("existing") or {}
    listed = existing.get("tables")
    if not isinstance(listed, list):
        report.error("existing.tables 必须是列表")
        return
    names = [row.get("table") for row in listed if isinstance(row, dict)]
    if len(names) != len(set(names)):
        report.error("existing.tables 存在重复表名")

    owner: Dict[str, str] = {}
    group_counts: Dict[str, int] = {}
    for group in EXISTING_GROUPS:
        info = existing.get(group)
        if not isinstance(info, dict):
            report.error(f"existing.{group} 必须是对象")
            continue
        files = info.get("migrations")
        if not isinstance(files, list) or not files:
            report.error(f"existing.{group}.migrations 必须是非空列表")
            continue
        for name in files:
            if not isinstance(name, str) or not name:
                report.error(f"existing.{group}.migrations 含非法文件名: {name!r}")
                continue
            if not (MIGRATION_DIR / name).is_file():
                report.error(f"existing.{group} 登记的迁移文件不存在: {name}")
                continue
            previous = owner.get(name)
            if previous is not None:
                report.error(f"迁移 {name} 同时登记在 {previous} 与 {group}")
                continue
            owner[name] = group
        owned = [row for row in migrations if row["migration"] in set(files)]
        group_counts[group] = len(owned)
        if info.get("expected_count") != len(owned):
            report.error(
                f"{group} 应为 {len(owned)} 张，清单写 {info.get('expected_count')}"
            )
        declared = info.get("tables")
        if isinstance(declared, list):
            owned_names = {row["table"] for row in owned}
            if set(declared) != owned_names:
                missing_names = sorted(owned_names - set(declared))
                extra_names = sorted(set(declared) - owned_names)
                if missing_names:
                    report.error(f"{group} 漏登迁移表: {missing_names}")
                if extra_names:
                    report.error(f"{group} 登记了迁移中不存在的表: {extra_names}")

    unclassified = sorted(
        {row["migration"] for row in migrations if row["migration"] not in owner}
    )
    if unclassified:
        report.error(
            f"未归类迁移: {unclassified}（请在 existing 分组里显式登记，不能默认并入手册基线）"
        )

    actual = {row["table"]: (row["migration"], row["line"]) for row in migrations}
    listed_map = {
        row.get("table"): (row.get("migration"), row.get("line"))
        for row in listed
        if isinstance(row, dict)
    }
    if set(names) != set(actual):
        missing = sorted(set(actual) - set(names))
        extra = sorted(set(names) - set(actual))
        if missing:
            report.error(f"清单漏登迁移表: {missing}")
        if extra:
            report.error(f"清单登记了迁移中不存在的表: {extra}")
    for table, (migration, line) in actual.items():
        recorded = listed_map.get(table)
        if recorded != (migration, line):
            report.error(f"{table}: 清单的迁移位置 {recorded} 与源码 {(migration, line)} 不一致")
    for row in listed:
        if not isinstance(row, dict):
            continue
        group = row.get("group")
        expected_group = owner.get(str(row.get("migration")))
        if group not in EXISTING_GROUPS:
            report.error(f"{row.get('table')}: 分组 {group!r} 未登记")
        elif expected_group is not None and group != expected_group:
            report.error(
                f"{row.get('table')}: 分组写 {group}，但 {row.get('migration')} 属于 {expected_group}"
            )

    if existing.get("expected_total") != len(migrations):
        report.error(
            f"全量已有表应为 {len(migrations)} 张，清单写 {existing.get('expected_total')}"
        )
    manual = existing.get("manual_baseline") or {}
    system_table = manual.get("system_table")
    if system_table not in set(names):
        report.error(f"手册基线缺少系统表: {system_table}")
    business = len(
        [
            row
            for row in migrations
            if row["table"] != system_table and owner.get(row["migration"]) == "manual_baseline"
        ]
    )
    if manual.get("business_count") != business:
        report.error(f"手册基线业务表应为 {business} 张，清单写 {manual.get('business_count')}")
    report.counts["existing"] = {
        "manual_baseline": group_counts.get("manual_baseline", 0),
        "manual_business": business,
        "manual_system": group_counts.get("manual_baseline", 0) - business,
        "scan": group_counts.get("scan", 0),
        "decision_chain": group_counts.get("decision_chain", 0),
        "total": len(migrations),
    }


def check_batches(manifest: dict, report: Report) -> None:
    batches = manifest.get("batches")
    if not isinstance(batches, list):
        report.error("batches 必须是列表")
        return
    ids = [row.get("id") for row in batches if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        report.error("batches 存在重复 id")
    legacy = manifest.get("legacy_tables") or []
    targets = manifest.get("target_tables") or []
    for batch in batches:
        if not isinstance(batch, dict):
            report.error("batches 的元素必须是对象")
            continue
        batch_id = batch.get("id")
        legacy_count = sum(1 for row in legacy if row.get("batch") == batch_id)
        target_count = sum(1 for row in targets if row.get("batch") == batch_id)
        if batch.get("legacy_count") != legacy_count:
            report.error(
                f"{batch_id}: legacy_count 写 {batch.get('legacy_count')}，实际 {legacy_count}"
            )
        active_count = sum(
            1
            for row in legacy
            if row.get("batch") == batch_id and row.get("disposition") == "active"
        )
        deferred_count = sum(
            1
            for row in legacy
            if row.get("batch") == batch_id and row.get("disposition") == "deferred"
        )
        if batch.get("active_legacy_count") != active_count:
            report.error(
                f"{batch_id}: active_legacy_count 写 {batch.get('active_legacy_count')}，实际 {active_count}"
            )
        if batch.get("deferred_legacy_count") != deferred_count:
            report.error(
                f"{batch_id}: deferred_legacy_count 写 {batch.get('deferred_legacy_count')}，实际 {deferred_count}"
            )
        if batch.get("expected_target_count") != target_count:
            report.error(
                f"{batch_id}: expected_target_count 写 {batch.get('expected_target_count')}，实际 {target_count}"
            )
        chapters = batch.get("chapters")
        if not isinstance(chapters, list) or not chapters:
            report.error(f"{batch_id}: chapters 必须是非空列表")
            continue
        for chapter in chapters:
            if not (HERE / chapter).is_file():
                report.error(f"{batch_id}: 章节不存在 {chapter}")


def check_legacy(manifest: dict, report: Report) -> Dict[str, dict]:
    legacy = manifest.get("legacy_tables")
    targets = manifest.get("target_tables")
    if not isinstance(legacy, list) or not isinstance(targets, list):
        report.error("legacy_tables 与 target_tables 必须是列表")
        return {}
    target_map = {
        row.get("table"): row for row in targets if isinstance(row, dict) and row.get("table")
    }
    expected_total = (manifest.get("legacy_snapshot") or {}).get("expected_total")
    if expected_total != len(legacy):
        report.error(f"旧表总数应为 {expected_total}，实际 {len(legacy)}")
    seen: Dict[Tuple[str, str], int] = {}
    cache: Dict[Tuple[str, str], List[str]] = {}
    for row in legacy:
        if not isinstance(row, dict):
            report.error("legacy_tables 的元素必须是对象")
            continue
        key = (str(row.get("batch")), str(row.get("table")))
        seen[key] = seen.get(key, 0) + 1
        disposition = row.get("disposition")
        if disposition not in LEGACY_DISPOSITIONS:
            report.error(
                f"{row.get('batch')}:{row.get('table')} 的 disposition 必须是 {LEGACY_DISPOSITIONS}"
            )
        target = row.get("target")
        if disposition == "active" and target not in target_map:
            report.error(f"{row.get('batch')}:{row.get('table')} 的目标 {target} 不在 target_tables")
        if disposition == "deferred" and target is not None:
            report.error(f"{row.get('batch')}:{row.get('table')} 已延期但仍声明目标 {target}")
        source = row.get("source")
        if not isinstance(source, dict):
            report.error(f"{key[1]}: 缺少 source 快照")
            continue
        file = source.get("file")
        ref = source.get("ref")
        line = source.get("line")
        text = source.get("text")
        cache_key = (str(ref), str(file))
        if cache_key not in cache:
            try:
                result = subprocess.run(
                    ["git", "show", f"{ref}:{file}"],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as error:
                report.error(f"无法运行 git 读取快照: {error}")
                return target_map
            if result.returncode != 0:
                report.error(f"快照读取失败 {ref}:{file}: {result.stderr.strip()}")
                return target_map
            cache[cache_key] = result.stdout.split("\n")
        lines = cache[cache_key]
        if not isinstance(line, int) or line < 1 or line > len(lines):
            report.error(f"{file}:{line} 超出快照行数")
            continue
        if lines[line - 1].rstrip() != str(text).rstrip():
            report.error(
                f"{file}:{line} 内容与快照不符: {lines[line - 1][:60]!r} != {str(text)[:60]!r}"
            )
    duplicates = [f"{batch}:{table}" for (batch, table), count in seen.items() if count > 1]
    if duplicates:
        report.error(f"旧表在同一批次重复登记: {duplicates[:5]}")
    global_names = [row.get("table") for row in legacy if isinstance(row, dict)]
    repeated = sorted({name for name in global_names if global_names.count(name) > 1})
    if repeated:
        report.note(f"跨批次同名的旧表名（按批次分别登记）: {repeated}")
    report.counts["legacy"] = {"total": len(legacy)}
    active_total = sum(
        1 for row in legacy if isinstance(row, dict) and row.get("disposition") == "active"
    )
    deferred_total = sum(
        1 for row in legacy if isinstance(row, dict) and row.get("disposition") == "deferred"
    )
    snapshot = manifest.get("legacy_snapshot") or {}
    if snapshot.get("active_total") != active_total:
        report.error(
            f"活动旧提案总数应为 {snapshot.get('active_total')}，实际 {active_total}"
        )
    if snapshot.get("deferred_total") != deferred_total:
        report.error(
            f"延期旧提案总数应为 {snapshot.get('deferred_total')}，实际 {deferred_total}"
        )
    report.counts["legacy"].update(active=active_total, deferred=deferred_total)
    return target_map


def check_targets(manifest: dict, target_map: Dict[str, dict], report: Report) -> None:
    targets = manifest.get("target_tables") or []
    legacy = manifest.get("legacy_tables") or []
    batches = {row.get("id"): row for row in manifest.get("batches") or [] if isinstance(row, dict)}
    referenced = {
        row.get("target")
        for row in legacy
        if isinstance(row, dict) and row.get("disposition") == "active"
    }
    names = [row.get("table") for row in targets if isinstance(row, dict)]
    if len(names) != len(set(names)):
        report.error("target_tables 存在重复表名")
    for row in targets:
        if not isinstance(row, dict):
            report.error("target_tables 的元素必须是对象")
            continue
        table = row.get("table")
        batch_id = row.get("batch")
        origin = row.get("origin")
        if origin not in ORIGINS:
            report.error(f"{table}: origin 必须是 {ORIGINS}")
        batch = batches.get(batch_id)
        if batch is None:
            report.error(f"{table}: batch {batch_id} 未登记")
            continue
        if row.get("chapter") not in (batch.get("chapters") or []):
            report.error(f"{table}: chapter {row.get('chapter')} 不属于批次 {batch_id}")
        carries = row.get("carries")
        if not isinstance(carries, list) or not carries:
            report.error(f"{table}: carries 必须是非空列表")
        if origin == "legacy_merge" and table not in referenced:
            report.error(f"{table}: 标记 legacy_merge 但没有旧表映射到它")
        if origin in ("new", "new_required_dependency") and not row.get("note"):
            report.error(f"{table}: 新增表必须写明理由")
        if origin == "new_required_dependency":
            ref = row.get("design_ref")
            if not isinstance(ref, str) or not ref:
                report.error(f"{table}: new_required_dependency 必须给出 design_ref")
    for row in legacy:
        if (
            isinstance(row, dict)
            and row.get("disposition") == "active"
            and row.get("target") not in target_map
        ):
            report.error(f"{row.get('table')}: 目标不存在")
    new_only = [
        row.get("table")
        for row in targets
        if isinstance(row, dict) and row.get("origin") == "new"
    ]
    report.counts["targets"] = {"total": len(targets), "new_only": new_only}


def check_required_content(manifest: dict, report: Report) -> None:
    required = manifest.get("required_content")
    targets = {
        row.get("table"): row
        for row in manifest.get("target_tables") or []
        if isinstance(row, dict)
    }
    if not isinstance(required, list):
        report.error("required_content 必须是列表")
        return
    seen_roles = set()
    for row in required:
        if not isinstance(row, dict):
            report.error("required_content 的元素必须是对象")
            continue
        role = row.get("role")
        seen_roles.add(role)
        if role not in ROLES:
            report.error(f"required_content 角色未知: {role}")
            continue
        status = row.get("status")
        if status == "pending":
            report.todo(f"待登记 {role}: {row.get('note')}")
            continue
        target = targets.get(row.get("target"))
        if target is None:
            report.error(f"{role}: 目标 {row.get('target')} 不在 target_tables")
            continue
        if role not in (target.get("carries") or []):
            report.error(f"{role}: 目标 {row.get('target')} 的 carries 未包含该角色")
    missing = [role for role in ROLES if role not in seen_roles]
    if missing:
        report.error(f"required_content 缺少必须显式登记的角色: {missing}")


def check_paths(manifest: dict, report: Report) -> None:
    """清单只能引用仓库内相对路径，不能依赖 /tmp 或个人目录。"""

    def walk(value, path: str) -> None:
        if isinstance(value, str):
            if "/tmp/" in value or value.startswith("/home/"):
                report.error(f"清单含临时目录或用户目录路径: {path} = {value}")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(manifest, "")
    for batch in manifest.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        for key in ("plan_source", "plan_review"):
            source = batch.get(key)
            if source is None:
                continue
            if not isinstance(source, str) or source.startswith("/"):
                report.error(f"{batch.get('id')}: {key} 必须是仓库相对路径")
                continue
            if not (REPO / source).is_file():
                report.error(f"{batch.get('id')}: {key} 不存在 {source}")
    for row in manifest.get("target_tables") or []:
        if not isinstance(row, dict):
            continue
        ref = row.get("design_ref")
        if ref is None:
            continue
        if not isinstance(ref, str) or ref.startswith("/"):
            report.error(f"{row.get('table')}: design_ref 必须是仓库相对路径")
            continue
        if not (REPO / ref).is_file():
            report.error(f"{row.get('table')}: design_ref 不存在 {ref}")
    reviews = manifest.get("review_documents")
    if reviews is not None and not isinstance(reviews, list):
        report.error("review_documents 必须是列表")
    for ref in reviews or []:
        if not isinstance(ref, str) or ref.startswith("/"):
            report.error(f"review_documents 必须是仓库相对路径: {ref}")
            continue
        if not (REPO / ref).is_file():
            report.error(f"review_documents 不存在 {ref}")


def check_declarations(manifest: dict, report: Report) -> None:
    declaration = manifest.get("declaration") or {}
    allowed = set(declaration.get("chapters") or [])
    targets = {
        row.get("table"): row
        for row in manifest.get("target_tables") or []
        if isinstance(row, dict)
    }
    declared: Dict[str, List[Tuple[str, int]]] = {}
    for name in SOURCES:
        path = HERE / name
        if not path.is_file():
            report.error(f"缺少章节: {name}")
            continue
        in_fence = False
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = DECL_RE.match(line)
            if match:
                declared.setdefault(match.group(1), []).append((name, number))
                if name not in allowed:
                    report.error(f"{name}:{number} 受保护章节不应出现物理表声明")
                continue
            if DECL_NEAR_RE.match(line):
                report.error(f"{name}:{number} 声明格式不匹配: {line[:60]}")
    for table, places in declared.items():
        if len(places) > 1:
            report.error(f"{table}: 声明重复 {[f'{f}:{n}' for f, n in places]}")
        target = targets.get(table)
        if target is None:
            report.error(f"{table}: 正文声明未在清单登记（孤立声明）")
        elif target.get("chapter") != places[0][0]:
            report.error(
                f"{table}: 声明在 {places[0][0]}，清单要求 {target.get('chapter')}"
            )
    missing = [table for table in targets if table not in declared]
    for table in missing:
        row = targets[table]
        report.todo(f"待作者声明: {row.get('chapter')} 物理表：`{table}`")
    report.counts["declarations"] = {
        "declared": len([table for table in targets if table in declared]),
        "missing": len(missing),
    }


def is_table_sep(line: str) -> bool:
    row = line.strip()
    if "|" not in row:
        return False
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    cells = [cell.strip() for cell in row.split("|")]
    if not cells or any(not cell for cell in cells):
        return False
    return all(re.fullmatch(r":?-{2,}:?", cell) is not None for cell in cells)


def count_doc_tables(paths: Sequence[Path]) -> int:
    total = 0
    for path in paths:
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if line.startswith("```"):
                index += 1
                while index < len(lines) and not lines[index].strip().startswith("```"):
                    index += 1
                index += 1
                continue
            if "|" in line and index + 1 < len(lines) and is_table_sep(lines[index + 1]):
                total += 1
                index += 2
                while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                    index += 1
                continue
            index += 1
    return total


def check_html(manifest: dict, report: Report) -> None:
    if not INDEX_PATH.is_file():
        report.error("缺少 index.html，请先运行 python3 docs/api-database/render.py")
        return
    page = INDEX_PATH.read_text(encoding="utf-8")
    stats = {
        label: int(count)
        for count, label in STAT_RE.findall(page)
    }
    existing = manifest.get("existing") or {}
    manual = (existing.get("manual_baseline") or {}).get("expected_count")
    scan = (existing.get("scan") or {}).get("expected_count")
    decision = (existing.get("decision_chain") or {}).get("expected_count")
    design = len(manifest.get("target_tables") or [])
    expected = {
        "已有数据库表（手册基线）": manual,
        "扫描表（手册外）": scan,
        "决策链表（手册外）": decision,
        "B05-B11 设计表": design,
        "手册范围合计": manual + design,
        "全仓含扩展合计": manual + scan + decision + design,
    }
    for label, value in expected.items():
        if label not in stats:
            report.error(f"index.html 缺少统计标签: {label}")
        elif stats[label] != value:
            report.error(f"index.html 统计 {label} 应为 {value}，实际 {stats[label]}")
    if "表格" in stats:
        report.error("index.html 仍使用旧统计标签「表格」，应改为「说明表格」")
    if "接口与数据卡" in stats:
        report.error("index.html 仍把文档卡片计为接口与数据卡，应收敛为说明统计")
    if "全仓含扫描合计" in stats:
        report.error("index.html 仍使用旧统计标签「全仓含扫描合计」，应改为「全仓含扩展合计」")
    document_tables = count_doc_tables([HERE / name for name in SOURCES])
    if "说明表格" not in stats:
        report.error("index.html 缺少统计标签: 说明表格")
    elif stats["说明表格"] != document_tables:
        report.error(
            f"说明表格应为 {document_tables}，index.html 实际 {stats['说明表格']}"
        )
    report.counts["document_tables"] = document_tables
    report.counts["html"] = stats
    report.note(
        "数据库表数来自迁移与清单；说明表格是文档统计，两者分列"
    )


def normalize_baseline(data) -> Tuple[Optional[Dict[str, str]], Dict[str, str]]:
    """只支持本轮 {sha256: {...}} 结构与约定的裸字典 {path: hash}。"""
    if not isinstance(data, dict):
        return None, {}
    if isinstance(data.get("sha256"), dict):
        meta = {key: data.get(key) for key in ("commit", "scope") if data.get(key)}
        return {str(key): str(value) for key, value in data["sha256"].items()}, meta
    if data and all(isinstance(value, str) for value in data.values()):
        return {str(key): str(value) for key, value in data.items()}, {}
    return None, {}


def check_baseline(path: Optional[Path], report: Report) -> None:
    """本轮范围保护审计；默认不跑，避免把历史 417 项变成日常门槛。"""
    if path is None:
        report.note("未指定 --baseline：跳过受保护文件 SHA 审计；本轮交付审计需显式给出")
        return
    if not path.is_file():
        report.error(f"baseline 不存在: {path}")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.error(f"baseline 不是合法 JSON: {error}")
        return
    entries, meta = normalize_baseline(data)
    if entries is None:
        report.error(f"baseline 结构无法识别: {path}")
        return
    mismatched = []
    missing = []
    for relative, digest in sorted(entries.items()):
        target = REPO / relative
        if not target.is_file():
            missing.append(relative)
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            mismatched.append(relative)
    if missing:
        report.error(f"baseline 列出的文件不存在: {missing[:5]}")
    if mismatched:
        report.error(f"受保护文件 SHA-256 不匹配: {mismatched[:8]}")
    try:
        shown = str(path.relative_to(REPO))
    except ValueError:
        shown = str(path)
    report.counts["baseline"] = {
        "path": shown,
        "entries": len(entries),
        "mismatched": len(mismatched),
        "commit": meta.get("commit"),
    }


def report_json(report: Report) -> dict:
    return {
        "status": "errors" if report.errors else ("pending" if report.pending else "ok"),
        "errors": list(report.errors),
        "pending": list(report.pending),
        "notes": list(report.notes),
        "counts": report.counts,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="校验 B05-B11 合表清单、正文声明与统计口径")
    parser.add_argument("--strict", action="store_true", help="待办项同样导致失败")
    parser.add_argument("--baseline", type=Path, default=None, help="baseline JSON 路径")
    parser.add_argument("--report", type=Path, default=None, help="写入机器可读摘要")
    args = parser.parse_args(argv)

    report = Report()
    manifest = load_manifest(report)
    if manifest is not None:
        status = manifest.get("status")
        if status not in ("in_progress", "design_only"):
            report.error(f"manifest.status 未知: {status}")
        if not manifest.get("status_note"):
            report.error("manifest 缺少 status_note：需要说明物理整理授权与候选状态不变的语义")
        strict = args.strict or status == "design_only"
        migrations = scan_migrations()
        check_existing(manifest, migrations, report)
        check_batches(manifest, report)
        target_map = check_legacy(manifest, report)
        check_targets(manifest, target_map, report)
        check_required_content(manifest, report)
        check_paths(manifest, report)
        check_declarations(manifest, report)
        check_html(manifest, report)
    else:
        strict = args.strict
    if manifest is not None:
        check_baseline(args.baseline, report)

    counts = report.counts
    existing = counts.get("existing") or {}
    legacy = counts.get("legacy") or {}
    targets = counts.get("targets") or {}
    print(
        "清单: 旧表 {legacy} 张 → 目标 {target} 张；已有手册基线 {manual} 张"
        "（业务 {business} + 系统 {system}）+ 扫描表 {scan} + 决策链表 {decision} = 全仓 {total}".format(
            legacy=legacy.get("total"),
            target=targets.get("total"),
            manual=existing.get("manual_baseline"),
            business=existing.get("manual_business"),
            system=existing.get("manual_system"),
            scan=existing.get("scan"),
            decision=existing.get("decision_chain"),
            total=existing.get("total"),
        )
    )
    manual = existing.get("manual_baseline") or 0
    design = targets.get("total") or 0
    scan = existing.get("scan") or 0
    decision = existing.get("decision_chain") or 0
    print(
        f"统计口径: 手册范围 {manual + design} = {manual} + {design}；"
        f"全仓含扩展 {manual + scan + decision + design}"
    )
    print(
        "文档统计: 说明表格 {tables} 张（与数据库表数分列）".format(
            tables=counts.get("document_tables")
        )
    )
    declarations = counts.get("declarations") or {}
    print(
        f"正文声明: 已声明 {declarations.get('declared')} / 待声明 {declarations.get('missing')}"
    )
    for note in report.notes:
        print(f"提示: {note}")
    for item in report.pending:
        print(f"待办: {item}")
    for item in report.errors:
        print(f"错误: {item}", file=sys.stderr)

    payload = report_json(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    failed = bool(report.errors) or (strict and bool(report.pending))
    print(
        "FAIL: {errors} 个错误，{pending} 个待办".format(
            errors=len(report.errors), pending=len(report.pending)
        )
        if failed
        else "OK: 清单结构、迁移事实、快照来源、正文声明与统计口径通过（待办 {pending}）".format(
            pending=len(report.pending)
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
