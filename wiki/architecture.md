# Architecture

## Purpose

Capture the current high-level MVP architecture so future work can start from the same mental model.

## Key Files

- `docs/bao_cao_tuan_1.md`
- `src/dashboard/streamlit_app.py`
- `src/workbench/intervar_pipeline.py`
- `src/preprocessing/convert_consumer_genome.py`
- `src/preprocessing/build_annovar_intervar_testset.py`

## Important Concepts

- Consumer SNP input remains the main user-facing input, especially `rsID + genotype` files.
- Dockerized Ensembl VEP is the current production annotation backbone candidate.
- API lookup/enrichment remains the fallback and explanation path; MyVariant.info is not treated as the production annotation backbone.
- OpenCRAVAT is optional local file-level validation, not a required MVP dependency.
- Chatbot behavior should be grounded in the selected annotation run and source links.
- Kaggle `Child 1 Genome.csv` is the current concrete test input for VEP/benchmark preparation; metadata indicates build37/GRCh37/hg19.
- The Streamlit workbench now has a dedicated `Full SNP -> InterVar` tab that runs the local DB route on the current UI input and creates a fresh run folder under `data/processed/workbench/full_intervar_runs/`.

## Data Flow

```text
consumer SNP file
  -> preprocessing / delimiter normalization
  -> preserve original rsID, chromosome, position, genotype, build
  -> curated or clinically relevant rsID subset
  -> normalize rsID to VEP-compatible input
  -> Dockerized VEP with matching GRCh37/hg19 cache
  -> parse VEP annotations
  -> join original genotype back to annotation rows
  -> MyVariant.info lookup/enrichment for unresolved or selected variants
  -> MyGene.info enrichment for mapped gene symbols
  -> ClinPGx/PharmGKB API for PGx context
  -> optional MyChem.info enrichment for PGx drugs
  -> optional ANNOVAR/InterVar benchmark/classification experiment
  -> normalized result schema
  -> evidence-priority scoring
  -> dashboard report + assistant context
```

## Dependencies

- Python preprocessing script.
- Ensembl VEP Docker/local CLI + matching cache for the tested genome build.
- MyVariant.info, MyGene.info, ClinPGx/PharmGKB APIs as fallback/enrichment.
- Optional Ensembl REST / Variant Recoder prototype for selected variants.
- Optional ANNOVAR + InterVar benchmark/classification experiment and synchronous Streamlit full-run tab.
- Optional OpenCRAVAT converter/mapper/report export for local validation only.

## Known Caveats

- Build37 means GRCh37/hg19, not hg38.
- `Child 1 Genome.csv` parsing and testset generation are verified, but VEP Docker/cache setup is still the next implementation step.
- rsID normalization can produce multiple records for one rsID.
- Genotype context must be joined back after VEP annotation.
- VEP/ClinVar/InterVar-style annotations do not replace expert clinical review.
- OpenCRAVAT `23andme-converter` expects tab-delimited input if used.
- InterVar direct/default mode still needs heavy local databases such as `dbnsfp42a`, `gnomad_genome`, `1000g2015aug`, and related resources; the Streamlit full-run tab intentionally uses the local DB route that is already available.

## Links

- [Preprocessing module](modules/preprocessing.md)
- [Dockerized VEP production annotation](decisions/dockerized_vep_production_annotation.md)
- [ANNOVAR + InterVar candidate backbone](decisions/annovar_intervar_candidate_backbone.md) - superseded as production default; retained as benchmark context.
- [API-first fallback decision](decisions/api_first_mvp_annotation.md)
- [OpenCRAVAT superseded decision](decisions/opencravat_mvp_pipeline.md)
- [Glossary](glossary.md)

## Last Verified

2026-06-02
