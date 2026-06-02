# Decision: API-first MVP Annotation / Fallback

## Purpose

Record the API-first annotation/enrichment path. This was the MVP backbone after the OpenCRAVAT pivot, and is now retained as fallback/enrichment while ANNOVAR + InterVar is tested as the clinical backbone.

## Key Files

- `docs/core/01_research_genomics_datasets.md`
- `docs/core/02_data_preprocessing.md`
- `docs/supplementary/annotation_tools_manual_testing_notes.md`
- `src/preprocessing/convert_consumer_genome.py`

## Important Concepts

- Consumer SNP files remain the main user-facing input.
- `rsID` lookup is the most practical fallback/enrichment strategy for consumer data.
- MyVariant.info is the primary variant-level fallback/enrichment API.
- MyGene.info is used after variant-to-gene mapping for gene context.
- ClinPGx/PharmGKB API is used for PGx/drug-response context.
- MyChem.info is optional for drug/chemical metadata enrichment.
- OpenCRAVAT remains optional for local file-level validation only.

## Fallback / Enrichment Flow

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> MyVariant.info selected variant lookup/enrichment
  -> MyGene.info mapped gene enrichment
  -> ClinPGx/PharmGKB API for PGx context
  -> optional MyChem.info drug metadata
  -> normalized result schema
  -> evidence-priority scoring
  -> dashboard report + assistant context
```

## Dependencies

Primary MVP path:

- Python standard library preprocessing script.
- MyVariant.info API.
- MyGene.info API.
- ClinPGx/PharmGKB API.
- Optional MyChem.info API.

Not required for MVP demo:

- Local OpenCRAVAT annotator modules.
- Full local dbSNP/gnomAD/CADD downloads.

## Known Caveats

- API calls require network access and rate/error handling.
- Missing API result does not mean missing biological/clinical risk.
- API-first flow must preserve raw payloads for audit and debugging.
- OpenCRAVAT converter tests are still useful for local validation, but not a required path.

## Links

- [Architecture](../architecture.md)
- [Preprocessing module](../modules/preprocessing.md)
- [ANNOVAR + InterVar candidate backbone](annovar_intervar_candidate_backbone.md)
- [OpenCRAVAT superseded decision](opencravat_mvp_pipeline.md)
- [Glossary](../glossary.md)

## Last Verified

2026-06-02
