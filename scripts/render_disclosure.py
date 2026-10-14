#!/usr/bin/env python3
"""Render a reviewed disclosure model as editable draw.io and SVG preview.

This script reads the analyst's JSON model. It never imports or runs code from the
skill being analysed. Only Python's standard library is required.
"""

import json
import os
import sys
import unicodedata
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET


WIDTH = 1840
LEFT = 150
LEFT_CHILD = 188
LEFT_WIDTH = 620
RIGHT = 840
RIGHT_WIDTH = 930
START_Y = 155
GAP = 26
FONT = 'system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif'
ANCILLARY_NAMES = {"license", "license.txt", "license.md", "readme", "readme.md",
                   "readme.en.md", "changelog", "changelog.md", "history.md"}


def work_ref(ref):
    path = ref.get("path")
    if not path:
        return True
    return bool(ref.get("work_relevant")) or Path(str(path)).name.lower() not in ANCILLARY_NAMES


def width_units(value):
    return sum(2 if unicodedata.east_asian_width(c) in "FW" else 1 for c in value)


def wrap(value, limit):
    """Wrap without silently dropping source text."""
    parts = []
    for para in str(value).splitlines() or [""]:
        buf = ""
        for char in para:
            if buf and width_units(buf + char) > limit:
                parts.append(buf)
                buf = ""
            buf += char
        parts.append(buf)
    return parts


def load_model(path):
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    root = Path(model["skill_root"]).expanduser().resolve()
    if not (root / "SKILL.md").is_file():
        raise ValueError("skill_root 必须包含 SKILL.md")
    all_sections = model["sections"]
    if not isinstance(all_sections, list) or not all_sections:
        raise ValueError("sections 必须是非空数组")
    ids = [str(s["id"]) for s in all_sections]
    if len(ids) != len(set(ids)):
        raise ValueError("sections.id 不能重复")
    required = ("title", "meaning", "input", "judgment", "action", "output")
    sections = []
    for original in all_sections:
        if original.get("diagram") is False:
            if not original.get("omission_reason"):
                raise ValueError(f"省略节点 {original['id']} 须写 omission_reason")
            continue
        section = dict(original)
        for key in required:
            if key not in section:
                raise ValueError(f"节点 {section['id']} 缺少 {key}")
        if section.get("level", 0) not in (0, 1):
            raise ValueError("level 只支持 0 或 1")
        ui = section.get("user_input")
        if ui and ui.get("type") not in ("conditional", "before_final", "required"):
            raise ValueError("user_input.type 不合法")
        if section.get("refs") and section.get("branches"):
            raise ValueError("同一节点不要同时填写 refs 与 branches；把文件放进分支，或拆成两个节点")
        details = section.get("details") or []
        if not isinstance(details, list) or any(not isinstance(item, dict) or not item.get("label") or not item.get("text") for item in details):
            raise ValueError(f"节点 {section['id']} details 须逐项写 label 与 text")
        section["refs"] = [ref for ref in section.get("refs") or [] if work_ref(ref)]
        section["branches"] = [branch for branch in section.get("branches") or [] if work_ref(branch)]
        sections.append(section)
    if not sections:
        raise ValueError("没有可绘制的工作节点")
    return root, sections


def resolve_ref(root, ref_path, out_dir):
    shown = "/" + str(ref_path).lstrip("/")
    target = (root / shown.lstrip("/")).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"引用越出 Skill 根目录：{shown}")
    if not target.exists():
        return shown, None
    return shown, os.path.relpath(target, out_dir).replace(os.sep, "/")


def card_lines(section):
    fields = (("含义", "meaning"), ("输入", "input"), ("判断", "judgment"),
              ("执行", "action"), ("输出", "output"))
    lines = []
    for label, key in fields:
        lines.extend(wrap(label + "：" + str(section[key]), 64))
    for item in section.get("details") or []:
        lines.extend(wrap(str(item["label"]) + "：" + str(item["text"]), 64))
    return lines


def item_height(section):
    card_h = max(196, 66 + len(card_lines(section)) * 24)
    if section.get("user_input"):
        card_h += 32
    refs = len(section.get("refs") or [])
    branches = len(section.get("branches") or [])
    if branches:
        right_h = max(196, 54 + branches * 80)
    elif refs:
        right_h = max(196, 25 + ((refs + 1) // 2) * 79)
    else:
        right_h = 196
    return card_h, right_h, max(card_h, right_h)


class Diagram:
    def __init__(self, root, out_base, sections):
        self.root_path = root
        self.out_base = Path(out_base).expanduser().resolve()
        self.out_base.parent.mkdir(parents=True, exist_ok=True)
        self.sections = sections
        self.heights = [item_height(s) for s in sections]
        self.total_height = START_Y + sum(h[2] + GAP for h in self.heights) + 45
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {WIDTH} {self.total_height}" role="img">',
            f'<style>text{{font-family:{FONT}}}.title{{font-size:30px;font-weight:700;fill:#202631}}.head{{font-size:19px;font-weight:700;fill:#202631}}.body{{font-size:16px;fill:#344054}}.small{{font-size:13px;fill:#667085}}.red{{font-size:13px;font-weight:700;fill:#b42318}}</style>',
            f'<rect width="{WIDTH}" height="{self.total_height}" fill="#f8f9fb"/>',
            '<text class="title" x="112" y="52">SKILL.md｜渐进式披露树</text>',
            '<text class="small" x="112" y="80">按原文顺序披露，不代表实际执行顺序；后段规则可能在前段作业中调用。</text>',
            '<text class="small" x="112" y="101">左：主干与子步骤　　右：判断分支、引用文件和该处用途　　红色：原文要求用户输入</text>',
            '<text class="head" x="150" y="140">SKILL.md 主干</text>',
            '<text class="head" x="840" y="140">引用与判断</text>',
        ]
        self.mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "agent": "skill-disclosure-analysis"})
        diagram = ET.SubElement(self.mxfile, "diagram", {"name": "SKILL.md 渐进披露树", "id": "disclosure"})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": str(WIDTH), "dy": str(self.total_height), "grid": "1", "gridSize": "10",
            "page": "1", "pageScale": "1", "pageWidth": str(WIDTH),
            "pageHeight": str(self.total_height), "math": "0", "shadow": "0"})
        self.xml_root = ET.SubElement(model, "root")
        ET.SubElement(self.xml_root, "mxCell", {"id": "0"})
        ET.SubElement(self.xml_root, "mxCell", {"id": "1", "parent": "0"})
        self.seq = 1
        self.node_ids = []
        self.missing = []
        root_link = os.path.relpath(self.root_path / "SKILL.md", self.out_base.parent).replace(os.sep, "/")
        self.cell(112, 15, 680, 112,
                  '<b>SKILL.md｜渐进式披露树</b><br>主干按原文顺序排列，不代表实际执行顺序。<br>后段规则可能在前段作业中调用。',
                  "rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                  "strokeColor=#CBD5E1;align=left;verticalAlign=middle;spacing=14;fontSize=17;",
                  root_link)
        self.cell(840, 15, 930, 112,
                  '<b>引用与判断</b><br>右侧卡片标文件名、完整相对路径与此处用途。<br>红色节点表示来源要求用户输入。',
                  "rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                  "strokeColor=#CBD5E1;align=left;verticalAlign=middle;spacing=14;fontSize=16;")

    def next_id(self):
        self.seq += 1
        return "c" + str(self.seq)

    def cell(self, x, y, w, h, label, style, link=None):
        ident = self.next_id()
        parent = self.xml_root
        attrs = {"style": style, "vertex": "1", "parent": "1"}
        if link:
            parent = ET.SubElement(self.xml_root, "UserObject", {"id": ident, "label": label, "link": link})
        else:
            attrs.update({"id": ident, "value": label})
        cell = ET.SubElement(parent, "mxCell", attrs)
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w),
                                            "height": str(h), "as": "geometry"})
        return ident

    def edge(self, start, end):
        ident = self.next_id()
        cell = ET.SubElement(self.xml_root, "mxCell", {
            "id": ident, "value": "", "edge": "1", "parent": "1",
            "source": start, "target": end,
            "style": "endArrow=classic;html=1;edgeStyle=orthogonalEdgeStyle;strokeColor=#98A2B3;strokeWidth=1.4;"})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    def svg_text(self, x, y, value, css="body", anchor=None):
        extra = f' text-anchor="{anchor}"' if anchor else ""
        self.svg.append(f'<text class="{css}" x="{x}" y="{y}"{extra}>{escape(str(value))}</text>')

    def svg_rect(self, x, y, w, h, fill="#fff", stroke="#d0d5dd", radius=8):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def svg_line(self, x1, y1, x2, y2, dash=False):
        dashed = ' stroke-dasharray="5 5"' if dash else ""
        self.svg.append(f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="#98a2b3" stroke-width="1.5"{dashed}/>')

    def ref_card(self, x, y, w, ref):
        path = ref.get("path")
        label = str(ref.get("label") or (Path(path).name if path else "结果"))
        use = str(ref.get("use") or "文档未说明用途")
        if any(width_units(value) > (w - 20) // 7 for value in (label, use)):
            raise ValueError(f"引用卡文字过长，需缩短：{label}")
        shown, link = resolve_ref(self.root_path, path, self.out_base.parent) if path else ("", None)
        if path and link is None:
            self.missing.append(shown)
            use = "缺失｜" + use
        border = "#f04438" if path and link is None else "#d0d5dd"
        if link:
            self.svg.append(f'<a href="{escape(link, quote=True)}" xlink:href="{escape(link, quote=True)}">')
        self.svg_rect(x, y, w, 68, "#f4f6f8", border, 7)
        self.svg_text(x + 11, y + 20, label, "head")
        self.svg_text(x + 11, y + 39, shown, "small")
        self.svg_text(x + 11, y + 58, use, "small")
        if link:
            self.svg.append("</a>")
        content = (f'<b>{escape(label)}</b><br><font color="#667085" style="font-size:13px">'
                   f'{escape(shown)}</font><br><font color="#667085" style="font-size:13px">'
                   f'{escape(use)}</font>')
        return self.cell(x, y, w, 68, content,
                         "rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor=#F4F6F8;"
                         f"strokeColor={border};align=left;verticalAlign=middle;spacing=10;fontSize=15;",
                         link)

    def section(self, section, y, heights):
        card_h, right_h, _ = heights
        child = section.get("level", 0) == 1
        x = LEFT_CHILD if child else LEFT
        w = LEFT_WIDTH - (LEFT_CHILD - LEFT if child else 0)
        num = str(section["id"])
        title = f'{num} · {section["title"]}'
        ui = section.get("user_input")
        red_border = bool(ui)
        root_link = os.path.relpath(self.root_path / "SKILL.md", self.out_base.parent).replace(os.sep, "/")
        self.svg_line(90 if not child else 128, y + 95, x, y + 95)
        if section.get("branches"):
            marker = 90 if not child else 128
            self.svg.append(f'<path d="M {marker} {y+80} L {marker+15} {y+95} L {marker} {y+110} L {marker-15} {y+95} Z" fill="#344054"/>')
            self.svg_text(marker, y + 100, "?", "small", "middle")
        else:
            marker = 90 if not child else 128
            self.svg.append(f'<circle cx="{marker}" cy="{y+95}" r="8" fill="#475467"/>')
        self.svg.append(f'<a href="{escape(root_link, quote=True)}" xlink:href="{escape(root_link, quote=True)}">')
        self.svg_rect(x, y, w, card_h, "#fff", "#d92d20" if red_border else "#cbd5e1", 9)
        self.svg_text(x + 17, y + 31, title, "head")
        for i, line in enumerate(card_lines(section)):
            self.svg_text(x + 17, y + 60 + i * 24, line)
        self.svg.append("</a>")
        label = '<b>' + escape(title) + '</b><br>' + '<br>'.join(escape(line) for line in card_lines(section))
        main_id = self.cell(x, y, w, card_h, label,
                            "rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                            f"strokeColor={'#D92D20' if red_border else '#CBD5E1'};"
                            "align=left;verticalAlign=middle;spacing=14;fontSize=16;", root_link)
        self.node_ids.append(main_id)
        if ui:
            defaults = {"conditional": "满足条件时先问", "before_final": "终版前确认",
                        "required": "必须输入"}
            badge = str(ui.get("label") or defaults[ui["type"]])
            bx = x + w - 183
            badge_y = y + card_h - 35
            self.svg_rect(bx, badge_y, 170, 27, "#fff1f0", "#d92d20", 6)
            self.svg_text(bx + 85, badge_y + 18, badge, "red", "middle")
            self.cell(bx, badge_y, 170, 27, escape(badge),
                      "rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor=#FFF1F0;"
                      "strokeColor=#D92D20;fontColor=#B42318;align=center;verticalAlign=middle;"
                      "fontStyle=1;fontSize=13;")
        refs = section.get("refs") or []
        branches = section.get("branches") or []
        if refs or branches:
            self.svg_line(x + w, y + 95, RIGHT - 9, y + 95, True)
            self.svg_rect(RIGHT, y, RIGHT_WIDTH, right_h)
            panel_id = self.cell(RIGHT, y, RIGHT_WIDTH, right_h, "引用与判断",
                                 "rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                                 "strokeColor=#D0D5DD;fontColor=#667085;fontSize=13;")
            self.edge(main_id, panel_id)
        if refs:
            for i, ref in enumerate(refs):
                rx = RIGHT + 18 + (i % 2) * 445
                ry = y + 17 + (i // 2) * 79
                self.ref_card(rx, ry, 426, ref)
        if branches:
            self.svg_text(RIGHT + 18, y + 30, "判断分支：按证据条件展开", "head")
            decision_y = y + right_h / 2
            dx = RIGHT + 60
            self.svg.append(f'<path d="M {dx} {decision_y-36} L {dx+38} {decision_y} L {dx} {decision_y+36} L {dx-38} {decision_y} Z" fill="#344054"/>')
            self.svg_text(dx, decision_y + 5, "判断", "small", "middle")
            d_id = self.cell(dx - 38, decision_y - 36, 76, 72, "判断", "rhombus;html=1;"
                             "fillColor=#344054;strokeColor=#344054;fontColor=#FFFFFF;"
                             "align=center;verticalAlign=middle;fontSize=14;")
            self.edge(main_id, d_id)
            for i, branch in enumerate(branches):
                by = y + 48 + i * 80
                condition = str(branch.get("condition") or "条件未说明")
                result = str(branch.get("label") or "结果")
                shown = f'{condition} → {result}'
                condition_lines = wrap(shown, 35)
                if len(condition_lines) > 3:
                    raise ValueError(f"分支标签过长，需缩短：{shown}")
                self.svg_line(dx + 38, decision_y, RIGHT + 107, decision_y)
                self.svg_line(RIGHT + 107, decision_y, RIGHT + 107, by + 35)
                self.svg_line(RIGHT + 107, by + 35, RIGHT + 120, by + 35)
                self.svg_rect(RIGHT + 120, by, 305, 68, "#fff", "#d0d5dd", 7)
                for j, line in enumerate(condition_lines):
                    self.svg_text(RIGHT + 130, by + 20 + j * 19, line, "small")
                c_id = self.cell(RIGHT + 120, by, 305, 68, escape(shown),
                                 "rounded=1;arcSize=6;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                                 "strokeColor=#D0D5DD;align=left;verticalAlign=middle;spacing=10;"
                                 "fontSize=13;")
                self.edge(d_id, c_id)
                ref = {"path": branch.get("path"), "label": branch.get("file_name")
                       or (Path(branch["path"]).name if branch.get("path") else result),
                       "use": branch.get("use") or "本分支的依据"}
                rid = self.ref_card(RIGHT + 442, by, 469, ref)
                self.edge(c_id, rid)

    def render(self):
        y = START_Y
        self.svg_line(90, START_Y + 95, 90,
                      START_Y + sum(h[2] + GAP for h in self.heights[:-1]) + 95)
        for section, heights in zip(self.sections, self.heights):
            self.section(section, y, heights)
            y += heights[2] + GAP
        for a, b in zip(self.node_ids, self.node_ids[1:]):
            self.edge(a, b)
        self.svg_text(112, self.total_height - 20,
                      "draw.io 为可编辑源文件；SVG 为预览。源 Skill 未由本脚本执行。", "small")
        self.svg.append("</svg>")
        self.out_base.with_suffix(".svg").write_text("\n".join(self.svg), encoding="utf-8")
        ET.indent(self.mxfile, space="  ")
        ET.ElementTree(self.mxfile).write(self.out_base.with_suffix(".drawio"),
                                          encoding="utf-8", xml_declaration=True)
        return self.missing


def main(argv):
    if len(argv) != 2:
        print("用法：render_disclosure.py model.json /path/to/output-base", file=sys.stderr)
        return 2
    root, sections = load_model(argv[0])
    missing = Diagram(root, argv[1], sections).render()
    print(str(Path(argv[1]).with_suffix(".drawio")))
    print(str(Path(argv[1]).with_suffix(".svg")))
    if missing:
        print("未找到的引用：" + "、".join(sorted(set(missing))), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"模型错误：{exc}", file=sys.stderr)
        sys.exit(2)
