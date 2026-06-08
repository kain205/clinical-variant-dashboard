# Decision: ANNOVAR + InterVar Candidate Clinical Backbone (Superseded)

## Purpose

Record the previous candidate direction: test ANNOVAR as the main local variant annotation engine and InterVar as the ACMG/AMP-style clinical classification layer for the MVP.

Current decision: superseded as the production default by the Dockerized Ensembl VEP direction. ANNOVAR + InterVar is retained as an optional offline benchmark/classification experiment.

## Key Files

- `docs/bao_cao_tuan_1.md`

## Important Concepts

- Consumer SNP files remain the user-facing input.
- Production annotation should prioritize Dockerized Ensembl VEP; this note remains useful only for benchmark context.
- `rsID + genotype + build` must be preserved in `original_variants`.
- ANNOVAR can use `avinput` or convert an `rsID` list through `convert2annovar.pl -format rsid` when the matching dbSNP database is available locally.
- InterVar can provide ACMG/AMP-style clinical classification after ANNOVAR-compatible annotation.
- Genotype context is not automatically preserved when running ANNOVAR from an `rsID` list, so the pipeline must join genotype back after annotation.
- MyVariant.info, MyGene.info, ClinPGx/PharmGKB, and MyChem.info remain lookup/enrichment APIs.
- Ensembl VEP / Variant Recoder should be tested as the production annotation path, not merely benchmark.

## Superseded Candidate Data Flow

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

Use this only if the team wants to benchmark ANNOVAR/InterVar against VEP:

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
- Full local database setup may still be heavier than VEP REST prototyping or API enrichment, so ANNOVAR/InterVar should remain optional unless the benchmark proves useful.
- Do not call ANNOVAR/InterVar directly inside a dashboard HTTP request; wrap it in a batch worker if it is ever used beyond benchmark.

## Links

- [Architecture](../architecture.md)
- [Dockerized VEP production annotation](dockerized_vep_production_annotation.md)
- [API lookup/enrichment fallback](api_first_mvp_annotation.md)
- [OpenCRAVAT superseded decision](opencravat_mvp_pipeline.md)

## Last Verified

2026-06-02
