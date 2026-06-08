# Repo Wiki Index

## Purpose

Persistent knowledge layer for the Clinical Variant Dashboard repo. Use this wiki before rediscovering project structure or repeating stable decisions.

## Pages

- [Architecture](architecture.md): high-level MVP architecture and data flow.
- [Documentation workflow](modules/documentation.md): repo-scoped documentation skill and maturity-level writing rules.
- [Preprocessing module](modules/preprocessing.md): consumer SNP input normalization and OpenCRAVAT-ready output.
- [Dockerized VEP production annotation](decisions/dockerized_vep_production_annotation.md): current production annotation candidate.
- [ANNOVAR + InterVar candidate backbone](decisions/annovar_intervar_candidate_backbone.md): superseded as production default; optional benchmark/classification context.
- [API lookup/enrichment fallback decision](decisions/api_first_mvp_annotation.md): lookup/enrichment fallback strategy.
- [OpenCRAVAT MVP pipeline decision](decisions/opencravat_mvp_pipeline.md): superseded local OpenCRAVAT decision and caveats.
- [Glossary](glossary.md): shared terms used across docs/code.
- [Log](log.md): chronological wiki updates.

## Current MVP Direction

The MVP takes consumer genome/SNP files, preserves original variant fields, prepares Dockerized Ensembl VEP as the production annotation path, uses APIs for lookup/enrichment fallback, scores findings, and displays source-linked dashboard reports with a controlled chatbot/report-guide layer.

## Last Verified

2026-06-05
