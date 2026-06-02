# Module: Preprocessing

## Purpose

Normalize raw consumer SNP files into formats that annotation tools can consume, while preserving traceability to the original input.

## Key Files

- `src/preprocessing/convert_consumer_genome.py`
- `docs/core/02_data_preprocessing.md`
- `data/raw_inputs/kaggle_family/genome_zeeshan_usmani.csv`

## Important Concepts

- Public mock files may look 23andMe-like but still differ in delimiter/header conventions.
- Kaggle family files use comma-separated CSV, while some downstream tools expect tab-delimited or variant-coordinate input.
- Header aliases should normalize to `rsid`, `chromosome`, `position`, `genotype`.
- For ANNOVAR/InterVar, preprocessing must preserve genotype context separately because rsID-to-avinput conversion does not carry the user's genotype through automatically.

## Data Flow

```text
raw CSV/TSV
  -> detect delimiter
  -> find rsid/chromosome/position/genotype header
  -> skip comments/blank rows
  -> preserve original_variants: rsID, chromosome, position, genotype, build
  -> extract curated/clinically relevant rsID list
  -> convert rsID list to ANNOVAR avinput
  -> join genotype back after ANNOVAR/InterVar output
```

Optional validation output:

```text
raw CSV/TSV
  -> tab-delimited 23andMe-style TSV
  -> OpenCRAVAT -i 23andme
```

## Dependencies

The converter script uses Python standard library only.

## Usage

```powershell
python src\preprocessing\convert_consumer_genome.py `
  data\raw_inputs\kaggle_family\genome_zeeshan_usmani.csv `
  data\processed\opencravat\kaggle_zeeshan_usmani\genome_zeeshan_usmani_23andme.tsv
```

Observed result for `genome_zeeshan_usmani.csv`:

- Input rows: `610,544`
- Output rows: `610,544`
- Skipped rows: `0`

## Known Caveats

- The script does not infer clinical meaning.
- The script does not liftover coordinates.
- Genome build still needs to be recorded separately and matched to tools/databases such as ANNOVAR humandb/dbSNP, Ensembl VEP, or optional OpenCRAVAT validation.
- One rsID may map to multiple variant records; preprocessing should preserve enough fields to audit the selected mapping.

## Links

- [Architecture](../architecture.md)
- [ANNOVAR + InterVar candidate backbone](../decisions/annovar_intervar_candidate_backbone.md)
- [OpenCRAVAT MVP pipeline decision](../decisions/opencravat_mvp_pipeline.md)

## Last Verified

2026-06-02
