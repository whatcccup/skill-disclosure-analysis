# Skill Disclosure Analysis

This skill separates “understand an existing skill → extract reusable rules → adapt them to your workflow” into three on-demand subskills. Start at [SKILL.md](SKILL.md). A source skill remains evidence to inspect; reading it does not authorize running it.

| Stage | Use it when | Deliverable |
| --- | --- | --- |
| [Explain](subskills/explain.md) | You need to understand a specified skill and its boundaries | A dialog asks for a brief explanation or a full Markdown report with draw.io/SVG; no answer defaults to the full deliverable. The original procedure is preserved, with a tighter diagram scope |
| [Split](subskills/split.md) | You need to decide which source rules can migrate and how to use them | Four decisions with learner actions, contextual seven-field mapping, a candidate skeleton for a defined task family |
| [Upgrade](subskills/upgrade.md) | You want to adapt one source capability or compose a new workflow | Choose the source branch or candidate skeleton, review impact and gaps, then create and rehearse after confirmation |

Stages do **not** run automatically in sequence. A request to explain a skill does not silently create a derivative. The upgrade stage asks only for missing decisions that block progress and waits for confirmation of the adaptation map before writing a new `SKILL.md`. Evidence links and rule IDs connect the stages without copying whole reports.

The split stage explains the source rule's input, decision, action, and observable effect before choosing how to adapt it. A skeleton is a discussion template for a stated task family. An existing-artifact-plus-new-materials update workflow does not automatically apply to work created from scratch or to every semantic extraction task.

Upgrade has two routes. A local adaptation starts from the source skill's selected capability and its dependencies, preserving valid steps while changing the requested parts. A workflow recomposition starts from selected mechanisms and a suitable candidate skeleton. A narrow skeleton must not erase useful behavior from the original capability.

**Analysis files default to the current project folder**, not the skills installation folder. If the project or output folder cannot be identified, ask the user for a concrete analysis directory before writing files. A newly derived skill has a separate installation location.

## Package layout

- `SKILL.md`: entry point and stage router.
- `subskills/`: operational instructions for the three stages. The explain workflow is preserved, with the user-requested delivery choice, diagram scope, and output-location rules added.
- `references/`: existing diagram and evidence guides, unchanged.
- `scripts/render_disclosure.py`: renders reviewed JSON to draw.io and SVG; it does not run the analyzed skill.
- `harness/` and `scripts/run_harness.py`: stage gates, deduplication rules, regression scenarios, and a static/diagram smoke test.

## Verification

Run from this directory:

```bash
python3 scripts/run_harness.py
```

This checks the explanation core against its current baseline, package structure, regression case coverage, and a diagram generated in a temporary directory. Real-world facts, human confirmation, editor display, and desktop behavior require separate verification. See the [Harness](harness/README.md).

The disclosure diagram shows modules that affect the skill's work. Ordinary README, License, and Changelog files stay out of the graph. When a source enumerates trigger phrases or branches, the cards spell out each item and its effect instead of merely reporting a count.

Licensed under [MIT](LICENSE.md). If you reuse third-party code or substantial text, review its license and attribution separately.
