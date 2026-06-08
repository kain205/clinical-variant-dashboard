"""Convert consumer SNP CSV/TSV files into OpenCRAVAT-friendly 23andMe TSV.

The OpenCRAVAT 23andMe converter expects tab-delimited rows:

    rsid    chromosome    position    genotype

Some public mock inputs, such as the Kaggle family files, use comma-separated
CSV with a comment-style header. This script normalizes those files before
annotation.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO


REQUIRED_COLUMNS = ("rsid", "chromosome", "position", "genotype")
COLUMN_ALIASES = {
    "rsid": "rsid",
    "rs_id": "rsid",
    "snp": "rsid",
    "chromosome": "chromosome",
    "chrom": "chromosome",
    "chr": "chromosome",
    "position": "position",
    "pos": "position",
    "genotype": "genotype",
    "geno": "genotype",
}


@dataclass
class ConversionStats:
    input_rows: int = 0
    output_rows: int = 0
    skipped_rows: int = 0
    skipped_missing_required: int = 0


def normalize_header_name(value: str) -> str:
    clean = value.strip().lstrip("\ufeff").lstrip("#").strip().lower().replace(" ", "_")
    return COLUMN_ALIASES.get(clean, clean)


def detect_delimiter(lines: Iterable[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        comma_count = stripped.count(",")
        tab_count = stripped.count("\t")
        return "\t" if tab_count > comma_count else ","
    return ","


def parse_row(line: str, delimiter: str) -> list[str]:
    return next(csv.reader([line], delimiter=delimiter))


def find_header(input_file: TextIO, delimiter: str) -> tuple[list[str], list[str]]:
    """Return normalized header and any data rows consumed while searching."""

    consumed_data_rows: list[str] = []
    for raw_line in input_file:
        line = raw_line.strip()
        if not line:
            continue

        cells = parse_row(line, delimiter)
        normalized = [normalize_header_name(cell) for cell in cells]
        has_required = all(col in normalized for col in REQUIRED_COLUMNS)

        if has_required:
            return normalized, consumed_data_rows

        if line.startswith("#"):
            continue

        consumed_data_rows.append(raw_line)

    raise ValueError(
        "Could not find a header containing rsid, chromosome, position, genotype"
    )


def convert_file(input_path: Path, output_path: Path) -> ConversionStats:
    sample = input_path.read_text(encoding="utf-8", errors="replace").splitlines()[:20]
    delimiter = detect_delimiter(sample)

    stats = ConversionStats()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        header, consumed_data_rows = find_header(src, delimiter)
        column_index = {name: idx for idx, name in enumerate(header)}

        def rows() -> Iterable[str]:
            yield from consumed_data_rows
            yield from src

        with output_path.open("w", encoding="ascii", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t", lineterminator="\n")
            writer.writerow(("# rsid", "chromosome", "position", "genotype"))

            for raw_line in rows():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                stats.input_rows += 1
                cells = parse_row(line, delimiter)

                try:
                    values = {
                        col: cells[column_index[col]].strip()
                        for col in REQUIRED_COLUMNS
                    }
                except IndexError:
                    stats.skipped_rows += 1
                    stats.skipped_missing_required += 1
                    continue

                if not all(values.values()):
                    stats.skipped_rows += 1
                    stats.skipped_missing_required += 1
                    continue

                writer.writerow(
                    (
                        values["rsid"],
                        values["chromosome"],
                        values["position"],
                        values["genotype"],
                    )
                )
                stats.output_rows += 1

    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize consumer SNP CSV/TSV into 23andMe-style TSV."
    )
    parser.add_argument("input", type=Path, help="Input consumer SNP CSV/TSV file")
    parser.add_argument("output", type=Path, help="Output normalized TSV path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    stats = convert_file(args.input, args.output)
    print(f"Input rows: {stats.input_rows}")
    print(f"Output rows: {stats.output_rows}")
    print(f"Skipped rows: {stats.skipped_rows}")
    if stats.skipped_missing_required:
        print(f"Skipped missing required fields: {stats.skipped_missing_required}")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
