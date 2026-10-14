#!/usr/bin/env python3
"""Static gates and diagram smoke test for the three-stage skill package."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def check_explain_snapshot():
    text = (ROOT / "subskills/explain.md").read_text(encoding="utf-8")
    text = text.split("\n## 本轮新增｜交付选择与披露图聚焦\n", 1)[0]
    normalized = text.replace("(../references/artifacts.md)", "(references/artifacts.md)")
    normalized = normalized.replace("(../references/evidence.md)", "(references/evidence.md)")
    normalized = normalized.replace("`../scripts/render_disclosure.py`", "`scripts/render_disclosure.py`")
    expected = (ROOT / "harness/explain-body.sha256").read_text().strip()
    actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if actual != expected:
        raise AssertionError("explain core differs from the approved baseline")


def check_package():
    required = ["SKILL.md", "subskills/explain.md", "subskills/split.md", "subskills/upgrade.md",
                "references/artifacts.md", "references/evidence.md", "scripts/render_disclosure.py",
                "README.md", "README.en.md", "LICENSE"]
    for name in required:
        if not (ROOT / name).is_file():
            raise AssertionError(f"missing {name}")
    cases = json.loads((ROOT / "harness/cases.json").read_text(encoding="utf-8"))
    expected = {"explain", "split", "upgrade-review", "upgrade-build"}
    if {c["expected_stage"] for c in cases} != expected:
        raise AssertionError("harness cases do not cover all four gates")
    if len({c["id"] for c in cases}) != len(cases):
        raise AssertionError("duplicate harness case id")
    split_text = (ROOT / "subskills/split.md").read_text(encoding="utf-8")
    for phrase in ("读者下一步", "可观察效果", "适用任务", "不适用任务", "不是所有语义提取任务",
                   "完整文件名", "Markdown 链接", "文档内定位线索", "只能跳到文件，不能直达该段"):
        if phrase not in split_text:
            raise AssertionError(f"split teaching gate missing: {phrase}")
    if "split-overcompressed-example" not in {c["id"] for c in cases}:
        raise AssertionError("missing contextual split regression case")
    upgrade_text = (ROOT / "subskills/upgrade.md").read_text(encoding="utf-8")
    for phrase in ("局部改造", "工作流重组", "候选骨架不是默认起点", "时间轴触发", "受影响的上下游模块"):
        if phrase not in upgrade_text:
            raise AssertionError(f"upgrade route gate missing: {phrase}")
    if "upgrade-local-timeline-layout" not in {c["id"] for c in cases}:
        raise AssertionError("missing local-adaptation regression case")


def check_diagram():
    with tempfile.TemporaryDirectory(prefix="skill-disclosure-harness-") as temp:
        folder = Path(temp)
        source = folder / "source"
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: sample\ndescription: sample\n---\n# Step\n", encoding="utf-8")
        (source / "references/rule.md").write_text("# Sample rule\n", encoding="utf-8")
        (source / "README.md").write_text("# About\n", encoding="utf-8")
        (source / "LICENSE").write_text("Sample license\n", encoding="utf-8")
        model = {"skill_root": str(source), "sections": [
            {"id": "1", "title": "触发", "meaning": "四种口令进入示例流程",
             "input": "用户请求", "judgment": "是否匹配口令", "action": "调用相应处理", "output": "候选结果",
             "details": [{"label": f"口令 {i}", "text": f"示例口令{i}：进入对应动作{i}"} for i in range(1, 5)],
             "refs": [{"path": "/references/rule.md", "use": "核对规则"},
                      {"path": "/README.md", "use": "一般介绍"}]},
            {"id": "2", "title": "许可", "diagram": False, "omission_reason": "只说明许可，不改变技能工作"}]}
        model_path = folder / "model.json"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        target = folder / "diagram"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/render_disclosure.py"), str(model_path), str(target)],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise AssertionError(f"diagram smoke test failed: {result.stderr}")
        drawio = ET.parse(target.with_suffix(".drawio"))
        svg = ET.parse(target.with_suffix(".svg"))
        if not drawio.findall(".//mxCell") or not svg.getroot().tag.endswith("svg"):
            raise AssertionError("diagram output has no editable cells or SVG root")
        svg_text = target.with_suffix(".svg").read_text(encoding="utf-8")
        if any(f"示例口令{i}" not in svg_text for i in range(1, 5)):
            raise AssertionError("explicit trigger examples were collapsed")
        if "README.md" in svg_text or "许可" in svg_text:
            raise AssertionError("ancillary material leaked into diagram")


def main():
    check_explain_snapshot()
    check_package()
    check_diagram()
    print("PASS: explanation core matches baseline; package and stage cases present; diagram smoke test passed")


if __name__ == "__main__":
    main()
