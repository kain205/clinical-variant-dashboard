"""Observable parsing for consumer SNP files and manual rsID lists.

The workbench parser keeps raw lines, parser decisions, skipped rows, no-calls,
and duplicate state visible so downstream annotation results can be audited.
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = ("rsid", "chromosome", "position", "genotype")
COLUMN_ALIASES = {
    "rsid": "rsid",
    "rs_id": "rsid",
    "snp": "rsid",
    "snp_id": "rsid",
    "chromosome": "chromosome",
    "chrom": "chromosome",
    "chr": "chromosome",
    "position": "position",
    "pos": "position",
    "base_pair_location": "position",
    "genotype": "genotype",
    "geno": "genotype",
    "alleles": "genotype",
}
NO_CALL_VALUES = {"", "--", "nn", "n/a", "na", "null", "."}
RSID_RE = re.compile(r"\brs\d+\b", re.IGNORECASE)


@dataclass
class RawInspection:
    source_label: str
    delimiter: str
    delimiter_name: str
    header_line_number: int | None
    header_cells: list[str]
    normalized_header: list[str]
    detected_columns: dict[str, int]
    comment_lines: list[str]
    genome_build: str
    warnings: list[str]
    raw_preview_lines: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ParsedVariant:
    source_label: str
    source_kind: str
    row_index: int
    raw_line: str
    rsid: str
    chromosome: str
    position: str
    genotype: str
    genome_build: str
    is_no_call: bool
    is_duplicate: bool
    skip_reason: str

    @property
    def is_valid_for_sample(self) -> bool:
        return (
            bool(self.rsid)
            and not self.is_no_call
            and not self.is_duplicate
            and not self.skip_reason
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class PreprocessingSummary:
    source_label: str
    mode: str
    genome_build: str
    total_data_rows: int
    parsed_rows: int
    valid_genotype_rows: int
    no_call_rows: int
    missing_rsid_rows: int
    duplicate_rsid_rows: int
    skipped_rows: int
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ParsedInput:
    source_label: str
    mode: str
    genome_build: str
    raw_text: str
    inspection: RawInspection
    variants: list[ParsedVariant]
    skipped_rows: list[ParsedVariant]
    summary: PreprocessingSummary


def normalize_header_name(value: str) -> str:
    clean = value.strip().lstrip("\ufeff").lstrip("#").strip().lower()
    clean = re.sub(r"\s+", "_", clean)
    return COLUMN_ALIASES.get(clean, clean)


def detect_delimiter(lines: Iterable[str]) -> tuple[str, str]:
    whitespace_candidate = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        tab_count = line.count("\t")
        comma_count = line.count(",")
        if tab_count > comma_count and tab_count > 0:
            return "\t", "TSV"
        if comma_count > 0:
            return ",", "CSV"
        if not line.startswith("#") and len(line.split()) > 1:
            whitespace_candidate = True
    if whitespace_candidate:
        return "whitespace", "whitespace"
    return ",", "CSV"


def split_row(line: str, delimiter: str) -> list[str]:
    if delimiter == "whitespace":
        return line.split()
    return next(csv.reader([line], delimiter=delimiter))


def detect_genome_build(lines: Iterable[str], fallback: str = "unknown") -> str:
    joined = "\n".join(lines[:80] if isinstance(lines, list) else list(lines)[:80])
    lower = joined.lower()
    if any(token in lower for token in ("build 36", "build36", "hg18", "grch36")):
        return "build36/hg18"
    if any(token in lower for token in ("build 37", "build37", "hg19", "grch37")):
        return "GRCh37/hg19"
    if any(token in lower for token in ("build 38", "build38", "hg38", "grch38")):
        return "GRCh38/hg38"
    return fallback


def find_header(
    lines: list[str], delimiter: str
) -> tuple[int | None, list[str], list[str], dict[str, int], list[str]]:
    comments: list[str] = []
    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line)

        cells = split_row(line, delimiter)
        normalized = [normalize_header_name(cell) for cell in cells]
        if all(col in normalized for col in REQUIRED_COLUMNS):
            detected = {col: normalized.index(col) for col in REQUIRED_COLUMNS}
            return index, cells, normalized, detected, comments

        if len(comments) >= 50 and not line.startswith("#"):
            # Keep the UI readable for very large 23andMe-style headers.
            comments = comments[:50]

    return None, [], [], {}, comments[:50]


def parse_consumer_text(
    text: str,
    source_label: str,
    genome_build: str | None = None,
    max_rows: int | None = None,
) -> ParsedInput:
    lines = text.splitlines()
    delimiter, delimiter_name = detect_delimiter(lines[:50])
    header_index, header_cells, normalized_header, detected_columns, comments = find_header(
        lines, delimiter
    )
    detected_build = genome_build or detect_genome_build(lines, fallback="unknown")
    warnings: list[str] = []

    if detected_build == "build36/hg18":
        warnings.append(
            "Input appears to use build36/hg18; prefer rsID-based lookup unless liftover is validated."
        )
    if header_index is None:
        warnings.append(
            "Could not find rsid/chromosome/position/genotype header; no consumer rows parsed."
        )

    variants: list[ParsedVariant] = []
    skipped_rows: list[ParsedVariant] = []
    seen_rsids: set[str] = set()
    total_data_rows = 0
    no_call_rows = 0
    missing_rsid_rows = 0
    duplicate_rsid_rows = 0

    if header_index is not None:
        rows = enumerate(lines[header_index:], start=header_index + 1)
        for line_number, raw_line in rows:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if max_rows is not None and total_data_rows >= max_rows:
                warnings.append(f"Parsing stopped at max_rows={max_rows}.")
                break

            total_data_rows += 1
            cells = split_row(line, delimiter)
            skip_reason = ""
            try:
                rsid = cells[detected_columns["rsid"]].strip()
                chromosome = cells[detected_columns["chromosome"]].strip()
                position = cells[detected_columns["position"]].strip()
                genotype = cells[detected_columns["genotype"]].strip()
            except IndexError:
                rsid = ""
                chromosome = ""
                position = ""
                genotype = ""
                skip_reason = "missing_required_column"

            is_no_call = genotype.strip().lower() in NO_CALL_VALUES
            is_duplicate = bool(rsid and rsid in seen_rsids)
            if not rsid:
                missing_rsid_rows += 1
                skip_reason = skip_reason or "missing_rsid"
            if is_no_call:
                no_call_rows += 1
            if is_duplicate:
                duplicate_rsid_rows += 1
            if rsid and not is_duplicate:
                seen_rsids.add(rsid)

            parsed = ParsedVariant(
                source_label=source_label,
                source_kind="sample",
                row_index=line_number,
                raw_line=raw_line,
                rsid=rsid,
                chromosome=chromosome,
                position=position,
                genotype=genotype,
                genome_build=detected_build,
                is_no_call=is_no_call,
                is_duplicate=is_duplicate,
                skip_reason=skip_reason,
            )
            variants.append(parsed)
            if skip_reason:
                skipped_rows.append(parsed)

    inspection = RawInspection(
        source_label=source_label,
        delimiter=delimiter,
        delimiter_name=delimiter_name,
        header_line_number=header_index,
        header_cells=header_cells,
        normalized_header=normalized_header,
        detected_columns=detected_columns,
        comment_lines=comments[:50],
        genome_build=detected_build,
        warnings=warnings,
        raw_preview_lines=lines[:300],
    )
    summary = PreprocessingSummary(
        source_label=source_label,
        mode="consumer_file",
        genome_build=detected_build,
        total_data_rows=total_data_rows,
        parsed_rows=len(variants),
        valid_genotype_rows=sum(1 for row in variants if row.is_valid_for_sample),
        no_call_rows=no_call_rows,
        missing_rsid_rows=missing_rsid_rows,
        duplicate_rsid_rows=duplicate_rsid_rows,
        skipped_rows=len(skipped_rows),
        warnings=warnings,
    )
    return ParsedInput(
        source_label=source_label,
        mode="consumer_file",
        genome_build=detected_build,
        raw_text=text,
        inspection=inspection,
        variants=variants,
        skipped_rows=skipped_rows,
        summary=summary,
    )


def parse_manual_rsids(text: str, source_label: str = "manual_rsids") -> ParsedInput:
    rsids = []
    seen: set[str] = set()
    for match in RSID_RE.findall(text):
        normalized = match.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        rsids.append(normalized)

    warnings = [
        "Manual rsID mode has no genotype, coordinate, row-index, or sample-specific context."
    ]
    variants = [
        ParsedVariant(
            source_label=source_label,
            source_kind="manual",
            row_index=index,
            raw_line=rsid,
            rsid=rsid,
            chromosome="",
            position="",
            genotype="",
            genome_build="unknown",
            is_no_call=True,
            is_duplicate=False,
            skip_reason="manual_no_genotype_context",
        )
        for index, rsid in enumerate(rsids, start=1)
    ]
    inspection = RawInspection(
        source_label=source_label,
        delimiter="manual",
        delimiter_name="manual rsID list",
        header_line_number=None,
        header_cells=[],
        normalized_header=[],
        detected_columns={"rsid": 0},
        comment_lines=[],
        genome_build="unknown",
        warnings=warnings,
        raw_preview_lines=text.splitlines()[:300],
    )
    summary = PreprocessingSummary(
        source_label=source_label,
        mode="manual_rsid_list",
        genome_build="unknown",
        total_data_rows=len(rsids),
        parsed_rows=len(rsids),
        valid_genotype_rows=0,
        no_call_rows=len(rsids),
        missing_rsid_rows=0,
        duplicate_rsid_rows=0,
        skipped_rows=0,
        warnings=warnings,
    )
    return ParsedInput(
        source_label=source_label,
        mode="manual_rsid_list",
        genome_build="unknown",
        raw_text=text,
        inspection=inspection,
        variants=variants,
        skipped_rows=[],
        summary=summary,
    )


def parse_consumer_file(path: Path, genome_build: str | None = None) -> ParsedInput:
    return parse_consumer_text(
        path.read_text(encoding="utf-8", errors="replace"),
        source_label=str(path),
        genome_build=genome_build,
    )
