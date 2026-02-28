#!/usr/bin/env python3
"""
将 simplified/<book>/ 下的 Markdown 文件合并生成一本风格统一的 PDF。
配色：浅黄底色、天蓝色标题装饰、红色用于重要标注。

用法：
    python build_pdf.py           # 构建全部已注册的书
    python build_pdf.py ostep     # 只构建 OSTEP
    python build_pdf.py redis     # 只构建 Redis
"""

import os
import re
import sys
import glob

from pygments import highlight as pyg_highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    NextPageTemplate,
    Image as RLImage,
)
from reportlab.platypus.xpreformatted import XPreformatted
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── 颜色 ─────────────────────────────────────────────────────────
CREAM       = HexColor("#FFFDF0")      # 浅黄/奶油底色
SKY_BLUE    = HexColor("#4A90D9")      # 天蓝 - 标题
LIGHT_BLUE  = HexColor("#D6EAF8")      # 浅天蓝 - 装饰条
RED_ACCENT  = HexColor("#D9534F")      # 红色 - 重要标注
DARK_TEXT   = HexColor("#2C3E50")      # 深色文字
CODE_BG     = HexColor("#F5F0E8")      # 代码背景（暖灰）
TABLE_HEAD  = HexColor("#D6EAF8")      # 表头背景
TABLE_ALT   = HexColor("#FAFAF5")      # 表格交替行
BORDER_GREY = HexColor("#CCCCCC")      # 表格边线
LIGHT_YELLOW = HexColor("#FFF9E3")     # 目录条目交替底色

PAGE_W, PAGE_H = A4
MARGIN_L = 2.2 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 2.4 * cm
MARGIN_B = 2.2 * cm

# ── 注册字体 ──────────────────────────────────────────────────────
# 使用文泉驿微米黑（WenQuanYi Micro Hei）—— 风格最接近微软雅黑的开源字体
# TTC 含两个子字体：index 0 = Regular, index 1 = Bold
WQY_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
FONT_DIR_TT = "/usr/share/fonts/truetype/noto"

pdfmetrics.registerFont(TTFont("NotoSansSC",       WQY_PATH, subfontIndex=0))
pdfmetrics.registerFont(TTFont("NotoSansSC-Bold",  WQY_PATH, subfontIndex=1))
pdfmetrics.registerFont(TTFont("NotoSerifSC",      WQY_PATH, subfontIndex=0))
pdfmetrics.registerFont(TTFont("NotoSerifSC-Bold", WQY_PATH, subfontIndex=1))
pdfmetrics.registerFont(TTFont("NotoMono",         f"{FONT_DIR_TT}/NotoSansMono-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NotoMono-Bold",    f"{FONT_DIR_TT}/NotoSansMono-Bold.ttf"))

# 注册字体族，使 <b>/<i> 标签正确映射
pdfmetrics.registerFontFamily("NotoSerifSC",
    normal="NotoSerifSC", bold="NotoSerifSC-Bold",
    italic="NotoSerifSC", boldItalic="NotoSerifSC-Bold")
pdfmetrics.registerFontFamily("NotoSansSC",
    normal="NotoSansSC", bold="NotoSansSC-Bold",
    italic="NotoSansSC", boldItalic="NotoSansSC-Bold")

# ── 样式 ─────────────────────────────────────────────────────────

def make_styles():
    """返回全部自定义段落样式。"""
    base = ParagraphStyle(
        "base",
        fontName="NotoSerifSC",
        fontSize=10,
        leading=16,
        textColor=DARK_TEXT,
        alignment=TA_LEFT,
    )
    styles = {
        "body": base,
        "h1": ParagraphStyle(
            "h1", parent=base,
            fontName="NotoSansSC-Bold", fontSize=20, leading=28,
            textColor=SKY_BLUE, spaceAfter=6, spaceBefore=0,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base,
            fontName="NotoSansSC-Bold", fontSize=14, leading=20,
            textColor=SKY_BLUE, spaceBefore=14, spaceAfter=6,
            alignment=TA_LEFT,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base,
            fontName="NotoSansSC-Bold", fontSize=12, leading=17,
            textColor=HexColor("#34638A"), spaceBefore=10, spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "h4": ParagraphStyle(
            "h4", parent=base,
            fontName="NotoSansSC-Bold", fontSize=11, leading=16,
            textColor=HexColor("#34638A"), spaceBefore=8, spaceAfter=3,
            alignment=TA_LEFT,
        ),
        "code": ParagraphStyle(
            "code", parent=base,
            fontName="NotoMono", fontSize=8.2, leading=12,
            textColor=DARK_TEXT, alignment=TA_LEFT,
            leftIndent=6, rightIndent=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base,
            leftIndent=18, bulletIndent=6,
            spaceBefore=2, spaceAfter=2,
        ),
        "bullet2": ParagraphStyle(
            "bullet2", parent=base,
            leftIndent=36, bulletIndent=22,
            spaceBefore=1, spaceAfter=1, fontSize=9.5, leading=15,
        ),
        "toc_h1": ParagraphStyle(
            "toc_h1", parent=base,
            fontName="NotoSansSC-Bold", fontSize=11, leading=18,
            textColor=SKY_BLUE, leftIndent=0,
        ),
        "toc_h2": ParagraphStyle(
            "toc_h2", parent=base,
            fontName="NotoSerifSC", fontSize=9.5, leading=15,
            textColor=DARK_TEXT, leftIndent=16,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base,
            fontName="NotoSansSC-Bold", fontSize=32, leading=44,
            textColor=SKY_BLUE, alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base,
            fontName="NotoSerifSC", fontSize=14, leading=22,
            textColor=DARK_TEXT, alignment=TA_CENTER,
        ),
    }
    return styles


# ── Markdown → Flowable 转换 ─────────────────────────────────────

def escape_xml(text):
    """转义 XML 特殊字符（给 Paragraph 用）。"""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _wrap_cjk_with_font(text):
    """将文本中连续的 CJK 字符段用 NotoSansSC 字体标签包裹，使 NotoMono 代码块能正确显示中文。"""
    # 匹配连续的 CJK 统一表意文字、CJK 标点、全角字符
    return re.sub(
        r'([\u2E80-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFFEF\U00020000-\U0002FA1F]+)',
        r'<font name="NotoSansSC">\1</font>',
        text,
    )


# ── Pygments 语法高亮配色（暖色调，搭配 CODE_BG #F5F0E8）──────────
_TOKEN_COLORS = {
    Token.Keyword:             "#8B1A1A",   # 关键字：深红
    Token.Keyword.Type:        "#2E6DA4",   # 类型关键字：蓝
    Token.Name.Function:       "#6A3D9A",   # 函数名：紫
    Token.Name.Class:          "#6A3D9A",   # 类名：紫
    Token.Name.Builtin:        "#6A3D9A",   # 内建名：紫
    Token.Literal.String:      "#2D882D",   # 字符串：绿
    Token.Literal.String.Doc:  "#2D882D",
    Token.Literal.Number:      "#B85C00",   # 数字：橙
    Token.Comment:             "#888888",   # 注释：灰
    Token.Comment.Single:      "#888888",
    Token.Comment.Multiline:   "#888888",
    Token.Comment.Preproc:     "#8B1A1A",   # 预处理指令：深红
    Token.Operator:            "#666666",   # 运算符：深灰
    Token.Punctuation:         "#444444",   # 标点：深灰
}


def _get_token_color(ttype):
    """查找 token 类型对应的颜色，沿 token 继承链向上找。"""
    while ttype:
        if ttype in _TOKEN_COLORS:
            return _TOKEN_COLORS[ttype]
        ttype = ttype.parent
    return None


def _highlight_code(code, lang=""):
    """用 Pygments 对代码做语法高亮，输出带 <font> 标签的 XML 字符串（CJK 已处理）。"""
    try:
        lexer = get_lexer_by_name(lang, stripall=False) if lang else TextLexer()
    except Exception:
        lexer = TextLexer()

    tokens = lexer.get_tokens(code)
    parts = []
    for ttype, value in tokens:
        escaped = escape_xml(value)
        # CJK 字符用中文字体包裹
        escaped = _wrap_cjk_with_font(escaped)
        color = _get_token_color(ttype)
        if color:
            # 注释用斜体
            if ttype in Token.Comment:
                parts.append(f'<font color="{color}"><i>{escaped}</i></font>')
            else:
                parts.append(f'<font color="{color}">{escaped}</font>')
        else:
            parts.append(escaped)
    return "".join(parts)


def _latex_to_readable(text):
    """将简单 LaTeX 数学语法转为 reportlab XML 可渲染的近似形式。"""
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)        # \text{x} → x
    text = re.sub(r'\\times', '×', text)                      # \times → ×
    text = re.sub(r'\\cdot', '·', text)                       # \cdot → ·
    text = re.sub(r'\\leq', '≤', text)
    text = re.sub(r'\\geq', '≥', text)
    text = re.sub(r'\\neq', '≠', text)
    text = re.sub(r'\\approx', '≈', text)
    text = re.sub(r'\\rightarrow', '→', text)
    text = re.sub(r'\\leftarrow', '←', text)
    text = re.sub(r'\\infty', '∞', text)
    text = re.sub(r'\\sum', 'Σ', text)
    text = re.sub(r'\\log', 'log', text)
    text = re.sub(r'\^\{([^}]+)\}', r'<super>\1</super>', text)   # ^{x}
    text = re.sub(r'_\{([^}]+)\}', r'<sub>\1</sub>', text)        # _{x}
    text = re.sub(r'\^(\w)', r'<super>\1</super>', text)           # ^x
    text = re.sub(r'_(\w)', r'<sub>\1</sub>', text)                # _x
    text = text.replace('{', '').replace('}', '')                     # 清除剩余花括号
    return text


def _latex_inline_replace(m):
    """行内 $...$ 的替换回调。"""
    inner = escape_xml(m.group(1))
    inner = _latex_to_readable(inner)
    return f'<font color="#D9534F"><i>{inner}</i></font>'


def inline_markup(text):
    """将行内 Markdown 标记转换为 reportlab XML 标签。"""
    # 先提取行内代码，用占位符保护，防止内部 ** / $ 被二次处理
    code_placeholders = {}
    def _save_code(m):
        key = f"\x00C{len(code_placeholders)}\x00"
        code_placeholders[key] = f'<font name="NotoMono" size="8.5" color="#8B4513">{escape_xml(m.group(1))}</font>'
        return key
    text = re.sub(r'`([^`]+)`', _save_code, text)

    # 行内数学 $...$ → 红色斜体（在转义前处理，因为 LaTeX 含特殊字符）
    text = re.sub(r'\$([^$]+)\$', _latex_inline_replace, text)

    # 转义 XML
    text = escape_xml(text)

    # 粗体 **bold**
    text = re.sub(
        r'\*\*([^*]+)\*\*',
        r'<b>\1</b>',
        text,
    )
    # 斜体 *italic*（排除已处理的粗体）
    text = re.sub(
        r'(?<!\*)\*([^*]+)\*(?!\*)',
        r'<i>\1</i>',
        text,
    )

    # 还原行内代码占位符
    for key, val in code_placeholders.items():
        text = text.replace(key, val)

    return text


def parse_table(lines):
    """将 Markdown 表格行列表解析为 [[cell, ...], ...] 二维数组。"""
    rows = []
    for line in lines:
        line = line.strip().strip("|")
        cells = [c.strip() for c in line.split("|")]
        # 跳过分隔行
        if all(re.match(r'^[-:]+$', c) for c in cells):
            continue
        rows.append(cells)
    return rows


class MarkdownToFlowables:
    """简易 Markdown → reportlab Flowable 列表转换器。"""

    def __init__(self, styles):
        self.S = styles
        self.toc_entries = []  # [(level, title, key), ...]
        self.base_dir = "."   # 图片相对路径的基准目录

    def convert_file(self, filepath):
        """读取一个 .md 文件，返回 flowable 列表。"""
        self.base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        return self._parse(text)

    def _parse(self, text):
        lines = text.split("\n")
        flowables = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # ── 图片 ![alt](path) ──
            img_m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)', line.strip())
            if img_m:
                flowables.extend(self._make_image(img_m.group(2), img_m.group(1)))
                i += 1
                continue

            # ── 围栏代码块 ──
            if line.startswith("```"):
                lang = line.strip("`").strip() or ""  # 提取语言标识
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                flowables.extend(self._make_code_block(code_lines, lang))
                continue

            # ── 表格 ──
            if "|" in line and i + 1 < len(lines) and re.search(r'\|[-:]+\|', lines[i + 1].strip() if i + 1 < len(lines) else ""):
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                flowables.extend(self._make_table(table_lines))
                continue

            # ── 标题 ──
            m = re.match(r'^(#{1,4})\s+(.*)', line)
            if m:
                level = len(m.group(1))
                title_text = m.group(2).strip()
                flowables.extend(self._make_heading(level, title_text))
                i += 1
                continue

            # ── 列表项 ──
            m = re.match(r'^(\s*)-\s+(.*)', line)
            if m:
                indent = len(m.group(1))
                item_text = m.group(2)
                # 收集续行
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and not lines[i].strip().startswith("-") and not lines[i].strip().startswith("#") and lines[i].strip():
                    item_text += " " + lines[i].strip()
                    i += 1
                style_key = "bullet2" if indent >= 2 else "bullet"
                flowables.append(
                    Paragraph(
                        f'<bullet>&bull; </bullet>{inline_markup(item_text)}',
                        self.S[style_key],
                    )
                )
                continue

            # ── 有序列表 ──
            m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
            if m:
                indent = len(m.group(1))
                num_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
                num = num_match.group(2)
                item_text = num_match.group(3)
                i += 1
                while i < len(lines) and lines[i].startswith("   ") and not re.match(r'^\s*\d+\.', lines[i]) and lines[i].strip():
                    item_text += " " + lines[i].strip()
                    i += 1
                flowables.append(
                    Paragraph(
                        f'<bullet>{num}. </bullet>{inline_markup(item_text)}',
                        self.S["bullet"],
                    )
                )
                continue

            # ── 数学块 $$ ──
            if line.strip().startswith("$$"):
                stripped = line.strip()
                # 单行形式 $$...$$
                if len(stripped) > 4 and stripped.endswith("$$") and stripped != "$$":
                    math_text = stripped[2:-2].strip()
                    i += 1
                else:
                    # 多行形式
                    math_lines = []
                    i += 1
                    while i < len(lines) and not lines[i].strip().startswith("$$"):
                        math_lines.append(lines[i])
                        i += 1
                    i += 1  # skip closing $$
                    math_text = "\n".join(math_lines).strip()
                math_text = escape_xml(math_text)
                math_text = _latex_to_readable(math_text)
                flowables.append(Spacer(1, 4))
                flowables.append(
                    Paragraph(
                        f'<font name="NotoMono" color="#D9534F" size="10"><i>{math_text}</i></font>',
                        ParagraphStyle("math_block", parent=self.S["body"], alignment=TA_CENTER, spaceBefore=6, spaceAfter=6),
                    )
                )
                continue

            # ── 空行 ──
            if not line.strip():
                i += 1
                continue

            # ── 普通段落 ──
            para_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") and not lines[i].startswith("```") and not lines[i].startswith("- ") and not re.match(r'^\d+\.', lines[i]) and not ("|" in lines[i] and i + 1 < len(lines) and "|" in lines[i + 1]) and not lines[i].strip().startswith("$$"):
                para_lines.append(lines[i])
                i += 1
            para_text = " ".join(l.strip() for l in para_lines)
            flowables.append(Paragraph(inline_markup(para_text), self.S["body"]))
            flowables.append(Spacer(1, 4))

        return flowables

    def _make_heading(self, level, title_text):
        """生成标题 flowable，同时记录目录条目。"""
        style_map = {1: "h1", 2: "h2", 3: "h3", 4: "h4"}
        style_key = style_map.get(level, "h4")
        key = f"toc_{len(self.toc_entries)}"
        self.toc_entries.append((level, title_text, key))

        items = []
        if level <= 2:
            items.append(Spacer(1, 6))
        # 标题加书签锚点
        anchor = f'<a name="{key}"/>'
        items.append(
            Paragraph(anchor + inline_markup(title_text), self.S[style_key])
        )
        if level == 1:
            # H1 下面加一条天蓝色装饰线
            items.append(Spacer(1, 2))
            items.append(
                Table(
                    [[""]],
                    colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
                    rowHeights=[2],
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), SKY_BLUE),
                        ("LINEBELOW", (0, 0), (-1, -1), 0, SKY_BLUE),
                    ]),
                )
            )
            items.append(Spacer(1, 8))
        return items

    def _make_image(self, src, alt=""):
        """将 Markdown 图片转为 PDF 内嵌图片，自动缩放到页面宽度以内。"""
        img_path = os.path.join(self.base_dir, src)
        if not os.path.isfile(img_path):
            # 图片找不到时退化为文字说明
            label = alt or src
            return [
                Paragraph(
                    f'<i><font color="#999999">[图片: {escape_xml(label)}]</font></i>',
                    self.S["body"],
                ),
                Spacer(1, 4),
            ]
        max_w = PAGE_W - MARGIN_L - MARGIN_R
        max_h = 260  # 限制图片最大高度（点），避免撑爆页面
        try:
            img = RLImage(img_path)
            iw, ih = img.imageWidth, img.imageHeight
            if iw <= 0 or ih <= 0:
                raise ValueError("bad dimensions")
            ratio = min(max_w / iw, max_h / ih, 1.0)  # 不放大，只缩小
            img.drawWidth = iw * ratio
            img.drawHeight = ih * ratio
            img.hAlign = "CENTER"
            result = [Spacer(1, 4), img, Spacer(1, 4)]
            if alt:
                result.append(
                    Paragraph(
                        f'<font size="8" color="#888888">{escape_xml(alt)}</font>',
                        ParagraphStyle("img_caption", parent=self.S["body"], alignment=TA_CENTER, spaceBefore=0, spaceAfter=6),
                    )
                )
            return result
        except Exception as e:
            label = alt or src
            return [
                Paragraph(
                    f'<i><font color="#999999">[图片加载失败: {escape_xml(label)} — {escape_xml(str(e))}]</font></i>',
                    self.S["body"],
                ),
                Spacer(1, 4),
            ]

    def _make_code_block(self, code_lines, lang=""):
        """生成代码块 flowable（带浅色背景 + 语法高亮）。"""
        code_text = "\n".join(code_lines)
        code_xml = _highlight_code(code_text, lang)
        # 用 XPreformatted 保持格式（继承自 Paragraph，正确处理 XML 实体）
        pre = XPreformatted(code_xml, self.S["code"])
        # 包在表格里加背景色
        t = Table(
            [[pre]],
            colWidths=[PAGE_W - MARGIN_L - MARGIN_R - 12],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]),
        )
        return [Spacer(1, 4), t, Spacer(1, 4)]

    def _make_table(self, table_lines):
        """生成表格 flowable。"""
        raw = parse_table(table_lines)
        if not raw:
            return []

        # 把每个 cell 变成 Paragraph 以支持自动换行和 inline markup
        cell_style = ParagraphStyle(
            "table_cell", parent=self.S["body"],
            fontSize=9, leading=13, alignment=TA_LEFT,
        )
        cell_head_style = ParagraphStyle(
            "table_head", parent=cell_style,
            fontName="NotoSansSC-Bold", textColor=DARK_TEXT,
        )

        data = []
        for ri, row in enumerate(raw):
            style = cell_head_style if ri == 0 else cell_style
            data.append([Paragraph(inline_markup(c), style) for c in row])

        n_cols = max(len(r) for r in data)
        col_w = (PAGE_W - MARGIN_L - MARGIN_R - 12) / n_cols

        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        # 交替行背景
        for ri in range(1, len(data)):
            if ri % 2 == 0:
                t_style.append(("BACKGROUND", (0, ri), (-1, ri), TABLE_ALT))

        t = Table(data, colWidths=[col_w] * n_cols, style=TableStyle(t_style))
        return [Spacer(1, 4), t, Spacer(1, 6)]


# ── 页面模板（背景色 + 页眉页脚）──────────────────────────────────

def _draw_page_bg(canvas_obj, doc):
    """绘制每页的浅黄底色和页脚。"""
    canvas_obj.saveState()
    # 底色
    canvas_obj.setFillColor(CREAM)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # 页脚：页码
    canvas_obj.setFont("NotoSansSC", 8)
    canvas_obj.setFillColor(HexColor("#999999"))
    canvas_obj.drawCentredString(PAGE_W / 2, 1.2 * cm, f"— {doc.page} —")
    # 页脚线
    canvas_obj.setStrokeColor(LIGHT_BLUE)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN_L, 1.8 * cm, PAGE_W - MARGIN_R, 1.8 * cm)
    canvas_obj.restoreState()


def _draw_cover_bg(canvas_obj, doc):
    """封面页背景。"""
    canvas_obj.saveState()
    canvas_obj.setFillColor(CREAM)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # 顶部装饰条
    canvas_obj.setFillColor(SKY_BLUE)
    canvas_obj.rect(0, PAGE_H - 3 * cm, PAGE_W, 3 * cm, fill=1, stroke=0)
    # 底部装饰条
    canvas_obj.setFillColor(LIGHT_BLUE)
    canvas_obj.rect(0, 0, PAGE_W, 1.2 * cm, fill=1, stroke=0)
    canvas_obj.restoreState()


# ── 书籍配置 ──────────────────────────────────────────────────────

BOOKS = {
    "ostep": {
        "title": "OSTEP 精简版",
        "subtitle": "Operating Systems: Three Easy Pieces",
        "tagline": "后端面试速查笔记",
        "tags": "虚拟化 · 并发 · 持久化",
        "dir": "ostep",
        "parts": {
            "01": "第一部分：虚拟化",
            "02": "第二部分：并发",
            "03": "第三部分：持久化",
        },
        "files": [
            "ostep-01-01.md", "ostep-01-02.md", "ostep-01-03.md", "ostep-01-04.md",
            "ostep-01-05.md", "ostep-01-06.md", "ostep-01-07.md", "ostep-01-08.md",
            "ostep-01-09.md", "ostep-01-10.md", "ostep-01-11.md", "ostep-01-12.md",
            "ostep-01-13.md",
            "ostep-02-01.md", "ostep-02-02.md", "ostep-02-03.md", "ostep-02-04.md",
            "ostep-02-05.md", "ostep-02-06.md", "ostep-02-07.md", "ostep-02-08.md",
            "ostep-03-01.md", "ostep-03-02.md", "ostep-03-03.md", "ostep-03-04.md",
            "ostep-03-05.md",
        ],
    },
    "redis": {
        "title": "Redis 设计与实现 精简版",
        "subtitle": "Redis Design and Implementation",
        "tagline": "后端面试速查笔记",
        "tags": "常用命令 · 数据结构 · 单机数据库 · 多机数据库",
        "dir": "redis",
        "parts": {
            "00": "常用命令速查",
            "01": "第一部分：数据结构与对象",
            "02": "第二部分：单机数据库",
            "03": "第三部分：多机数据库",
        },
        "files": [
            "redis-00-01.md",
            "redis-01-01.md", "redis-01-02.md", "redis-01-03.md", "redis-01-04.md",
            "redis-01-05.md",
            "redis-02-01.md", "redis-02-02.md", "redis-02-03.md", "redis-02-04.md",
            "redis-02-05.md",
            "redis-03-01.md", "redis-03-02.md", "redis-03-03.md",
        ],
    },
    "mysql": {
        "title": "MySQL 是怎样运行的 精简版",
        "subtitle": "How MySQL Works: Understanding from the Root",
        "tagline": "后端面试速查笔记",
        "tags": "常用命令 · 存储与索引 · 查询优化 · 事务与锁",
        "dir": "mysql",
        "parts": {
            "00": "常用命令速查",
            "01": "第一部分：存储引擎与索引",
            "02": "第二部分：查询优化",
            "03": "第三部分：事务与锁",
        },
        "files": [
            "mysql-00-01.md",
            "mysql-01-01.md", "mysql-01-02.md", "mysql-01-03.md", "mysql-01-04.md",
            "mysql-01-05.md",
            "mysql-02-01.md", "mysql-02-02.md", "mysql-02-03.md", "mysql-02-04.md",
            "mysql-03-01.md", "mysql-03-02.md", "mysql-03-03.md", "mysql-03-04.md",
            "mysql-03-05.md",
        ],
    },
}


# ── 构建 PDF ─────────────────────────────────────────────────────

def build_pdf(book_key):
    book = BOOKS[book_key]
    src_dir = os.path.join(os.path.dirname(__file__), "..", "simplified", book["dir"])
    out_path = os.path.join(os.path.dirname(__file__), "..", "simplified", f"{book['dir']}-simplified.pdf")

    styles = make_styles()
    converter = MarkdownToFlowables(styles)

    story = []

    # ── 封面 ──
    story.append(NextPageTemplate("cover"))
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph(book["title"], styles["cover_title"]))
    story.append(Spacer(1, 1 * cm))
    story.append(
        Paragraph(
            book["subtitle"],
            ParagraphStyle("cover_en", parent=styles["cover_sub"], fontSize=12, textColor=HexColor("#777777")),
        )
    )
    story.append(Spacer(1, 1.5 * cm))
    story.append(
        Paragraph(
            book["tagline"],
            styles["cover_sub"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            f'<font color="#D9534F">{book["tags"]}</font>',
            ParagraphStyle("cover_tags", parent=styles["cover_sub"], fontSize=12),
        )
    )

    story.append(NextPageTemplate("normal"))
    story.append(PageBreak())

    # ── 目录页 ──
    story.append(Paragraph("目录", styles["h1"]))
    story.append(
        Table(
            [[""]],
            colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
            rowHeights=[2],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), SKY_BLUE)]),
        )
    )
    story.append(Spacer(1, 12))
    # 目录会在第二遍填充，先放占位符
    toc_placeholder_index = len(story)  # 记录位置

    # ── 正文 ──
    current_part = None
    for fname in book["files"]:
        fpath = os.path.join(src_dir, fname)
        if not os.path.exists(fpath):
            print(f"WARNING: {fpath} not found, skipping")
            continue

        # 检查是否进入新的 Part（文件名格式：xxx-PP-NN.md）
        parts = fname.rsplit(".", 1)[0].split("-")
        part_key = parts[-2] if len(parts) >= 3 else "01"
        if part_key != current_part:
            current_part = part_key
            story.append(PageBreak())
            # Part 分隔页
            story.append(Spacer(1, 5 * cm))
            part_name = book["parts"].get(part_key, f"Part {part_key}")
            # 加一条蓝色装饰
            story.append(
                Table(
                    [[""]],
                    colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
                    rowHeights=[3],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), SKY_BLUE)]),
                )
            )
            story.append(Spacer(1, 12))
            story.append(
                Paragraph(
                    part_name,
                    ParagraphStyle(
                        "part_title", parent=styles["h1"],
                        fontSize=26, leading=36, alignment=TA_CENTER,
                    ),
                )
            )
            story.append(Spacer(1, 8))
            story.append(
                Table(
                    [[""]],
                    colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
                    rowHeights=[3],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), SKY_BLUE)]),
                )
            )
            story.append(PageBreak())

        # 每章新页
        file_flowables = converter.convert_file(fpath)
        story.extend(file_flowables)
        story.append(PageBreak())

    # ── 在目录位置插入目录条目 ──
    toc_items = []
    for level, title, key in converter.toc_entries:
        if level > 2:
            continue  # 目录只收录 H1/H2
        style_key = "toc_h1" if level == 1 else "toc_h2"
        prefix = "　" * (level - 1)
        linked_title = f'{prefix}<a href="#{key}" color="#2C3E50">{escape_xml(title)}</a>'
        toc_items.append(Paragraph(linked_title, styles[style_key]))
        toc_items.append(Spacer(1, 2))

    # 把目录项插入 story
    for idx, item in enumerate(toc_items):
        story.insert(toc_placeholder_index + idx, item)

    # ── 构建 ──
    frame_normal = Frame(
        MARGIN_L, MARGIN_B,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - MARGIN_T - MARGIN_B,
        id="normal_frame",
    )
    frame_cover = Frame(
        MARGIN_L, MARGIN_B,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - MARGIN_T - MARGIN_B,
        id="cover_frame",
    )

    doc = BaseDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title=book["title"],
        author="Simplified",
    )
    doc.addPageTemplates([
        PageTemplate(id="cover",  frames=[frame_cover],  onPage=_draw_cover_bg),
        PageTemplate(id="normal", frames=[frame_normal], onPage=_draw_page_bg),
    ])

    print(f"Building {book['title']} with {len(story)} flowables...")
    doc.build(story)
    print(f"✓ PDF saved to {out_path}")


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(BOOKS.keys())
    for t in targets:
        if t not in BOOKS:
            print(f"ERROR: unknown book '{t}'. Available: {', '.join(BOOKS.keys())}")
            sys.exit(1)
        build_pdf(t)
