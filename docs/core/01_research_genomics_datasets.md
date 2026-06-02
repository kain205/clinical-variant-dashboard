# 1. Research Genomics Datasets

Tuần 1 tập trung khảo sát các nguồn dữ liệu có thể dùng cho dự án Clinical Variant Analytics Dashboard. Mục tiêu của giai đoạn này là hiểu rõ hai nhóm tài nguyên chính:

- **Mock Input Data:** Dữ liệu gen mẫu dùng để test hệ thống, mô phỏng dữ liệu người dùng upload.
- **Reference Databases & Annotation Tools:** Các cơ sở dữ liệu và công cụ dùng để đối chiếu, chú giải và diễn giải biến thể gen.

Kết quả của tuần này sẽ dùng để xác định nguồn dữ liệu nào phù hợp, dữ liệu có cấu trúc ra sao, ưu/nhược điểm là gì, và có thể dùng vào phần nào của hệ thống.

## 1.1 Tìm kiếm Dữ liệu Đầu vào mẫu (Mock Input Data)

Mục đích: Tìm kiếm các dữ liệu genome/SNP cá nhân có thể dùng để mô phỏng file người dùng upload vào hệ thống.

| Tên Dataset | Đặc điểm dữ liệu | Thông tin bệnh nhân / phenotype | Ưu điểm | Nhược điểm / Ghi chú |
| --- | --- | --- | --- | --- |
| Harvard Personal Genome Project (PGP) | Dữ liệu genome cá nhân công khai, `6,224` entries. Bao gồm raw SNPs, VCF/genome files, phenotype survey và health records tùy hồ sơ. | Có tuổi, giới tính, đặc điểm cơ thể, bệnh nền, thuốc đang dùng và các tính trạng tự khai. | Dùng để test luồng end-to-end khi người dùng có genome file kèm optional health record/profile. | Phenotype/health record không phải hồ sơ nào cũng đầy đủ; dữ liệu tự khai nên có thể thiếu hoặc không đồng nhất. |
| My Complete Genome (Kaggle) | Dữ liệu genome cá nhân của một gia đình, gồm 7 file sau: `Child 1 Genome.csv`, `Child 2 Genome.csv`, `Child 3 Genome.csv`, `Father Genome.csv`, `Mother Genome.csv`, `genome_file_description.csv`, `genome_zeeshan_usmani.csv`. | Gần như không có health record chi tiết; có liên kết di truyền của một gia đình gồm bố, mẹ và 3 con. | Dùng để test MVP trong trường hợp phổ biến: người dùng chỉ có genome/SNP file, không có health record đi kèm. Dữ liệu của 5 người trong cùng một gia đình giúp kiểm thử thêm các giả thuyết liên quan đến quan hệ di truyền, tính nhất quán genotype và so sánh variant giữa các cá nhân. | Quy mô nhỏ; thiếu thông tin bệnh lý/phenotype. |

### Nhận xét

- Với mục tiêu test luồng upload và phân tích genome/SNP cá nhân, **PGP** và **My Complete Genome (Kaggle)** là hai nguồn mock input phù hợp nhất.
- **PGP** phù hợp để test trường hợp có thêm optional health record/profile, giúp kiểm tra luồng end-to-end sát thực tế hơn.
- **My Complete Genome (Kaggle)** phù hợp để test MVP trong trường hợp chỉ có genome/SNP file, không có health record đi kèm.
- Sau phần mock input, cần khảo sát thêm các reference databases để hệ thống có nguồn đối chiếu variant, bệnh liên quan, tần suất alen và ý nghĩa lâm sàng.

## 1.2 Khảo sát Cơ sở dữ liệu Tham chiếu (Reference Databases)

Trước khi xây dựng pipeline phân tích biến thể gen, cần phân biệt rõ vai trò của từng loại cơ sở dữ liệu tham chiếu. Một file genome/SNP thô chỉ cho biết người dùng có genotype nào tại một số vị trí nhất định, ví dụ `rsID`, `chromosome`, `position`, `genotype`. Bản thân các giá trị này chưa đủ để kết luận biến thể đó liên quan đến bệnh gì, có phổ biến trong dân số không, hay ảnh hưởng đến thuốc nào.

Vì vậy, hệ thống cần dùng nhiều nhóm database khác nhau:

* **Variant identifier databases**: xác thực mã biến thể như rsID và chuẩn hóa thông tin biến thể.
* **Clinical variant databases**: tra ý nghĩa lâm sàng của biến thể theo bệnh/condition.
* **Population frequency databases**: kiểm tra biến thể phổ biến hay hiếm trong các quần thể.
* **Pharmacogenomics databases**: tra mối liên hệ giữa gene/variant và phản ứng thuốc.
* **Association study databases**: tham khảo các liên hệ SNP-trait từ nghiên cứu GWAS.
* **Gene-disease / literature databases**: bổ sung ngữ cảnh sinh học, giải thích bệnh và dẫn nguồn nghiên cứu.
* **Functional prediction databases**: dự đoán khả năng biến thể ảnh hưởng đến chức năng gene/protein.

Các database này không thay thế nhau, mà bổ sung cho nhau trong pipeline phân tích. Để đánh giá thực tế hơn, các database bên dưới được kiểm tra thủ công bằng cùng một nhóm rsID mẫu, gồm `rs3093017`, `rs6025` và `rs12562034`. Cách test này giúp so sánh rõ database nào có thể tra bằng rsID, database nào trả về clinical significance, database nào trả về association nghiên cứu, và database nào không có record cho một SNP phổ thông.

| Tài nguyên | Nhóm dữ liệu | Tra cứu / Kết quả trả về | Ứng dụng trong dự án | Ghi chú |
| --- | --- | --- | --- | --- |
| dbSNP | Variant identifier / variant mapping | Tra bằng `rsID` để lấy allele, chromosome-position, genome build, merged IDs, gene/consequence, MAF và HGVS/SPDI. | Xác thực rsID và chuẩn hóa thông tin biến thể trước khi tra cứu ở các database khác. | Không đưa ra kết luận bệnh lý hay thuốc. Một rsID có thể có merged IDs hoặc nhiều allele/representation. |
| ClinVar | Clinical variant database | Tra bằng `rsID`, gene hoặc genomic location để lấy clinical significance, disease/condition, review status và submission records. | Xác định biến thể có ý nghĩa lâm sàng hay không, ví dụ Pathogenic, Likely pathogenic, VUS, Benign hoặc drug response. | Không phải rsID nào cũng có record. Một rsID/gene có thể trả nhiều kết quả theo variant, condition và review status. |
| GWAS Catalog | SNP-trait association | Tra bằng `rsID`, gene, trait/disease hoặc study để lấy SNP-trait associations, p-value, risk allele, effect size, mapped gene và publication/study. | Bổ sung liên hệ giữa SNP/allele và trait/disease để tạo health insight ở mức tham khảo/research. | Association không đồng nghĩa với chẩn đoán cá nhân; cần xét population, effect size, p-value và study context. |
| ClinPGx | Pharmacogenomics | Tra bằng `rsID`, gene, drug hoặc phenotype để lấy variant annotation, drug/phenotype association, allele/haplotype, genotype-specific summary, label annotation, summary annotation và evidence level. | Bổ sung thông tin pharmacogenomics, đặc biệt là liên hệ giữa biến thể/gene và phản ứng thuốc hoặc adverse drug reaction. | Không phải database bệnh tổng quát. Không phải variant nào cũng có record PGx; cần xét drug, phenotype, genotype/allele và evidence level. |
| SNPedia | Consumer genomics knowledge base | Tra bằng `rsID` hoặc genotype cụ thể để lấy mô tả dễ đọc, gene, chromosome-position, orientation, genotype-specific summary, magnitude, population frequency, liên kết sang dbSNP/ClinVar/gnomAD/LitVar/GWAS Catalog và các PMID liên quan. | Có thể dùng làm nguồn tham khảo phụ để giải thích SNP theo cách gần với consumer DNA report. | Evidence không đồng đều và nội dung kiểu wiki/literature summary. Cần kiểm tra orientation/strand và không nên dùng làm nguồn clinical chính. |
| gnomAD | Population frequency | Tra bằng `rsID` hoặc tốt hơn bằng variant chuẩn hóa `chromosome-position-ref-alt` để lấy allele frequency, allele count, allele number, homozygote count, population/group frequency, filter status, VEP consequence và một số predictor/constraint. | Kiểm tra biến thể phổ biến hay hiếm trong quần thể, hỗ trợ lọc và diễn giải tần suất biến thể. | Không phải clinical database. Cần chuẩn hóa genome build và ref-alt trước khi join; allele frequency không đồng nghĩa với ý nghĩa bệnh lý. |
| OMIM | Gene-disease knowledge | Tra theo gene, phenotype, disease hoặc một số rsID được index để lấy gene-phenotype relationship, inheritance, allelic variant, mô tả bệnh và references. | Bổ sung ngữ cảnh gene-disease khi giải thích gene/variant có ý nghĩa clinical rõ. | Không phải nguồn annotate SNP trực tiếp từ consumer SNP file; nhiều rsID phổ thông hoặc GWAS SNP sẽ không có kết quả. |
| ClinGen Allele Registry | Allele registry / variant identifier | Tra bằng `dbSNP Id`, HGVS, ClinVar ID, gnomAD ID hoặc reference sequence-position để lấy CAid, allele representation, gene, transcript/protein consequence và linkouts sang ClinVar/dbSNP/gnomAD. | Chuẩn hóa và liên kết định danh allele giữa nhiều nguồn dữ liệu, hỗ trợ mapping variant trước khi annotate sâu hơn. | Không phải annotation pipeline và không phải nguồn kết luận bệnh lý; linkouts sang database khác chỉ là liên kết tham chiếu. |
| LitVar | Literature-linked variant | Tra bằng `rsID` hoặc tên variant để tìm publications, PMID/PMCID, article snippets, related BioConcepts, normalized variant name, gene context và link sang dbSNP/ClinGen. | Dùng để truy vết tài liệu, cung cấp evidence links và kiểm tra variant được nhắc trong literature nào. | Là literature mining, không phải nguồn clinical interpretation; có bài báo không đồng nghĩa variant có ý nghĩa bệnh lý. |

### Khả năng truy cập và tích hợp dữ liệu

Ngoài việc khảo sát nội dung trả về, cần đánh giá thêm cách truy cập dữ liệu của từng database. Với MVP, các nguồn có API rõ ràng, file download ổn định hoặc có thể chạy local sẽ dễ tích hợp hơn. Các nguồn chỉ phù hợp để đọc thủ công hoặc bị giới hạn licensing nên được dùng làm nguồn tham khảo, không nên phụ thuộc trực tiếp vào pipeline tự động.

| Tài nguyên | API / Programmatic access | Download / Local data | Mức phù hợp cho MVP |
| --- | --- | --- | --- |
| dbSNP | Cho phép tự động tra `rsID` để lấy bản ghi biến thể và chuẩn hóa sang coordinate, allele, HGVS, VCF/SPDI. Có bulk data để xử lý local nếu cần annotate nhiều variant. | rsID, allele, merged IDs, chromosome-position theo genome build, HGVS/SPDI/VCF representation, population frequency/ALFA nếu có. | Rất phù hợp cho bước chuẩn hóa variant ban đầu: `rsID → normalized variant / coordinate / allele`. |
| ClinVar | Cho phép tự động tra variant để lấy clinical interpretation theo từng condition; có file XML/VCF/TSV để tải về và join local theo variant ID hoặc coordinate. | Clinical significance, condition, review status, submitter/submission, ClinVar Variation ID/VCV, variant-condition relationship. | Rất phù hợp cho MVP clinical annotation nếu lọc kỹ theo condition, classification và review status. |
| GWAS Catalog | Cho phép tự động truy vấn association theo variant, trait, gene, region hoặc study; có full catalog download để xử lý batch. | SNP-trait association, p-value, risk allele, effect size, mapped gene, trait, study accession, publication metadata. | Phù hợp cho module research-level disease/trait association; không dùng như chẩn đoán cá nhân. |
| ClinPGx | Có REST API trả JSON/JSON-LD cho dữ liệu PGx như variants, genes, drugs/chemicals, clinical annotations, variant annotations, pathways và dosing guideline-related data. | Variant-drug-phenotype annotation, clinical annotation, evidence level, gene/drug object, PGx guideline/pathway context. | Phù hợp cho drug-response insight ở mức tra cứu chọn lọc; cần kiểm tra license/data usage nếu dùng bulk. |
| SNPedia | Có thể truy qua MediaWiki/Semantic MediaWiki API vì SNPedia là wiki dựa trên Semantic MediaWiki; tuy nhiên cấu trúc dữ liệu không tối ưu cho clinical pipeline tự động. | Page theo rsID/genotype, genotype summary, magnitude, orientation, references, links sang nguồn khác nếu page có. | Chỉ nên dùng làm nguồn phụ/consumer-friendly explanation; không nên là dependency chính của MVP. |
| gnomAD | Nên dùng bulk data/open dataset theo release thay vì phụ thuộc browser API; dữ liệu có trên cloud/open dataset và phù hợp xử lý batch/local. | Allele count, allele number, allele frequency, homozygote count, ancestry/group frequency, filter status, constraint, VEP consequence/predictor tùy release. | Phù hợp để lấy population frequency sau khi đã chuẩn hóa `chr-pos-ref-alt` và genome build. |
| OMIM | Có API/FTP nhưng thường cần đăng ký và tuân thủ licensing/terms of use. Không nên coi là open bulk source tự do như dbSNP/ClinVar. | Gene-phenotype relationship, inheritance, MIM number, allelic variant, disease description, references. | Dùng làm nguồn bổ sung gene-disease context; không nên là dependency chính của MVP nếu chưa xử lý licensing. |
| ClinGen Allele Registry | Có web/API để lookup allele bằng dbSNP ID, HGVS, ClinVar ID, gnomAD ID, CAid hoặc reference sequence-position; trả canonical allele identifier. | CAid, allele representation, gene, transcript/protein consequence, mapping/linkouts sang dbSNP/ClinVar/gnomAD. | Phù hợp cho bước chuẩn hóa/liên kết allele identifier giữa nhiều database. |
| LitVar | Có LitVar API/SmartAPI để search literature theo variant và related concepts. | Normalized variant name, PMID/PMCID, article title/snippet, publication metadata, related BioConcepts như gene/disease/drug. | Phù hợp để tạo evidence links cho dashboard; không dùng làm nguồn clinical interpretation. |

### Nhận xét

Qua quá trình khảo sát, có thể thấy không có một database đơn lẻ nào đủ để diễn giải hoàn chỉnh dữ liệu SNP cá nhân. Mỗi nguồn dữ liệu chỉ giải quyết một lớp thông tin riêng trong pipeline: `dbSNP` và `ClinGen Allele Registry` hỗ trợ xác thực, chuẩn hóa và liên kết định danh biến thể; `gnomAD` cung cấp tần suất allele trong quần thể; `ClinVar`, `OMIM` và ClinGen curation bổ sung ngữ cảnh lâm sàng/gene-disease; `GWAS Catalog` cung cấp SNP-trait association ở mức nghiên cứu; `ClinPGx` phục vụ pharmacogenomics; còn `LitVar` giúp truy vết literature evidence.

Với input dạng consumer SNP file, hệ thống không nên diễn giải trực tiếp theo kiểu `rsID → bệnh`. Một `rsID` chỉ là mã định danh biến thể; để tạo insight có ý nghĩa hơn, pipeline cần chuẩn hóa genome build và allele, ánh xạ genotype của người dùng với risk/alternate allele, kiểm tra tần suất trong quần thể, tra clinical significance nếu có, đối chiếu GWAS/PGx/literature evidence, rồi mới trình bày kết quả ở mức tham khảo. Đặc biệt, association từ GWAS hoặc số lượng bài báo trong LitVar không đồng nghĩa với chẩn đoán cá nhân.

Đối với MVP, nên ưu tiên các nguồn có vai trò rõ và dễ tích hợp: `dbSNP` cho chuẩn hóa rsID/variant, `ClinVar` cho clinical significance, `GWAS Catalog` cho research-level SNP-trait association, `gnomAD` cho allele frequency, `ClinPGx` cho drug-response context, `ClinGen Allele Registry` cho chuẩn hóa allele identifier, và `LitVar` cho evidence links. `OMIM` nên dùng như nguồn bổ sung ngữ cảnh gene-disease khi gặp gene hoặc variant nổi bật, không nên dùng làm nguồn annotate SNP hàng loạt.

Các nguồn như `SNPedia` có thể giúp tham khảo cách diễn giải gần với consumer DNA report, nhưng không nên dùng làm nguồn clinical chính vì evidence không đồng đều và cần kiểm tra orientation/strand. Các công cụ như `PharmCAT`, `VEP`, `ANNOVAR`, `SnpEff`, `OpenCRAVAT` hoặc nhóm functional prediction tools nên được khảo sát riêng ở phần annotation tools, vì chúng không chỉ là database tra cứu mà là công cụ xử lý/chú giải tích hợp.

## 1.3 Khảo sát Công cụ Chú giải Tích hợp (Annotation Tools)

Ở phần 1.2, các reference databases đã được khảo sát theo từng lớp thông tin như định danh biến thể, clinical significance, allele frequency, GWAS association, pharmacogenomics và literature evidence. Tuy nhiên, nếu tự gọi từng database riêng lẻ, pipeline sẽ phải tự xử lý nhiều bước kỹ thuật như chuẩn hóa `rsID`, genome build, ref/alt allele, transcript consequence, mapping identifier và merge kết quả.

Vì vậy, phần này khảo sát thêm các annotation tools. Đây là các công cụ có thể nhận input như `rsID`, VCF, HGVS, `chromosome-position-ref-alt` hoặc file variant list, sau đó tự động gắn annotation cho biến thể. Mục tiêu là xác định tool nào phù hợp cho MVP, tool nào phù hợp cho pipeline nâng cao, và tool nào chỉ nên dùng cho module chuyên biệt.

Khác với phần 1.2 chỉ test theo từng `rsID`, phần 1.3 cần test thêm ở mức file input, vì dashboard thực tế sẽ xử lý file SNP/variant do người dùng upload.

### 1.3.1 Mục tiêu khảo sát annotation tools

Phần này tập trung trả lời:

* Tool nhận input dạng gì: `rsID`, VCF, HGVS, coordinate, TSV/CSV hay raw consumer SNP file?
* Tool có xử lý batch/file input không?
* Tool có cần chuẩn hóa genome build/ref-alt trước không?
* Tool trả output gì: gene, transcript, consequence, clinical significance, allele frequency, PGx, prediction score?
* Output có dễ parse để đưa lên dashboard không?
* Tool phù hợp MVP, pipeline nâng cao hay module chuyên biệt?

### 1.3.2 Kế hoạch manual testing

Annotation tools sẽ được test theo hai lớp:

| Lớp test | Input dùng | Mục đích |
| --- | --- | --- |
| Single-variant testing | `rs3093017`, `rs6025`, `rs12562034` | Kiểm tra tool có nhận `rsID` không, output có gene/consequence/clinical/association không. |
| File-level testing | 20–50 dòng từ mock SNP file | Kiểm tra tool có xử lý file/batch được không, có cần convert sang VCF/TSV/coordinate không, output có dùng được cho pipeline không. |

File test ban đầu có thể ở dạng:

```text
rsid, chromosome, position, genotype
```

Sau đó sẽ thử chuyển sang format phù hợp với từng tool:

```text
consumer SNP file → normalized TSV / coordinate list / VCF → annotation output
```

### 1.3.3 Bảng khảo sát annotation tools

| Công cụ / workflow | Input hỗ trợ | Cách truy cập | Output chính | Vai trò trong dự án | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| MyVariant.info | `rsID`, HGVS, genomic variant ID, batch query; không nhận raw 23andMe file trực tiếp | REST API GET/POST, Python wrapper | JSON annotation từ nhiều nguồn như dbSNP, ClinVar, gnomAD, CADD, dbNSFP tùy variant | API lookup nhanh / fallback enrichment | Đã test 3 rsID và batch 10/100 rsID từ PGP file đều chạy OK. Với 23andMe/PGP file cần parse cột `rsid` rồi batch query bằng `scopes=dbsnp.rsid`. Coordinate từ build36/hg18 không nên gửi thẳng, ưu tiên query bằng `rsID`. |
| OpenCRAVAT | VCF, CRAVAT TSV, dbSNP identifiers, 23andMe/Ancestry formats | Web interface, local CLI, Python package | Gene, consequence và report export nếu converter/module setup ổn | Optional local validation / experiment, không còn là MVP backbone | Đã test với PGP `hu43860C`: forced `23andme` tạo được SQLite/TSV/XLSX usable nhưng còn 4,325 converter/mapping errors. Khi thử cài annotator modules cho MVP, `pharmgkb`, `gwas_catalog`, `litvar` cài được nhưng đã uninstall; `clinvar_acmg` bị treo; full `clinvar` có xu hướng kéo dependency rất lớn như `dbsnp`. Kết luận: OpenCRAVAT hữu ích để experiment file-level annotation nhưng module ecosystem quá brittle cho MVP demo nhanh. |
| ANNOVAR + InterVar | ANNOVAR nhận VCF, `avinput`, coordinate-based variant, và `rsID` list qua `convert2annovar.pl -format rsid`; InterVar dùng ANNOVAR-style input/output | Local CLI: ANNOVAR Perl scripts + `humandb`; InterVar chạy sau ANNOVAR | ANNOVAR trả gene-based, region-based, filter-based annotation; InterVar trả ACMG/AMP-style classification như Pathogenic, Likely pathogenic, VUS, Likely benign, Benign kèm evidence tags | Candidate clinical annotation/classification backbone cho MVP | Hợp với consumer SNP input vì có thể đi từ `rsID` sang `avinput` mà không cần build full VCF. Cần kiểm soát genome build/dbSNP version, multiple mappings của cùng một rsID, và join lại genotype từ file gốc. Nên test trước bằng curated ClinVar-rich variants. |
| Ensembl VEP | VCF, HGVS, coordinate, variant identifier qua Variant Recoder | Web interface, REST API, local CLI | Gene, transcript, consequence, HGVS, SIFT/PolyPhen, phenotype/frequency annotations tùy config | Benchmark / normalization đối chứng | Nên dùng để so sánh consequence/gene/transcript mapping với ANNOVAR và MyVariant.info. Hữu ích để kiểm tra rsID/coordinate/HGVS consistency, nhưng local setup/cache/plugin có thể nặng nên chưa chọn làm MVP backbone. |
| PharmCAT | VCF, outside-call file | Local CLI / PharmCAT pipeline | PGx allele/diplotype, phenotype, CPIC drug recommendation | PGx module chuyên biệt | Không phải general annotation tool. Chỉ nên test sau khi pipeline có VCF hoặc PGx markers phù hợp; dùng cho pharmacogenomics report, không thay thế clinical variant annotation chung. |

Các công cụ phụ trợ không đưa vào bảng chính:

* **MyGene.info**: dùng cho gene-level enrichment sau khi variant đã được map ra gene. Đã test batch gene symbols `CCR6`, `F5`, `LINC01128`, `RNF223`; API trả đủ gene ID/name/summary để bổ sung context cho dashboard/chatbot, nhưng không annotate variant trực tiếp.
* **SnpEff / SnpSift**: có thể dùng như lựa chọn thay thế cho pipeline VCF hoặc để so sánh với VEP trong tương lai, nhưng chưa cần thiết cho MVP.
* **CADD / REVEL / SIFT / PolyPhen / AlphaMissense**: là các functional/pathogenicity prediction scores, thường được lấy qua ANNOVAR, VEP, MyVariant.info hoặc dbNSFP. Chúng chỉ đóng vai trò supporting evidence và không nên được dùng để đưa ra kết luận lâm sàng độc lập.

### Nhận xét

Với mục tiêu MVP, MyVariant.info phù hợp làm API lookup nhanh và fallback enrichment cho các `rsID` đã parse từ file consumer SNP. OpenCRAVAT đã chứng minh có thể xử lý file-level annotation và tạo output usable, nhưng quá trình cài annotator modules không ổn định, đặc biệt với các module clinical lớn như ClinVar/ClinVar ACMG. Vì vậy OpenCRAVAT nên được giữ ở vai trò optional experiment/local validation thay vì MVP backbone.

Workflow đáng ưu tiên tiếp theo là ANNOVAR + InterVar. ANNOVAR đảm nhiệm bước annotation bằng database local, còn InterVar bổ sung clinical classification theo ACMG/AMP. Ensembl VEP nên giữ vai trò benchmark để kiểm tra transcript/consequence/HGVS consistency. PharmCAT nên tách riêng cho pharmacogenomics vì nó giải bài toán drug response/diplotype/CPIC recommendation, không phải annotation tổng quát.

# 2. Kết quả Bàn giao (Deliverables)

## 2.1 Danh sách tài nguyên

| Nhóm | Tài nguyên chính | Mục đích sử dụng |
| --- | --- | --- |
| Mock input data | Harvard PGP, Kaggle 23andMe Family of Five | Test parser, annotation flow và dashboard end-to-end. |
| Population baseline | 1000 Genomes, gnomAD | Tham chiếu tần suất quần thể và lọc biến thể phổ biến. |
| Disease/clinical annotation | ClinVar, ClinGen, OMIM | Đối chiếu biến thể với bệnh lý và gene-disease context. |
| Pharmacogenomics | PharmGKB, ClinPGx, CPIC, PharmCAT | Phân tích drug response và precision medicine. |
| Research association | GWAS Catalog, GRASP, SNPedia, LitVar | Cung cấp insight nghiên cứu và literature references. |
| Annotation tools / APIs | ANNOVAR, InterVar, MyVariant.info, MyGene.info, ClinPGx/PharmGKB API, Ensembl VEP benchmark, OpenCRAVAT optional | Hỗ trợ annotation/classification clinical, lookup/enrichment biến thể, enrichment theo gene, PGx context và chuẩn hóa output. |

## 2.2 Dữ liệu mẫu đã tải / kiểm tra

| Dataset | Tình trạng | Ghi chú |
| --- | --- | --- |
| Harvard PGP sample `hu43860C` | Đã tải và kiểm tra raw SNPs file. | File có định dạng 23andMe-style, gồm `rsid`, `chromosome`, `position`, `genotype`; metadata ghi human assembly build 36. |
| Kaggle 23andMe Family of Five | Đã xác định là mock input chính. | Gồm nhiều file CSV của các thành viên gia đình, phù hợp để test parser và multi-sample workflow. |

## 2.3 Cấu trúc dữ liệu dự kiến

```text
clinical-variant-pipeline/
├── data/
│   ├── raw_inputs/
│   │   ├── kaggle_family/
│   │   └── pgp_hu43860C/
│   └── processed/
└── src/
```

## 2.4 Kết luận Tuần 1

- Dữ liệu đầu vào nên ưu tiên consumer genomics format như 23andMe/PGP để sát bài toán dashboard cá nhân.
- PGP phù hợp để test người dùng có health context; Kaggle 23andMe phù hợp để test parser nhanh.
- Các database gốc cung cấp kiến thức y sinh học quan trọng nhưng có cấu trúc phức tạp.
- MVP nên test hướng parser + ANNOVAR + InterVar trước cho clinical backbone: consumer SNP file được parse thành `rsID/genotype/build`, rsID được convert sang `avinput`, ANNOVAR tạo annotation, InterVar tạo ACMG/AMP-style classification, sau đó join genotype gốc lại để dashboard/chatbot diễn giải. MyVariant.info, MyGene.info và ClinPGx/PharmGKB giữ vai trò API fallback/enrichment; Ensembl VEP dùng để benchmark; OpenCRAVAT giữ optional validation/experiment.
