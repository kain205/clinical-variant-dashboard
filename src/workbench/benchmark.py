"""Benchmark subset and transformation trace helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from src.workbench.input_parser import ParsedVariant


CURATED_VARIANT_GROUPS: dict[str, tuple[str, ...]] = {
    "Clinical / PGx rich": (
        "rs6025",
        "rs4244285",
        "rs1799853",
        "rs1057910",
        "rs9923231",
    ),
    "Research / common controls": ("rs3093017", "rs12562034"),
    "Additional common / clinical controls": ("rs7412", "rs429358", "rs1801133"),
}

CURATED_GENE_HINTS = {
    "rs6025": "F5",
    "rs3093017": "CCR6",
    "rs4244285": "CYP2C19",
    "rs1799853": "CYP2C9",
    "rs1057910": "CYP2C9",
    "rs9923231": "VKORC1",
    "rs7412": "APOE",
    "rs429358": "APOE",
    "rs1801133": "MTHFR",
}

TOOL_NAMES = (
    "VEP REST / Variant Recoder",
    "ClinVar E-utilities",
    "MyVariant.info",
    "MyGene.info",
    "ClinPGx",
    "GWAS Catalog",
    "PubMed E-utilities",
    "Open Targets",
    "OpenCRAVAT",
    "SnpEff / SnpSift",
    "ANNOVAR / InterVar",
    "PharmCAT",
    "ClinGen Allele Registry",
    "gnomAD direct",
    "OMIM",
    "CADD / dbNSFP / REVEL / AlphaMissense",
)


@dataclass
class BenchmarkVariant:
    rsid: str
    source_type: str
    parsed_variant: ParsedVariant | None
    gene_hint: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["parsed_variant"] = (
            self.parsed_variant.to_dict() if self.parsed_variant else None
        )
        return data


@dataclass
class TransformationTrace:
    rsid: str
    source_type: str
    original_row: str
    parsed_variant: dict[str, object] | None
    tool_inputs: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def flatten_curated_groups(group_names: Iterable[str]) -> list[str]:
    rsids: list[str] = []
    for group_name in group_names:
        for rsid in CURATED_VARIANT_GROUPS.get(group_name, ()):
            if rsid not in rsids:
                rsids.append(rsid)
    return rsids


def build_benchmark_subset(
    variants: list[ParsedVariant],
    top_n: int,
    include_sample_present: bool,
    curated_group_names: Iterable[str],
) -> list[BenchmarkVariant]:
    subset: list[BenchmarkVariant] = []
    seen: set[str] = set()

    if include_sample_present:
        for row in variants:
            if not row.rsid or row.is_duplicate or row.is_no_call:
                continue
            key = row.rsid.lower()
            if key in seen:
                continue
            seen.add(key)
            subset.append(
                BenchmarkVariant(
                    rsid=row.rsid,
                    source_type="sample_present",
                    parsed_variant=row,
                    gene_hint=CURATED_GENE_HINTS.get(key, ""),
                )
            )
            if len(subset) >= top_n:
                break

    sample_by_rsid = {
        row.rsid.lower(): row
        for row in variants
        if row.rsid and not row.is_duplicate and not row.is_no_call
    }
    for rsid in flatten_curated_groups(curated_group_names):
        key = rsid.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed = sample_by_rsid.get(key)
        subset.append(
            BenchmarkVariant(
                rsid=rsid,
                source_type="sample_present_control" if parsed else "external_control",
                parsed_variant=parsed,
                gene_hint=CURATED_GENE_HINTS.get(key, ""),
            )
        )

    return subset


def tool_specific_inputs(
    variant: BenchmarkVariant, genome_build: str, tools: Iterable[str] = TOOL_NAMES
) -> dict[str, str]:
    row = variant.parsed_variant
    vep_input = (
        f"Variant Recoder ID lookup: {variant.rsid}; assembly={genome_build or 'unknown'}"
    )
    if row and row.chromosome and row.position and row.genotype:
        vep_input += (
            f"; original coordinate context chr{row.chromosome}:{row.position}; "
            f"genotype={row.genotype}"
        )

    opencravat_input = "requires converted TSV/VCF batch input"
    if row:
        opencravat_input = (
            "# rsid\tchromosome\tposition\tgenotype\n"
            f"{row.rsid}\t{row.chromosome}\t{row.position}\t{row.genotype}"
        )

    annovar_input = (
        f"hg19 avinput from curated allele map for {variant.rsid}; "
        "fallback requires rsID -> chr/start/end/ref/alt normalization"
    )
    gene_input = (
        f"symbol:{variant.gene_hint}"
        if variant.gene_hint
        else "skipped until VEP/MyVariant provides a gene symbol"
    )

    mapping = {
        "VEP REST / Variant Recoder": vep_input,
        "ClinVar E-utilities": f"db=clinvar; term={variant.rsid}; retmode=json",
        "MyVariant.info": f"q={variant.rsid}",
        "MyGene.info": gene_input,
        "ClinPGx": f"variant symbol={variant.rsid}; optional gene={variant.gene_hint or 'unknown'}",
        "GWAS Catalog": f"summary-statistics association lookup for {variant.rsid}",
        "PubMed E-utilities": f"db=pubmed; term={variant.rsid}",
        "Open Targets": gene_input,
        "OpenCRAVAT": opencravat_input,
        "SnpEff / SnpSift": "requires VCF with chr/pos/ref/alt and matching local genome database",
        "ANNOVAR / InterVar": annovar_input,
        "PharmCAT": "requires VCF or outside-calls TSV with PGx-relevant genotype calls",
        "ClinGen Allele Registry": f"requires validated Allele Registry lookup route for {variant.rsid}/HGVS/SPDI",
        "gnomAD direct": "requires build-specific chr-pos-ref-alt or gnomAD variant ID",
        "OMIM": f"requires OMIM API key; gene query={variant.gene_hint or 'unknown'}",
        "CADD / dbNSFP / REVEL / AlphaMissense": "requires precise chr-pos-ref-alt and local/license-governed score resources",
    }
    return {tool: mapping[tool] for tool in tools if tool in mapping}


def build_transformation_trace(
    variant: BenchmarkVariant, genome_build: str, tools: Iterable[str] = TOOL_NAMES
) -> TransformationTrace:
    parsed = variant.parsed_variant.to_dict() if variant.parsed_variant else None
    original_row = variant.parsed_variant.raw_line if variant.parsed_variant else variant.rsid
    return TransformationTrace(
        rsid=variant.rsid,
        source_type=variant.source_type,
        original_row=original_row,
        parsed_variant=parsed,
        tool_inputs=tool_specific_inputs(variant, genome_build, tools),
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", "utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
