#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/mnt/d/PROJECT/clinical_variant_dashboard}"
RAW="${RAW:-$ROOT/data/raw_inputs/kaggle_family/Child 1 Genome.csv}"
RUN="${RUN:-$ROOT/data/processed/workbench/annovar_rsid_route/phase3_full_snp_to_intervar}"
ANN="${ANN:-$ROOT/tools/annovar}"
IV="${IV:-$ROOT/tools/InterVar}"
MAX_SAMPLE_RSIDS="${MAX_SAMPLE_RSIDS:-600000}"

mkdir -p "$RUN"
cd "$ROOT"

python3 src/preprocessing/build_annovar_intervar_testset.py \
  "$RAW" \
  "$RUN" \
  --genome-build GRCh37/hg19 \
  --max-sample-rsids "$MAX_SAMPLE_RSIDS" \
  --dbsnp-file "$ANN/humandb/hg19_snp138.txt" \
  --extract-dbsnp-subset \
  > "$RUN/prepare_inputs.log"

/usr/bin/time -v perl "$ANN/convert2annovar.pl" \
  -format rsid "$RUN/rsids.txt" \
  -dbsnpfile "$RUN/hg19_snp138.selected.txt" \
  > "$RUN/converted.avinput" \
  2> "$RUN/convert_rsid_to_avinput.time.log"

/usr/bin/time -v perl "$ANN/table_annovar.pl" \
  "$RUN/converted.avinput" \
  "$ANN/humandb" \
  -buildver hg19 \
  -out "$RUN/annovar_child1" \
  -protocol refGene,clinvar_20240917 \
  -operation g,f \
  -nastring . \
  -polish \
  -otherinfo \
  2> "$RUN/table_annovar.time.log"

cp "$RUN/annovar_child1.hg19_multianno.txt" "$RUN/intervar_child1.hg19_multianno.txt"

cd "$IV"
/usr/bin/time -v python3 Intervar.py \
  -b hg19 \
  -i "$RUN/converted.avinput" \
  --input_type=AVinput \
  -o "$RUN/intervar_child1" \
  --skip_annovar \
  2>&1 | tee "$RUN/intervar_skip_annovar.log"

cd "$ROOT"
python3 src/preprocessing/build_annovar_intervar_testset.py \
  "$RAW" \
  "$RUN" \
  --genome-build GRCh37/hg19 \
  --max-sample-rsids "$MAX_SAMPLE_RSIDS" \
  --dbsnp-file "$ANN/humandb/hg19_snp138.txt" \
  --converted-avinput "$RUN/converted.avinput" \
  > "$RUN/final_join_back_manifest.log"

wc -l \
  "$RUN/rsids.txt" \
  "$RUN/converted.avinput" \
  "$RUN/annovar_child1.hg19_multianno.txt" \
  "$RUN/intervar_child1.hg19_multianno.txt.intervar" \
  "$RUN/join_back.tsv" \
  | tee "$RUN/full_pipeline_line_counts.txt"
