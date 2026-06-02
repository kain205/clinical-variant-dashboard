# Repo Wiki Index

## Purpose

Persistent knowledge layer for the Clinical Variant Dashboard repo. Use this wiki before rediscovering project structure or repeating stable decisions.

## Pages

- [Architecture](architecture.md): high-level MVP architecture and data flow.
- [Preprocessing module](modules/preprocessing.md): consumer SNP input normalization and OpenCRAVAT-ready output.
- [ANNOVAR + InterVar candidate backbone](decisions/annovar_intervar_candidate_backbone.md): current clinical annotation/classification candidate.
- [API-first MVP annotation decision](decisions/api_first_mvp_annotation.md): fallback/enrichment strategy.
- [OpenCRAVAT MVP pipeline decision](decisions/opencravat_mvp_pipeline.md): superseded local OpenCRAVAT decision and caveats.
- [Glossary](glossary.md): shared terms used across docs/code.
- [Log](log.md): chronological wiki updates.

## Current MVP Direction

The MVP takes consumer genome/SNP files, preserves original variant fields, tests ANNOVAR + InterVar as the clinical annotation/classification path, uses APIs for fallback/enrichment, scores findings, and displays source-linked dashboard reports with a controlled chatbot/report-guide layer.

## Last Verified

2026-06-02
