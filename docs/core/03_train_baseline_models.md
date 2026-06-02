# 3. Baseline Models and Chatbot Layer

Tài liệu này định nghĩa baseline cho MVP. Trong phạm vi dự án này, "model" không có nghĩa là mô hình dự đoán bệnh hoặc chẩn đoán y khoa. Baseline hợp lý hơn là một lớp **rule-based evidence scoring** kết hợp với **dashboard assistant/chatbot** có kiểm soát, chỉ trả lời dựa trên annotation results và source links đã có.

## 3.1 Mục tiêu

- Xếp hạng variant/finding theo mức độ ưu tiên để hiển thị trên dashboard.
- Tách rõ clinical evidence, pharmacogenomics evidence, population frequency và research-only evidence.
- Hỗ trợ người dùng hỏi nhanh về kết quả thay vì phải đọc toàn bộ bảng.
- Giữ mọi câu trả lời của chatbot có nguồn, có ngữ cảnh, và có cảnh báo giới hạn.
- Không đưa ra chẩn đoán y khoa, dự đoán bệnh cá nhân, hoặc khuyến nghị thay đổi thuốc.

## 3.2 Baseline cho MVP

MVP nên có hai baseline chính:

| Layer | Vai trò | Cách làm MVP |
| --- | --- | --- |
| Evidence-priority scoring | Ưu tiên finding nào cần hiển thị trước. | Rule-based score từ InterVar/ACMG classification, ClinVar, PGx evidence, allele frequency, consequence và source quality. |
| Dashboard chatbot | Giúp người dùng hỏi đáp trên kết quả đã annotate. | Retrieval + structured query trên annotation run hiện tại, sau đó tạo câu trả lời ngắn có source links. |

Không train mô hình ML riêng trong MVP. Các tác vụ như polygenic risk score, disease prediction, genotype-to-phenotype model, hoặc fine-tuning LLM nên để future work.

## 3.3 Input cho baseline

Baseline chỉ dùng dữ liệu đã đi qua pipeline annotation:

- original variant fields: `rsID`, chromosome, position, genotype, source file, genome build
- normalized annotation fields: gene, consequence, condition, drug, phenotype, evidence level
- source-specific fields: InterVar ACMG/AMP-style classification, ANNOVAR gene/consequence/filter annotations, ClinVar significance/review status, gnomAD frequency, GWAS trait, ClinPGx/PharmGKB annotation
- source links/raw payloads: ANNOVAR, InterVar, dbSNP, ClinVar, gnomAD, GWAS Catalog, ClinPGx/PharmGKB, LitVar, MyVariant.info, MyGene.info; optional VEP/OpenCRAVAT validation output nếu có
- annotation run metadata: run ID, engine, version, timestamp, status

Chatbot không nên truy cập trực tiếp toàn bộ raw genome file nếu câu hỏi chỉ cần dữ liệu đã annotate. Điều này giúp giảm rủi ro trả lời sai, lộ thông tin không cần thiết, hoặc suy diễn ngoài phạm vi.

## 3.4 Evidence-priority scoring

Điểm ưu tiên nên được thiết kế để phục vụ dashboard ordering, không phải medical risk prediction.

| Priority | Điều kiện gợi ý | Cách hiển thị |
| --- | --- | --- |
| High | InterVar/ClinVar `Pathogenic` hoặc `Likely pathogenic`; review status mạnh; PGx finding có drug/phenotype/evidence rõ; variant hiếm và có clinical context. | Đặt lên đầu, có badge rõ, yêu cầu professional review. |
| Medium | InterVar `VUS`, ClinVar `Conflicting interpretations`, ClinVar `drug response`; PGx annotation có evidence nhưng cần genotype/allele context; consequence đáng chú ý nhưng chưa đủ clinical claim. | Hiển thị trong nhóm cần xem kỹ, kèm giải thích giới hạn. |
| Low | GWAS/SNPedia/LitVar-only association; common variant; evidence yếu hoặc research-level. | Đưa vào tab research/exploration, tránh ngôn ngữ chẩn đoán. |
| Unknown | Không có annotation hữu ích hoặc chỉ có dbSNP/coordinate/frequency cơ bản. | Giữ để audit hoặc ẩn mặc định khỏi summary. |

Ví dụ rule đơn giản:

```text
if (
  InterVar classification in [Pathogenic, Likely pathogenic]
  or ClinVar significance in [Pathogenic, Likely pathogenic]
) and review_status is not low-confidence:
    priority = High
else if PGx annotation has drug + phenotype + evidence level:
    priority = Medium or High depending on evidence/actionability
else if GWAS/SNPedia/LitVar association only:
    priority = Low
else:
    priority = Unknown
```

## 3.5 Tín hiệu dùng cho scoring

Clinical signals:

- InterVar ACMG/AMP-style classification
- InterVar evidence tags nếu parse được
- ANNOVAR gene/consequence/filter annotations
- ClinVar clinical significance
- ClinVar review status
- disease/condition name
- conflicting interpretation flag
- source link and Variation ID nếu có

Pharmacogenomics signals:

- ClinPGx/PharmGKB evidence level
- drug name
- phenotype or response summary
- genotype/allele/named allele context
- annotation type: label, clinical annotation, variant annotation, guideline

Population/frequency signals:

- gnomAD allele frequency
- population-specific frequency nếu có
- homozygote count nếu có
- rare/common flag

Research/supporting signals:

- GWAS trait
- p-value/effect size nếu có
- LitVar publication count and PMID links
- SNPedia magnitude hoặc genotype page nếu có
- consequence and functional prediction scores từ ANNOVAR/MyVariant.info/dbNSFP/CADD fields nếu có; optional VEP/OpenCRAVAT output nếu đã chạy validation

## 3.6 Chatbot trong dashboard

MVP chatbot nên là một **assistant panel bên cạnh dashboard**, không phải một chatbot tự do. Người dùng có thể hỏi bằng tiếng Việt hoặc tiếng Anh, nhưng câu trả lời phải bị giới hạn bởi dữ liệu trong annotation run hiện tại và tài liệu giải thích đã chuẩn bị.

Các loại câu hỏi nên hỗ trợ:

- Summary: "Có finding nào high priority không?"
- Filtering: "Cho tôi các variant liên quan thuốc."
- Explanation: "ClinVar conflicting interpretation nghĩa là gì?"
- Source navigation: "Finding rs6025 lấy từ nguồn nào?"
- Comparison: "Vì sao rs6025 được ưu tiên hơn rs12562034?"
- Safety: "Tôi có nên đổi thuốc không?" -> phải từ chối khuyến nghị y khoa và hướng người dùng gặp chuyên gia.

Các loại câu hỏi không hỗ trợ trong MVP:

- "Tôi có bị bệnh X không?"
- "Tôi nên dùng/ngừng thuốc nào?"
- "Tính nguy cơ bệnh cả đời của tôi."
- "Suy luận từ biến thể không có annotation."

## 3.7 Chatbot baseline architecture

```text
User question
  -> intent classifier
  -> retrieve current annotation_run context
  -> structured filters/counts over normalized annotations
  -> retrieve short glossary/source explanations
  -> compose answer with source links and safety disclaimer
  -> show suggested follow-up actions in dashboard
```

Implementation notes:

- Dùng deterministic query/filter cho số liệu, count, danh sách finding.
- Dùng LLM chủ yếu để diễn giải ngắn gọn, không để tự tạo fact mới.
- Mỗi câu trả lời nên có `based_on` gồm run ID, rows/finding IDs, và source links.
- Nếu không có dữ liệu trong annotation run, trả lời "không thấy trong dữ liệu hiện tại" thay vì suy đoán.
- Các câu hỏi medical-action phải có safety response cố định.

## 3.8 Dashboard patterns có thể học theo

Các BI/dashboard hiện đại đã tích hợp natural-language assistant theo một số pattern đáng học:

| Product | Pattern đáng học | Bài học cho project |
| --- | --- | --- |
| Power BI Copilot | Chat/assistant panel hỏi về report hoặc semantic model. | Cần semantic layer sạch, field names rõ, mô tả field dễ hiểu để chatbot hiểu đúng dữ liệu. |
| Tableau Pulse | Metric layer, natural-language insight, trends/outliers. | Nên định nghĩa metric/finding rõ trước, rồi để assistant giải thích thay đổi hoặc ưu tiên. |
| Gemini in Looker / Conversational Analytics | Hỏi đáp dựa trên Looker model và quyền truy cập dữ liệu. | Chatbot phải tôn trọng access control và chỉ query dữ liệu đã được model hóa. |
| Amazon QuickSight Q | Natural-language Q&A trên dashboard/topic/dataset. | Cần curated topic/schema để giới hạn câu hỏi và tránh hiểu sai cột dữ liệu. |
| ThoughtSpot Spotter | Search/chat analytics với token/semantic layer có thể kiểm chứng. | Câu trả lời nên có logic có thể kiểm tra, không chỉ là đoạn văn tự tin. |

Áp dụng cho Clinical Variant Dashboard: chatbot nên giống một "report guide" hơn là "medical advisor". Nó giúp người dùng tìm, lọc, tóm tắt và hiểu nguồn evidence, còn kết luận y khoa vẫn nằm ngoài scope.

## 3.9 Evaluation cho baseline

Test cases tối thiểu:

| Test | Expected behavior |
| --- | --- |
| `rs6025` có InterVar/ClinVar/PGx result | Score không thấp hơn medium; chatbot nêu gene, source, drug/condition context nếu có. |
| Variant chỉ có dbSNP/gnomAD | Score unknown hoặc low; chatbot nói không có clinical annotation trong run hiện tại. |
| GWAS-only association | Score low; chatbot ghi rõ research-level/non-diagnostic. |
| Câu hỏi đổi thuốc | Chatbot không đưa khuyến nghị dùng/ngừng thuốc; nhắc professional review. |
| Câu hỏi không có trong dữ liệu | Chatbot nói không thấy evidence trong annotation run hiện tại. |
| Câu hỏi yêu cầu source | Chatbot trả source links hoặc nói source chưa có. |

## 3.10 Deliverables

- Mapping table từ annotation fields sang priority.
- Hàm `score_finding(annotation_row)` hoặc equivalent service.
- Normalized finding schema có `priority`, `evidence_type`, `source_links`, `safety_label`.
- Parser cho ANNOVAR/InterVar output fields cần cho scoring.
- Logic join genotype gốc vào finding sau khi ANNOVAR/InterVar annotation chạy từ `rsID`/`avinput`.
- Chatbot intent list và safety policy tối thiểu.
- Retrieval/query layer chỉ đọc từ annotation run hiện tại.
- Bộ test case nhỏ cho scoring và chatbot responses.
- Ví dụ dashboard report có score, source links, và assistant panel.

## 3.11 Out of scope

- Polygenic Risk Score.
- Disease prediction model.
- Fine-tuning LLM trên dữ liệu genome cá nhân.
- Automated medical recommendations.
- Full genotype-to-drug prescribing engine.
- Chatbot trả lời dựa trên kiến thức y khoa tổng quát ngoài annotation result của người dùng.
