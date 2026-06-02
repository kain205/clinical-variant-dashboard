# 6. Documentation & Demo

Tài liệu này hiện chỉ giữ ở mức outline cho phần bàn giao cuối.

## 6.1 Mục tiêu

- Ghi lại cách setup và chạy MVP.
- Giải thích pipeline từ input đến dashboard.
- Cung cấp demo flow và sample output.
- Ghi rõ giới hạn và safety disclaimer.

## 6.2 Demo flow

```text
Upload/select genome file
-> parse variants
-> run annotation/enrichment
-> normalize findings
-> calculate evidence-priority score
-> view dashboard reports
-> inspect one variant detail
```

## 6.3 Tài liệu cần có

- README setup guide.
- Data source notes.
- Preprocessing notes.
- Annotation engine notes.
- Schema/data dictionary.
- Scoring rules.
- Dashboard guide.
- Known limitations.
- Future work roadmap.

## 6.4 Giới hạn cần nhắc rõ

- Consumer SNP files có thể thiếu variant hoặc dùng genome build cũ.
- rsID không luôn đủ để xác định allele chính xác.
- OpenCRAVAT với 23andMe build36 có thể tạo partial converter errors.
- Kết quả chỉ dùng cho mục đích tham khảo/giáo dục, không dùng để chẩn đoán hoặc tự thay đổi điều trị.

## 6.5 Deliverables sau

- Final documentation.
- Demo script.
- Sample input.
- Sample output report.
- Screenshots.
