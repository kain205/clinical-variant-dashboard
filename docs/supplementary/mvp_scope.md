# MVP Scope: Clinical Variant Dashboard

Tài liệu này chốt phạm vi MVP cho **Clinical Variant Dashboard**. Style tài liệu cố ý dùng tiếng Việt là chính, giữ nguyên các thuật ngữ dev/genomics quen thuộc như `MVP`, `pipeline`, `annotation`, `dashboard`, `chatbot`, `schema`, `source link`, `run`, `ClinVar`, `gnomAD`, `ANNOVAR`, `InterVar`, `MyVariant.info`, `ClinPGx`.

## 1. Mục tiêu sản phẩm

Xây dựng một visualization dashboard giúp người dùng chuyển file genome/variant thô từ consumer genomics thành báo cáo dễ đọc, có source link, tập trung vào:

- clinically relevant variants
- pharmacogenomic findings
- population frequency / filtering
- research-level associations
- chatbot/assistant để hỏi đáp trên annotation report hiện tại

MVP ưu tiên **workflow diễn giải kết quả**, **độ rõ ràng**, và **source-grounded explanation**. MVP không cố rebuild toàn bộ clinical genomics database, không phải hệ thống chẩn đoán, và không phải AI bác sĩ.

## 2. Bài toán cốt lõi

Các file raw SNP/variant như 23andMe, PGP, CSV hoặc VCF chứa rất nhiều variant nhưng khó đọc trực tiếp. Người dùng thường chỉ có các cột như `rsid`, `chromosome`, `position`, `genotype`, nhưng không biết variant nào có ý nghĩa lâm sàng, variant nào liên quan thuốc, variant nào chỉ là research association.

Hệ thống cần tự động hóa bước first-pass annotation:

- parse file đầu vào
- giữ lại dữ liệu gốc để trace
- chạy annotation bằng các engine/public knowledge source phù hợp
- chuẩn hóa output về một schema nội bộ
- score/prioritize finding
- trình bày kết quả trên dashboard
- cho phép hỏi đáp qua chatbot-style assistant

Kết quả MVP chỉ dùng cho mục đích tham khảo, giáo dục và decision-support exploration. Hệ thống và chatbot **không được** chẩn đoán, kê đơn, khuyến nghị đổi thuốc, hoặc suy luận risk cá nhân ngoài evidence có trong annotation result.

## 3. Quyết định MVP: ANNOVAR + InterVar candidate clinical backbone

Với MVP, project sẽ test hướng **ANNOVAR + InterVar** làm clinical annotation/classification backbone. Lý do là ANNOVAR không bắt buộc input VCF: pipeline có thể đi từ `rsID` list hoặc `avinput`, phù hợp với consumer SNP file có các cột `rsid`, `chromosome`, `position`, `genotype`.

Candidate clinical backbone:

- ANNOVAR: convert `rsID` hoặc coordinate/ref-alt sang annotation đầy đủ, gồm gene-based, region-based và filter-based annotation.
- InterVar: phân loại clinical significance theo ACMG/AMP-style classification trên output/format tương thích ANNOVAR.
- MyVariant.info: fallback/enrichment theo `rsID`, sanity check và variant-level JSON annotation nếu ANNOVAR conversion fail hoặc thiếu field.
- ClinPGx / PharmGKB API: nguồn chuyên biệt cho pharmacogenomics, drug response, genotype/allele-level annotation.
- MyGene.info: gene-level enrichment sau khi variant đã map ra gene, dùng cho dashboard detail và chatbot explanation.

Ensembl VEP nên được test như benchmark đối chứng cho gene/consequence/HGVS mapping. OpenCRAVAT vẫn hữu ích cho local file-level validation/converter experiment, nhưng **không còn là MVP backbone** vì quá trình cài local annotator modules bị brittle, dễ treo hoặc kéo dependency rất lớn.

Điểm kỹ thuật bắt buộc: nếu ANNOVAR chạy từ `rsID` list, genotype người dùng sẽ không tự đi theo annotation output. Parser phải preserve bảng `rsID -> genotype -> sample/build`, sau đó join genotype ngược lại bằng `rsID` và coordinate/ref-alt nếu có.

## 4. Reference databases và annotation tools

Project cần phân biệt hai nhóm:

- **Primary reference databases:** nguồn dữ liệu gốc/uy tín, nhưng thường khó consume trực tiếp.
- **Aggregated annotation tools:** công cụ đã normalize/index/combine nhiều nguồn và trả output thực dụng hơn cho pipeline.

### Primary reference databases

| Resource | Vai trò chính | Vấn đề thực tế với input kiểu 23andMe/PGP | Quyết định cho MVP |
| --- | --- | --- | --- |
| ClinVar | Clinical significance cho variant và disease/condition assertions. | Một `rsID` có thể map tới nhiều record, allele, condition, review status và conflicting classification. | Không parse trực tiếp trong MVP. Consume qua MyVariant.info/source API nếu có; giữ ClinVar fields và source links. |
| gnomAD | Population allele frequency để đánh giá variant phổ biến/hiếm. | Query tốt nhất bằng `chromosome-position-ref-alt` và genome build cụ thể, không chỉ bằng consumer `rsID`. | Không index gnomAD trực tiếp. Dùng frequency annotation qua MyVariant.info nếu có; bulk/local để future work. |
| PharmGKB / ClinPGx | Pharmacogenomics annotations, drug response, labels, guidelines. | Drug response phụ thuộc genotype, allele, named allele, haplotype, diplotype và evidence level. | Tích hợp riêng cho PGx module. Dùng API/export nếu khả thi. |
| CPIC / PharmCAT | Guideline và genotype-to-phenotype interpretation cho pharmacogenomics. | Giá trị cao nhưng thường cần star allele/diplotype calling, vượt quá simple rsID matching. | Future enhancement. MVP chỉ dùng context qua ClinPGx/PharmGKB, chưa build full PharmCAT pipeline. |
| dbSNP | Registry cho `rsID`, merged IDs, aliases, allele và coordinate references. | Hữu ích để validate/normalize `rsID`, nhưng không phải clinical interpretation source. | Dùng gián tiếp qua annotation engines; cân nhắc dùng trực tiếp sau cho rsID normalization. |
| GWAS Catalog / GRASP | Trait/disease association studies. | Association thường là research-level, population-specific, không dùng để chẩn đoán cá nhân. | Dùng như low-priority research evidence qua MyVariant.info hoặc source API/link nếu có. |
| OMIM | Gene-disease và Mendelian disease knowledge. | Text-heavy, có licensing concern, khó chuyển thành risk score đơn giản. | Dùng như explanation/reference layer, không phải core MVP integration. |
| ClinGen | Gene-disease validity, dosage sensitivity, expert curation. | Nghiêng về gene-level hơn consumer-SNP-level; cần clinical context. | Future evidence-quality enhancement, có thể qua source API/link hoặc curated gene context. |
| dbNSFP / prediction sources | Functional prediction scores như CADD, REVEL, SIFT, PolyPhen, AlphaMissense. | Hữu ích cho prioritization nhưng không đủ để claim clinical một mình. | Consume qua MyVariant.info nếu có như supporting evidence. |
| SNPedia / LitVar | Human-readable variant notes và literature links. | Hữu ích để exploration, nhưng evidence quality không đồng đều, text có thể noisy. | Chỉ dùng trong research/explainer section, mark rõ non-diagnostic. |

### Aggregated annotation tools

| Tool | Vai trò chính | Quan sát thực tế | Quyết định cho MVP |
| --- | --- | --- | --- |
| OpenCRAVAT | Local/hosted annotation pipeline với converters, mapper, annotator modules, aggregation, report export. | Converter/report export chạy được cho validation, nhưng local annotator module install bị brittle trong test hiện tại. | Optional local validation / experiment, không phải MVP backbone. |
| ANNOVAR | Local annotation engine cho VCF, `avinput`, coordinate-based variant và `rsID` list qua `convert2annovar.pl -format rsid`. | Rất hợp với consumer SNP input vì có thể đi từ `rsID` sang `avinput`; cần dbSNP/humandb đúng genome build. | Candidate clinical annotation backbone cho MVP. |
| InterVar | Clinical classification layer thường chạy sau ANNOVAR. | Trả ACMG/AMP-style classification, useful cho dashboard priority, nhưng không thay thế expert review. | Candidate clinical classification layer cho MVP. |
| MyVariant.info | REST API nhanh, aggregate nhiều nguồn annotation thành JSON. | Rất hợp cho `rsID` lookup, fallback enrichment và sanity check. Không phải `rsID` nào cũng có clinical fields. | Fallback API và enrichment layer, không phải single source of truth. |
| MyGene.info | REST API cho gene annotation theo gene symbol, Entrez Gene ID, Ensembl Gene ID. | Không nhận `rsID`/raw SNP file trực tiếp, nhưng trả gene name, IDs, summary và context tốt. | Gene-level enrichment / explainer layer cho dashboard và chatbot. |
| ClinPGx web/API | Nguồn thống nhất cho PharmGKB, CPIC, PharmCAT-related PGx knowledge. | Mạnh cho pharmacogenomics, nhưng output phải đọc theo genotype/allele/drug/evidence level. | Specialized PGx engine cho pharmacogenomics report. |

## 5. Vì Sao Chưa Rebuild Raw DB Parsing

Directly consume raw clinical genomics databases là hướng mạnh nhưng quá nặng cho MVP.

Lý do chính:

- ClinVar có nhiều record trên cùng một `rsID`, nhiều condition, conflicting interpretations, Variation/RCV/SCV concepts riêng.
- PharmGKB/ClinPGx map variant với drug qua genotype, allele, named allele, haplotype, guideline, label và evidence-level structures.
- gnomAD hoạt động tốt nhất bằng exact coordinate + allele, không chỉ `rsID`.
- Consumer files có thể dùng genome build cũ như build 36/hg18, trong khi nhiều source hiện đại dùng hg19/GRCh37 hoặc hg38/GRCh38.
- Variant normalization và liftover dễ biến thành project riêng.

Vì vậy MVP nên tập trung vào việc biến annotation results thành thông tin dễ hiểu, có trace, có source, và có cảnh báo giới hạn.

## 6. Phạm vi input

Core input:

- 23andMe-style raw text/CSV files với các cột tương tự `rsid`, `chromosome`, `position`, `genotype`.
- VCF files nếu sau này cần mở rộng sang pipeline bioinformatics chuẩn hơn.

Optional input:

- Basic user profile như sex, age range, ancestry, medical context.

MVP cần preserve original input fields để trace:

- original `rsID`
- original chromosome
- original position
- original genotype
- source file format
- declared hoặc inferred genome build

## 7. Phạm vi output

Dashboard nên chia finding thành bốn report sections và một assistant layer.

### Clinical variant report

Tập trung vào variant có clinical relevance từ ANNOVAR/InterVar, ClinVar/MyVariant.info/source APIs.

Fields cần hiển thị:

- `rsID`
- gene
- variant / base change
- condition
- clinical significance
- review status hoặc evidence quality
- source database
- source link

### Pharmacogenomics report

Tập trung vào drug response và precision medicine findings từ ClinPGx/PharmGKB API.

Fields cần hiển thị:

- `rsID`
- gene
- genotype hoặc allele
- drug
- response hoặc phenotype summary
- evidence level
- annotation type
- source link

### Population frequency / filtering

Tập trung vào việc variant phổ biến hay hiếm trong population databases.

Fields cần hiển thị:

- gnomAD allele frequency nếu có
- population-specific frequency nếu có
- rare/common flag
- source

### Research / association findings

Tập trung vào lower-confidence associations như GWAS/GRASP/SNPedia/LitVar-style findings.

Phần này phải được label rõ là research-level hoặc non-diagnostic.

### Dashboard assistant / chatbot

Assistant dùng để guided exploration trên annotation run hiện tại.

Assistant nên hỗ trợ:

- summarize high/medium/low priority findings
- filter theo gene, `rsID`, condition, drug, evidence type, source
- explain các field như clinical significance, review status, allele frequency, evidence level
- show source nào support một finding
- trả lời câu kiểu "finding này nghĩa là gì trong report?" mà không đưa medical recommendation

Assistant không được:

- diagnose disease
- recommend medication changes
- infer disease risk ngoài annotation hiện có
- trả lời như thể "không có annotation" nghĩa là "không có risk"
- dùng unsupported general medical knowledge như thể nó đến từ user data

## 8. Design pattern cho dashboard chatbot

MVP chatbot nên học pattern từ các BI/dashboard có natural-language assistant, nhưng áp dụng theo hướng clinical-safe hơn.

| Existing product pattern | Họ làm gì | Bài học cho project |
| --- | --- | --- |
| Power BI Copilot | Cho phép hỏi về report hoặc semantic model qua Copilot/report experience. | Cần semantic layer sạch: field names, descriptions, measure definitions rõ trước khi thêm chat. |
| Tableau Pulse | Dùng metric layer để summarize trends, drivers, outliers bằng natural language. | Nên định nghĩa finding/metric concepts trước, rồi assistant mới giải thích priority/evidence context. |
| Gemini in Looker / Conversational Analytics | Kết nối conversation với modeled data và user permissions. | Chatbot phải chỉ đọc data mà current user/current annotation run được phép truy cập. |
| Amazon QuickSight Q | Natural-language Q&A trên curated topics, dashboards, datasets. | Nên có curated query topics như clinical findings, PGx findings, source links, run status. |
| ThoughtSpot Spotter | Conversational analytics dựa trên semantic layer và query logic có thể kiểm chứng. | Câu trả lời phải auditable: show source rows, source links, scoring rule nếu có. |

Reference links:

- Power BI Copilot: https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-ask-data-question
- Tableau Pulse: https://help.tableau.com/current/online/en-us/pulse_intro.htm
- Gemini in Looker: https://cloud.google.com/looker/docs/gemini-overview-looker
- Amazon QuickSight Q / Amazon Quick: https://docs.aws.amazon.com/en_us/quicksight/latest/user/working-with-quicksight-q.html
- ThoughtSpot Spotter: https://www.thoughtspot.com/product/agents/spotter

Với Clinical Variant Dashboard, assistant nên là **report guide**, không phải **medical advisor**. Nó giúp user tìm, lọc, tóm tắt, hiểu source/evidence, và luôn bám vào annotation run đang chọn.

Recommended MVP chat flow:

```text
User question
  -> classify intent
  -> query normalized annotation tables for current run
  -> retrieve short glossary/source explanations
  -> compose answer with source links and safety wording
  -> optionally highlight matching dashboard rows
```

## 9. Risk / priority scoring

MVP chỉ implement **evidence-priority score**, không phải disease risk prediction model.

High priority:

- ClinVar `Pathogenic` hoặc `Likely pathogenic`.
- Review status mạnh như expert panel hoặc multiple submitters with no conflict.
- Genotype/allele match có liên quan.
- Rare trong population frequency databases.

Medium priority:

- ClinVar conflicting interpretation.
- ClinVar drug response.
- PharmGKB/ClinPGx clinical annotations có evidence level dùng được.
- Variant có drug-response interpretation rõ nhưng actionability còn giới hạn.

Low priority:

- GWAS, GRASP, SNPedia hoặc literature-only associations.
- Weak, ambiguous hoặc research-level evidence.
- Không có clinical annotation.

Out of scope cho MVP:

- Polygenic Risk Score modeling.
- Diagnostic-grade clinical interpretation.
- Automated medical recommendations.
- Open-ended medical chatbot behavior.
- Full raw ClinVar/PharmGKB/gnomAD ingestion pipeline.
- Complete genome build liftover pipeline.

## 10. MVP pipeline đề xuất

```text
User genome file
  -> file parser and validator
  -> preserve original rsID/genotype/build metadata
  -> extract curated/clinically relevant rsID list
  -> convert rsID to ANNOVAR avinput using dbSNP/humandb
  -> ANNOVAR annotation
  -> InterVar ACMG/AMP-style classification
  -> join original genotype back to annotated variants
  -> MyVariant.info fallback/enrichment for unresolved or selected rsIDs
  -> MyGene.info enrichment for mapped gene symbols
  -> ClinPGx/PharmGKB lookup for pharmacogenomics variants
  -> optional MyChem.info drug metadata enrichment
  -> normalize annotation result shape
  -> evidence-priority scoring
  -> dashboard report
  -> chatbot context builder for latest annotation run

Optional validation branch:
  -> Ensembl VEP / Variant Recoder benchmark for selected variants
  -> OpenCRAVAT converter/report export experiment
  -> store run status and converter/mapping errors
```

## 11. Annotation flow có thể cập nhật

MVP cần thiết kế để có thể refresh kết quả khi annotation engines hoặc source databases thay đổi.

Hệ thống không nên overwrite annotation result cũ. Mỗi lần analysis nên tạo một annotation run mới.

Core persisted layers:

```text
original_variants
  -> parsed variants exactly as received from user file

annotation_runs
  -> one row per analysis attempt, including engine names, versions if available, run time, and status

variant_annotations
  -> normalized annotation rows linked to a specific annotation_run

raw_annotation_payloads
  -> raw ANNOVAR/InterVar/MyVariant/MyGene/ClinPGx/PharmGKB output for audit/debugging; optional VEP/OpenCRAVAT validation payload if run

assistant_interactions
  -> optional chat history linked to a specific annotation_run, storing question, answer, referenced finding IDs, and safety category
```

Minimum fields cần preserve từ input:

- sample ID
- original `rsID`
- original chromosome
- original position
- original genotype
- declared hoặc inferred genome build
- source file name hoặc upload ID

Minimum fields cho mỗi annotation run:

- run ID
- sample ID
- annotation engine
- engine version nếu có
- module/source versions nếu có
- query time hoặc run time
- status
- error message nếu failed

Minimum fields cho assistant answers:

- interaction ID
- run ID
- user question
- assistant answer
- intent category
- referenced finding IDs hoặc row IDs
- source links used
- safety/refusal category nếu có
- timestamp

Dashboard behavior:

- Default dùng latest successful annotation run.
- Giữ previous runs để audit.
- Cho phép future "Re-run annotation" mà không cần upload lại genome file.
- Cho phép future comparison giữa hai runs để thấy new findings, removed findings, classification changes, evidence-level changes.
- Chatbot answers phải tied rõ với selected annotation run.
- Nếu user switch run, reset hoặc label rõ chat context.

MVP update strategy:

- Phase 1: store original variants, annotation runs, normalized annotations, raw payloads.
- Phase 2: add manual re-run annotation và read-only chatbot trên latest successful run.
- Phase 3: add scheduled monthly reannotation, change notifications, assistant support cho comparing runs.

Versioned design này giúp project dùng external annotation engines nhưng vẫn giữ reproducibility và auditability.

## 12. Trách nhiệm của từng engine/layer

ANNOVAR:

- Candidate main clinical annotation engine.
- Có thể nhận `avinput` hoặc convert `rsID` list bằng `convert2annovar.pl -format rsid`.
- Cần dbSNP/humandb đúng genome build; một `rsID` có thể map ra nhiều variant records.
- Không giữ genotype context nếu chỉ chạy bằng rsID list, nên phải join lại với `original_variants`.

InterVar:

- Candidate ACMG/AMP-style clinical classification layer.
- Dùng để tạo clinical priority và classification fields cho dashboard.
- Không thay thế expert review; classification phải đi kèm source/caveat.

Ensembl VEP:

- Benchmark/validation layer cho selected variants.
- Dùng để so sánh gene, transcript, consequence, HGVS và variant normalization với ANNOVAR.
- Không phải required MVP path nếu ANNOVAR/InterVar chạy ổn.

OpenCRAVAT:

- Optional local validation / experiment layer.
- Hữu ích để kiểm tra converter, mapper, file-level report export và error summary.
- Không dùng local annotator modules làm MVP demo backbone vì install/dependency không ổn định trong test hiện tại.

MyVariant.info:

- Fast API lookup theo `rsID` qua query endpoints.
- Hữu ích cho sanity check và variant-level enrichment.
- Nên dùng `/v1/query`, không dùng `/v1/variant/{rsid}`, vì `/variant` expects normalized variant identifier như HGVS.

MyGene.info:

- Gene-level enrichment sau khi đã map variant ra gene.
- Bổ sung gene symbol/name, Entrez ID, Ensembl ID và summary cho dashboard/chatbot.
- Không dùng để annotate variant trực tiếp vì không nhận `rsID` như variant query chính.

ClinPGx / PharmGKB:

- Pharmacogenomics-specific source.
- Quan trọng cho drug response vì output phụ thuộc genotype, allele, named allele, haplotype, evidence level.
- Không được treat như simple `rsID -> drug warning` lookup.

Chatbot / assistant layer:

- Chỉ đọc normalized annotation results, source links, glossary text và run metadata.
- Dùng deterministic filters/counts cho factual answers.
- Không generate clinical interpretation nếu không có source row.
- Refuse medical-action requests như đổi thuốc, ngừng thuốc, quyết định treatment.

## 13. Data safety và disclaimers

Dashboard phải ghi rõ:

- Kết quả chỉ mang tính informational và không phải diagnostic.
- Consumer SNP files có thể thiếu variant, dùng genome build cũ, hoặc có strand/build ambiguity.
- User không nên thay đổi thuốc, screening hoặc treatment chỉ dựa trên dashboard output.
- Clinically significant findings cần được confirm và review bởi qualified healthcare professional.
- Chatbot answers chỉ là summary của selected annotation run, không phải medical advice.
- Không thấy finding trong dashboard/chatbot answer không đồng nghĩa là không có clinical risk.

## 14. Next implementation steps

1. Build parser cho 23andMe/PGP-style input files.
2. Tạo small test set gồm common, ClinVar-rich và pharmacogenomic rsIDs.
3. Test `convert2annovar.pl -format rsid` với curated rsID list và dbSNP/humandb đúng build.
4. Run ANNOVAR trên `avinput` output và inspect output columns.
5. Run InterVar trên ANNOVAR-compatible input/output và parse clinical classification.
6. Join genotype từ `original_variants` ngược lại vào ANNOVAR/InterVar findings.
7. Add MyVariant.info lookup cho unresolved hoặc selected variants.
8. Add MyGene.info enrichment cho mapped gene symbols.
9. Add ClinPGx/PharmGKB lookup cho pharmacogenomic variants.
10. Test Ensembl VEP / Variant Recoder như benchmark cho selected variants.
11. Define normalized internal result schema.
12. Define annotation run schema và raw payload storage.
13. Implement evidence-priority scoring.
14. Build dashboard views đầu tiên cho clinical, PGx, frequency, research sections và annotation run status.
15. Add read-only assistant panel để summarize, filter, explain fields và link back to source rows.
16. Add safety/refusal templates cho medical-action questions.
17. Add chatbot evaluation cases với variants như `rs6025`, `rs3093017`, `rs12562034`.
18. Giữ OpenCRAVAT ở nhánh optional validation nếu cần demo file-level conversion/report export, không đưa vào setup path bắt buộc.
