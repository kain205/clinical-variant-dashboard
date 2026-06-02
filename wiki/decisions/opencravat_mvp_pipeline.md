# Decision: OpenCRAVAT MVP Pipeline (Superseded)

## Purpose

Record the previous OpenCRAVAT-centered direction and why it is no longer the MVP backbone.

Current decision: superseded by [API-first MVP annotation](api_first_mvp_annotation.md).

## Key Files

- `docs/core/01_research_genomics_datasets.md`
- `docs/core/02_data_preprocessing.md`
- `docs/supplementary/annotation_tools_manual_testing_notes.md`
- `src/preprocessing/convert_consumer_genome.py`

## Important Concepts

- Use OpenCRAVAT only for optional file-level validation/output experiments.
- Use MyVariant.info for selected variant fallback/enrichment.
- Use MyGene.info only after variant-to-gene mapping.
- Use MyChem.info only for optional drug/chemical enrichment in PGx views.
- Do not install OpenCRAVAT annotator modules for the MVP demo path.

## Data Flow

```text
OpenCRAVAT-ready TSV
  -> oc run ... -l hg19 -i 23andme
  -> SQLite / TSV / XLSX
  -> normalized dashboard schema
```

## Dependencies

Minimum OpenCRAVAT modules:

```powershell
oc module install 23andme-converter
oc module install hg19wgs
oc module install textreporter excelreporter
```

Attempted MVP-light annotators:

- `pharmgkb`
- `gwas_catalog`
- `litvar`

Outcome:

- `pharmgkb`, `gwas_catalog`, and `litvar` installed successfully but were uninstalled after the API-first pivot.
- `clinvar_acmg` install stalled.
- Full `clinvar` may pull or depend on large resources such as full `dbsnp`.

## Known Caveats

- PGP `hu43860C` build36/hg18 required forced `23andme` input and produced usable output with converter errors.
- Kaggle `genome_zeeshan_usmani.csv` is build37/hg19 but must be converted from comma CSV to tab-delimited TSV before OpenCRAVAT.
- `no such table: info` can appear after converter failure because the output SQLite is incomplete/corrupt.
- Local annotator installation is brittle enough that it should not block MVP reporting/demo work.

## Links

- [Architecture](../architecture.md)
- [API-first MVP annotation](api_first_mvp_annotation.md)
- [Preprocessing module](../modules/preprocessing.md)
- [Glossary](../glossary.md)

## Last Verified

2026-06-02
