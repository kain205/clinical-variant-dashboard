# 4. Experiment Optimization (Tối ưu hóa thử nghiệm)

Tài liệu này hiện chỉ giữ ở mức outline. Nội dung chi tiết sẽ được viết sau khi có parser, annotation output và scoring rules đầu tiên.

## 4.1 Mục tiêu

- So sánh chất lượng output giữa các nguồn annotation.
- Giảm nhiễu trong findings.
- Tinh chỉnh scoring/filtering rules.
- Chuẩn bị khả năng so sánh nhiều annotation runs.

## 4.2 Annotation source comparison

So sánh các nguồn:

- ANNOVAR
- InterVar
- MyVariant.info
- MyGene.info
- ClinPGx/PharmGKB
- Ensembl VEP / Variant Recoder benchmark
- OpenCRAVAT optional validation output nếu có

Các câu hỏi cần trả lời:

- Source nào có field clinical/PGx tốt nhất?
- Source nào dễ parse nhất?
- Source nào thiếu field nhiều?
- Source nào dễ gây ambiguity về build/ref/alt?

## 4.3 Test Ensembl / VEP cần làm

Ở đây "Ensembl" nên hiểu là **Ensembl VEP** và **Variant Recoder**. Mục tiêu không phải thay backbone ngay, mà dùng làm benchmark để kiểm chứng ANNOVAR/InterVar và rsID normalization.

Test tối thiểu:

| Test | Input | Mục tiêu |
| --- | --- | --- |
| Variant Recoder rsID mapping | `rs6025`, `rs3093017`, `rs12562034` và 20-50 curated rsIDs | Kiểm tra một `rsID` map ra bao nhiêu variant records, genome build nào, HGVS/VCF representation ra sao. |
| VEP consequence comparison | `chr-pos-ref-alt` từ ANNOVAR avinput | So sánh gene, transcript, consequence, HGVSc/HGVSp giữa VEP và ANNOVAR. |
| Build consistency | Cùng variant trên hg19 và hg38 nếu có mapping | Kiểm tra pipeline có nhầm build không, nhất là consumer file build36/build37. |
| Clinical/frequency fields | VEP output với phenotype/frequency options nếu dùng được | Xem VEP có bổ sung ClinVar/gnomAD/SIFT/PolyPhen hữu ích không, và output có dễ parse không. |
| Multiple rsID mappings | rsID có nhiều mappings hoặc multi-allelic record | Xác định rule chọn record đúng hoặc flag ambiguity cho dashboard. |

Kết quả test cần trả lời:

- Ensembl/VEP có confirm được coordinate/ref-alt mà ANNOVAR tạo từ `rsID` không?
- Gene/consequence giữa VEP và ANNOVAR có lệch đáng kể không?
- VEP có giúp detect build mismatch tốt hơn không?
- VEP REST/web có đủ nhẹ để dùng làm fallback cho selected variants, hay chỉ nên dùng offline/manual benchmark?
- Output VEP có field nào nên đưa vào normalized schema không?

## 4.4 Filtering & scoring

- Lọc common benign variants.
- Hạ mức ưu tiên research-only associations.
- Xử lý conflicting interpretation.
- Xử lý rsID có nhiều allele hoặc nhiều clinical records.
- Xử lý InterVar `VUS` và các classification thiếu/conflict với ClinVar.
- Xử lý ANNOVAR/Ensembl consequence mismatch.

## 4.5 Deliverables sau

- Báo cáo so sánh annotation sources.
- Danh sách edge cases.
- Scoring/filtering rules đã tinh chỉnh.
- Regression test cases.
- Bảng benchmark ANNOVAR vs InterVar vs Ensembl VEP vs MyVariant.info cho curated rsID set.
