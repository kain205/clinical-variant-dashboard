# ANNOVAR + InterVar Official Workflow Notes

## Why this note exists

ANNOVAR + InterVar should not be documented as a direct `raw SNP file -> clinical output` path. The official workflow expects normalized variant input first: either VCF or ANNOVAR `avinput`. For this project, that distinction matters because consumer SNP files provide `rsID`, `chromosome`, `position`, and `genotype`, but not reliable `REF/ALT` context.

Project decision: keep ANNOVAR + InterVar as a controlled offline benchmark/classification experiment. It can support citation-grounded reporting and chatbot explanation later, but it is not the MVP runtime annotation backbone and does not replace HITL review.

## Official routes

### VCF route

Use this route when a real VCF already exists or when a conservative SNP-to-VCF bridge has produced unambiguous `CHROM/POS/REF/ALT/GT` rows.

```text
sample.vcf
  -> table_annovar.pl -vcfinput
  -> sample.hg19_multianno.txt
  -> InterVar
  -> ACMG-style evidence output
```

Representative command:

```bash
perl tools/annovar/table_annovar.pl input.vcf tools/annovar/humandb \
  -buildver hg19 \
  -out myanno \
  -protocol refGene,clinvar_20240917 \
  -operation g,f \
  -nastring . \
  -polish \
  -otherinfo \
  -vcfinput
```

### avinput route

ANNOVAR `avinput` requires the first five columns:

```text
chromosome
start
end
reference
observed
```

Additional columns are allowed and can be preserved as context. In this project, the extra column should include `rsID` whenever possible so output can be joined back to the original consumer SNP row.

### rsID route for consumer SNP files

Consumer SNP files should not be fed directly into ANNOVAR or InterVar. The project route is:

```text
consumer SNP row
  -> preserve original rsID/genotype/row_index/build
  -> rsID list
  -> convert2annovar.pl -format rsid + local dbSNP
  -> converted.avinput
  -> table_annovar.pl
  -> hg19_multianno.txt
  -> join back original genotype
  -> optional InterVar
```

Representative command:

```bash
perl tools/annovar/convert2annovar.pl \
  -format rsid data/processed/workbench/annovar_rsid_route/phase0_curated/rsids.txt \
  -dbsnpfile tools/annovar/humandb/hg19_snp138.txt \
  > data/processed/workbench/annovar_rsid_route/phase0_curated/converted.avinput
```

Important limitation: `rsID -> avinput` does not automatically preserve sample genotype interpretation. After ANNOVAR maps `rsID` to `REF/ALT`, the pipeline must join back the original genotype and flag multiple mappings, missing sample context, and genotype/ref-alt mismatch.

### Complete Genomics route

If PGP Complete Genomics b37 `var*ASM.tsv` data is available, ANNOVAR has a dedicated conversion route:

```bash
perl tools/annovar/convert2annovar.pl \
  -format cg \
  -out pgp_cgi \
  var-GS00253-DNA_A01_200_37-ASM.tsv
```

This is potentially cleaner than a build36/hg18 23andMe-style file because the Complete Genomics data is closer to WGS variant calls and can include zygosity context. It is not included in the first implementation unless a b37 `var*ASM.tsv` file is available.

## InterVar caveats

InterVar should run only after ANNOVAR-compatible annotation is stable. The current project smoke test used `--skip_annovar`, meaning InterVar consumed an existing ANNOVAR `multianno.txt` rather than calling ANNOVAR itself.

Known caveats:

| Caveat | Project handling |
| --- | --- |
| `mim2gene.txt` is required by InterVar runtime | Keep it documented under `tools/InterVar/intervardb/`. |
| InterVar config may point to local `./annotate_variation.pl` paths | Patch config only when direct InterVar -> ANNOVAR mode is needed. |
| Installed ANNOVAR humandb may not match InterVar default database list | Treat output as benchmark evidence until database coverage is aligned. |
| InterVar classification is ACMG-style evidence, not diagnosis | Route through `HITL review gate` and dashboard scope boundary. |

## Implemented project artifact

The script below prepares the official rsID route without running ANNOVAR/InterVar:

```powershell
python src\preprocessing\build_annovar_intervar_testset.py `
  "data\raw_inputs\kaggle_family\Child 1 Genome.csv" `
  data\processed\workbench\annovar_rsid_route\phase0_curated `
  --genome-build "GRCh37/hg19" `
  --max-sample-rsids 40 `
  --extract-dbsnp-subset
```

Expected outputs:

```text
original_variants.tsv
rsids.txt
annovar_intervar_test_rsids.txt
sample_present_rsids.tsv
external_benchmark_rsids.txt
hg19_snp138.selected.txt
conversion_manifest.json
join_back.tsv
commands.sh
```

The generated `commands.sh` contains the next manual/local steps:

```text
convert2annovar.pl -format rsid
table_annovar.pl
InterVar.py --skip_annovar
```

## References

- ANNOVAR input documentation: https://annovar.openbioinformatics.org/en/latest/user-guide/input/
- InterVar README: https://github.com/WGLab/InterVar
