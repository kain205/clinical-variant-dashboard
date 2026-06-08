"""Prepare an official-docs-aligned ANNOVAR/InterVar rsID route.

This module does not run ANNOVAR or InterVar. It prepares auditable inputs for
the documented route:

consumer SNP -> rsID list -> convert2annovar -format rsid -> avinput
-> table_annovar.pl -> multianno.txt -> optional InterVar -> join-back.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workbench.input_parser import ParsedVariant, parse_consumer_file

DEFAULT_BENCHMARK_RSIDS: tuple[str, ...] = (
    "rs6025",
    "rs4244285",
    "rs7412",
    "rs1801133",
    "rs3093017",
    "rs12562034",
)

INTERVAR_CLASS_RE = re.compile(
    r"InterVar:\s*(Pathogenic|Likely pathogenic|Uncertain significance|"
    r"Likely benign|Benign)",
    re.IGNORECASE,
)


@dataclass
class OriginalVariantRecord:
    row_index: int
    rsid: str
    original_chromosome: str
    original_position: str
    original_genotype: str
    genome_build: str
    source_kind: str
    selection_kind: str


@dataclass
class AvinputRecord:
    chrom: str
    start: str
    end: str
    ref: str
    alt: str
    rsid: str
    raw_fields: list[str]


@dataclass
class JoinBackRecord:
    row_index: str
    rsid: str
    original_chromosome: str
    original_position: str
    original_genotype: str
    genome_build: str
    avinput_chr: str
    avinput_start: str
    avinput_end: str
    avinput_ref: str
    avinput_alt: str
    mapping_status: str
    mapping_warning: str
    annovar_multianno_path: str
    intervar_path: str
    genotype_match_status: str


@dataclass
class InterVarParsedRecord:
    chrom: str
    start: str
    end: str
    ref: str
    alt: str
    intervar_classification: str
    acmg_evidence_raw: str
    clinical_interpretation: str


@dataclass
class RsidRouteManifest:
    input_path: str
    output_dir: str
    genome_build: str
    total_rows: int
    valid_rows: int
    missing_or_no_call_rows: int
    duplicate_rsid_rows: int
    selected_count: int
    sample_present_count: int
    external_benchmark_count: int
    mapped_in_selected_dbsnp_count: int
    unresolved_in_selected_dbsnp_count: int
    multi_mapping_rsid_count: int
    original_variants_path: str
    rsid_list_path: str
    compatibility_rsid_list_path: str
    sample_present_path: str
    external_benchmark_path: str
    dbsnp_subset_path: str
    converted_avinput_path: str
    conversion_manifest_path: str
    join_back_path: str
    annovar_multianno_path: str
    intervar_output_path: str
    commands_path: str
    notes: list[str]


def normalize_rsid(value: str) -> str:
    return value.strip()


def normalize_genotype(value: str) -> str:
    return value.strip().upper().replace("/", "").replace("|", "")


def is_no_call_or_missing(variant: ParsedVariant) -> bool:
    return bool(variant.skip_reason or variant.is_no_call or not variant.rsid)


def variant_to_original_record(
    variant: ParsedVariant, selection_kind: str
) -> OriginalVariantRecord:
    return OriginalVariantRecord(
        row_index=variant.row_index,
        rsid=variant.rsid,
        original_chromosome=variant.chromosome,
        original_position=variant.position,
        original_genotype=variant.genotype,
        genome_build=variant.genome_build,
        source_kind=variant.source_kind,
        selection_kind=selection_kind,
    )


def select_route_records(
    variants: Sequence[ParsedVariant],
    max_sample_rsids: int,
    benchmark_rsids: Sequence[str],
) -> tuple[list[OriginalVariantRecord], list[str], list[str]]:
    valid = [variant for variant in variants if variant.is_valid_for_sample]
    by_rsid = {variant.rsid.lower(): variant for variant in valid}

    selected_records: list[OriginalVariantRecord] = []
    selected_seen: set[str] = set()
    sample_present_count = 0

    for rsid in benchmark_rsids:
        normalized = normalize_rsid(rsid)
        variant = by_rsid.get(normalized.lower())
        if variant:
            selected_records.append(variant_to_original_record(variant, "benchmark_present"))
            selected_seen.add(normalized.lower())

    for variant in valid:
        if sample_present_count >= max_sample_rsids:
            break
        if variant.rsid.lower() in selected_seen:
            continue
        selected_records.append(variant_to_original_record(variant, "sample_present"))
        selected_seen.add(variant.rsid.lower())
        sample_present_count += 1

    benchmark_present = sorted(
        {
            row.rsid
            for row in selected_records
            if row.selection_kind == "benchmark_present"
        }
    )
    external_benchmark = [
        normalize_rsid(rsid)
        for rsid in benchmark_rsids
        if normalize_rsid(rsid).lower() not in selected_seen
    ]
    return selected_records, benchmark_present, external_benchmark


def write_tsv(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_lines(path: Path, values: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def write_original_variants(path: Path, records: Sequence[OriginalVariantRecord]) -> None:
    write_tsv(
        path,
        (
            "row_index",
            "rsid",
            "original_chromosome",
            "original_position",
            "original_genotype",
            "genome_build",
            "source_kind",
            "selection_kind",
        ),
        (
            (
                row.row_index,
                row.rsid,
                row.original_chromosome,
                row.original_position,
                row.original_genotype,
                row.genome_build,
                row.source_kind,
                row.selection_kind,
            )
            for row in records
        ),
    )


def read_original_variants(path: Path) -> list[OriginalVariantRecord]:
    with path.open("r", encoding="utf-8", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        return [
            OriginalVariantRecord(
                row_index=int(row["row_index"]),
                rsid=row["rsid"],
                original_chromosome=row["original_chromosome"],
                original_position=row["original_position"],
                original_genotype=row["original_genotype"],
                genome_build=row["genome_build"],
                source_kind=row["source_kind"],
                selection_kind=row["selection_kind"],
            )
            for row in reader
        ]


def extract_dbsnp_subset(
    dbsnp_path: Path, rsids: Sequence[str], output_path: Path
) -> dict[str, int]:
    wanted = {rsid.lower() for rsid in rsids}
    counts: Counter[str] = Counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with dbsnp_path.open("r", encoding="utf-8", errors="replace") as src, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        for line in src:
            fields = line.rstrip("\n").split("\t")
            matched = sorted({field.lower() for field in fields if field.lower() in wanted})
            if not matched:
                continue
            dst.write(line)
            for rsid in matched:
                counts[rsid] += 1
    return {rsid: counts.get(rsid.lower(), 0) for rsid in rsids}


def count_dbsnp_subset(subset_path: Path, rsids: Sequence[str]) -> dict[str, int]:
    wanted = {rsid.lower() for rsid in rsids}
    counts: Counter[str] = Counter()
    if not subset_path.exists():
        return {rsid: 0 for rsid in rsids}
    with subset_path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            fields = line.rstrip("\n").split("\t")
            for field in fields:
                lowered = field.lower()
                if lowered in wanted:
                    counts[lowered] += 1
    return {rsid: counts.get(rsid.lower(), 0) for rsid in rsids}


def parse_avinput(path: Path) -> list[AvinputRecord]:
    records: list[AvinputRecord] = []
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for raw_line in src:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 5:
                continue
            rsid = fields[5] if len(fields) > 5 and fields[5].startswith("rs") else ""
            records.append(
                AvinputRecord(
                    chrom=fields[0],
                    start=fields[1],
                    end=fields[2],
                    ref=fields[3],
                    alt=fields[4],
                    rsid=rsid,
                    raw_fields=fields,
                )
            )
    return records


def genotype_match_status(genotype: str, ref: str, alt: str) -> str:
    normalized = normalize_genotype(genotype)
    if not normalized:
        return "no_sample_genotype"
    if any(base not in "ACGT" for base in normalized):
        return "unsupported_genotype"
    observed = set(normalized)
    expected = {ref.upper(), alt.upper()}
    if not observed.issubset(expected):
        return "genotype_ref_alt_mismatch"
    if alt.upper() in observed:
        return "sample_carries_alt"
    return "sample_homozygous_reference"


def join_avinput_to_originals(
    avinput_records: Sequence[AvinputRecord],
    original_records: Sequence[OriginalVariantRecord],
    annovar_multianno_path: Path | None = None,
    intervar_path: Path | None = None,
) -> list[JoinBackRecord]:
    originals_by_rsid: dict[str, OriginalVariantRecord] = {
        row.rsid.lower(): row for row in original_records
    }
    avinput_counts = Counter(record.rsid.lower() for record in avinput_records if record.rsid)
    joined: list[JoinBackRecord] = []

    for record in avinput_records:
        original = originals_by_rsid.get(record.rsid.lower())
        if original is None:
            joined.append(
                JoinBackRecord(
                    row_index="",
                    rsid=record.rsid,
                    original_chromosome="",
                    original_position="",
                    original_genotype="",
                    genome_build="",
                    avinput_chr=record.chrom,
                    avinput_start=record.start,
                    avinput_end=record.end,
                    avinput_ref=record.ref,
                    avinput_alt=record.alt,
                    mapping_status="no_sample_context",
                    mapping_warning="rsID was external benchmark or not found in original variants",
                    annovar_multianno_path=str(annovar_multianno_path or ""),
                    intervar_path=str(intervar_path or ""),
                    genotype_match_status="no_sample_genotype",
                )
            )
            continue

        is_multi = avinput_counts[record.rsid.lower()] > 1
        joined.append(
            JoinBackRecord(
                row_index=str(original.row_index),
                rsid=record.rsid,
                original_chromosome=original.original_chromosome,
                original_position=original.original_position,
                original_genotype=original.original_genotype,
                genome_build=original.genome_build,
                avinput_chr=record.chrom,
                avinput_start=record.start,
                avinput_end=record.end,
                avinput_ref=record.ref,
                avinput_alt=record.alt,
                mapping_status="multi_mapping" if is_multi else "mapped",
                mapping_warning="multiple avinput records for rsID" if is_multi else "",
                annovar_multianno_path=str(annovar_multianno_path or ""),
                intervar_path=str(intervar_path or ""),
                genotype_match_status=genotype_match_status(
                    original.original_genotype, record.ref, record.alt
                ),
            )
        )
    return joined


def write_join_back(path: Path, rows: Sequence[JoinBackRecord]) -> None:
    write_tsv(
        path,
        (
            "row_index",
            "rsid",
            "original_chromosome",
            "original_position",
            "original_genotype",
            "genome_build",
            "avinput_chr",
            "avinput_start",
            "avinput_end",
            "avinput_ref",
            "avinput_alt",
            "mapping_status",
            "mapping_warning",
            "annovar_multianno_path",
            "intervar_path",
            "genotype_match_status",
        ),
        (asdict(row).values() for row in rows),
    )


def parse_intervar_classification(value: str) -> tuple[str, str]:
    match = INTERVAR_CLASS_RE.search(value)
    classification = match.group(1) if match else "Unknown"
    return classification, value.strip()


def parse_intervar_output(path: Path) -> list[InterVarParsedRecord]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        if not reader.fieldnames:
            return []
        intervar_column = next(
            (name for name in reader.fieldnames if "InterVar" in name),
            "",
        )
        records: list[InterVarParsedRecord] = []
        for row in reader:
            raw_evidence = row.get(intervar_column, "") if intervar_column else ""
            classification, evidence = parse_intervar_classification(raw_evidence)
            records.append(
                InterVarParsedRecord(
                    chrom=row.get("#Chr", row.get("Chr", "")),
                    start=row.get("Start", ""),
                    end=row.get("End", ""),
                    ref=row.get("Ref", ""),
                    alt=row.get("Alt", ""),
                    intervar_classification=classification,
                    acmg_evidence_raw=evidence,
                    clinical_interpretation="evidence_only_not_diagnosis",
                )
            )
    return records


def write_commands(
    path: Path,
    rsid_list_path: Path,
    dbsnp_path: Path,
    dbsnp_subset_path: Path,
    converted_avinput_path: Path,
    annovar_out_prefix: Path,
    intervar_out_prefix: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                "# Official-docs-aligned ANNOVAR + InterVar rsID route",
                "",
                "# Optional speed-up: use hg19_snp138.selected.txt generated by this script.",
                "perl tools/annovar/convert2annovar.pl \\",
                f"  -format rsid {rsid_list_path.as_posix()} \\",
                f"  -dbsnpfile {dbsnp_subset_path.as_posix() if dbsnp_subset_path.exists() else dbsnp_path.as_posix()} \\",
                f"  > {converted_avinput_path.as_posix()}",
                "",
                "perl tools/annovar/table_annovar.pl \\",
                f"  {converted_avinput_path.as_posix()} \\",
                "  tools/annovar/humandb \\",
                "  -buildver hg19 \\",
                f"  -out {annovar_out_prefix.as_posix()} \\",
                "  -protocol refGene,clinvar_20240917 \\",
                "  -operation g,f \\",
                "  -nastring . \\",
                "  -polish \\",
                "  -otherinfo",
                "",
                "cd tools/InterVar",
                "python3 Intervar.py \\",
                "  -b hg19 \\",
                f"  -i ../../{converted_avinput_path.as_posix()} \\",
                "  --input_type=AVinput \\",
                f"  -o ../../{intervar_out_prefix.as_posix()} \\",
                "  --skip_annovar",
                "",
            )
        ),
        encoding="utf-8",
    )


def build_route_inputs(
    input_path: Path,
    output_dir: Path,
    genome_build: str,
    max_sample_rsids: int,
    benchmark_rsids: Sequence[str],
    dbsnp_file: Path,
    extract_subset: bool,
    converted_avinput: Path | None = None,
) -> RsidRouteManifest:
    parsed = parse_consumer_file(input_path, genome_build=genome_build)
    selected_records, benchmark_present, external_benchmark = select_route_records(
        parsed.variants,
        max_sample_rsids=max_sample_rsids,
        benchmark_rsids=benchmark_rsids,
    )
    rsids = [row.rsid for row in selected_records] + external_benchmark

    output_dir.mkdir(parents=True, exist_ok=True)
    original_variants_path = output_dir / "original_variants.tsv"
    rsid_list_path = output_dir / "rsids.txt"
    compatibility_rsid_list_path = output_dir / "annovar_intervar_test_rsids.txt"
    sample_present_path = output_dir / "sample_present_rsids.tsv"
    external_benchmark_path = output_dir / "external_benchmark_rsids.txt"
    dbsnp_subset_path = output_dir / "hg19_snp138.selected.txt"
    converted_avinput_path = converted_avinput or (output_dir / "converted.avinput")
    conversion_manifest_path = output_dir / "conversion_manifest.json"
    join_back_path = output_dir / "join_back.tsv"
    annovar_out_prefix = output_dir / "annovar_child1"
    annovar_multianno_path = output_dir / "annovar_child1.hg19_multianno.txt"
    intervar_out_prefix = output_dir / "intervar_child1"
    intervar_output_path = output_dir / "intervar_child1.hg19_multianno.txt.intervar"
    commands_path = output_dir / "commands.sh"

    write_original_variants(original_variants_path, selected_records)
    write_lines(rsid_list_path, rsids)
    write_lines(compatibility_rsid_list_path, rsids)
    write_original_variants(sample_present_path, selected_records)
    write_lines(external_benchmark_path, external_benchmark)

    dbsnp_counts = {rsid: 0 for rsid in rsids}
    if extract_subset and dbsnp_file.exists():
        dbsnp_counts = extract_dbsnp_subset(dbsnp_file, rsids, dbsnp_subset_path)
    elif dbsnp_subset_path.exists():
        dbsnp_counts = count_dbsnp_subset(dbsnp_subset_path, rsids)

    join_back_rows: list[JoinBackRecord] = []
    if converted_avinput_path.exists():
        join_back_rows = join_avinput_to_originals(
            parse_avinput(converted_avinput_path),
            selected_records,
            annovar_multianno_path=annovar_multianno_path,
            intervar_path=intervar_output_path,
        )
        write_join_back(join_back_path, join_back_rows)
    else:
        write_tsv(
            join_back_path,
            (
                "row_index",
                "rsid",
                "original_chromosome",
                "original_position",
                "original_genotype",
                "genome_build",
                "avinput_chr",
                "avinput_start",
                "avinput_end",
                "avinput_ref",
                "avinput_alt",
                "mapping_status",
                "mapping_warning",
                "annovar_multianno_path",
                "intervar_path",
                "genotype_match_status",
            ),
            (),
        )

    write_commands(
        commands_path,
        rsid_list_path=rsid_list_path,
        dbsnp_path=dbsnp_file,
        dbsnp_subset_path=dbsnp_subset_path,
        converted_avinput_path=converted_avinput_path,
        annovar_out_prefix=annovar_out_prefix,
        intervar_out_prefix=intervar_out_prefix,
    )

    mapped_count = sum(1 for count in dbsnp_counts.values() if count > 0)
    multi_mapping_count = sum(1 for count in dbsnp_counts.values() if count > 1)
    manifest = RsidRouteManifest(
        input_path=str(input_path),
        output_dir=str(output_dir),
        genome_build=genome_build,
        total_rows=parsed.summary.total_data_rows,
        valid_rows=parsed.summary.valid_genotype_rows,
        missing_or_no_call_rows=parsed.summary.no_call_rows
        + parsed.summary.missing_rsid_rows,
        duplicate_rsid_rows=parsed.summary.duplicate_rsid_rows,
        selected_count=len(rsids),
        sample_present_count=len(selected_records),
        external_benchmark_count=len(external_benchmark),
        mapped_in_selected_dbsnp_count=mapped_count,
        unresolved_in_selected_dbsnp_count=len(rsids) - mapped_count,
        multi_mapping_rsid_count=multi_mapping_count,
        original_variants_path=str(original_variants_path),
        rsid_list_path=str(rsid_list_path),
        compatibility_rsid_list_path=str(compatibility_rsid_list_path),
        sample_present_path=str(sample_present_path),
        external_benchmark_path=str(external_benchmark_path),
        dbsnp_subset_path=str(dbsnp_subset_path),
        converted_avinput_path=str(converted_avinput_path),
        conversion_manifest_path=str(conversion_manifest_path),
        join_back_path=str(join_back_path),
        annovar_multianno_path=str(annovar_multianno_path),
        intervar_output_path=str(intervar_output_path),
        commands_path=str(commands_path),
        notes=[
            "ANNOVAR/InterVar is an offline benchmark/classification experiment, not MVP runtime.",
            "Run convert2annovar before table_annovar; run InterVar only after multianno is stable.",
            "rsID -> avinput does not preserve sample genotype automatically; use join_back.tsv.",
            f"Benchmark rsIDs present in sample: {', '.join(benchmark_present) or 'none'}.",
        ],
    )
    conversion_manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare official-docs-aligned ANNOVAR/InterVar rsID-route inputs."
    )
    parser.add_argument("input", type=Path, help="Input consumer SNP CSV/TSV file")
    parser.add_argument("output_dir", type=Path, help="Directory for route outputs")
    parser.add_argument("--genome-build", default="GRCh37/hg19")
    parser.add_argument("--max-sample-rsids", type=int, default=40)
    parser.add_argument(
        "--benchmark-rsid",
        action="append",
        dest="benchmark_rsids",
        help="Additional benchmark rsID. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dbsnp-file",
        type=Path,
        default=Path("tools/annovar/humandb/hg19_snp138.txt"),
        help="Local ANNOVAR dbSNP file used by convert2annovar -format rsid.",
    )
    parser.add_argument(
        "--extract-dbsnp-subset",
        action="store_true",
        help="Pre-extract exact rsID matches from dbSNP to avoid repeated full scans.",
    )
    parser.add_argument(
        "--converted-avinput",
        type=Path,
        help="Existing converted.avinput to join back to original genotype context.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    benchmark_rsids = DEFAULT_BENCHMARK_RSIDS
    if args.benchmark_rsids:
        benchmark_rsids = benchmark_rsids + tuple(args.benchmark_rsids)

    manifest = build_route_inputs(
        input_path=args.input,
        output_dir=args.output_dir,
        genome_build=args.genome_build,
        max_sample_rsids=args.max_sample_rsids,
        benchmark_rsids=benchmark_rsids,
        dbsnp_file=args.dbsnp_file,
        extract_subset=args.extract_dbsnp_subset,
        converted_avinput=args.converted_avinput,
    )
    print(json.dumps(asdict(manifest), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
