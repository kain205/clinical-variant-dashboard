# Thực trạng dự án và kế hoạch tiếp theo

Ngày cập nhật: 2026-06-08

## 1. Phân tích thực trạng dự án

Dự án hiện đã vượt qua giai đoạn research thuần túy và có một `pipeline` có thể kiểm chứng bằng artifact thật. Trục kỹ thuật chính hiện nay là:

```text
raw consumer SNP file
  -> parser / preprocessing
  -> rsID / coordinate normalization
  -> annotation tool output
  -> InterVar classification evidence
  -> normalized comparison / dashboard-ready finding
```

### Điểm đã làm tốt

| Mảng | Thực trạng | Ý nghĩa |
| --- | --- | --- |
| Input parser | Đã parse được CSV/TSV/23andMe-like input, giữ `rsid`, `genotype`, `row_index`, duplicate/no-call/skipped rows. | Có nền tảng traceability từ raw file tới output. |
| Workbench UI | Streamlit đã có các tab inspect raw input, parsed input, subset, adapters, raw payload, normalized comparison và full SNP -> InterVar. | Dự án đã có internal GUI để demo và debug pipeline. |
| Adapter benchmark | Đã có adapter layer cho REST/GraphQL/local annotation tools, raw payload được giữ riêng. | Không bị mất thông tin khi normalize nhiều nguồn annotation khác nhau. |
| ANNOVAR route | Đã validate cả VCF subset route và rsID -> avinput route. | Chọn được đường đi phù hợp hơn cho consumer SNP file. |
| InterVar output | Full Child 1 run đã tạo `.intervar` với 788,431 data rows, gồm `Benign`, `Likely benign`, `Uncertain significance`, `Likely pathogenic`. | Có evidence backbone thật cho scoring và dashboard review queue. |
| Join-back genotype | Có `join_back.tsv` nối annotation row về genotype gốc, mapping status và warning. | Giảm rủi ro diễn giải nhầm variant không thuộc sample hoặc multi-mapping. |
| Safety framing | Đã định hình `traceability layer`, `HITL review gate`, `scope boundary`. | Dự án không trình bày output như chẩn đoán tự động. |
| Tests | Đã có test cho parser, SNP-to-VCF, InterVar pipeline, rsID route. | Pipeline có regression evidence cơ bản. |

### Mức độ trưởng thành hiện tại

Dự án đang ở mức `PoC evidence -> Benchmark-ready`, chưa phải `production runtime`.

Lý do: các bước quan trọng đã chạy được end-to-end và có output thật, nhưng output InterVar còn lớn, chạy lâu, và có warning ở một số evidence columns. Vì vậy hiện tại nên xem ANNOVAR/InterVar full run là offline benchmark artifact, còn dashboard MVP nên ưu tiên đọc/normalize artifact đã sinh ra thay vì chạy full annotation trực tiếp trong mỗi demo.

### Rủi ro chính

| Rủi ro | Tác động | Cách xử lý hiện tại |
| --- | --- | --- |
| Consumer SNP thiếu `REF/ALT` | Không thể dùng trực tiếp với VCF-first tools nếu không resolve allele. | Dùng route `rsID -> avinput`, sau đó join-back genotype. |
| Multi-mapping / allele ambiguity | Có thể tạo nhiều annotation rows cho cùng một rsID. | Gắn flag `multi_mapping`, `genotype_ref_alt_mismatch`, `sample_carries_alt`. |
| InterVar exit non-zero sau khi đã ghi output | UI có thể hiểu nhầm là failed hoàn toàn. | Giữ `.intervar` nếu hợp lệ, surface warning, parse như evidence cần review. |
| Full output quá lớn | Không phù hợp cho demo realtime. | Dùng offline run folder và normalize thành file nhỏ. |
| Clinical-looking labels | Dễ bị hiểu nhầm thành kết luận y tế. | Bắt buộc qua `HITL review gate` và wording "evidence priority", không phải diagnosis. |
| Local ANNOVAR DB rất nặng | Không nên push lên GitHub. | `tools/` được đưa vào `.gitignore`; chỉ push code, docs, tests, scripts. |

## 2. Làm gì tiếp theo

### Ưu tiên ngay

| Priority | Task | Output mong muốn |
| --- | --- | --- |
| High | Viết InterVar/ANNOVAR normalizer | `normalized_intervar_findings.csv` gồm `rsid`, gene, consequence, ClinVar signal, InterVar classification, genotype match status, warning, raw source path. |
| High | Tạo review queue rõ cho `Likely pathogenic` / `Uncertain significance` | Dashboard chỉ hiển thị như "Requires review", có link về raw `.intervar` và `join_back.tsv`. |
| High | Harden InterVar full-run handling | Preflight/sanitize các numeric placeholder như `X`, log warning rõ thay vì để user thấy ambiguous failure. |
| Medium | Thêm `evidence_tier` vào normalized schema | Phân biệt `clinical`, `PGx`, `research`, `explanation`, `technical`. |
| Medium | So sánh curated variants qua ClinVar, VEP REST, MyVariant.info, ANNOVAR/InterVar | Có bảng multi-tool comparison để Week 3/4 scoring có baseline. |
| Medium | Chuẩn hóa dashboard scoring baseline | Rule-based `High/Medium/Low/Unknown`, không gọi là disease prediction. |
| Low | Liftover cho hg18/hg36 sample nếu cần | Mở rộng ngoài Child 1 mà không dùng sai coordinate build. |

### Deliverable nhỏ nhất nên làm kế tiếp

Deliverable nên làm trước là normalizer đọc:

```text
data/processed/workbench/annovar_rsid_route/phase2_full_child1/intervar_child1.hg19_multianno.txt.intervar
data/processed/workbench/annovar_rsid_route/phase2_full_child1/join_back.tsv
```

và xuất:

```text
data/processed/workbench/annovar_rsid_route/phase2_full_child1/normalized_intervar_findings.csv
```

File này nên nhỏ hơn nhiều so với raw output và chỉ chứa các variant cần review hoặc các row có evidence đáng dùng cho dashboard. Đây là bước biến artifact offline thành input thật cho MVP.

### Kế hoạch theo sprint ngắn

| Sprint | Việc chính | Tiêu chí hoàn thành |
| --- | --- | --- |
| Sprint 1 | InterVar parser + join-back normalizer | Có CSV normalized, test parser, count classification khớp report. |
| Sprint 2 | Evidence-priority scoring baseline | Mỗi finding có `priority`, `evidence_tier`, `requires_review`, `source_paths`. |
| Sprint 3 | Dashboard review queue | UI lọc theo classification/priority/gene/rsID, mở được raw source path. |
| Sprint 4 | Multi-tool comparison | Curated variants có comparison giữa ClinVar/VEP/MyVariant/ANNOVAR/InterVar. |
| Sprint 5 | Report assistant scope | Assistant chỉ trả lời dựa trên selected run, có refusal cho câu hỏi ngoài scope. |

## 3. Repo / push checklist

Đã chuẩn bị repo theo hướng chỉ push phần reproducible:

- Push: source code trong `src/`, tests trong `tests/`, docs trong `docs/`, wiki trong `wiki/`, scripts nhỏ trong `scripts/`.
- Không push: local data, generated outputs, ANNOVAR/InterVar database nặng trong `tools/`.
- Lý do: `tools/annovar/humandb/hg19_snp138.txt` hơn 12GB và không phù hợp để lưu trực tiếp trên GitHub.

Sau push, repo nên thể hiện được:

```text
docs -> báo cáo tuần 1/2, workflow notes, status memo
src  -> parser, workbench, preprocessing, InterVar pipeline
tests -> regression tests cho parser/conversion/pipeline
wiki -> architecture decisions và module notes
scripts -> command wrapper cho full SNP -> InterVar
```
