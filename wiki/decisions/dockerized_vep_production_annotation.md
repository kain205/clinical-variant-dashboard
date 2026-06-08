# Decision: Dockerized VEP Production Annotation

## Purpose

Record the current production-oriented direction: use Ensembl VEP as the annotation backbone, preferably packaged as a Docker/local-cache worker.

## Key Files

- `docs/bao_cao_tuan_1.md`
- `src/preprocessing/convert_consumer_genome.py`
- `src/preprocessing/build_annovar_intervar_testset.py`

## Important Concepts

- Consumer SNP files remain the user-facing input.
- `rsID + genotype + build` must be preserved in `original_variants`.
- VEP production runs should use a fixed assembly/cache, such as GRCh37/hg19 for Kaggle `Child 1 Genome.csv`.
- MyVariant.info is a lookup/enrichment fallback, not the annotation backbone.
- ANNOVAR + InterVar is optional benchmark/classification context, not the default production service.
- Genotype context must be joined back after VEP annotation because annotation output is variant-centric.

## Candidate Data Flow

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> selected rsID subset
  -> normalize rsID to VEP-compatible input
  -> Dockerized VEP with matching cache/build
  -> parse VEP gene/transcript/consequence/HGVS output
  -> join original genotype back to annotation rows
  -> MyVariant.info lookup/enrichment for unresolved/selected variants
  -> MyGene.info gene enrichment
  -> ClinPGx/PharmGKB PGx context
  -> normalized clinical findings
  -> evidence-priority scoring
  -> dashboard report + assistant context
```

## Test Plan

- Start with the existing Child 1 testset:
  `data/processed/annovar_intervar/kaggle_child1/annovar_intervar_test_rsids.txt`.
- Prototype selected rsIDs through VEP REST `/vep/id` or Variant Recoder.
- Decide the local VEP input representation: VCF, HGVS, or coordinate/ref-alt.
- Run Dockerized VEP with GRCh37/hg19 cache.
- Parse VEP output into `variant_annotations`.
- Join genotype back from `sample_present_rsids.tsv`.
- Compare selected results against MyVariant.info and optional ANNOVAR/InterVar benchmark output.

## Caveats

- One `rsID` may map to multiple variant records.
- VEP cache/build must match the input build.
- VEP consequence and phenotype fields are annotations, not diagnosis.
- Missing enrichment from MyVariant.info or other APIs does not imply absence of clinical relevance.
- Dashboard requests should enqueue annotation jobs; they should not block on long-running annotation commands.

## Links

- [Architecture](../architecture.md)
- [API lookup/enrichment fallback](api_first_mvp_annotation.md)
- [ANNOVAR + InterVar superseded candidate](annovar_intervar_candidate_backbone.md)

## Last Verified

2026-06-02
