"""Full SNP-to-InterVar pipeline runner and InterVar result normalizer."""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import shutil
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from src.preprocessing.build_annovar_intervar_testset import (
    DEFAULT_BENCHMARK_RSIDS,
    build_route_inputs,
    parse_intervar_classification,
)
from src.workbench.input_parser import ParsedInput


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FULL_INTERVAR_OUTPUT_ROOT = REPO_ROOT / "data/processed/workbench/full_intervar_runs"
DEFAULT_ANNOVAR_DIR = REPO_ROOT / "tools/annovar"
DEFAULT_INTERVAR_DIR = REPO_ROOT / "tools/InterVar"

ANNOVAR_PREFIX = "annovar_child1"
INTERVAR_PREFIX = "intervar_child1"
REVIEW_CLASSIFICATIONS = {"Pathogenic", "Likely pathogenic", "Uncertain significance"}
HITL_REVIEW_CLASSIFICATIONS = {"Pathogenic", "Likely pathogenic"}
PRIMARY_CHROMS = {str(chrom) for chrom in range(1, 23)} | {"X", "Y", "M", "MT"}
CLASSIFICATION_ORDER = [
    "Pathogenic",
    "Likely pathogenic",
    "Uncertain significance",
    "Likely benign",
    "Benign",
    "Unknown",
]

REVIEW_QUEUE_COLUMNS = [
    "rsid",
    "gene",
    "classification",
    "clinvar_signal",
    "chrom",
    "start",
    "ref",
    "alt",
    "func_refgene",
    "exonic_func_refgene",
    "original_genotype",
    "genotype_match_status",
    "mapping_status",
    "mapping_warning",
    "row_index",
    "review_required",
    "raw_intervar_path",
    "raw_join_back_path",
]


class FullIntervarPipelineError(RuntimeError):
    """Raised when the local SNP-to-InterVar pipeline cannot complete."""


@dataclass(frozen=True)
class PipelineCommand:
    name: str
    command: list[str]
    bash_command: str
    log_path: Path


@dataclass(frozen=True)
class FullIntervarRun:
    run_id: str
    run_dir: Path
    input_path: Path
    manifest_path: Path
    converted_avinput_path: Path
    annovar_multianno_path: Path
    intervar_multianno_path: Path
    intervar_output_path: Path
    join_back_path: Path
    line_counts_path: Path
    commands: list[PipelineCommand]


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def new_full_intervar_run_id(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("run_%Y%m%d_%H%M%S")


def get_full_intervar_paths(
    run_dir: Path,
    annovar_dir: Path = DEFAULT_ANNOVAR_DIR,
    intervar_dir: Path = DEFAULT_INTERVAR_DIR,
) -> dict[str, Path]:
    humandb = annovar_dir / "humandb"
    return {
        "run_dir": run_dir,
        "annovar_dir": annovar_dir,
        "intervar_dir": intervar_dir,
        "humandb": humandb,
        "dbsnp_file": humandb / "hg19_snp138.txt",
        "dbsnp_subset": run_dir / "hg19_snp138.selected.txt",
        "rsids": run_dir / "rsids.txt",
        "converted_avinput": run_dir / "converted.avinput",
        "annovar_out_prefix": run_dir / ANNOVAR_PREFIX,
        "annovar_multianno": run_dir / f"{ANNOVAR_PREFIX}.hg19_multianno.txt",
        "intervar_out_prefix": run_dir / INTERVAR_PREFIX,
        "intervar_multianno": run_dir / f"{INTERVAR_PREFIX}.hg19_multianno.txt",
        "intervar_output": run_dir / f"{INTERVAR_PREFIX}.hg19_multianno.txt.intervar",
        "join_back": run_dir / "join_back.tsv",
        "manifest": run_dir / "conversion_manifest.json",
        "prepare_log": run_dir / "prepare_inputs.log",
        "final_manifest_log": run_dir / "regenerate_join_back_manifest.log",
        "convert_log": run_dir / "convert_rsid_to_avinput.time.log",
        "table_log": run_dir / "table_annovar.time.log",
        "intervar_log": run_dir / "intervar_skip_annovar.log",
        "avinput_filter_log": run_dir / "avinput_primary_contig_filter.json",
        "avinput_filter_skipped": run_dir / "converted.non_primary_contigs.avinput",
        "pipeline_warnings": run_dir / "pipeline_warnings.json",
        "line_counts": run_dir / "full_pipeline_line_counts.txt",
    }


def write_current_input_for_full_run(parsed: ParsedInput, run_dir: Path) -> Path:
    """Return a file path for the current Streamlit input.

    Built-in sample mode can reuse the original path. Uploaded files only exist in
    Streamlit memory, so this persists the raw upload inside the run folder before
    the local CLI pipeline starts.
    """

    if parsed.mode != "consumer_file":
        raise FullIntervarPipelineError(
            "Full SNP-to-InterVar requires a consumer SNP file with genotype context."
        )

    source_path = Path(parsed.source_label)
    if source_path.exists():
        return source_path

    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", parsed.source_label).strip("_")
    output_path = input_dir / (safe_name or "uploaded_consumer_snp.txt")
    output_path.write_text(parsed.raw_text, encoding="utf-8", newline="")
    return output_path


def _path_for_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def _shell_path(path: Path, use_wsl: bool) -> str:
    return _path_for_wsl(path) if use_wsl else str(path)


def _quote_path(path: Path, use_wsl: bool) -> str:
    return shlex.quote(_shell_path(path, use_wsl))


def _bash_invocation(bash_command: str, use_wsl: bool) -> list[str]:
    if use_wsl:
        return ["wsl", "-e", "bash", "-lc", bash_command]
    return ["bash", "-lc", bash_command]


def _use_wsl_by_default() -> bool:
    return os.name == "nt"


def build_full_intervar_commands(
    run_dir: Path,
    *,
    annovar_dir: Path = DEFAULT_ANNOVAR_DIR,
    intervar_dir: Path = DEFAULT_INTERVAR_DIR,
    use_wsl: bool | None = None,
) -> list[PipelineCommand]:
    use_wsl = _use_wsl_by_default() if use_wsl is None else use_wsl
    paths = get_full_intervar_paths(run_dir, annovar_dir, intervar_dir)

    repo = _quote_path(REPO_ROOT, use_wsl)
    convert_script = _quote_path(annovar_dir / "convert2annovar.pl", use_wsl)
    table_script = _quote_path(annovar_dir / "table_annovar.pl", use_wsl)
    humandb = _quote_path(paths["humandb"], use_wsl)
    rsids = _quote_path(paths["rsids"], use_wsl)
    dbsnp_subset = _quote_path(paths["dbsnp_subset"], use_wsl)
    converted = _quote_path(paths["converted_avinput"], use_wsl)
    annovar_prefix = _quote_path(paths["annovar_out_prefix"], use_wsl)
    convert_log = _quote_path(paths["convert_log"], use_wsl)
    table_log = _quote_path(paths["table_log"], use_wsl)

    convert_bash = (
        "set -euo pipefail; "
        f"cd {repo}; "
        f"/usr/bin/time -v perl {convert_script} "
        f"-format rsid {rsids} -dbsnpfile {dbsnp_subset} "
        f"> {converted} 2> {convert_log}"
    )
    table_bash = (
        "set -euo pipefail; "
        f"cd {repo}; "
        f"/usr/bin/time -v perl {table_script} {converted} {humandb} "
        "-buildver hg19 "
        f"-out {annovar_prefix} "
        "-protocol refGene,clinvar_20240917 "
        "-operation g,f "
        "-nastring . "
        "-polish "
        "-otherinfo "
        f"2> {table_log}"
    )

    intervar_dir_q = _quote_path(intervar_dir, use_wsl)
    intervar_input = _quote_path(paths["converted_avinput"], use_wsl)
    intervar_prefix = _quote_path(paths["intervar_out_prefix"], use_wsl)
    intervar_log = _quote_path(paths["intervar_log"], use_wsl)
    intervar_bash = (
        "set -euo pipefail; "
        f"cd {intervar_dir_q}; "
        "/usr/bin/time -v python3 Intervar.py "
        "-b hg19 "
        f"-i {intervar_input} "
        "--input_type=AVinput "
        f"-o {intervar_prefix} "
        "--skip_annovar "
        f"2>&1 | tee {intervar_log}"
    )

    return [
        PipelineCommand(
            name="convert_rsid_to_avinput",
            command=_bash_invocation(convert_bash, use_wsl),
            bash_command=convert_bash,
            log_path=paths["convert_log"],
        ),
        PipelineCommand(
            name="table_annovar",
            command=_bash_invocation(table_bash, use_wsl),
            bash_command=table_bash,
            log_path=paths["table_log"],
        ),
        PipelineCommand(
            name="intervar_skip_annovar",
            command=_bash_invocation(intervar_bash, use_wsl),
            bash_command=intervar_bash,
            log_path=paths["intervar_log"],
        ),
    ]


def validate_full_intervar_dependencies(
    annovar_dir: Path = DEFAULT_ANNOVAR_DIR,
    intervar_dir: Path = DEFAULT_INTERVAR_DIR,
) -> list[Path]:
    humandb = annovar_dir / "humandb"
    required = [
        annovar_dir / "convert2annovar.pl",
        annovar_dir / "table_annovar.pl",
        humandb / "hg19_snp138.txt",
        humandb / "hg19_refGene.txt",
        humandb / "hg19_clinvar_20240917.txt",
        intervar_dir / "Intervar.py",
        intervar_dir / "intervardb/mim2gene.txt",
    ]
    return [path for path in required if not path.exists()]


def _run_command(
    command: PipelineCommand,
    command_runner: CommandRunner,
    *,
    partial_output_path: Path | None = None,
) -> bool:
    result = command_runner(command.command, cwd=str(REPO_ROOT), text=True, capture_output=True)
    if result.returncode != 0:
        debug_path = command.log_path.with_suffix(command.log_path.suffix + ".subprocess.log")
        debug_path.write_text(
            "COMMAND:\n"
            + command.bash_command
            + "\n\nSTDOUT:\n"
            + (result.stdout or "")
            + "\n\nSTDERR:\n"
            + (result.stderr or ""),
            encoding="utf-8",
        )
        if partial_output_path and _count_lines(partial_output_path) > 1:
            return False
        raise FullIntervarPipelineError(
            f"Pipeline phase failed: {command.name}. See {command.log_path} and {debug_path}."
        )
    return True


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return sum(1 for _ in handle)


def _write_line_counts(paths: dict[str, Path]) -> None:
    count_paths = [
        paths["rsids"],
        paths["dbsnp_subset"],
        paths["converted_avinput"],
        paths["annovar_multianno"],
        paths["intervar_output"],
        paths["join_back"],
    ]
    lines = [f"{_count_lines(path):>10} {path.name}" for path in count_paths]
    paths["line_counts"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_primary_chrom(chrom: str) -> bool:
    return _normalized_chrom(chrom) in PRIMARY_CHROMS


def filter_avinput_to_primary_contigs(
    avinput_path: Path,
    *,
    skipped_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    """Keep only primary chromosomes in converted avinput before InterVar.

    dbSNP can map rsIDs to alternate/haplotype contigs such as
    ``chr17_ctg5_hap1`` or ``chrUn_gl000223``. InterVar's ACMG checks assume a
    primary-chromosome table and can crash when those rows shift expected numeric
    columns, so full UI runs filter them out and record a traceable skip file.
    """

    backup_path = avinput_path.with_name("converted.unfiltered.avinput")
    if backup_path.exists():
        source_path = backup_path
    else:
        shutil.copyfile(avinput_path, backup_path)
        source_path = backup_path

    kept = 0
    skipped = 0
    skipped_counter: Counter[str] = Counter()
    with source_path.open("r", encoding="utf-8", errors="replace", newline="") as src, avinput_path.open(
        "w", encoding="utf-8", newline=""
    ) as kept_dst, skipped_path.open("w", encoding="utf-8", newline="") as skipped_dst:
        for line in src:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                kept_dst.write(line)
                continue
            fields = stripped.split()
            chrom = fields[0] if fields else ""
            if is_primary_chrom(chrom):
                kept_dst.write(line)
                kept += 1
            else:
                skipped_dst.write(line)
                skipped += 1
                skipped_counter[chrom] += 1

    summary = {
        "input_path": str(source_path),
        "filtered_output_path": str(avinput_path),
        "skipped_output_path": str(skipped_path),
        "kept_primary_contig_rows": kept,
        "skipped_non_primary_contig_rows": skipped,
        "skipped_contigs": dict(skipped_counter.most_common()),
    }
    log_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_full_intervar_pipeline(
    input_path: Path,
    *,
    output_root: Path = DEFAULT_FULL_INTERVAR_OUTPUT_ROOT,
    genome_build: str = "GRCh37/hg19",
    max_sample_rsids: int = 600_000,
    run_id: str | None = None,
    annovar_dir: Path = DEFAULT_ANNOVAR_DIR,
    intervar_dir: Path = DEFAULT_INTERVAR_DIR,
    command_runner: CommandRunner = subprocess.run,
    use_wsl: bool | None = None,
) -> FullIntervarRun:
    """Run the local DB SNP-to-InterVar route for one consumer SNP input file."""

    missing = validate_full_intervar_dependencies(annovar_dir, intervar_dir)
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FullIntervarPipelineError(f"Missing required local DB/tool files:\n{formatted}")

    run_id = run_id or new_full_intervar_run_id()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = get_full_intervar_paths(run_dir, annovar_dir, intervar_dir)

    manifest = build_route_inputs(
        input_path=input_path,
        output_dir=run_dir,
        genome_build=genome_build,
        max_sample_rsids=max_sample_rsids,
        benchmark_rsids=DEFAULT_BENCHMARK_RSIDS,
        dbsnp_file=paths["dbsnp_file"],
        extract_subset=True,
    )
    paths["prepare_log"].write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")

    commands = build_full_intervar_commands(
        run_dir,
        annovar_dir=annovar_dir,
        intervar_dir=intervar_dir,
        use_wsl=use_wsl,
    )
    _run_command(commands[0], command_runner)

    if not paths["converted_avinput"].exists():
        raise FullIntervarPipelineError(f"convert2annovar did not produce {paths['converted_avinput']}")

    filter_summary = filter_avinput_to_primary_contigs(
        paths["converted_avinput"],
        skipped_path=paths["avinput_filter_skipped"],
        log_path=paths["avinput_filter_log"],
    )
    warnings: list[str] = []
    if filter_summary["skipped_non_primary_contig_rows"]:
        warnings.append(
            "Filtered "
            f"{filter_summary['skipped_non_primary_contig_rows']} non-primary contig rows "
            "before ANNOVAR/InterVar full run."
        )

    _run_command(commands[1], command_runner)
    if not paths["annovar_multianno"].exists():
        raise FullIntervarPipelineError(f"table_annovar did not produce {paths['annovar_multianno']}")

    shutil.copyfile(paths["annovar_multianno"], paths["intervar_multianno"])
    intervar_clean_exit = _run_command(
        commands[2],
        command_runner,
        partial_output_path=paths["intervar_output"],
    )
    if not intervar_clean_exit:
        warnings.append(
            "InterVar exited with a non-zero status after writing an output file. "
            "The run is normalized from the generated .intervar output and should be reviewed."
        )
    if not paths["intervar_output"].exists():
        raise FullIntervarPipelineError(f"InterVar did not produce {paths['intervar_output']}")

    final_manifest = build_route_inputs(
        input_path=input_path,
        output_dir=run_dir,
        genome_build=genome_build,
        max_sample_rsids=max_sample_rsids,
        benchmark_rsids=DEFAULT_BENCHMARK_RSIDS,
        dbsnp_file=paths["dbsnp_file"],
        extract_subset=False,
        converted_avinput=paths["converted_avinput"],
    )
    paths["final_manifest_log"].write_text(
        json.dumps(asdict(final_manifest), indent=2), encoding="utf-8"
    )
    if warnings:
        paths["pipeline_warnings"].write_text(
            json.dumps({"warnings": warnings}, indent=2),
            encoding="utf-8",
        )
    _write_line_counts(paths)

    return FullIntervarRun(
        run_id=run_id,
        run_dir=run_dir,
        input_path=input_path,
        manifest_path=paths["manifest"],
        converted_avinput_path=paths["converted_avinput"],
        annovar_multianno_path=paths["annovar_multianno"],
        intervar_multianno_path=paths["intervar_multianno"],
        intervar_output_path=paths["intervar_output"],
        join_back_path=paths["join_back"],
        line_counts_path=paths["line_counts"],
        commands=commands,
    )


def _canonical_classification(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "pathogenic": "Pathogenic",
        "likely pathogenic": "Likely pathogenic",
        "uncertain significance": "Uncertain significance",
        "likely benign": "Likely benign",
        "benign": "Benign",
    }
    return mapping.get(normalized, value.strip() or "Unknown")


def _normalized_chrom(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("chr"):
        text = text[3:]
    if text.upper() == "M":
        return "MT"
    return text.upper()


def _variant_key(chrom: Any, start: Any, end: Any, ref: Any, alt: Any, rsid: Any = "") -> tuple[str, str, str, str, str, str]:
    return (
        _normalized_chrom(chrom),
        str(start or "").strip(),
        str(end or "").strip(),
        str(ref or "").strip().upper(),
        str(alt or "").strip().upper(),
        str(rsid or "").strip(),
    )


def _find_field(fieldnames: Iterable[str] | None, *needles: str) -> str | None:
    if not fieldnames:
        return None
    lowered_needles = [needle.lower() for needle in needles]
    for field in fieldnames:
        normalized = field.strip().lower()
        if all(needle in normalized for needle in lowered_needles):
            return field
    return None


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_join_back(
    path: Path,
) -> tuple[
    dict[tuple[str, str, str, str, str, str], dict[str, str]],
    dict[str, dict[str, str]],
    Counter[str],
    Counter[str],
]:
    index: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    rsid_index: dict[str, dict[str, str]] = {}
    mapping_counter: Counter[str] = Counter()
    genotype_counter: Counter[str] = Counter()

    if not path.exists():
        return index, rsid_index, mapping_counter, genotype_counter

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rsid = row.get("rsid", "")
            key = _variant_key(
                row.get("avinput_chr"),
                row.get("avinput_start"),
                row.get("avinput_end"),
                row.get("avinput_ref"),
                row.get("avinput_alt"),
                rsid,
            )
            index[key] = row
            if rsid and rsid not in rsid_index:
                rsid_index[rsid] = row
            mapping_counter[row.get("mapping_status") or "unknown"] += 1
            genotype_counter[row.get("genotype_match_status") or "unknown"] += 1

    return index, rsid_index, mapping_counter, genotype_counter


def _summary_rows(counter: Counter[str], preferred_order: list[str] | None = None) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in preferred_order or []:
        if key in counter:
            ordered.append(
                {
                    "label": key,
                    "count": int(counter[key]),
                    "review_required": key in HITL_REVIEW_CLASSIFICATIONS,
                }
            )
            seen.add(key)
    for key, count in counter.most_common():
        if key not in seen:
            ordered.append(
                {
                    "label": key,
                    "count": int(count),
                    "review_required": key in HITL_REVIEW_CLASSIFICATIONS,
                }
            )
    return ordered


def _extract_rsid(otherinfo: str) -> str:
    for token in str(otherinfo or "").replace(";", "\t").split():
        if token.startswith("rs"):
            return token
    return ""


def normalize_intervar_results(
    intervar_path: Path,
    join_back_path: Path,
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Read InterVar output and join it back to original SNP/genotype context."""

    join_index, rsid_index, mapping_counter, genotype_counter = _load_join_back(join_back_path)
    classification_counter: Counter[str] = Counter()
    review_queue: list[dict[str, Any]] = []
    total_rows = 0
    missing_join_back = 0

    if not intervar_path.exists():
        raise FullIntervarPipelineError(f"Missing InterVar output: {intervar_path}")

    with intervar_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        intervar_field = _find_field(reader.fieldnames, "intervar")
        clinvar_field = _find_field(reader.fieldnames, "clinvar")
        chrom_field = _find_field(reader.fieldnames, "chr") or "#Chr"
        otherinfo_field = _find_field(reader.fieldnames, "otherinfo") or "Otherinfo"

        if not intervar_field:
            raise FullIntervarPipelineError("Could not find InterVar classification column.")

        for row in reader:
            total_rows += 1
            classification_raw, _evidence = parse_intervar_classification(row.get(intervar_field, ""))
            classification = _canonical_classification(classification_raw)
            classification_counter[classification] += 1

            if classification not in REVIEW_CLASSIFICATIONS:
                continue

            rsid = _extract_rsid(row.get(otherinfo_field, ""))
            key = _variant_key(
                row.get(chrom_field),
                row.get("Start"),
                row.get("End"),
                row.get("Ref"),
                row.get("Alt"),
                rsid,
            )
            join_row = join_index.get(key)
            if join_row is None and rsid:
                # Some InterVar outputs preserve rsID only in Otherinfo while coordinate
                # formats may vary; fall back to the first exact rsID match.
                join_row = rsid_index.get(rsid)

            if join_row is None:
                missing_join_back += 1
                join_row = {}
                mapping_status = "missing_join_back"
                mapping_warning = "No join_back row matched this InterVar record."
            else:
                mapping_status = join_row.get("mapping_status") or "unknown"
                mapping_warning = join_row.get("mapping_warning") or ""

            review_queue.append(
                {
                    "rsid": rsid or join_row.get("rsid", ""),
                    "gene": row.get("Ref.Gene", ""),
                    "classification": classification,
                    "clinvar_signal": row.get(clinvar_field, "") if clinvar_field else "",
                    "chrom": row.get(chrom_field, ""),
                    "start": row.get("Start", ""),
                    "ref": row.get("Ref", ""),
                    "alt": row.get("Alt", ""),
                    "func_refgene": row.get("Func.refGene", ""),
                    "exonic_func_refgene": row.get("ExonicFunc.refGene", ""),
                    "original_genotype": join_row.get("original_genotype", ""),
                    "genotype_match_status": join_row.get("genotype_match_status", ""),
                    "mapping_status": mapping_status,
                    "mapping_warning": mapping_warning,
                    "row_index": join_row.get("row_index", ""),
                    "review_required": classification in HITL_REVIEW_CLASSIFICATIONS,
                    "raw_intervar_path": str(intervar_path),
                    "raw_join_back_path": str(join_back_path),
                }
            )

    priority = {"Pathogenic": 0, "Likely pathogenic": 1, "Uncertain significance": 2}
    review_queue.sort(
        key=lambda row: (
            priority.get(str(row.get("classification", "")), 99),
            str(row.get("rsid", "")),
        )
    )

    manifest = _load_manifest(manifest_path) if manifest_path else {}
    converted_avinput = intervar_path.parent / "converted.avinput"
    metrics = {
        "selected_rsids": int(manifest.get("selected_count") or 0),
        "avinput_rows": _count_lines(converted_avinput),
        "intervar_rows": total_rows,
        "likely_pathogenic": int(classification_counter.get("Likely pathogenic", 0)),
        "uncertain_significance": int(classification_counter.get("Uncertain significance", 0)),
        "missing_join_back": missing_join_back,
    }

    return {
        "run_dir": str(intervar_path.parent),
        "metrics": metrics,
        "manifest": manifest,
        "classification_counts": dict(classification_counter),
        "classification_summary": _summary_rows(classification_counter, CLASSIFICATION_ORDER),
        "mapping_summary": _summary_rows(mapping_counter),
        "genotype_summary": _summary_rows(genotype_counter),
        "review_queue": review_queue,
        "review_queue_columns": REVIEW_QUEUE_COLUMNS,
        "paths": {
            "intervar_output": str(intervar_path),
            "join_back": str(join_back_path),
            "manifest": str(manifest_path) if manifest_path else "",
        },
    }


def load_full_intervar_results(run_dir: Path) -> dict[str, Any]:
    paths = get_full_intervar_paths(run_dir)
    result = normalize_intervar_results(
        paths["intervar_output"],
        paths["join_back"],
        manifest_path=paths["manifest"],
    )
    warnings_payload = _load_manifest(paths["pipeline_warnings"])
    result["pipeline_warnings"] = warnings_payload.get("warnings", [])
    return result
