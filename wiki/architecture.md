# Architecture

## Purpose

Capture the current high-level MVP architecture so future work can start from the same mental model.

## Key Files

- `docs/supplementary/mvp_scope.md`
- `docs/core/01_research_genomics_datasets.md`
- `docs/core/02_data_preprocessing.md`
- `src/preprocessing/convert_consumer_genome.py`

## Important Concepts

- Consumer SNP input remains the main user-facing input, especially `rsID + genotype` files.
- ANNOVAR + InterVar is the current candidate clinical annotation/classification backbone.
- API-first annotation/enrichment remains the fallback and enrichment path.
- OpenCRAVAT is optional local file-level validation, not a required MVP dependency.
- Chatbot behavior should be grounded in the selected annotation run and source links.

## Data Flow

```text
consumer SNP file
  -> preprocessing / delimiter normalization
  -> preserve original rsID, chromosome, position, genotype, build
  -> curated or clinically relevant rsID subset
  -> convert rsID to ANNOVAR avinput with matching dbSNP/humandb
  -> ANNOVAR annotation
  -> InterVar ACMG/AMP-style clinical classification
  -> join original genotype back to annotation rows
  -> MyVariant.info fallback/enrichment for unresolved or selected variants
  -> MyGene.info enrichment for mapped gene symbols
  -> ClinPGx/PharmGKB API for PGx context
  -> optional MyChem.info enrichment for PGx drugs
  -> normalized result schema
  -> evidence-priority scoring
  -> dashboard report + assistant context
```

## Dependencies

- Python preprocessing script.
- ANNOVAR + matching humandb/dbSNP database for the tested genome build.
- InterVar.
- MyVariant.info, MyGene.info, ClinPGx/PharmGKB APIs as fallback/enrichment.
- Optional Ensembl VEP / Variant Recoder benchmark for selected variants.
- Optional OpenCRAVAT converter/mapper/report export for local validation only.

## Known Caveats

- Build37 means GRCh37/hg19, not hg38.
- ANNOVAR rsID conversion can produce multiple records for one rsID.
- Genotype context must be joined back after ANNOVAR/InterVar annotation.
- InterVar classification does not replace expert clinical review.
- OpenCRAVAT `23andme-converter` expects tab-delimited input if used.
- Full local databases such as `dbsnp`, `gnomad`, and `cadd` are large and should not be installed for MVP.

## Links

- [Preprocessing module](modules/preprocessing.md)
- [ANNOVAR + InterVar candidate backbone](decisions/annovar_intervar_candidate_backbone.md)
- [API-first fallback decision](decisions/api_first_mvp_annotation.md)
- [OpenCRAVAT superseded decision](decisions/opencravat_mvp_pipeline.md)
- [Glossary](glossary.md)

## Last Verified

2026-06-02
