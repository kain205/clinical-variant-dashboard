# Wiki Log

## 2026-06-05

- Updated preprocessing wiki with full Child 1 ANNOVAR rsID-route phase2 artifact status: 592,580 selected rsIDs, 546,068 mapped in selected dbSNP subset, 46,512 unresolved, 4,147 multi-mapping rsIDs, and generated `converted.avinput`, `multianno.txt`, `.intervar`, and `join_back.tsv`.
- Updated `docs/bao_cao_tuan_2.md` so the full-file ANNOVAR rsID route is marked as demo-ready, while InterVar direct/default database mode remains a manual heavy task.
- Added `src/workbench/intervar_pipeline.py` and Streamlit `Full SNP -> InterVar` tab so current built-in/uploaded consumer SNP input can run the local DB route into a fresh `full_intervar_runs/run_*` folder, normalize InterVar classification counts, and expose a HITL review queue.
- Hardened the full InterVar runner after `run_20260605_162642`: regenerate `join_back.tsv` when InterVar writes output but exits non-zero, filter non-primary avinput contigs before new InterVar runs, and show pipeline warnings in Streamlit.
- Updated `docs/bao_cao_tuan_2.md` with Streamlit run `run_20260605_165354`: UI runtime around 28 minutes, 20,203 non-primary contig rows filtered, 788,431 InterVar data rows, 3 `Likely pathogenic`, and 2,090 `Uncertain significance`.

## 2026-06-04

- Added repo-scoped documentation skill `.agents/skills/clinical-variant-doc-writer/SKILL.md`.
- Added documentation workflow wiki page describing the maturity-level documentation approach and validation caveat.
- Rewrote `docs/bao_cao_tuan_1.md` using the documentation skill: reframed it from merged notes into a maturity-level report with MVP decisions, PoC evidence, benchmark plan, dashboard/demo readiness, and safety boundaries.
- Updated `docs/bao_cao_tuan_1.md` and the documentation skill for mentor-facing weekly report style: Week 1 deliverables table, 3-layer safety architecture, 4-part structure, and planned evaluation metrics.

## 2026-06-02

- Initialized repo wiki according to `AGENT.md`.
- Added architecture overview, preprocessing module notes, OpenCRAVAT MVP decision record, and glossary.
- Recorded Kaggle consumer SNP CSV -> OpenCRAVAT TSV conversion script and observed row counts.
- Pivoted MVP annotation strategy to API-first after OpenCRAVAT local annotator module install proved brittle. Uninstalled `pharmgkb`, `gwas_catalog`, and `litvar`; `clinvar_acmg` was not installed successfully.
- Updated current candidate strategy to prioritize Dockerized Ensembl VEP as the production annotation backbone; MyVariant.info is retained as lookup/enrichment fallback, and ANNOVAR + InterVar is retained only as optional benchmark/classification context.
