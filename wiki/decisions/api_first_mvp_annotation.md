# Decision: API Lookup / Enrichment Fallback

## Purpose

Record the API lookup/enrichment path. This was previously considered as a practical MVP path after the OpenCRAVAT pivot, but is now retained as fallback/enrichment while Dockerized Ensembl VEP is explored as the production annotation backbone.

## Key Files

- `docs/bao_cao_tuan_1.md`
- `src/preprocessing/convert_consumer_genome.py`

## Important Concepts

- Consumer SNP files remain the main user-facing input.
- `rsID` lookup is the most practical fallback/enrichment strategy for consumer data.
- MyVariant.info is the primary variant-level lookup/enrichment API, not the production annotation backbone.
- MyGene.info is used after variant-to-gene mapping for gene context.
- ClinPGx/PharmGKB API is used for PGx/drug-response context.
- MyChem.info is optional for drug/chemical metadata enrichment.
- OpenCRAVAT remains optional for local file-level validation only.

## Lookup / Enrichment Flow

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> Dockerized VEP production annotation when available
  -> MyVariant.info selected variant lookup/enrichment for unresolved or selected variants
  -> MyGene.info mapped gene enrichment
  -> ClinPGx/PharmGKB API for PGx context
  -> optional MyChem.info drug metadata
  -> normalized result schema
  -> evidence-priority scoring
  -> dashboard report + assistant context
```

## Dependencies

Fallback/enrichment path:

- Python standard library preprocessing script.
- MyVariant.info API for lookup/enrichment.
- MyGene.info API.
- ClinPGx/PharmGKB API.
- Optional MyChem.info API.

Not required for MVP demo:

- Local OpenCRAVAT annotator modules.
- Full local dbSNP/gnomAD/CADD downloads.

## Known Caveats

- API calls require network access and rate/error handling.
- Missing API result does not mean missing biological/clinical risk.
- API lookup/enrichment flow must preserve raw payloads for audit and debugging.
- OpenCRAVAT converter tests are still useful for local validation, but not a required path.
- Missing MyVariant fields should not be interpreted as a negative clinical finding.

## Links

- [Architecture](../architecture.md)
- [Preprocessing module](../modules/preprocessing.md)
- [ANNOVAR + InterVar candidate backbone](annovar_intervar_candidate_backbone.md) - superseded as production default.
- [OpenCRAVAT superseded decision](opencravat_mvp_pipeline.md)
- [Glossary](../glossary.md)

## Last Verified

2026-06-02
