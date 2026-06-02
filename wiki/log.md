# Wiki Log

## 2026-06-02

- Initialized repo wiki according to `AGENT.md`.
- Added architecture overview, preprocessing module notes, OpenCRAVAT MVP decision record, and glossary.
- Recorded Kaggle consumer SNP CSV -> OpenCRAVAT TSV conversion script and observed row counts.
- Pivoted MVP annotation strategy to API-first after OpenCRAVAT local annotator module install proved brittle. Uninstalled `pharmgkb`, `gwas_catalog`, and `litvar`; `clinvar_acmg` was not installed successfully.
- Updated current candidate strategy to test ANNOVAR + InterVar as the clinical backbone, with API-first tools retained as fallback/enrichment and Ensembl VEP as benchmark.
