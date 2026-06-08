# Documentation Workflow

## Purpose

Keep project documentation focused on maturity rather than the original six-week roadmap. Documentation should move from survey content toward MVP decisions, PoC evidence, benchmark readiness, dashboard/demo evidence, and safety-aware reporting.

## Key files

- `.agents/skills/clinical-variant-doc-writer/SKILL.md`
- `docs/bao_cao_tuan_1.md`
- `docs/images/`

## Important concepts

- The repo has a project-scoped Codex skill named `clinical-variant-doc-writer`.
- Use the skill for writing, editing, reviewing, or extending Markdown docs for the Clinical Variant Analytics Dashboard.
- The skill treats the six-week roadmap as a stakeholder tracking frame while surfacing real PoC and benchmark-readiness evidence.
- Preferred documentation maturity path: `Survey -> Decision -> PoC evidence -> Benchmark -> Dashboard/demo evidence`.
- Clinical docs must preserve safety boundaries: educational/decision-support only, no diagnosis, no medication-change advice.
- Mentor-facing weekly reports should use a 4-part structure, a scannable deliverables table, positive safety architecture language, and planned evaluation metrics when benchmark results are not measured yet.

## Data flow

```text
rough notes / current repo evidence
  -> clinical-variant-doc-writer guidance
  -> maturity-level documentation
  -> docs/bao_cao_tuan_1.md
  -> optional screenshots in docs/images/
```

## Dependencies

- The skill is repo-scoped under `.agents/skills`, so it travels with this project.
- Skill validation can use `quick_validate.py` from the system `skill-creator` skill if the active Python environment has `PyYAML` installed.

## Known caveats

- Do not let docs invent completed experiments or benchmark numbers.
- Do not force content to stay inside the original week-by-week roadmap if the project already has stronger PoC evidence.
- The current Python environment used for validation may not include `PyYAML`, causing `quick_validate.py` to fail before checking the skill.

## Links to related wiki pages

- [Architecture](../architecture.md)
- [Preprocessing module](preprocessing.md)
- [Dockerized VEP production annotation](../decisions/dockerized_vep_production_annotation.md)
- [Glossary](../glossary.md)

## Last verified date

2026-06-04
