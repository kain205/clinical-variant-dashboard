# Decision: ANNOVAR + InterVar Candidate Clinical Backbone

## Purpose

Record the current candidate direction: test ANNOVAR as the main local variant annotation engine and InterVar as the ACMG/AMP-style clinical classification layer for the MVP.

## Key Files

- `docs/supplementary/mvp_scope.md`
- `docs/core/01_research_genomics_datasets.md`
- `docs/core/02_data_preprocessing.md`
- `docs/core/03_train_baseline_models.md`
- `docs/core/04_experiment_optimization.md`

## Important Concepts

- Consumer SNP files remain the user-facing input.
- `rsID + genotype + build` must be preserved in `original_variants`.
- ANNOVAR can use `avinput` or convert an `rsID` list through `convert2annovar.pl -format rsid` when the matching dbSNP database is available locally.
- InterVar can provide ACMG/AMP-style clinical classification after ANNOVAR-compatible annotation.
- Genotype context is not automatically preserved when running ANNOVAR from an `rsID` list, so the pipeline must join genotype back after annotation.
- MyVariant.info, MyGene.info, ClinPGx/PharmGKB, and MyChem.info remain fallback/enrichment APIs.
- Ensembl VEP / Variant Recoder should be tested as a benchmark for rsID mapping, HGVS, gene, transcript, and consequence consistency.

## Candidate Data Flow

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> curated or clinically relevant rsID subset
  -> convert2annovar.pl -format rsid
  -> ANNOVAR avinput: chr start end ref alt rsID
  -> ANNOVAR annotation
  -> InterVar ACMG/AMP-style classification
  -> join original genotype back to annotation rows
  -> MyVariant.info fallback/enrichment for unresolved/selected variants
  -> MyGene.info gene enrichment
  -> ClinPGx/PharmGKB PGx context
  -> normalized clinical findings
  -> dashboard report + assistant context
```

## Test Plan

- Start with 20-50 curated rsIDs, including `rs6025`, `rs3093017`, `rs12562034`, ClinVar pathogenic/likely pathogenic variants, and PGx variants.
- Confirm `convert2annovar.pl -format rsid` output shape and how it handles multiple mappings.
- Run ANNOVAR and inspect output columns.
- Run InterVar and inspect classification fields.
- Join genotype back from parsed consumer input.
- Compare selected variants against Ensembl VEP / Variant Recoder and MyVariant.info.

## Caveats

- One `rsID` may map to multiple variant records.
- Genome build must match dbSNP/ANNOVAR database, such as hg19 or hg38.
- InterVar classification is not diagnostic and does not replace expert review.
- Unconverted variants need fallback handling through MyVariant.info, ClinGen Allele Registry, dbSNP API, or an unresolved queue.
- Full local database setup may still be heavier than API-first enrichment, so MVP should begin with a curated subset.

## Links

- [Architecture](../architecture.md)
- [API-first fallback decision](api_first_mvp_annotation.md)
- [OpenCRAVAT superseded decision](opencravat_mvp_pipeline.md)

## Last Verified

2026-06-02
