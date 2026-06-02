# Annotation Tools Manual Testing Notes

Tài liệu này ghi lại kết quả manual testing cho phần **1.3 Khảo sát Công cụ Chú giải Tích hợp (Annotation Tools)** trong [01_research_genomics_datasets.md](../core/01_research_genomics_datasets.md). Mục tiêu là xác định tool nào có thể dùng thực tế cho MVP pipeline, tool nào phù hợp làm fallback/enrichment, và output có đủ dễ parse để đưa vào dashboard hay không.

Tài liệu này chỉ giữ các kết quả đã test hoặc đã có quan sát thực tế. Các phần placeholder kiểu "chưa test" đã được bỏ để tránh nhiễu khi dùng cho báo cáo.

## Test scope

### Single-variant lookup

Dùng lại bộ `rsID` mẫu từ reference database testing để so sánh giữa database lookup và annotation tool.

| rsID | Lý do chọn |
| --- | --- |
| `rs3093017` | SNP có GWAS association rõ, gene `CCR6`, liên quan rheumatoid arthritis trong GWAS Catalog. |
| `rs6025` | Variant clinical/PGx nổi tiếng hơn, gene `F5`, có record trong ClinVar, GWAS Catalog và một số nguồn khác. |
| `rs12562034` | SNP random từ consumer DNA file, có record trong dbSNP nhưng không có record rõ trong ClinVar/GWAS Catalog. |

### File-level annotation

File-level test dùng Harvard PGP sample `hu43860C`, cụ thể file 23andMe-style:

```text
data/raw_inputs/pgp_hu43860C/hu43860C_20110115044231/genome_George_Church_Full_20091107080045.txt
```

File này có metadata human assembly build 36 / `hg18`, phù hợp để kiểm tra case khó nhưng thực tế: consumer SNP file cũ, cần converter/mapping/liftover trước khi annotation output dùng được.

## Summary

| Tool | Input đã test | Kết quả | Vai trò MVP | Ghi chú |
| --- | --- | --- | --- | --- |
| MyVariant.info | 3 `rsID` mẫu và batch 10/100 `rsID` từ PGP file | Chạy OK cho lookup/batch query theo `rsID`; trả JSON dễ dùng cho enrichment tùy variant. | MVP API lookup / fallback enrichment. | Không nhận raw 23andMe file trực tiếp; cần parse cột `rsid`, query theo `scopes=dbsnp.rsid`, chia chunk nếu chạy full file lớn. |
| MyGene.info | Batch gene symbols `CCR6`, `F5`, `LINC01128`, `RNF223` | Chạy OK với `/v3/query`; trả gene symbol, gene name, Entrez ID, Ensembl gene ID và summary nếu có. | Gene-level enrichment / explainer layer. | Không nhận `rsID` hoặc raw SNP file trực tiếp. Dùng sau khi MyVariant.info/source API đã map variant ra gene. |
| OpenCRAVAT | PGP `hu43860C` 23andMe-style file, forced input format `23andme`, input assembly `hg18` | Chạy xong bình thường, tạo SQLite/TSV/XLSX usable; có 554,636 variant rows và 16,726 gene rows. | Optional local validation / experiment. | Converter/report export dùng được, nhưng local annotator module install khá brittle. `pharmgkb`, `gwas_catalog`, `litvar` từng cài được nhưng đã uninstall; `clinvar_acmg` bị treo khi cài; full `clinvar` có nguy cơ kéo dependency rất lớn như `dbsnp`. |

## MyVariant.info

### Mục tiêu test

Kiểm tra khả năng dùng MyVariant.info như API lookup nhanh sau bước parse consumer SNP file.

### Kết quả chính

| Tiêu chí | Kết quả |
| --- | --- |
| Input phù hợp | `rsID`, HGVS, genomic variant ID, batch query. |
| Raw consumer file | Không nhận trực tiếp. Cần parse file trước, lấy danh sách `rsID`. |
| Query strategy cho PGP/23andMe | Ưu tiên query theo `rsID` với `scopes=dbsnp.rsid`, không gửi thẳng coordinate từ build36/hg18. |
| Batch query | Đã test batch 10/100 `rsID` từ PGP file chạy OK. Với full file lớn cần chia chunk. |
| Output | JSON annotation từ nhiều nguồn như dbSNP, ClinVar, gnomAD, CADD/dbNSFP tùy variant. |
| Parse cho dashboard | Phù hợp làm enrichment/fallback vì JSON có cấu trúc và gọi API nhanh. |

### Kết luận

MyVariant.info phù hợp cho MVP ở vai trò **API lookup / fallback enrichment layer**. Tool này không phải full local file annotation engine, nhưng thực tế hơn cho demo API-first vì có thể sanity check một số `rsID`, enrich selected variants, hoặc bổ sung fields còn thiếu từ annotation run.

Với consumer SNP file cũ như PGP build36, không nên dùng coordinate gốc để query trực tiếp. Cách an toàn hơn cho MVP là parse `rsID`, query theo `dbsnp.rsid`, rồi giữ source/raw payload để audit.

## MyGene.info

### Mục tiêu test

Kiểm tra MyGene.info như một gene-level enrichment API cho dashboard/chatbot. MyGene.info khác MyVariant.info: MyGene xử lý **gene annotation**, không phải variant annotation.

Theo official docs, MyGene.info có hai service chính:

- `/v3/query`: query gene bằng symbol, Entrez Gene ID, Ensembl Gene ID hoặc các gene-related identifiers.
- `/v3/gene/<geneid>`: retrieve gene annotation bằng Entrez hoặc Ensembl Gene ID.

Reference docs: https://docs.mygene.info/en/latest/

### Test query

Batch query các gene xuất hiện trong reference/manual testing và OpenCRAVAT example:

```powershell
Invoke-RestMethod -Uri "https://mygene.info/v3/query" -Method Post -Body @{
  q="CCR6,F5,LINC01128,RNF223";
  scopes="symbol";
  species="human";
  fields="symbol,name,entrezgene,ensembl.gene,summary"
}
```

### Kết quả chính

| Query gene | Entrez Gene ID | Ensembl Gene ID | Gene name | Summary |
| --- | --- | --- | --- | --- |
| `CCR6` | `1235` | `ENSG00000112486` | C-C motif chemokine receptor 6 | Có summary RefSeq về chemokine receptor, immune cell migration/recruitment. |
| `F5` | `2153` | `ENSG00000198734` | coagulation factor V | Có summary RefSeq về coagulation factor V, activated protein C resistance/thrombophilia context. |
| `LINC01128` | `643837` | `ENSG00000228794` | long intergenic non-protein coding RNA 1128 | Không thấy summary trong response test, nhưng có gene ID/name mapping. |
| `RNF223` | `401934` | `ENSG00000237330` | ring finger protein 223 | Có summary ngắn từ Alliance of Genome Resources. |

### Kết luận

MyGene.info phù hợp cho MVP ở vai trò **gene-level enrichment / explainer layer**:

- Bổ sung gene full name, Entrez ID, Ensembl Gene ID.
- Bổ sung gene summary để dashboard/chatbot giải thích gene trong variant detail page.
- Hữu ích sau khi MyVariant.info hoặc source API khác đã map variant ra gene.

MyGene.info không phù hợp để làm variant annotation backbone:

- Không nhận raw 23andMe/PGP SNP file.
- Không nhận `rsID` như variant query chính.
- Không trả clinical significance, genotype-level PGx interpretation, allele frequency hoặc consequence cho variant cụ thể.

Vì vậy, MyGene.info nên đứng sau bước variant annotation, không đứng trước.

## OpenCRAVAT

### Mục tiêu test

Kiểm tra khả năng chạy file-level annotation từ PGP/23andMe-style raw SNP file, vì dashboard thực tế sẽ xử lý file do user upload chứ không chỉ lookup từng variant riêng lẻ.

### Test command

Sau khi cài `23andme-converter` và `hg19wgs`, OpenCRAVAT được chạy lại với forced input format:

```powershell
oc run data\raw_inputs\pgp_hu43860C\hu43860C_20110115044231\genome_George_Church_Full_20091107080045.txt -d data\processed\opencravat\pgp_hu43860C -n george_church_23andme_forced --user-email-opt-out --cleanrun -l hg18 -t text excel --debug -i 23andme
```

### Final status

| Field | Result |
| --- | --- |
| Run name | `george_church_23andme_forced` |
| Final OpenCRAVAT status | Finished normally |
| Input format | Forced `23andme` because the old 23andMe header was not auto-detected |
| Input assembly | `hg18` / build36 according to file header |
| Output SQLite | `data/processed/opencravat/pgp_hu43860C/george_church_23andme_forced.sqlite` |
| Output TSV | `data/processed/opencravat/pgp_hu43860C/george_church_23andme_forced.tsv` |
| Output XLSX | `data/processed/opencravat/pgp_hu43860C/george_church_23andme_forced.xlsx` |
| Variant rows in SQLite | 554,636 |
| Gene rows in SQLite | 16,726 |
| Converter error records | 4,325 |

### Example successful annotation record

| Field | Value |
| --- | --- |
| Original tag | `rs3934834` |
| Original input position | `chr1:995669` |
| Lifted/mapped position | `chr1:1070426` |
| Ref/alt | `T>C` |
| Gene | `RNF223` |
| Transcript | `ENST00000453464.3` |
| Sequence ontology | `2kb_downstream_variant` |
| cDNA change | `c.*1391A>G` |
| Zygosity | `hom` |

### Interpretation

OpenCRAVAT đã annotate được file PGP/23andMe-style và tạo output usable ở SQLite/TSV/XLSX. Đây là kết quả quan trọng cho validation vì chứng minh pipeline có thể xử lý ở mức file, không chỉ single-variant lookup, nhưng không đủ để giữ OpenCRAVAT làm backbone demo sau khi module install bị brittle.

Điểm cần hiểu đúng: file `.err` chỉ chứa các variant fail conversion/mapping. Nếu chỉ mở `.err`, run sẽ nhìn có vẻ fail nặng hơn thực tế. Output chính vẫn usable và có hàng trăm nghìn variant rows.

### Caveat

Đây vẫn chưa phải production-clean build36/23andMe pipeline. File input là build36/hg18, trong khi 23andMe converter phụ thuộc `hg19wgs` để infer reference bases trước khi OpenCRAVAT liftover. Điều này có khả năng giải thích nhiều lỗi `Invalid reference base`.

Kết luận thực tế:

- Acceptable cho local file-level validation.
- Cần stricter preprocessing nếu muốn production-quality file-level pipeline.
- Với dashboard, cần hiển thị annotation run status và error summary để user/dev biết run có partial mapping errors.
- Không nên dùng OpenCRAVAT local annotator modules làm backbone MVP demo hiện tại.

## Alignment với tài liệu core

Kết quả trong file này nhất quán với phần **1.3.3 Bảng khảo sát annotation tools** của [01_research_genomics_datasets.md](../core/01_research_genomics_datasets.md):

- MyVariant.info phù hợp làm **MVP/API lookup nhanh** sau bước parse SNP file.
- MyGene.info phù hợp làm **gene-level enrichment / explainer layer** sau khi variant đã được map ra gene.
- OpenCRAVAT chỉ nên giữ vai trò **optional local validation / experiment** sau khi gặp vấn đề với module install/dependency.

## Recommendation cho MVP

Kết quả đã test hiện tại vẫn ủng hộ API-first làm fallback/enrichment path:

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> MyVariant.info fallback/enrichment cho selected rsIDs
  -> MyGene.info enrichment cho mapped gene symbols
  -> ClinPGx/PharmGKB API cho PGx/drug-response context
  -> normalize output schema
  -> evidence-priority scoring
  -> dashboard report
```

OpenCRAVAT có thể chạy ở nhánh optional để validate file-level conversion/report export, nhưng không nên là dependency bắt buộc của demo vì module install không ổn định trong test hiện tại.

## Next test target: ANNOVAR + InterVar

Sau khi xem ANNOVAR docs, hướng đáng test tiếp theo là dùng **ANNOVAR + InterVar** làm candidate clinical backbone:

```text
consumer SNP file
  -> parser / validator
  -> preserve original rsID, chromosome, position, genotype, build
  -> extract curated rsID list
  -> convert2annovar.pl -format rsid
  -> generate avinput: chr start end ref alt rsID
  -> run ANNOVAR annotation
  -> run InterVar ACMG/AMP-style classification
  -> join genotype back from original_variants
  -> normalize clinical findings
  -> dashboard report + chatbot explanation
```

Test này chưa được tính là manual testing result trong file này cho tới khi chạy được local command và inspect output. Các caveat cần kiểm tra:

- `rsID` có thể map ra nhiều records.
- dbSNP/ANNOVAR database phải match genome build.
- Genotype người dùng phải được join lại sau annotation.
- InterVar classification không thay thế expert clinical review.
- Variant không convert được cần fallback bằng MyVariant.info/ClinGen/dbSNP API hoặc unresolved queue.

## Update log

| Ngày | Nội dung cập nhật |
| --- | --- |
| 2026-06-01 | Ghi nhận OpenCRAVAT retest sau khi cài `hg19wgs`; run `george_church_23andme_forced` finished normally và tạo SQLite/TSV/XLSX usable. |
| 2026-06-01 | Rút gọn tài liệu cho báo cáo: bỏ placeholder chưa test, giữ các kết quả đã verify để consistent với tài liệu core. |
| 2026-06-02 | Bổ sung MyGene.info sau khi verify `/v3/query` với batch gene symbols `CCR6`, `F5`, `LINC01128`, `RNF223`; xác định vai trò là gene-level enrichment, không phải variant annotation backbone. |
| 2026-06-02 | Pivot MVP sang API-first sau khi OpenCRAVAT annotator module install bị treo/brittle; uninstall `pharmgkb`, `gwas_catalog`, `litvar`; giữ OpenCRAVAT là optional validation. |
| 2026-06-02 | Ghi nhận ANNOVAR + InterVar là next test target/candidate clinical backbone; chưa đưa vào bảng result vì chưa chạy local pipeline. |
