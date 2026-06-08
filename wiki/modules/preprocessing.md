# Module: Preprocessing

## Purpose

Normalize raw consumer SNP files into formats that annotation tools can consume, while preserving traceability to the original input.

## Key Files

- `src/preprocessing/convert_consumer_genome.py`
- `src/preprocessing/build_annovar_intervar_testset.py`
- `src/workbench/intervar_pipeline.py`
- `src/dashboard/streamlit_app.py`
- `docs/bao_cao_tuan_1.md`
- `docs/bao_cao_tuan_2.md`
- `data/raw_inputs/kaggle_family/Child 1 Genome.csv`
- `data/raw_inputs/kaggle_family/genome_zeeshan_usmani.csv`
- `data/processed/workbench/annovar_rsid_route/phase2_full_child1/conversion_manifest.json`

## Important Concepts

- Public mock files may look 23andMe-like but still differ in delimiter/header conventions.
- Kaggle family files use comma-separated CSV, while some downstream tools expect tab-delimited or variant-coordinate input.
- Header aliases should normalize to `rsid`, `chromosome`, `position`, `genotype`.
- Header normalization strips a UTF-8 BOM before checking comment-style headers such as `# rsid,chromosome,position,genotype`.
- For VEP and any benchmark tools, preprocessing must preserve genotype context separately because normalized annotation input/output does not carry the user's original genotype context automatically.
- Full Child 1 ANNOVAR rsID-route output exists as an offline benchmark artifact under `data/processed/workbench/annovar_rsid_route/phase2_full_child1/`.
- The full route uses an exact-match dbSNP subset to avoid repeatedly scanning the 12GB `hg19_snp138.txt` file during interactive work.
- Streamlit `Full SNP -> InterVar` runs this same local DB route on the current built-in/uploaded input and writes a fresh run directory under `data/processed/workbench/full_intervar_runs/run_*/`.

## Data Flow

```text
raw CSV/TSV
  -> detect delimiter
  -> find rsid/chromosome/position/genotype header
  -> skip comments/blank rows
  -> preserve original_variants: rsID, chromosome, position, genotype, build
  -> extract curated/clinically relevant rsID list
  -> normalize rsID list to VEP-compatible input
  -> join genotype back after VEP output
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

Child 1 VEP/benchmark testset:

```powershell
python src\preprocessing\build_annovar_intervar_testset.py `
  "data\raw_inputs\kaggle_family\Child 1 Genome.csv" `
  data\processed\annovar_intervar\kaggle_child1 `
  --genome-build GRCh37/hg19 `
  --max-sample-rsids 40
```

Observed result for `Child 1 Genome.csv`:

- Input rows: `601,802`
- Valid genotype rows: `592,578`
- No-call / missing genotype rows: `9,224`
- Duplicate rsID rows: `0`
- Sample-present rsIDs in test subset: `40`
- External benchmark rsIDs: `rs3093017`, `rs12562034`

Full Child 1 ANNOVAR rsID route artifact:

```powershell
Get-Content data\processed\workbench\annovar_rsid_route\phase2_full_child1\conversion_manifest.json
```

Observed phase2 result:

- Selected rsIDs: `592,580`
- Sample-present rsIDs: `592,578`
- External benchmark rsIDs: `2`
- Mapped in selected dbSNP subset: `546,068`
- Unresolved in selected dbSNP subset: `46,512`
- Multi-mapping rsIDs: `4,147`
- Converted ANNOVAR input rows processed by `table_annovar.pl`: `569,497`
- Main outputs: `converted.avinput`, `annovar_child1.hg19_multianno.txt`, `intervar_child1.hg19_multianno.txt.intervar`, `join_back.tsv`

Streamlit full-run route:

```powershell
streamlit run src\dashboard\streamlit_app.py
```

Open `Full SNP -> InterVar`, select a built-in/uploaded consumer SNP file, then run the local DB route. Manual rsID mode is disabled for this tab because it has no sample genotype context.

## Known Caveats

- The script does not infer clinical meaning.
- The script does not liftover coordinates.
- Genome build still needs to be recorded separately and matched to tools/databases such as Ensembl VEP cache, optional ANNOVAR humandb/dbSNP benchmark, or optional OpenCRAVAT validation.
- One rsID may map to multiple variant records; preprocessing should preserve enough fields to audit the selected mapping.
- External benchmark rsIDs are controls for tool validation, not sample-specific dashboard findings.
- The phase2 Child 1 artifact remains an offline benchmark/demo artifact; Streamlit full runs create new per-input run folders and execute synchronously from the UI.
- InterVar direct/default mode still needs manual database alignment for heavy resources such as `dbnsfp42a` and `gnomad_genome`.

## Links

- [Architecture](../architecture.md)
- [ANNOVAR + InterVar candidate backbone](../decisions/annovar_intervar_candidate_backbone.md) - superseded as production default; retained for benchmark context.
- [OpenCRAVAT MVP pipeline decision](../decisions/opencravat_mvp_pipeline.md)

## Last Verified

2026-06-05
