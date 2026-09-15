#!/usr/bin/env python3
"""render.py 的独立验证脚本。

把真实章节和模板复制到临时目录，给尚未落地的 b00-b03 写最小占位来源，然后跑正向渲染、
同步只读、陈旧、缺来源、坏链接和吞字用例。临时副本里可以出现假章节，仓库里不会。

    python3 docs/api-database/verify_renderer.py           全部用例通过时退出码 0
    KEEP=1 python3 docs/api-database/verify_renderer.py     保留临时目录
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CHAPTERS = ("foundations.md",) + tuple(f"b{index:02d}.md" for index in range(12))
TMP_ROOTS: List[Path] = []
FAILURES: List[str] = []


def long_token() -> str:
    return "urn:repomesh:" + "verify-fixture:" * 6 + "end"


def fixture(name: str) -> str:
    label = name[:3].upper()
    return f"""# {label} 验证占位章节

本文件只存在于验证脚本的临时副本里，用于在真实 {label} 落地前检查生成器。

## 批次范围与状态

### 占位卡片

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | uuid | PK、必填 |
| 路径 | text | 可空 |
| 说明 | text | 已实现 &#124; 本次提案 |

裸尖括号文字 <ID> 与长标识 {long_token()} 必须原样出现在页面里。

### 设计理由

同章同名标题的第一个。

### 设计理由

同章同名标题的第二个。

## 链接

引用 [公共规则](./foundations.md#共同设计规则与阅读方法) 和 [真实文件](../../README.md)。
"""


def make_stage() -> Path:
    root = Path(tempfile.mkdtemp(prefix="verify-renderer-"))
    TMP_ROOTS.append(root)
    api = root / "docs" / "api-database"
    api.mkdir(parents=True)
    shutil.copy(HERE / "render.py", api / "render.py")
    shutil.copytree(HERE / "templates", api / "templates")
    shutil.copy(HERE / "README.md", api / "README.md")
    shutil.copy(HERE / "table-manifest.json", api / "table-manifest.json")
    for name in CHAPTERS:
        source = HERE / name
        text = source.read_text(encoding="utf-8") if source.is_file() else fixture(name)
        (api / name).write_text(text, encoding="utf-8")
    for entry in REPO.iterdir():
        if entry.name != "docs":
            (root / entry.name).symlink_to(entry)
    for entry in (REPO / "docs").iterdir():
        if entry.name != "api-database":
            (root / "docs" / entry.name).symlink_to(entry)
    return api


def run(api: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(api / "render.py"), *args], capture_output=True, text=True
    )


def render(api: Path) -> str:
    result = run(api)
    check(result.returncode == 0, f"render 退出码 {result.returncode}: {result.stderr.strip()}")
    return (api / "index.html").read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(page: str) -> Dict[str, int]:
    return {
        label: int(count)
        for count, label in re.findall(r'<div class="n">(\d+)</div><div class="t">([^<]+)</div>', page)
    }


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def case_render_and_check() -> None:
    api = make_stage()
    page = render(api)
    check("<title>RepoMesh API 与数据库设计（B00-B11）</title>" in page, "页面标题没有覆盖 B00-B11")
    for index in range(12):
        check(f'href="#doc-b{index:02d}">B{index:02d}</a>' in page, f"导航缺少大写批次标签 B{index:02d}")
    check('<a href="#doc-foundations">foundations</a>' in page, "导航缺少 foundations 入口")
    manifest = json.loads((api / "table-manifest.json").read_text(encoding="utf-8"))
    manual = manifest["existing"]["manual_baseline"]["expected_count"]
    scan = manifest["existing"]["scan"]["expected_count"]
    decision = manifest["existing"]["decision_chain"]["expected_count"]
    design = len(manifest["target_tables"])
    page_stats = stats(page)
    check(page_stats["Markdown 章节"] == 13, f"章节数应为 13，实际 {page_stats}")
    check(page_stats["已有数据库表（手册基线）"] == manual, f"手册基线应 {manual}，实际 {page_stats}")
    check(page_stats["扫描表（手册外）"] == scan, f"扫描表应 {scan}，实际 {page_stats}")
    check(
        page_stats["决策链表（手册外）"] == decision,
        f"决策链表应 {decision}，实际 {page_stats}",
    )
    check(page_stats["B05-B11 设计表"] == design, f"设计表应 {design}，实际 {page_stats}")
    check(
        page_stats["手册范围合计"] == manual + design,
        f"手册范围应 {manual + design}，实际 {page_stats}",
    )
    check(
        page_stats["全仓含扩展合计"] == manual + scan + decision + design,
        f"全仓应 {manual + scan + decision + design}，实际 {page_stats}",
    )
    check("说明表格" in page_stats, f"缺少说明表格统计: {page_stats}")
    check("表格" not in page_stats, f"仍使用旧统计标签: {page_stats}")
    check("接口与数据卡" not in page_stats, f"仍把文档卡片当接口数: {page_stats}")
    source = (api / "b00.md").read_text(encoding="utf-8").splitlines()[0]
    heading = source[2:].strip() if source.startswith("# ") else "B00"
    plain = html.unescape(re.sub(r"<[^>]+>", "", page))
    check(heading in plain, f"章节标题没有保留 Markdown 原文: {heading}")
    duplicates = re.findall(r'<h2 class="doctitle">(B\d{2}) · \1', page)
    check(not duplicates, f"章节标题重复批次前缀: {duplicates[:3]}")
    result = run(api, "--check")
    check(result.returncode == 0, f"--check 应通过: {result.stderr.strip()}")
    check("OK:" in result.stdout, f"--check 成功时应打印 OK: {result.stdout!r}")


def case_check_is_read_only() -> None:
    api = make_stage()
    render(api)
    index = api / "index.html"
    before = (index.stat().st_mtime_ns, sha256(index))
    result = run(api, "--check")
    check(result.returncode == 0, f"--check 应通过: {result.stderr.strip()}")
    check((index.stat().st_mtime_ns, sha256(index)) == before, "--check 改写了 index.html")


def case_render_is_deterministic() -> None:
    api = make_stage()
    render(api)
    first = sha256(api / "index.html")
    render(api)
    check(sha256(api / "index.html") == first, "连续两次渲染结果不同，输出含时间戳或随机内容")


def case_missing_source_is_fatal() -> None:
    api = make_stage()
    render(api)
    before = sha256(api / "index.html")
    (api / "b03.md").unlink()
    result = run(api, "--check")
    check(result.returncode != 0, "--check 在缺来源时仍然通过")
    check("缺少来源文件: b03.md" in result.stderr, f"缺少来源提示不准确: {result.stderr.strip()}")
    result = run(api)
    check(result.returncode != 0, "缺来源时 render 仍然写文件")
    check(sha256(api / "index.html") == before, "缺来源时 index.html 被改写，等于静默省略章节")


def case_stale_source() -> None:
    api = make_stage()
    render(api)
    with (api / "b01.md").open("a", encoding="utf-8") as handle:
        handle.write("\n新增一段文字，使已生成的 HTML 变陈旧。\n")
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现来源改动")
    check("已陈旧" in result.stderr, f"缺少陈旧提示: {result.stderr.strip()}")


def case_stale_template() -> None:
    api = make_stage()
    render(api)
    template = api / "templates" / "app.js"
    template.write_text(template.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现模板改动")
    check("已陈旧" in result.stderr, f"缺少陈旧提示: {result.stderr.strip()}")


def case_stale_generator_code() -> None:
    api = make_stage()
    render(api)
    source = api / "render.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("B00-B11", "B00-B12", 1), encoding="utf-8"
    )
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现生成器代码改动")
    check("已陈旧" in result.stderr, f"缺少陈旧提示: {result.stderr.strip()}")


def case_stale_html_tamper() -> None:
    api = make_stage()
    render(api)
    index = api / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace("</main>", "<p>手工改动</p>\n</main>", 1),
        encoding="utf-8",
    )
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现被手工改动的 HTML")
    check("已陈旧" in result.stderr, f"缺少陈旧提示: {result.stderr.strip()}")


def case_extra_markdown() -> None:
    api = make_stage()
    render(api)
    (api / "draft.md").write_text("# 额外文件\n", encoding="utf-8")
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现未纳入索引的 Markdown")
    check("未纳入索引" in result.stderr, f"提示不准确: {result.stderr.strip()}")


def case_broken_file_link() -> None:
    api = make_stage()
    text = (api / "b04.md").read_text(encoding="utf-8")
    found = re.search(r"\]\((\.\./[^)\s#]+)", text)
    check(found is not None, "b04.md 里没有可用于负例的库外链接")
    target = found.group(1)
    (api / "b04.md").write_text(
        text.replace(target, "../current/does-not-exist.md", 1), encoding="utf-8"
    )
    render(api)
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现坏掉的库外文件链接")
    check("本地文件链接不可达" in result.stderr, f"提示不准确: {result.stderr.strip()}")


def case_bad_chapter_anchor() -> None:
    api = make_stage()
    with (api / "b06.md").open("a", encoding="utf-8") as handle:
        handle.write("\n参考 [不存在的卡片](./b05.md#没有这个标题)。\n")
    render(api)
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现库内章节的坏锚点")
    check("跨章锚点不存在" in result.stderr, f"提示不准确: {result.stderr.strip()}")


def case_good_chapter_anchor() -> None:
    api = make_stage()
    with (api / "b02.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## 锚点目标分组\n\n### 锚点目标卡片\n\n正文。\n")
    with (api / "b06.md").open("a", encoding="utf-8") as handle:
        handle.write("\n参考 [锚点目标卡片](./b02.md#锚点目标卡片) 与 [公共规则](./foundations.md)。\n")
    page = render(api)
    check('id="b02-锚点目标卡片"' in page, "目标章节没有生成锚点")
    check('href="#b02-锚点目标卡片"' in page, "跨章链接没有解析成目标章节的锚点")
    check('href="#doc-foundations"' in page, "章节链接没有解析成章节锚点")
    result = run(api, "--check")
    check(result.returncode == 0, f"正确锚点不应失败: {result.stderr.strip()}")


def case_counts_follow_content() -> None:
    api = make_stage()
    before = stats(render(api))
    with (api / "b07.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## 追加分组\n\n### 追加卡片\n\n正文。\n")
    page = render(api)
    after = stats(page)
    check(before["Markdown 章节"] == after["Markdown 章节"] == 13, "章节数应固定为 13")
    check(after["设计专题（说明）"] == before["设计专题（说明）"] + 1, "新增 H2 后分组计数没有跟着变")
    check(
        after["文档卡片（说明）"] == before["文档卡片（说明）"] + 1,
        "新增 H3 后卡片计数没有跟着变",
    )
    check("追加分组" in page and "追加卡片" in page, "新分组和新卡片没有进目录")


def case_stale_manifest() -> None:
    api = make_stage()
    render(api)
    manifest = api / "table-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["target_tables"][0]["note"] = "改动一行，让已生成的摘要失效"
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = run(api, "--check")
    check(result.returncode != 0, "--check 未发现 manifest 改动")
    check("已陈旧" in result.stderr, f"缺少陈旧提示: {result.stderr.strip()}")


def case_missing_manifest_is_fatal() -> None:
    api = make_stage()
    render(api)
    before = sha256(api / "index.html")
    (api / "table-manifest.json").unlink()
    result = run(api, "--check")
    check(result.returncode != 0, "--check 在缺 manifest 时仍然通过")
    check(
        "table-manifest.json" in result.stderr,
        f"缺少 manifest 提示不准确: {result.stderr.strip()}",
    )
    result = run(api)
    check(result.returncode != 0, "缺 manifest 时 render 仍然写文件")
    check(sha256(api / "index.html") == before, "缺 manifest 时 index.html 被改写")


def case_design_counts_follow_manifest() -> None:
    api = make_stage()
    manifest = api / "table-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    manual = data["existing"]["manual_baseline"]["expected_count"]
    scan = data["existing"]["scan"]["expected_count"]
    decision = data["existing"]["decision_chain"]["expected_count"]
    base = len(data["target_tables"])
    removed = data["target_tables"].pop()
    for batch in data["batches"]:
        if batch["id"] == removed["batch"]:
            batch["expected_target_count"] -= 1
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page = render(api)
    page_stats = stats(page)
    check(
        page_stats["B05-B11 设计表"] == base - 1,
        f"设计表统计没有跟随 manifest: {page_stats}",
    )
    check(
        page_stats["手册范围合计"] == manual + base - 1,
        f"手册范围统计没有跟随 manifest: {page_stats}",
    )
    check(
        page_stats["全仓含扩展合计"] == manual + scan + decision + base - 1,
        f"全仓统计没有跟随 manifest: {page_stats}",
    )
    result = run(api, "--check")
    check(result.returncode == 0, f"按 manifest 重生成后 --check 应通过: {result.stderr.strip()}")


def case_extension_counts_follow_manifest() -> None:
    api = make_stage()
    manifest = api / "table-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    manual = data["existing"]["manual_baseline"]["expected_count"]
    scan = data["existing"]["scan"]["expected_count"]
    design = len(data["target_tables"])
    data["existing"]["decision_chain"]["expected_count"] = 2
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_stats = stats(render(api))
    check(page_stats["决策链表（手册外）"] == 2, f"决策链统计没有跟随 manifest: {page_stats}")
    check(
        page_stats["手册范围合计"] == manual + design,
        f"决策链不应进入手册范围: {page_stats}",
    )
    check(
        page_stats["全仓含扩展合计"] == manual + scan + 2 + design,
        f"全仓含扩展没有跟随 manifest: {page_stats}",
    )
    result = run(api, "--check")
    check(result.returncode == 0, f"按 manifest 重生成后 --check 应通过: {result.stderr.strip()}")


def case_visible_table_declaration() -> None:
    api = make_stage()
    with (api / "b07.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## 声明卡片\n\n### 房间关联表\n\n物理表：`repomesh_issues.issue_room_links`\n"
        )
    page = render(api)
    text = html.unescape(re.sub(r"<[^>]+>", "", page))
    check("物理表：repomesh_issues.issue_room_links" in text, "可见物理表声明没有进入 HTML")
    result = run(api, "--check")
    check(result.returncode == 0, f"带声明行的页面 --check 应通过: {result.stderr.strip()}")


def case_text_anchors_and_escaping() -> None:
    api = make_stage()
    with (api / "b07.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"""
## 转义与锚点占位分组

### 转义与锚点占位卡片

裸尖括号文字 <ID> 与长标识 {long_token()} 必须原样出现在页面里。

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| id | uuid | 已实现 &#124; 本次提案 |

### 同名卡片

同名标题的第一个。

### 同名卡片

同名标题的第二个。
"""
        )
    page = render(api)
    ids = re.findall(r'\sid="([^"]+)"', page)
    duplicated = sorted({anchor for anchor in ids if ids.count(anchor) > 1})
    check(not duplicated, f"出现重复锚点: {duplicated[:5]}")
    check('id="b07-同名卡片"' in page and 'id="b07-同名卡片-2"' in page, "同章同名标题没有拿到计数锚点")
    missing = [href for href in re.findall(r'href="#([^"]*)"', page) if href not in set(ids)]
    check(not missing, f"内部锚点不存在: {sorted(set(missing))[:5]}")
    text = html.unescape(re.sub(r"<[^>]+>", "", page))
    check("<ID>" in text, "裸尖括号文字被吞掉")
    check("已实现 | 本次提案" in text, "&#124; 实体没有渲染成竖线")
    check(long_token() in text, "长标识被吞掉")
    result = run(api, "--check")
    check(result.returncode == 0, f"文字与锚点校验应通过: {result.stderr.strip()}")


def case_self_contained_and_responsive() -> None:
    api = make_stage()
    page = render(api)
    check("<script src" not in page and "<link " not in page and "@import" not in page, "引用了外部资源")
    check("url(http" not in page, "CSS 引用了外部资源")
    check("@media print" in page, "缺少打印样式")
    check("@media (max-width: 900px)" in page, "缺少窄屏样式")
    check("overflow-wrap: anywhere" in page, "缺少目录长标识换行样式")
    check("overflow-x: auto" in page, "表格没有横向滚动容器")
    check("scroll-margin-top: calc(var(--docnav-height" in page, "缺少按导航高度计算的锚点回退")
    check('setProperty("--docnav-height"' in page and 'addEventListener("resize"' in page, "缺少导航高度测量与 resize 同步")
    check('name="repomesh-index-digest"' in page, "缺少来源摘要 meta")
    check("页面不含时间戳" not in page, "页面首行仍在讲时间戳")
    check("采用状态与设计理由" in page, "页面首行没有说明采用状态与设计理由")


def case_crlf_checkout() -> None:
    api = make_stage()
    page = render(api)
    digest = re.search(r'name="repomesh-index-digest" content="([0-9a-f]+)"', page).group(1)
    files = list(api.glob("*.md")) + list((api / "templates").iterdir()) + [api / "index.html"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    result = run(api, "--check")
    check(result.returncode == 0, f"CRLF 检出不应让 --check 误判: {result.stderr.strip()}")
    check(digest[:12] in result.stdout, f"CRLF 检出后的内容摘要应保持一致: {result.stdout!r}")
    check(b"\r\n" in (api / "templates" / "app.js").read_bytes(), "负例没有真的改成 CRLF")
    render(api)
    check(b"\r\n" not in (api / "index.html").read_bytes(), "生成的 index.html 不是 LF 换行")


CASES = (
    ("render-and-check", case_render_and_check),
    ("check-is-read-only", case_check_is_read_only),
    ("render-is-deterministic", case_render_is_deterministic),
    ("missing-source-is-fatal", case_missing_source_is_fatal),
    ("stale-source", case_stale_source),
    ("stale-template", case_stale_template),
    ("stale-manifest", case_stale_manifest),
    ("missing-manifest-is-fatal", case_missing_manifest_is_fatal),
    ("design-counts-follow-manifest", case_design_counts_follow_manifest),
    ("extension-counts-follow-manifest", case_extension_counts_follow_manifest),
    ("visible-table-declaration", case_visible_table_declaration),
    ("stale-generator-code", case_stale_generator_code),
    ("stale-html-tamper", case_stale_html_tamper),
    ("extra-markdown", case_extra_markdown),
    ("broken-file-link", case_broken_file_link),
    ("bad-chapter-anchor", case_bad_chapter_anchor),
    ("good-chapter-anchor", case_good_chapter_anchor),
    ("counts-follow-content", case_counts_follow_content),
    ("text-anchors-and-escaping", case_text_anchors_and_escaping),
    ("self-contained-and-responsive", case_self_contained_and_responsive),
    ("crlf-checkout", case_crlf_checkout),
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
