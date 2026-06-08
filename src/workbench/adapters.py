"""Annotation adapter layer for the Streamlit workbench.

Adapters preserve raw payloads first. Normalized fields are only comparison
metadata so users can inspect what each tool actually returned.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.workbench.benchmark import BenchmarkVariant


REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_MAPPED = "mapped"
STATUS_UNRESOLVED = "unresolved"
STATUS_API_ERROR = "api_error"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_SKIPPED = "skipped"

ANNOVAR_HG19_CURATED_AVINPUT: dict[str, tuple[tuple[str, str], ...]] = {
    "rs6025": (
        ("chr1\t169519049\t169519049\tG\tA\trs6025\tmyvariant_top_hit", "G>A"),
        ("chr1\t169519049\t169519049\tT\tC\trs6025\tmyvariant_alternate_hit", "T>C"),
    ),
    "rs4244285": (
        ("chr10\t96541616\t96541616\tG\tC\trs4244285\tmyvariant_top_hit", "G>C"),
        ("chr10\t96541616\t96541616\tG\tT\trs4244285\tmyvariant_alternate_hit", "G>T"),
    ),
    "rs7412": (
        ("chr19\t45412079\t45412079\tC\tT\trs7412\tmyvariant_top_hit", "C>T"),
    ),
    "rs1801133": (
        ("chr1\t11856378\t11856378\tG\tC\trs1801133\tmyvariant_top_hit", "G>C"),
        ("chr1\t11856378\t11856378\tG\tA\trs1801133\tmyvariant_alternate_hit", "G>A"),
    ),
}


@dataclass
class AdapterResult:
    run_id: str
    rsid: str
    tool: str
    status: str
    gene: str
    clinical_fields: str
    pgx_fields: str
    frequency_fields: str
    source_links: str
    raw_payload_path: str
    runtime_ms: int
    error: str
    tool_input: str
    normalized_preview: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _http_get_json(url: str, timeout: int) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "clinical-variant-dashboard-workbench/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _http_post_json(url: str, payload: dict[str, Any], timeout: int) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "clinical-variant-dashboard-workbench/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _payload_path(run_dir: Path, tool: str, rsid: str, suffix: str = ".json") -> Path:
    safe_tool = (
        tool.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "")
        .replace("-", "_")
    )
    return run_dir / "raw_payloads" / safe_tool / f"{rsid}{suffix}"


def _write_payload(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", "utf-8")


def _path_for_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.relative_to(resolved.anchor).as_posix()
    return f"/mnt/{drive}/{tail}"


def _result(
    *,
    run_id: str,
    variant: BenchmarkVariant,
    tool: str,
    status: str,
    tool_input: str,
    raw_payload_path: Path | None = None,
    runtime_ms: int = 0,
    error: str = "",
    gene: str = "",
    clinical_fields: str = "",
    pgx_fields: str = "",
    frequency_fields: str = "",
    source_links: str = "",
    normalized_preview: dict[str, Any] | None = None,
) -> AdapterResult:
    return AdapterResult(
        run_id=run_id,
        rsid=variant.rsid,
        tool=tool,
        status=status,
        gene=gene,
        clinical_fields=clinical_fields,
        pgx_fields=pgx_fields,
        frequency_fields=frequency_fields,
        source_links=source_links,
        raw_payload_path=str(raw_payload_path or ""),
        runtime_ms=runtime_ms,
        error=error,
        tool_input=tool_input,
        normalized_preview=normalized_preview or {},
    )


def run_vep_variant_recoder(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "VEP REST / Variant Recoder"
    start = time.monotonic()
    url = (
        "https://rest.ensembl.org/variant_recoder/human/"
        + urllib.parse.quote(variant.rsid)
        + "?content-type=application/json"
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_get_json(url, timeout)
        _write_payload(payload_path, payload)
        status = STATUS_MAPPED if payload else STATUS_UNRESOLVED
        genes = sorted(
            {
                str(item.get("gene_symbol"))
                for item in payload if isinstance(item, dict) and item.get("gene_symbol")
            }
        )
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=status,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=", ".join(genes),
            source_links=url,
            normalized_preview={
                "record_count": len(payload) if isinstance(payload, list) else None,
                "genes": genes,
            },
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_myvariant(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "MyVariant.info"
    start = time.monotonic()
    query = urllib.parse.quote(variant.rsid)
    fields = urllib.parse.quote(
        "dbsnp.rsid,clinvar,gnomad_genome,gnomad_exome,snpedia,cadd,snpeff"
    )
    url = f"https://myvariant.info/v1/query?q={query}&fields={fields}&size=5"
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_get_json(url, timeout)
        _write_payload(payload_path, payload)
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        status = STATUS_MAPPED if hits else STATUS_UNRESOLVED
        clinical = any("clinvar" in hit for hit in hits if isinstance(hit, dict))
        frequency = any(
            "gnomad_genome" in hit or "gnomad_exome" in hit
            for hit in hits if isinstance(hit, dict)
        )
        genes = sorted(
            {
                str(hit.get("snpeff", {}).get("ann", {}).get("gene_name"))
                for hit in hits
                if isinstance(hit, dict)
                and isinstance(hit.get("snpeff"), dict)
                and isinstance(hit.get("snpeff", {}).get("ann"), dict)
                and hit.get("snpeff", {}).get("ann", {}).get("gene_name")
            }
        )
        if not genes and variant.gene_hint:
            genes = [variant.gene_hint]
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=status,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=", ".join(genes),
            clinical_fields="present" if clinical else "",
            frequency_fields="present" if frequency else "",
            source_links=url,
            normalized_preview={
                "hit_count": len(hits),
                "has_clinvar": clinical,
                "has_frequency": frequency,
                "genes": genes,
            },
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_clinvar_eutils(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "ClinVar E-utilities"
    start = time.monotonic()
    term = urllib.parse.quote(f"{variant.rsid}[All Fields]")
    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=clinvar&term={term}&retmax=20&retmode=json"
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        search_payload = _http_get_json(search_url, timeout)
        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        summary_payload: dict[str, Any] = {}
        summary_url = ""
        if ids:
            summary_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                f"?db=clinvar&id={','.join(ids[:20])}&retmode=json"
            )
            summary_payload = _http_get_json(summary_url, timeout)
        payload = {
            "search_url": search_url,
            "summary_url": summary_url,
            "esearch": search_payload,
            "esummary": summary_payload,
        }
        _write_payload(payload_path, payload)
        records = summary_payload.get("result", {}) if isinstance(summary_payload, dict) else {}
        uids = records.get("uids", []) if isinstance(records, dict) else []
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if ids else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            clinical_fields="present" if ids else "",
            source_links=summary_url or search_url,
            normalized_preview={
                "clinvar_uid_count": len(ids),
                "summarized_uid_count": len(uids),
                "uids": ids[:20],
            },
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=search_url,
        )


def run_mygene(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "MyGene.info"
    if not variant.gene_hint:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_SKIPPED,
            tool_input=tool_input,
            error="No gene hint available; run VEP/MyVariant first or add a curated gene hint.",
        )
    start = time.monotonic()
    query = urllib.parse.quote(f"symbol:{variant.gene_hint}")
    url = (
        "https://mygene.info/v3/query?q="
        f"{query}&species=human&fields=symbol,name,entrezgene,ensembl.gene,summary&size=3"
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_get_json(url, timeout)
        _write_payload(payload_path, payload)
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if hits else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            source_links=url,
            normalized_preview={"hit_count": len(hits), "gene_hint": variant.gene_hint},
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_gwas_catalog(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "GWAS Catalog"
    start = time.monotonic()
    url = (
        "https://www.ebi.ac.uk/gwas/summary-statistics/api/associations/"
        + urllib.parse.quote(variant.rsid)
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_get_json(url, timeout)
        _write_payload(payload_path, payload)
        embedded = payload.get("_embedded", {}) if isinstance(payload, dict) else {}
        associations = []
        if isinstance(embedded, dict):
            associations = embedded.get("associations", []) or embedded.get("association", [])
        if not associations and isinstance(payload, dict) and "p_value" in payload:
            associations = [payload]
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if associations else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            source_links=url,
            normalized_preview={"association_count": len(associations)},
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        status = STATUS_UNRESOLVED if isinstance(exc, urllib.error.HTTPError) and exc.code == 404 else STATUS_API_ERROR
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=status,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_pubmed_eutils(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "PubMed E-utilities"
    start = time.monotonic()
    term = urllib.parse.quote(variant.rsid)
    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={term}&retmax=20&retmode=json"
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        search_payload = _http_get_json(search_url, timeout)
        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        summary_payload: dict[str, Any] = {}
        summary_url = ""
        if ids:
            summary_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                f"?db=pubmed&id={','.join(ids[:20])}&retmode=json"
            )
            summary_payload = _http_get_json(summary_url, timeout)
        payload = {
            "search_url": search_url,
            "summary_url": summary_url,
            "esearch": search_payload,
            "esummary": summary_payload,
        }
        _write_payload(payload_path, payload)
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if ids else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            source_links=summary_url or search_url,
            normalized_preview={"pmid_count": len(ids), "pmids": ids[:20]},
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=search_url,
        )


def run_open_targets(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "Open Targets"
    if not variant.gene_hint:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_SKIPPED,
            tool_input=tool_input,
            error="No gene hint available; Open Targets adapter currently uses gene symbol search.",
        )
    start = time.monotonic()
    url = "https://api.platform.opentargets.org/api/v4/graphql"
    query = """
    query SearchGene($queryString: String!) {
      search(queryString: $queryString, entityNames: ["target"], page: {index: 0, size: 5}) {
        hits {
          id
          name
          entity
          object {
            ... on Target {
              approvedSymbol
              approvedName
              biotype
            }
          }
        }
      }
    }
    """
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_post_json(
            url,
            {"query": query, "variables": {"queryString": variant.gene_hint}},
            timeout,
        )
        _write_payload(payload_path, payload)
        hits = payload.get("data", {}).get("search", {}).get("hits", [])
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if hits else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            source_links=url,
            normalized_preview={"target_hit_count": len(hits), "query_gene": variant.gene_hint},
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_clinpgx(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "ClinPGx"
    start = time.monotonic()
    url = (
        "https://api.clinpgx.org/v1/data/variant/?symbol="
        + urllib.parse.quote(variant.rsid)
        + "&view=max"
    )
    payload_path = _payload_path(run_dir, tool, variant.rsid)
    try:
        payload = _http_get_json(url, timeout)
        _write_payload(payload_path, payload)
        count = len(payload) if isinstance(payload, list) else 1 if payload else 0
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_MAPPED if count else STATUS_UNRESOLVED,
            tool_input=tool_input,
            raw_payload_path=payload_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            gene=variant.gene_hint,
            pgx_fields="present" if count else "",
            source_links=url,
            normalized_preview={"record_count": count},
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            source_links=url,
        )


def run_setup_required_placeholder(
    run_id: str,
    variant: BenchmarkVariant,
    tool: str,
    tool_input: str,
    error: str,
) -> AdapterResult:
    return _result(
        run_id=run_id,
        variant=variant,
        tool=tool,
        status=STATUS_NOT_CONFIGURED,
        tool_input=tool_input,
        error=error,
    )


def run_opencravat_placeholder(
    run_id: str,
    variant: BenchmarkVariant,
    tool_input: str,
) -> AdapterResult:
    tool = "OpenCRAVAT"
    oc_path = shutil.which("oc")
    enabled = os.environ.get("OC_WORKBENCH_ENABLE") == "1"
    if not oc_path:
        error = "OpenCRAVAT CLI not found on PATH."
        status = STATUS_NOT_CONFIGURED
    elif not enabled:
        error = "Set OC_WORKBENCH_ENABLE=1 and configure batch input to run OpenCRAVAT."
        status = STATUS_NOT_CONFIGURED
    else:
        error = "OpenCRAVAT adapter is batch/file-level; use converted TSV run outside per-rsID API flow."
        status = STATUS_SKIPPED
    return _result(
        run_id=run_id,
        variant=variant,
        tool=tool,
        status=status,
        tool_input=tool_input,
        error=error,
    )


def run_annovar_placeholder(
    run_id: str,
    variant: BenchmarkVariant,
    tool_input: str,
) -> AdapterResult:
    tool = "ANNOVAR / InterVar"
    annovar_dir = os.environ.get("ANNOVAR_DIR")
    intervar_dir = os.environ.get("INTERVAR_DIR")
    if not annovar_dir:
        error = "ANNOVAR_DIR is not configured."
        status = STATUS_NOT_CONFIGURED
    elif not intervar_dir:
        error = "INTERVAR_DIR is not configured; ANNOVAR can be tested separately."
        status = STATUS_NOT_CONFIGURED
    else:
        error = "Local ANNOVAR/InterVar adapter placeholder; run configured batch benchmark separately."
        status = STATUS_SKIPPED
    return _result(
        run_id=run_id,
        variant=variant,
        tool=tool,
        status=status,
        tool_input=tool_input,
        error=error,
    )


def _run_annovar_command(
    annovar_dir: Path,
    input_path: Path,
    humandb_dir: Path,
    out_prefix: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    if os.name == "nt":
        command = " ".join(
            [
                "cd",
                shlex.quote(_path_for_wsl(REPO_ROOT)),
                "&&",
                "perl",
                shlex.quote(_path_for_wsl(annovar_dir / "table_annovar.pl")),
                shlex.quote(_path_for_wsl(input_path)),
                shlex.quote(_path_for_wsl(humandb_dir)),
                "-buildver",
                "hg19",
                "-out",
                shlex.quote(_path_for_wsl(out_prefix)),
                "-remove",
                "-protocol",
                "refGene,clinvar_20240917",
                "-operation",
                "g,f",
                "-nastring",
                ".",
                "-otherinfo",
            ]
        )
        return subprocess.run(
            ["wsl", "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    return subprocess.run(
        [
            "perl",
            str(annovar_dir / "table_annovar.pl"),
            str(input_path),
            str(humandb_dir),
            "-buildver",
            "hg19",
            "-out",
            str(out_prefix),
            "-remove",
            "-protocol",
            "refGene,clinvar_20240917",
            "-operation",
            "g,f",
            "-nastring",
            ".",
            "-otherinfo",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def run_annovar_local(
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int,
) -> AdapterResult:
    tool = "ANNOVAR / InterVar"
    annovar_dir = Path(os.environ.get("ANNOVAR_DIR", REPO_ROOT / "tools" / "annovar"))
    humandb_dir = annovar_dir / "humandb"
    if not (annovar_dir / "table_annovar.pl").exists():
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_NOT_CONFIGURED,
            tool_input=tool_input,
            error=f"table_annovar.pl not found under {annovar_dir}.",
        )
    if not (humandb_dir / "hg19_refGene.txt").exists() or not (
        humandb_dir / "hg19_clinvar_20240917.txt"
    ).exists():
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_NOT_CONFIGURED,
            tool_input=tool_input,
            error="Missing hg19_refGene or hg19_clinvar_20240917 in ANNOVAR humandb.",
        )
    if os.name == "nt" and not shutil.which("wsl"):
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_NOT_CONFIGURED,
            tool_input=tool_input,
            error="WSL is required on Windows because Git Perl is missing Pod::Usage.",
        )

    alleles = ANNOVAR_HG19_CURATED_AVINPUT.get(variant.rsid.lower())
    if not alleles:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_SKIPPED,
            tool_input=tool_input,
            error=(
                "ANNOVAR adapter needs chr/start/end/ref/alt or an optimized "
                "convert2annovar -format rsid resolver. This rsID is not in the "
                "curated hg19 allele map yet."
            ),
        )

    start = time.monotonic()
    payload_dir = _payload_path(run_dir, tool, variant.rsid, suffix="").with_suffix("")
    payload_dir.mkdir(parents=True, exist_ok=True)
    input_path = payload_dir / f"{variant.rsid}.hg19.avinput"
    input_path.write_text("\n".join(row for row, _label in alleles) + "\n", "utf-8")
    out_prefix = payload_dir / variant.rsid

    try:
        completed = _run_annovar_command(
            annovar_dir=annovar_dir,
            input_path=input_path,
            humandb_dir=humandb_dir,
            out_prefix=out_prefix,
            timeout=timeout,
        )
    except (subprocess.SubprocessError, TimeoutError) as exc:
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
            raw_payload_path=input_path,
        )

    log_path = payload_dir / f"{variant.rsid}.annovar.log.txt"
    log_path.write_text(
        "STDOUT:\n"
        + completed.stdout
        + "\nSTDERR:\n"
        + completed.stderr
        + f"\nRETURN_CODE: {completed.returncode}\n",
        "utf-8",
    )
    multianno_path = payload_dir / f"{variant.rsid}.hg19_multianno.txt"
    if completed.returncode != 0 or not multianno_path.exists():
        return _result(
            run_id=run_id,
            variant=variant,
            tool=tool,
            status=STATUS_API_ERROR,
            tool_input=tool_input,
            raw_payload_path=log_path,
            runtime_ms=int((time.monotonic() - start) * 1000),
            error=f"ANNOVAR failed with return code {completed.returncode}; see log.",
        )

    rows = multianno_path.read_text("utf-8", errors="replace").splitlines()
    header = rows[0].split("\t") if rows else []
    data_rows = [line.split("\t") for line in rows[1:]]
    col = {name: index for index, name in enumerate(header)}
    genes = sorted(
        {
            row[col["Gene.refGene"]]
            for row in data_rows
            if "Gene.refGene" in col and len(row) > col["Gene.refGene"] and row[col["Gene.refGene"]] != "."
        }
    )
    clinsig_values = sorted(
        {
            row[col["CLNSIG"]]
            for row in data_rows
            if "CLNSIG" in col and len(row) > col["CLNSIG"] and row[col["CLNSIG"]] != "."
        }
    )
    drug_response = any("drug_response" in value for value in clinsig_values)
    return _result(
        run_id=run_id,
        variant=variant,
        tool=tool,
        status=STATUS_MAPPED if data_rows else STATUS_UNRESOLVED,
        tool_input=tool_input,
        raw_payload_path=multianno_path,
        runtime_ms=int((time.monotonic() - start) * 1000),
        gene=", ".join(genes),
        clinical_fields="present" if clinsig_values else "",
        pgx_fields="present" if drug_response else "",
        source_links=str(multianno_path),
        normalized_preview={
            "row_count": len(data_rows),
            "alleles_tested": [label for _row, label in alleles],
            "genes": genes,
            "clinsig_values": clinsig_values,
            "log_path": str(log_path),
        },
    )


def run_adapter(
    tool: str,
    run_id: str,
    variant: BenchmarkVariant,
    run_dir: Path,
    tool_input: str,
    timeout: int = 15,
) -> AdapterResult:
    if tool == "VEP REST / Variant Recoder":
        return run_vep_variant_recoder(run_id, variant, run_dir, tool_input, timeout)
    if tool == "ClinVar E-utilities":
        return run_clinvar_eutils(run_id, variant, run_dir, tool_input, timeout)
    if tool == "MyVariant.info":
        return run_myvariant(run_id, variant, run_dir, tool_input, timeout)
    if tool == "MyGene.info":
        return run_mygene(run_id, variant, run_dir, tool_input, timeout)
    if tool == "ClinPGx":
        return run_clinpgx(run_id, variant, run_dir, tool_input, timeout)
    if tool == "GWAS Catalog":
        return run_gwas_catalog(run_id, variant, run_dir, tool_input, timeout)
    if tool == "PubMed E-utilities":
        return run_pubmed_eutils(run_id, variant, run_dir, tool_input, timeout)
    if tool == "Open Targets":
        return run_open_targets(run_id, variant, run_dir, tool_input, timeout)
    if tool == "OpenCRAVAT":
        return run_opencravat_placeholder(run_id, variant, tool_input)
    if tool == "SnpEff / SnpSift":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires local Java CLI, genome database download, and VCF chr/pos/ref/alt input.",
        )
    if tool == "ANNOVAR / InterVar":
        return run_annovar_local(run_id, variant, run_dir, tool_input, timeout)
    if tool == "PharmCAT":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires PharmCAT Docker/Java setup and VCF or outside-calls TSV input.",
        )
    if tool == "ClinGen Allele Registry":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires endpoint validation and preferably HGVS/SPDI/normalized allele input.",
        )
    if tool == "gnomAD direct":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires build-specific chr-pos-ref-alt or gnomAD variant ID; rsID-only lookup is ambiguous.",
        )
    if tool == "OMIM":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires OMIM API key and license/redistribution review.",
        )
    if tool == "CADD / dbNSFP / REVEL / AlphaMissense":
        return run_setup_required_placeholder(
            run_id,
            variant,
            tool,
            tool_input,
            "Requires precise chr-pos-ref-alt and local/API score resource setup with license review.",
        )
    return _result(
        run_id=run_id,
        variant=variant,
        tool=tool,
        status=STATUS_NOT_CONFIGURED,
        tool_input=tool_input,
        error=f"Unknown adapter: {tool}",
    )
