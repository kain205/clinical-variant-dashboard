"""Convert selected consumer SNP rows into an auditable VCF subset.

Consumer SNP files usually provide rsID, chromosome, position, and genotype,
but not REF/ALT. This converter only emits VCF rows when rsID resolution
provides a build-specific REF/ALT allele that matches the observed genotype.
Skipped/ambiguous rows are written to the manifest instead of being guessed.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workbench.input_parser import ParsedVariant, parse_consumer_file


MYVARIANT_QUERY_URL = "https://myvariant.info/v1/query"
HGVS_SNV_RE = re.compile(r"^chr(?P<chrom>[^:]+):g\.(?P<pos>\d+)(?P<ref>[ACGT])>(?P<alt>[ACGT])$")
COMPLEMENT = str.maketrans("ACGT", "TGCA")


@dataclass(frozen=True)
class ResolvedAllele:
    chrom: str
    pos: int
    ref: str
    alt: str
    source_id: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class VcfConversionRow:
    rsid: str
    status: str
    reason: str
    chromosome: str
    position: str
    genotype: str
    vcf_chrom: str = ""
    vcf_pos: int | None = None
    vcf_ref: str = ""
    vcf_alt: str = ""
    vcf_gt: str = ""
    candidate_alleles: list[dict[str, object]] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_chromosome(value: str) -> str:
    clean = value.strip()
    return clean[3:] if clean.lower().startswith("chr") else clean


def normalize_genotype(value: str) -> str:
    return value.strip().upper().replace("/", "").replace("|", "")


def reverse_complement_genotype(value: str) -> str:
    return normalize_genotype(value).translate(COMPLEMENT)


def parse_myvariant_hgvs_id(value: str) -> ResolvedAllele | None:
    match = HGVS_SNV_RE.match(value)
    if not match:
        return None
    return ResolvedAllele(
        chrom=normalize_chromosome(match.group("chrom")),
        pos=int(match.group("pos")),
        ref=match.group("ref"),
        alt=match.group("alt"),
        source_id=value,
    )


def extract_resolved_alleles(payload: dict[str, Any]) -> list[ResolvedAllele]:
    alleles: list[ResolvedAllele] = []
    hits = payload if isinstance(payload, list) else payload.get("hits", [])
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        parsed = parse_myvariant_hgvs_id(str(hit.get("_id", "")))
        if parsed:
            alleles.append(parsed)
    return alleles


def fetch_myvariant_payload(rsid: str, timeout: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "q": rsid,
            "fields": "dbsnp.rsid",
            "size": "20",
        }
    )
    request = urllib.request.Request(
        f"{MYVARIANT_QUERY_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "clinical-variant-dashboard-snp-to-vcf/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_myvariant_batch_hits(rsids: list[str], timeout: int) -> list[dict[str, Any]]:
    data = urllib.parse.urlencode(
        {
            "q": ",".join(rsids),
            "scopes": "dbsnp.rsid",
            "fields": "dbsnp.rsid",
            "size": "20",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        MYVARIANT_QUERY_URL,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "clinical-variant-dashboard-snp-to-vcf/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return payload if isinstance(payload, list) else []


def iter_chunks(values: list[ParsedVariant], chunk_size: int) -> Iterable[list[ParsedVariant]]:
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def load_or_fetch_payload(
    rsid: str,
    payload_dir: Path,
    timeout: int,
    use_cache: bool = True,
) -> tuple[dict[str, Any], Path]:
    payload_path = payload_dir / f"{rsid}.json"
    if use_cache and payload_path.exists():
        return json.loads(payload_path.read_text(encoding="utf-8")), payload_path

    payload = fetch_myvariant_payload(rsid, timeout=timeout)
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload, payload_path


def group_matching_alleles(
    variant: ParsedVariant, alleles: Iterable[ResolvedAllele]
) -> dict[tuple[str, int, str], list[str]]:
    genotype = normalize_genotype(variant.genotype)
    input_chrom = normalize_chromosome(variant.chromosome)
    input_pos = int(variant.position) if str(variant.position).isdigit() else None
    groups: dict[tuple[str, int, str], list[str]] = {}

    for allele in alleles:
        if input_chrom and allele.chrom != input_chrom:
            continue
        if input_pos is not None and allele.pos != input_pos:
            continue
        allowed = {allele.ref, allele.alt}
        if all(base in allowed for base in genotype):
            groups.setdefault((allele.chrom, allele.pos, allele.ref), [])
            if allele.alt not in groups[(allele.chrom, allele.pos, allele.ref)]:
                groups[(allele.chrom, allele.pos, allele.ref)].append(allele.alt)

    return groups


def genotype_to_vcf_gt(genotype: str, ref: str, alts: list[str]) -> str | None:
    normalized = normalize_genotype(genotype)
    if len(normalized) not in (1, 2):
        return None
    allele_numbers: list[str] = []
    for base in normalized:
        if base == ref:
            allele_numbers.append("0")
            continue
        if base in alts:
            allele_numbers.append(str(alts.index(base) + 1))
            continue
        return None
    if len(allele_numbers) == 1:
        allele_numbers.append(allele_numbers[0])
    allele_numbers = sorted(allele_numbers, key=int)
    return "/".join(allele_numbers)


def convert_variant_to_vcf_row(
    variant: ParsedVariant, alleles: list[ResolvedAllele]
) -> VcfConversionRow:
    candidates = [allele.to_dict() for allele in alleles]
    if not variant.rsid:
        return VcfConversionRow(
            rsid="",
            status="skipped",
            reason="missing_rsid",
            chromosome=variant.chromosome,
            position=variant.position,
            genotype=variant.genotype,
            candidate_alleles=candidates,
        )
    if variant.is_no_call:
        return VcfConversionRow(
            rsid=variant.rsid,
            status="skipped",
            reason="no_call_genotype",
            chromosome=variant.chromosome,
            position=variant.position,
            genotype=variant.genotype,
            candidate_alleles=candidates,
        )
    if not alleles:
        return VcfConversionRow(
            rsid=variant.rsid,
            status="skipped",
            reason="no_resolved_ref_alt",
            chromosome=variant.chromosome,
            position=variant.position,
            genotype=variant.genotype,
            candidate_alleles=candidates,
        )

    groups = group_matching_alleles(variant, alleles)
    if len(groups) != 1:
        rc_groups = group_matching_alleles(
            ParsedVariant(
                source_label=variant.source_label,
                source_kind=variant.source_kind,
                row_index=variant.row_index,
                raw_line=variant.raw_line,
                rsid=variant.rsid,
                chromosome=variant.chromosome,
                position=variant.position,
                genotype=reverse_complement_genotype(variant.genotype),
                genome_build=variant.genome_build,
                is_no_call=variant.is_no_call,
                is_duplicate=variant.is_duplicate,
                skip_reason=variant.skip_reason,
            ),
            alleles,
        )
        reason = "ambiguous_or_no_genotype_ref_alt_match"
        if len(rc_groups) == 1:
            reason = "possible_reverse_complement_match_not_emitted"
        return VcfConversionRow(
            rsid=variant.rsid,
            status="skipped",
            reason=reason,
            chromosome=variant.chromosome,
            position=variant.position,
            genotype=variant.genotype,
            candidate_alleles=candidates,
        )

    (chrom, pos, ref), alts = next(iter(groups.items()))
    gt = genotype_to_vcf_gt(variant.genotype, ref, alts)
    if gt is None:
        return VcfConversionRow(
            rsid=variant.rsid,
            status="skipped",
            reason="gt_encoding_failed",
            chromosome=variant.chromosome,
            position=variant.position,
            genotype=variant.genotype,
            candidate_alleles=candidates,
        )

    return VcfConversionRow(
        rsid=variant.rsid,
        status="converted",
        reason="matched_forward_ref_alt",
        chromosome=variant.chromosome,
        position=variant.position,
        genotype=variant.genotype,
        vcf_chrom=chrom,
        vcf_pos=pos,
        vcf_ref=ref,
        vcf_alt=",".join(alts),
        vcf_gt=gt,
        candidate_alleles=candidates,
    )


def build_vcf_lines(rows: list[VcfConversionRow], genome_build: str) -> list[str]:
    lines = [
        "##fileformat=VCFv4.2",
        f"##source=clinical_variant_dashboard_snp_to_vcf",
        f"##genome_build={genome_build}",
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
    ]
    for row in rows:
        if row.status != "converted":
            continue
        lines.append(vcf_line_for_row(row))
    return lines


def build_vcf_header(genome_build: str) -> list[str]:
    return [
        "##fileformat=VCFv4.2",
        "##source=clinical_variant_dashboard_snp_to_vcf",
        f"##genome_build={genome_build}",
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
    ]


def vcf_line_for_row(row: VcfConversionRow) -> str:
    return "\t".join(
        [
            row.vcf_chrom,
            str(row.vcf_pos),
            row.rsid,
            row.vcf_ref,
            row.vcf_alt,
            ".",
            "PASS",
            f"ORIGINAL_GT={row.genotype}",
            "GT",
            row.vcf_gt,
        ]
    )


def selected_variants(
    variants: list[ParsedVariant], rsids: set[str] | None, max_rows: int
) -> list[ParsedVariant]:
    selected: list[ParsedVariant] = []
    seen: set[str] = set()
    for variant in variants:
        key = variant.rsid.lower()
        if not key or key in seen or variant.is_no_call or variant.is_duplicate:
            continue
        if rsids and key not in rsids:
            continue
        seen.add(key)
        selected.append(variant)
        if len(selected) >= max_rows:
            break
    return selected


def convert_consumer_file_to_vcf(
    input_path: Path,
    output_vcf: Path,
    manifest_path: Path,
    payload_dir: Path,
    rsids: set[str] | None,
    max_rows: int,
    genome_build: str,
    timeout: int,
    batch_size: int = 500,
    detail_row_limit: int = 10000,
) -> list[VcfConversionRow]:
    parsed = parse_consumer_file(input_path, genome_build=genome_build)
    selected = selected_variants(parsed.variants, rsids=rsids, max_rows=max_rows)
    rows: list[VcfConversionRow] = []

    output_vcf.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload_dir.mkdir(parents=True, exist_ok=True)
    batch_payload_dir = payload_dir / "batches"
    batch_payload_dir.mkdir(parents=True, exist_ok=True)
    rows_jsonl_path = manifest_path.with_suffix(".rows.jsonl")

    converted_count = 0
    skipped_count = 0
    reason_counts: collections.Counter[str] = collections.Counter()
    detailed_rows_enabled = len(selected) <= detail_row_limit

    with output_vcf.open("w", encoding="utf-8", newline="") as vcf_dst, rows_jsonl_path.open(
        "w", encoding="utf-8", newline=""
    ) as rows_dst:
        vcf_dst.write("\n".join(build_vcf_header(genome_build)) + "\n")

        for batch_index, batch in enumerate(iter_chunks(selected, max(1, batch_size)), start=1):
            batch_rsids = [variant.rsid for variant in batch]
            try:
                batch_hits = fetch_myvariant_batch_hits(batch_rsids, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - keep full-run audit resilient.
                batch_hits = []
                batch_error = str(exc)
            else:
                batch_error = ""

            batch_payload_path = batch_payload_dir / f"batch_{batch_index:06d}.json"
            batch_payload_path.write_text(
                json.dumps(
                    {
                        "batch_index": batch_index,
                        "rsids": batch_rsids,
                        "error": batch_error,
                        "hits": batch_hits,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                "utf-8",
            )
            grouped_hits: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
            for hit in batch_hits:
                query = str(hit.get("query", "")).lower()
                if query:
                    grouped_hits[query].append(hit)

            for variant in batch:
                alleles = extract_resolved_alleles(grouped_hits.get(variant.rsid.lower(), []))
                row = convert_variant_to_vcf_row(variant, alleles)
                if batch_error:
                    row.status = "skipped"
                    row.reason = f"resolver_batch_error: {batch_error}"
                row.reason = f"{row.reason}; resolver_payload={batch_payload_path}"

                if row.status == "converted":
                    converted_count += 1
                    vcf_dst.write(vcf_line_for_row(row) + "\n")
                else:
                    skipped_count += 1
                reason_counts[row.reason.split(";")[0]] += 1
                rows_dst.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
                if detailed_rows_enabled:
                    rows.append(row)

    manifest_path.write_text(
        json.dumps(
            {
                "input_path": str(input_path),
                "output_vcf": str(output_vcf),
                "rows_jsonl": str(rows_jsonl_path),
                "genome_build": genome_build,
                "selected_count": len(selected),
                "converted_count": converted_count,
                "skipped_count": skipped_count,
                "batch_size": batch_size,
                "batch_payload_dir": str(batch_payload_dir),
                "reason_counts": dict(reason_counts),
                "rows": [row.to_dict() for row in rows] if detailed_rows_enabled else [],
                "rows_note": (
                    "Detailed rows are in rows_jsonl because selected_count exceeds detail_row_limit."
                    if not detailed_rows_enabled
                    else "Detailed rows included in this manifest and mirrored in rows_jsonl."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert selected consumer SNP rows to auditable VCF candidates."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output_vcf", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--payload-dir", type=Path, required=True)
    parser.add_argument("--genome-build", default="GRCh37/hg19")
    parser.add_argument("--max-rows", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--detail-row-limit", type=int, default=10000)
    parser.add_argument(
        "--rsid",
        action="append",
        default=[],
        help="Restrict conversion to an rsID. Can be repeated.",
    )
    parser.add_argument("--timeout", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rsids = {rsid.lower() for rsid in args.rsid} if args.rsid else None
    rows = convert_consumer_file_to_vcf(
        input_path=args.input,
        output_vcf=args.output_vcf,
        manifest_path=args.manifest,
        payload_dir=args.payload_dir,
        rsids=rsids,
        max_rows=args.max_rows,
        genome_build=args.genome_build,
        timeout=args.timeout,
        batch_size=args.batch_size,
        detail_row_limit=args.detail_row_limit,
    )
    print(
        json.dumps(
            {
                "converted": sum(1 for row in rows if row.status == "converted"),
                "skipped": sum(1 for row in rows if row.status != "converted"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
