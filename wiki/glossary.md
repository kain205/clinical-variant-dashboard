# Glossary

## Purpose

Shared vocabulary for project docs and implementation.

## Key Files

- `docs/supplementary/mvp_scope.md`
- `docs/core/01_research_genomics_datasets.md`
- `docs/core/02_data_preprocessing.md`

## Important Concepts

- `rsID`: dbSNP identifier commonly present in consumer SNP files.
- `genotype`: observed alleles in the user's raw file, such as `AG` or `TT`.
- `build37` / `GRCh37` / `hg19`: genome assembly naming used by many consumer genomics files.
- `hg38` / `GRCh38`: newer genome assembly; not interchangeable with build37.
- `annotation run`: one execution of an annotation engine over one input/sample.
- `source link`: URL or identifier pointing back to the source database or evidence record.
- `evidence-priority score`: dashboard ordering signal, not medical disease-risk prediction.
- `PGx`: pharmacogenomics, typically gene/variant-drug response context.

## Data Flow

See [Architecture](architecture.md).

## Dependencies

None.

## Known Caveats

- `rsID -> disease` is an unsafe simplification.
- Missing annotation does not mean missing biological or clinical risk.

## Links

- [Architecture](architecture.md)
- [OpenCRAVAT MVP pipeline decision](decisions/opencravat_mvp_pipeline.md)

## Last Verified

2026-06-02
