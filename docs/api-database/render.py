#!/usr/bin/env python3
"""docs/api-database 的 index.html 生成与同步校验工具。

    python3 docs/api-database/render.py           生成 / 刷新 index.html（幂等，输出不含时间戳）
    python3 docs/api-database/render.py --check   只校验不写文件；陈旧、缺来源、坏链接、坏锚点、吞字都退出非零

内容源固定为 foundations.md 与 b00.md ... b11.md 共 13 个章节；少一个来源文件就报错退出，不会跳过。
README.md 是维护入口，不参与渲染。
只用 Python 3 标准库，生成的 HTML 自包含，不引用任何外部资源。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE / "templates"
INDEX_PATH = HERE / "index.html"
MANIFEST_PATH = HERE / "table-manifest.json"

SOURCES = (
    "foundations.md",
    "b00.md",
    "b01.md",
    "b02.md",
    "b03.md",
    "b04.md",
    "b05.md",
    "b06.md",
    "b07.md",
    "b08.md",
    "b09.md",
    "b10.md",
    "b11.md",
)
NOT_RENDERED = ("README.md",)
GENERATOR = "repomesh-docs-index/1"
DIGEST_META = "repomesh-index-digest"
SITE_TITLE = "RepoMesh API 与数据库设计（B00-B11）"


@dataclass
class Heading:
    level: int
    text: str
    anchor: str = ""


@dataclass
class Para:
    text: str


@dataclass
class Bullets:
    ordered: bool
    items: List[str]


@dataclass
class Table:
    header: List[str]
    rows: List[List[str]]


@dataclass
class Code:
    lang: str
    text: str


Block = Union[Heading, Para, Bullets, Table, Code]


@dataclass
class Card:
    heading: Heading
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Group:
    heading: Heading
    blocks: List[Block] = field(default_factory=list)
    cards: List[Card] = field(default_factory=list)


@dataclass
class Doc:
    key: str
    source: str
    title: str
    anchor: str
    label: str = ""
    blocks: List[Block] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    lookup: Dict[str, str] = field(default_factory=dict)


@dataclass
class Ctx:
    docs: Dict[str, Doc]
    problems: List[str]
    notes: List[str]
    links: List[Tuple[str, str]]


@dataclass
class Build:
    html: str
    docs: List[Doc]
    links: List[Tuple[str, str]]
    stats: List[Tuple[int, str]]
    digest: str


class Anchorer:
    """生成带章节前缀且不重复的锚点，重复标题靠计数区分。"""

    def __init__(self, key: str) -> None:
        self.key = key
        self.used: set = set()

    def assign(self, text: str) -> str:
        base = f"{self.key}-{slugify(text)}"
        anchor = base
        count = 2
        while anchor in self.used:
            anchor = f"{base}-{count}"
            count += 1
        self.used.add(anchor)
        return anchor

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*?)\s*$")
LIST_RE = re.compile(r"^(?:[-*]\s+(.+)|(\d+)[.)]\s+(.+))$")
CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff01-\uff60]")
ENTITY_RE = re.compile(r"&(?!(?:#\d+|#x[0-9a-fA-F]+|\w+);)")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
INLINE_RE = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^()\s]+)\)")
BATCH_KEY_RE = re.compile(r"^b\d{2}$")
CHAPTER_RE = re.compile(r"^(?:\./)?(foundations|b(?:0\d|1[01]))\.md$")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
TAG_SEPARATORS = "、,，"
TOC_MARK_RE = re.compile(r"[`*]")


def escape_text(text: str) -> str:
    """转义 HTML 特殊字符，保留作者写下的实体（例如表格里的 &#124;）。"""
    return ENTITY_RE.sub("&amp;", text).replace("<", "&lt;").replace(">", "&gt;")


def slugify(text: str) -> str:
    chars = [ch if ch.isalnum() else "-" for ch in text.strip().lower()]
    slug = re.sub(r"-{2,}", "-", "".join(chars)).strip("-")
    return slug or "section"


def batch_label(key: str) -> str:
    """章节标签。批次文件在人读界面显示成 B00-B11，其他章节保持文件名。"""
    return key.upper() if BATCH_KEY_RE.match(key) else key


def display_title(doc: Doc) -> str:
    """标题已写批次前缀时不再拼接标签，避免渲染出 B04 · B04。"""
    if doc.label and doc.title.startswith(doc.label):
        return doc.title
    return f"{doc.label} · {doc.title}"


def plain_text(text: str) -> str:
    """去掉行内标记，得到用于目录和文字核对的可读文本。"""
    return TOC_MARK_RE.sub("", MD_LINK_RE.sub(r"\1", text))


def norm_text(text: str) -> str:
    """文字核对用的规范化：去掉链接目标、粗体标记和行内代码反引号，保留其他字符。"""
    plain = MD_LINK_RE.sub(r"\1", text).replace("**", "").replace("`", "")
    return re.sub(r"\s+", "", html.unescape(plain))


def norm_html(text: str) -> str:
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", text)))


def join_soft(lines: Sequence[str]) -> str:
    """合并被软换行拆开的段落；相邻中文之间不补空格。"""
    out = lines[0]
    for nxt in lines[1:]:
        gap = "" if (CJK_RE.search(out[-1]) or CJK_RE.search(nxt[0])) else " "
        out += gap + nxt
    return out


def split_row(line: str) -> List[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def is_table_sep(line: str) -> bool:
    if "|" not in line:
        return False
    cells = split_row(line)
    if not cells or any(not cell for cell in cells):
        return False
    return all(re.fullmatch(r":?-{2,}:?", cell) is not None for cell in cells)


def parse_blocks(
    text: str, key: str, problems: List[str], notes: List[str]
) -> Tuple[str, List[Block], Dict[str, str]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    anchors = Anchorer(key)
    lookup: Dict[str, str] = {}
    title = ""
    blocks: List[Block] = []
    para: List[str] = []

    def flush_para() -> None:
        if para:
            blocks.append(Para(join_soft(list(para))))
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush_para()
            i += 1
            continue

        if line.startswith("```"):
            flush_para()
            start = i + 1
            body: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                problems.append(f"{key}: 围栏代码块从第 {start} 行开始没有闭合")
            i += 1
            blocks.append(Code(line[3:].strip(), "\n".join(body)))
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_para()
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if level == 1:
                if not title:
                    title = heading_text
                    i += 1
                    continue
                notes.append(f"{key}: 出现第二个 H1「{heading_text}」，已按 H2 渲染")
                level = 2
            anchor = anchors.assign(heading_text)
            blocks.append(Heading(level, heading_text, anchor))
            lookup.setdefault(heading_text, anchor)
            lookup.setdefault(slugify(heading_text), anchor)
            lookup.setdefault(anchor, anchor)
            i += 1
            continue

        if "|" in line and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            flush_para()
            header = split_row(line)
            i += 2
            rows: List[List[str]] = []
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                rows.append(split_row(lines[i]))
                i += 1
            blocks.append(Table(header, rows))
            continue

        item = LIST_RE.match(line)
        if item:
            flush_para()
            ordered = item.group(2) is not None
            items: List[str] = []
            while i < len(lines):
                current = LIST_RE.match(lines[i].strip())
                if not current or (current.group(2) is not None) != ordered:
                    break
                items.append(current.group(1) if current.group(1) is not None else current.group(3))
                i += 1
            blocks.append(Bullets(ordered, items))
            continue

        para.append(line)
        i += 1

    flush_para()
    return title, blocks, lookup


def build_doc(source: str, text: str, problems: List[str], notes: List[str]) -> Doc:
    key = Path(source).stem
    title, blocks, lookup = parse_blocks(text, key, problems, notes)
    doc = Doc(
        key=key,
        source=source,
        title=title or key,
        anchor=f"doc-{key}",
        label=batch_label(key),
    )
    doc.lookup.update({doc.anchor: doc.anchor, slugify(doc.title): doc.anchor, doc.title: doc.anchor})
    doc.lookup.update(lookup)

    group: Optional[Group] = None
    card: Optional[Card] = None
    for block in blocks:
        if isinstance(block, Heading) and block.level == 2:
            group, card = Group(block), None
            doc.groups.append(group)
            continue
        if isinstance(block, Heading) and block.level == 3:
            if group is None:
                group = Group(Heading(2, "正文", f"{key}-body"))
                doc.groups.append(group)
                notes.append(f"{source}: H3 出现在任何 H2 之前，已按「正文」分组渲染")
            card = Card(block)
            group.cards.append(card)
            continue
        target = card.blocks if card is not None else (group.blocks if group is not None else doc.blocks)
        target.append(block)
    return doc


def link_target(url: str, doc: Doc, ctx: Ctx) -> Tuple[str, str]:
    """把 Markdown 链接解析成 (href, css class)。

    库内章节链接必须命中目标章节的标题锚点；库外文件链接只核对文件存在。
    """
    if url.startswith("#"):
        fragment = unquote(url[1:])
        anchor = doc.lookup.get(fragment)
        if anchor is None:
            ctx.problems.append(f"{doc.source}: 同章锚点不存在 #{fragment}")
            return "#" + doc.anchor, ""
        return "#" + anchor, ""
    if SCHEME_RE.match(url):
        return url, "ext"
    if url.startswith("/"):
        return url, "file"
    path, _, fragment = url.partition("#")
    chapter = CHAPTER_RE.match(path)
    if chapter:
        target = ctx.docs.get(chapter.group(1))
        if target is None:
            ctx.problems.append(f"{doc.source}: 链接指向未纳入索引的章节 {path}")
            return url, "file"
        if not fragment:
            return "#" + target.anchor, ""
        anchor = target.lookup.get(unquote(fragment))
        if anchor is None:
            ctx.problems.append(f"{doc.source}: 跨章锚点不存在 {path}#{unquote(fragment)}")
            return "#" + target.anchor, ""
        return "#" + anchor, ""
    ctx.links.append((doc.source, path))
    return url, "file"


def render_inline(text: str, doc: Doc, ctx: Ctx) -> str:
    out: List[str] = []
    pos = 0
    for match in INLINE_RE.finditer(text):
        out.append(escape_text(text[pos:match.start()]))
        code, bold, label, url = match.group(1), match.group(2), match.group(3), match.group(4)
        if code is not None:
            out.append(f"<code>{escape_text(code)}</code>")
        elif bold is not None:
            out.append(f"<strong>{render_inline(bold, doc, ctx)}</strong>")
        else:
            href, css = link_target(url, doc, ctx)
            attr = f' class="{css}"' if css else ""
            out.append(f'<a href="{html.escape(href, quote=True)}"{attr}>{render_inline(label, doc, ctx)}</a>')
        pos = match.end()
    out.append(escape_text(text[pos:]))
    return "".join(out)


COL_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("类型",), "c-type"),
    (("字段", "名称", "列名", "键名"), "c-name"),
    (("方法", "路径", "端点", "参数", "键"), "c-mono"),
    (("约束", "标记", "必填", "索引", "唯一", "状态", "角色", "作用域"), "c-tag"),
)

TAG_RULES: Tuple[Tuple[str, str], ...] = (
    ("已实现", "ok"),
    ("已采用", "adopt"),
    ("候选", "candidate"),
    ("本次提案", "proposed"),
    ("提案", "proposed"),
    ("未实现", "proposed"),
    ("待定", "proposed"),
    ("验证", "verify"),
    ("PK", "pk"),
    ("主键", "pk"),
    ("FK", "fk"),
    ("外键", "fk"),
    ("唯一", "unq"),
    ("索引", "ix"),
    ("必填", "req"),
    ("非空", "req"),
    ("可空", "nul"),
    ("NULL", "nul"),
    ("已废弃", "muted"),
    ("删除", "danger"),
    ("错误", "danger"),
)


def column_class(header: str) -> str:
    for keys, css in COL_RULES:
        if any(key in header for key in keys):
            return css
    return "c-text"


def chip_class(token: str) -> str:
    low = token.lower()
    for key, css in TAG_RULES:
        if key.lower() in low:
            return css
    return ""


def is_tag_separator(part: str) -> bool:
    return len(part) == 1 and part in TAG_SEPARATORS


def split_tag_parts(cell: str) -> List[str]:
    """按分隔符切开约束或状态列，但不切开行内代码里的分隔符。"""
    parts: List[str] = []
    buffer: List[str] = []
    in_code = False
    for char in cell:
        if char == "`":
            in_code = not in_code
            buffer.append(char)
            continue
        if not in_code and is_tag_separator(char):
            parts.append("".join(buffer))
            parts.append(char)
            buffer = []
            continue
        buffer.append(char)
    parts.append("".join(buffer))
    return parts


def render_tag_cell(cell: str, doc: Doc, ctx: Ctx) -> str:
    """把约束或状态列渲染成有色标签，文字与分隔符原样保留。"""
    parts = split_tag_parts(cell)
    tokens = [part.strip() for part in parts if part.strip() and not is_tag_separator(part)]
    if not tokens:
        return render_inline(cell, doc, ctx)
    out: List[str] = []
    for part in parts:
        if not part:
            continue
        if is_tag_separator(part):
            out.append(escape_text(part))
            continue
        token = part.strip()
        if len(plain_text(token)) <= 16:
            css = chip_class(plain_text(token))
            attr = f"tag {css}" if css else "tag"
            out.append(f'<span class="{attr}">{render_inline(token, doc, ctx)}</span>')
        else:
            out.append(render_inline(token, doc, ctx))
    return "".join(out)


def render_table(block: Table, doc: Doc, ctx: Ctx, wrap: bool) -> str:
    classes = [column_class(header) for header in block.header]
    head = "".join(
        f'<th class="{classes[i] if i < len(classes) else "c-text"}">{render_inline(cell, doc, ctx)}</th>'
        for i, cell in enumerate(block.header)
    )
    body: List[str] = []
    for row in block.rows:
        if len(row) != len(block.header):
            ctx.notes.append(
                f"{doc.source}: 表格行列数不一致（表头 {len(block.header)} 列，某数据行 {len(row)} 列）"
            )
        cells: List[str] = []
        for i, cell in enumerate(row):
            css = classes[i] if i < len(classes) else "c-text"
            inner = render_tag_cell(cell, doc, ctx) if css == "c-tag" else render_inline(cell, doc, ctx)
            cells.append(f'<td class="{css}">{inner}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    table = (
        f'<div class="tw"><table class="grid"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )
    return f'<div class="card tablecard">{table}</div>' if wrap else table


def render_blocks(blocks: Sequence[Block], doc: Doc, ctx: Ctx, wrap_tables: bool) -> str:
    out: List[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            out.append(f'<h5 class="detail" id="{block.anchor}">{render_inline(block.text, doc, ctx)}</h5>')
        elif isinstance(block, Para):
            out.append(f"<p>{render_inline(block.text, doc, ctx)}</p>")
        elif isinstance(block, Bullets):
            tag = "ol" if block.ordered else "ul"
            items = "".join(f"<li>{render_inline(item, doc, ctx)}</li>" for item in block.items)
            out.append(f"<{tag}>{items}</{tag}>")
        elif isinstance(block, Table):
            out.append(render_table(block, doc, ctx, wrap_tables))
        elif isinstance(block, Code):
            lang = f' data-lang="{html.escape(block.lang, quote=True)}"' if block.lang else ""
            out.append(f'<pre class="code"{lang}><code>{escape_text(block.text)}</code></pre>')
    return "\n".join(out)


def render_local_toc(doc: Doc) -> str:
    if not doc.groups:
        return ""
    items: List[str] = []
    for group in doc.groups:
        count = f'<span class="cnt">{len(group.cards)} 张卡片</span>' if group.cards else ""
        items.append(
            f'<li class="tgroup"><a href="#{group.heading.anchor}">'
            f'{escape_text(plain_text(group.heading.text))}</a>{count}</li>'
        )
        for card in group.cards:
            items.append(
                f'<li class="tnode lvl3"><a href="#{card.heading.anchor}">'
                f'{escape_text(plain_text(card.heading.text))}</a></li>'
            )
    return f'<div class="toc local"><ul>{"".join(items)}</ul></div>'


def render_doc(doc: Doc, ctx: Ctx) -> str:
    parts: List[str] = [f'<section class="doc" id="{doc.anchor}">']
    parts.append(
        f'<h2 class="doctitle">{render_inline(display_title(doc), doc, ctx)}'
        f'<span class="fname">{escape_text(doc.source)}</span></h2>'
    )
    parts.append(render_local_toc(doc))
    parts.append(render_blocks(doc.blocks, doc, ctx, True))
    for group in doc.groups:
        parts.append(f'<section class="group" id="{group.heading.anchor}">')
        parts.append(f"<h3>{render_inline(group.heading.text, doc, ctx)}</h3>")
        parts.append(render_blocks(group.blocks, doc, ctx, True))
        for card in group.cards:
            parts.append(f'<section class="card" id="{card.heading.anchor}">')
            parts.append(f'<h4 class="cardtitle">{render_inline(card.heading.text, doc, ctx)}</h4>')
            parts.append(f'<div class="cardbody">{render_blocks(card.blocks, doc, ctx, False)}</div>')
            parts.append("</section>")
        parts.append("</section>")
    parts.append("</section>")
    return "\n".join(part for part in parts if part)


def render_top_toc(docs: Sequence[Doc]) -> str:
    items: List[str] = []
    for doc in docs:
        cards = sum(len(group.cards) for group in doc.groups)
        count = f'<span class="cnt">{cards} 张卡片</span>' if cards else ""
        items.append(
            f'<li class="tgroup"><a href="#{doc.anchor}">'
            f'{escape_text(plain_text(display_title(doc)))}</a>{count}</li>'
        )
        for group in doc.groups:
            items.append(
                f'<li class="tnode"><a href="#{group.heading.anchor}">'
                f'{escape_text(plain_text(group.heading.text))}</a></li>'
            )
    return (
        '<div class="toc" id="toc">'
        '<input class="search" id="tocFilter" type="search" placeholder="筛选目录：章节 / 分组 / 卡片">'
        f'<ul>{"".join(items)}</ul></div>'
    )


def render_docnav(docs: Sequence[Doc]) -> str:
    links = "".join(f'<a href="#{doc.anchor}">{escape_text(doc.label)}</a>' for doc in docs)
    return f'<nav class="docnav">{links}<a href="#toc">目录</a></nav>'


def render_stats(stats: Sequence[Tuple[int, str]]) -> str:
    items = "".join(
        f'<div class="stat"><div class="n">{count}</div><div class="t">{escape_text(label)}</div></div>'
        for count, label in stats
    )
    return f'<div class="stats">{items}</div>'


def count_tables(blocks: Sequence[Block]) -> int:
    return sum(1 for block in blocks if isinstance(block, Table))


def fill(template: str, values: Dict[str, str]) -> str:
    missing: List[str] = []

    def replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name in values:
            return values[name]
        missing.append(name)
        return match.group(0)

    out = PLACEHOLDER_RE.sub(replace, template)
    if missing:
        raise SystemExit(f"模板缺少占位符取值: {sorted(set(missing))}")
    return out


def load_templates() -> Dict[str, str]:
    files = sorted(path for path in TEMPLATE_DIR.iterdir() if path.is_file())
    if not files:
        raise SystemExit(f"缺少模板目录内容: {TEMPLATE_DIR}")
    return {path.name: path.read_text(encoding="utf-8") for path in files}


def load_sources() -> Tuple[Dict[str, str], List[str]]:
    texts: Dict[str, str] = {}
    problems: List[str] = []
    # 文本模式读取把 CRLF 规范成 LF，Git 的换行转换不会改变来源摘要或误报陈旧。
    for name in SOURCES:
        path = HERE / name
        if path.is_file():
            texts[name] = path.read_text(encoding="utf-8")
        else:
            problems.append(f"缺少来源文件: {name}")
    known = set(SOURCES) | set(NOT_RENDERED)
    for path in sorted(HERE.glob("*.md")):
        if path.name not in known:
            problems.append(
                f"未纳入索引的 Markdown 文件: {path.name}（内容源固定为 {len(SOURCES)} 个章节加 README.md）"
            )
    return texts, problems


def load_manifest() -> Tuple[Optional[dict], str, List[str]]:
    """读取机器可读表清单；缺失或损坏时不给首页生成猜测数字。"""
    if not MANIFEST_PATH.is_file():
        return None, "", [f"缺少来源文件: {MANIFEST_PATH.name}"]
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return None, text, [f"表清单不是合法 JSON: {error}"]
    if not isinstance(data, dict):
        return None, text, ["表清单顶层必须是对象"]
    for key in ("existing", "batches", "target_tables"):
        if key not in data:
            return None, text, [f"表清单缺少字段: {key}"]
    return data, text, []


def write_index(page: str) -> None:
    """固定 LF 写出，产物字节不随检出平台的换行转换变化。"""
    with INDEX_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)


def source_digest(texts: Dict[str, str], templates: Dict[str, str], manifest: str) -> str:
    digest = hashlib.sha256()
    digest.update((GENERATOR + "\n").encode("utf-8"))
    for name in SOURCES:
        digest.update(name.encode("utf-8") + b"\0" + texts[name].encode("utf-8") + b"\0")
    for name in sorted(templates):
        digest.update(name.encode("utf-8") + b"\0" + templates[name].encode("utf-8") + b"\0")
    digest.update(b"table-manifest.json\0" + manifest.encode("utf-8") + b"\0")
    return digest.hexdigest()


def render_all(
    texts: Dict[str, str],
    templates: Dict[str, str],
    manifest: dict,
    manifest_text: str,
    problems: List[str],
    notes: List[str],
) -> Build:
    docs = [build_doc(name, texts[name], problems, notes) for name in SOURCES]
    ctx = Ctx(docs={doc.key: doc for doc in docs}, problems=problems, notes=notes, links=[])
    body = "\n".join(render_doc(doc, ctx) for doc in docs)
    existing = manifest.get("existing") or {}
    manual = (existing.get("manual_baseline") or {})
    scan = (existing.get("scan") or {})
    manual_count = manual.get("expected_count", 0)
    business_count = manual.get("business_count", 0)
    scan_count = scan.get("expected_count", 0)
    design_count = len(manifest.get("target_tables") or [])
    batch_counts = "、".join(
        f"{batch.get('id', '').upper()} {batch.get('expected_target_count', 0)}"
        for batch in manifest.get("batches") or []
        if isinstance(batch, dict)
    )
    stats = [
        (manual_count, "已有数据库表（手册基线）"),
        (scan_count, "扫描表（手册外）"),
        (design_count, "B05-B11 设计表"),
        (manual_count + design_count, "手册范围合计"),
        (manual_count + scan_count + design_count, "全仓含扫描合计"),
        (len(docs), "Markdown 章节"),
        (sum(len(doc.groups) for doc in docs), "设计专题（说明）"),
        (sum(len(group.cards) for doc in docs for group in doc.groups), "文档卡片（说明）"),
        (
            sum(count_tables(doc.blocks) for doc in docs)
            + sum(count_tables(group.blocks) for doc in docs for group in doc.groups)
            + sum(
                count_tables(card.blocks)
                for doc in docs
                for group in doc.groups
                for card in group.cards
            ),
            "说明表格",
        ),
        (len({path for _, path in ctx.links}), "本地来源链接（去重）"),
    ]
    values = {
        "TITLE": SITE_TITLE,
        "SUBTITLE": (
            "按 B00 至 B11 批次整理 API、数据库关系、采用状态与设计理由。"
            f"内容来自 docs/api-database 下的 {len(docs)} 个 Markdown 章节，"
            "目录和文档计数按内容计算。"
            f"数据库统计来自迁移与 table-manifest.json：手册基线 {manual_count} 张"
            f"（业务 {business_count} + 系统表 1）、扫描表 {scan_count} 张（手册外）、"
            f"B05-B11 设计表 {design_count} 张（{batch_counts}）；"
            f"手册范围合计 {manual_count + design_count}，全仓含扫描 {manual_count + scan_count + design_count}。"
            "设计专题、文档卡片、说明表格等数字是文档统计，不是 API 数或已实现表数。"
        ),
        "GENERATOR": GENERATOR,
        "DIGEST_META": DIGEST_META,
        "DIGEST": source_digest(texts, templates, manifest_text),
        "STYLE": templates["style.css"],
        "SCRIPT": templates["app.js"],
        "STATS": render_stats(stats),
        "DOCNAV": render_docnav(docs),
        "TOC": render_top_toc(docs),
        "BODY": body,
    }
    return Build(
        html=fill(templates["index.html.tmpl"], values),
        docs=docs,
        links=ctx.links,
        stats=stats,
        digest=values["DIGEST"],
    )


def text_units(doc: Doc) -> List[str]:
    """列出必须出现在 HTML 里的文字单元，用来证明渲染不吞字。"""
    units: List[str] = [doc.title]

    def collect(blocks: Sequence[Block]) -> None:
        for block in blocks:
            if isinstance(block, (Heading, Para)):
                units.append(block.text)
            elif isinstance(block, Bullets):
                units.extend(block.items)
            elif isinstance(block, Table):
                units.extend(block.header)
                for row in block.rows:
                    units.extend(row)
            elif isinstance(block, Code):
                units.extend(block.text.split("\n"))

    collect(doc.blocks)
    for group in doc.groups:
        units.append(group.heading.text)
        collect(group.blocks)
        for card in group.cards:
            units.append(card.heading.text)
            collect(card.blocks)
    return units


def check_artifact(build: Build, expected: str, problems: List[str]) -> None:
    if INDEX_PATH.is_file():
        disk = INDEX_PATH.read_text(encoding="utf-8")
        if disk != expected:
            problems.append("index.html 已陈旧：与当前 Markdown 或模板不一致，请重新运行 render.py")
        target = disk
    else:
        problems.append("缺少 index.html：请先运行 python3 docs/api-database/render.py")
        target = expected

    ids = re.findall(r'\sid="([^"]+)"', target)
    seen: set = set()
    duplicated: List[str] = []
    for anchor in ids:
        if anchor in seen and anchor not in duplicated:
            duplicated.append(anchor)
        seen.add(anchor)
    if duplicated:
        problems.append("重复锚点: " + ", ".join(duplicated[:8]))

    for href in re.findall(r'href="#([^"]*)"', target):
        if href == "" or href not in seen:
            problems.append(f"内部锚点不存在: #{href}")

    page = norm_html(target)
    for doc in build.docs:
        for unit in text_units(doc):
            text = norm_text(unit)
            if len(text) >= 2 and text not in page:
                problems.append(f"{doc.source}: 渲染结果缺少文字「{unit[:48]}」")

    for source, path in dict.fromkeys(build.links):
        if not (HERE / unquote(path)).exists():
            problems.append(f"{source}: 本地文件链接不可达 {path}")


def report(problems: Sequence[str], notes: Sequence[str]) -> None:
    for note in notes:
        print(f"提示: {note}", file=sys.stderr)
    for problem in problems:
        print(f"错误: {problem}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="渲染并校验 docs/api-database 的自包含 index.html")
    parser.add_argument("--check", action="store_true", help="只校验不写文件；发现问题时退出码非零")
    args = parser.parse_args(argv)

    problems: List[str] = []
    notes: List[str] = []
    texts, missing = load_sources()
    problems.extend(missing)
    manifest, manifest_text, manifest_problems = load_manifest()
    problems.extend(manifest_problems)
    if missing or manifest_problems:
        report(problems, notes)
        return 1

    build = render_all(texts, load_templates(), manifest, manifest_text, problems, notes)
    if args.check:
        check_artifact(build, build.html, problems)
        report(problems, notes)
        if problems:
            return 1
        print(f"OK: index.html 与 {len(SOURCES)} 个内容源一致（digest {build.digest[:12]}）")
        return 0

    write_index(build.html)
    report(problems, notes)
    counts = "，".join(f"{label} {count}" for count, label in build.stats)
    print(f"已写入 {INDEX_PATH.name}：{counts}（digest {build.digest[:12]}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
