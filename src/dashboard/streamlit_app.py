"""Streamlit Pipeline Inspection & Annotation Benchmark Workbench."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workbench.adapters import run_adapter
from src.workbench.benchmark import (
    CURATED_VARIANT_GROUPS,
    TOOL_NAMES,
    build_benchmark_subset,
    build_transformation_trace,
    write_csv,
    write_json,
)
from src.workbench.input_parser import (
    ParsedInput,
    parse_consumer_file,
    parse_consumer_text,
    parse_manual_rsids,
)
from src.workbench.intervar_pipeline import (
    DEFAULT_FULL_INTERVAR_OUTPUT_ROOT,
    FullIntervarPipelineError,
    get_full_intervar_paths,
    load_full_intervar_results,
    new_full_intervar_run_id,
    run_full_intervar_pipeline,
    write_current_input_for_full_run,
)


BUILT_IN_SAMPLES = {
    "Kaggle Child 1 (GRCh37/hg19)": {
        "path": REPO_ROOT / "data/raw_inputs/kaggle_family/Child 1 Genome.csv",
        "build": "GRCh37/hg19",
    },
    "PGP hu43860C (build36/hg18)": {
        "path": REPO_ROOT
        / "data/raw_inputs/pgp_hu43860C/hu43860C_20110115044231/genome_George_Church_Full_20091107080045.txt",
        "build": "build36/hg18",
    },
}


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def rows_to_csv_with_columns(rows: list[dict[str, Any]], columns: list[str]) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows([{key: row.get(key, "") for key in columns} for row in rows])
    return buffer.getvalue()


def file_signature(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


@st.cache_data(show_spinner=False)
def cached_load_full_intervar_results(
    run_dir: str,
    intervar_signature: tuple[int, int],
    join_back_signature: tuple[int, int],
    manifest_signature: tuple[int, int],
) -> dict[str, Any]:
    _ = (intervar_signature, join_back_signature, manifest_signature)
    return load_full_intervar_results(Path(run_dir))


def compact_result_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "run_id",
        "rsid",
        "tool",
        "status",
        "gene",
        "clinical_fields",
        "pgx_fields",
        "frequency_fields",
        "source_links",
        "raw_payload_path",
        "runtime_ms",
        "error",
    )
    return [{key: row.get(key, "") for key in keys} for row in results]


def parse_input_from_ui() -> ParsedInput | None:
    mode = st.radio(
        "Input mode",
        ("Built-in sample", "Upload file", "Manual rsID list"),
        horizontal=True,
    )
    genome_build = st.text_input("Genome build override", value="")

    if mode == "Built-in sample":
        sample_name = st.selectbox("Built-in sample", list(BUILT_IN_SAMPLES))
        sample = BUILT_IN_SAMPLES[sample_name]
        path = sample["path"]
        build = genome_build or sample["build"]
        if not path.exists():
            st.error(f"Sample file not found: {path}")
            return None
        return parse_consumer_file(path, genome_build=build)

    if mode == "Upload file":
        uploaded = st.file_uploader(
            "Upload CSV, TSV, TXT, or 23andMe-like file",
            type=["csv", "tsv", "txt"],
        )
        if not uploaded:
            st.info("Upload a file to inspect it.")
            return None
        text = uploaded.getvalue().decode("utf-8", errors="replace")
        return parse_consumer_text(
            text,
            source_label=uploaded.name,
            genome_build=genome_build or None,
        )

    manual_text = st.text_area(
        "Paste rsIDs",
        value="rs6025\nrs4244285\nrs3093017\nrs12562034",
        height=180,
    )
    return parse_manual_rsids(manual_text)


def render_full_intervar_results(run_dir: Path) -> None:
    paths = get_full_intervar_paths(run_dir)
    required_outputs = [paths["intervar_output"], paths["join_back"]]
    missing_outputs = [path for path in required_outputs if not path.exists()]
    if missing_outputs:
        st.warning("Run folder exists but full InterVar outputs are not complete yet.")
        st.code("\n".join(str(path) for path in missing_outputs))
        return

    result = cached_load_full_intervar_results(
        str(run_dir),
        file_signature(paths["intervar_output"]),
        file_signature(paths["join_back"]),
        file_signature(paths["manifest"]),
    )
    metrics = result["metrics"]
    st.text_input("Full run directory", value=str(run_dir), disabled=True)
    for warning in result.get("pipeline_warnings", []):
        st.warning(warning)

    metric_cols = st.columns(5)
    metric_cols[0].metric("Selected rsIDs", metrics["selected_rsids"])
    metric_cols[1].metric("AVinput rows", metrics["avinput_rows"])
    metric_cols[2].metric("InterVar rows", metrics["intervar_rows"])
    metric_cols[3].metric("Likely pathogenic", metrics["likely_pathogenic"])
    metric_cols[4].metric("Uncertain significance", metrics["uncertain_significance"])

    st.subheader("Classification summary")
    st.dataframe(result["classification_summary"], use_container_width=True)

    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.subheader("Mapping summary")
        st.dataframe(result["mapping_summary"], use_container_width=True)
    with summary_cols[1]:
        st.subheader("Genotype summary")
        st.dataframe(result["genotype_summary"], use_container_width=True)

    review_columns = result["review_queue_columns"]
    review_queue = [
        {key: row.get(key, "") for key in review_columns}
        for row in result["review_queue"]
    ]
    st.subheader("Review queue")
    if review_queue:
        preview_limit = min(5000, len(review_queue))
        st.dataframe(review_queue[:preview_limit], use_container_width=True, height=420)
        if len(review_queue) > preview_limit:
            st.caption(
                f"Showing first {preview_limit:,} review rows. "
                "Download the CSV for the full review queue."
            )
    else:
        st.success("No Pathogenic, Likely pathogenic, or Uncertain significance rows found.")

    summary_json = json.dumps(
        {
            "run_dir": result["run_dir"],
            "metrics": result["metrics"],
            "classification_counts": result["classification_counts"],
            "paths": result["paths"],
        },
        indent=2,
        ensure_ascii=False,
    )
    download_cols = st.columns(3)
    download_cols[0].download_button(
        "Download summary CSV",
        rows_to_csv(result["classification_summary"]),
        file_name="intervar_classification_summary.csv",
        mime="text/csv",
    )
    download_cols[1].download_button(
        "Download review queue CSV",
        rows_to_csv_with_columns(review_queue, review_columns),
        file_name="intervar_review_queue.csv",
        mime="text/csv",
    )
    download_cols[2].download_button(
        "Download summary JSON",
        summary_json,
        file_name="intervar_summary.json",
        mime="application/json",
    )


def app() -> None:
    st.set_page_config(
        page_title="Pipeline Inspection Workbench",
        page_icon="DNA",
        layout="wide",
    )
    st.title("Streamlit Pipeline Inspection & Annotation Benchmark Workbench")
    st.caption(
        "Raw input -> parsed input -> tool-specific input -> raw payload -> normalized comparison."
    )

    tabs = st.tabs(
        [
            "Input Mode",
            "Raw Input Viewer",
            "Parsed Input",
            "Preprocessing Summary",
            "Test Subset",
            "Transformation Trace",
            "Annotation Tools",
            "Raw Payloads",
            "Normalized Comparison",
            "Full SNP → InterVar",
            "Export Report",
        ]
    )

    with tabs[0]:
        parsed = parse_input_from_ui()
        st.session_state["parsed_input"] = parsed
        if parsed:
            st.success(f"Loaded {parsed.source_label}")

    parsed = st.session_state.get("parsed_input")
    if not parsed:
        return

    with tabs[1]:
        inspection = parsed.inspection
        cols = st.columns(4)
        cols[0].metric("Delimiter", inspection.delimiter_name)
        cols[1].metric("Header line", inspection.header_line_number or "none")
        cols[2].metric("Detected build", inspection.genome_build)
        cols[3].metric("Comment lines shown", len(inspection.comment_lines))
        st.subheader("Detected columns")
        st.json(inspection.to_dict())
        st.subheader("Raw preview")
        st.text("\n".join(inspection.raw_preview_lines))

    with tabs[2]:
        st.subheader("Parsed variants")
        rows = [row.to_dict() for row in parsed.variants[:1000]]
        st.dataframe(rows, use_container_width=True)
        if len(parsed.variants) > 1000:
            st.caption(f"Showing first 1,000 of {len(parsed.variants)} parsed rows.")
        if parsed.skipped_rows:
            st.subheader("Skipped / problematic rows")
            st.dataframe(
                [row.to_dict() for row in parsed.skipped_rows[:300]],
                use_container_width=True,
            )

    with tabs[3]:
        summary = parsed.summary
        metric_cols = st.columns(6)
        metric_cols[0].metric("Total rows", summary.total_data_rows)
        metric_cols[1].metric("Parsed rows", summary.parsed_rows)
        metric_cols[2].metric("Valid genotype", summary.valid_genotype_rows)
        metric_cols[3].metric("No-call", summary.no_call_rows)
        metric_cols[4].metric("Missing rsID", summary.missing_rsid_rows)
        metric_cols[5].metric("Duplicate rsID", summary.duplicate_rsid_rows)
        st.json(summary.to_dict())
        for warning in summary.warnings:
            st.warning(warning)

    with tabs[4]:
        top_n = st.slider("Sample-present top N", min_value=0, max_value=200, value=40)
        include_sample = st.checkbox("Include sample-present rsIDs", value=True)
        curated_groups = st.multiselect(
            "Curated benchmark groups",
            list(CURATED_VARIANT_GROUPS),
            default=list(CURATED_VARIANT_GROUPS),
        )
        subset = build_benchmark_subset(
            parsed.variants,
            top_n=top_n,
            include_sample_present=include_sample,
            curated_group_names=curated_groups,
        )
        st.session_state["benchmark_subset"] = subset
        st.dataframe([row.to_dict() for row in subset], use_container_width=True)

    subset = st.session_state.get("benchmark_subset", [])

    with tabs[5]:
        if not subset:
            st.info("Build a test subset first.")
        else:
            rsid = st.selectbox("Trace rsID", [row.rsid for row in subset])
            selected = next(row for row in subset if row.rsid == rsid)
            trace = build_transformation_trace(
                selected,
                parsed.genome_build,
                tools=TOOL_NAMES,
            )
            st.subheader("Original row")
            st.code(trace.original_row)
            st.subheader("Parsed variant")
            st.json(trace.parsed_variant or {})
            st.subheader("Tool-specific inputs")
            st.json(trace.tool_inputs)

    with tabs[6]:
        tools = st.multiselect("Annotation tools", TOOL_NAMES, default=list(TOOL_NAMES[:4]))
        max_variants = st.slider(
            "Max variants to run now",
            min_value=1,
            max_value=max(1, min(50, len(subset) or 1)),
            value=max(1, min(10, len(subset) or 1)),
        )
        timeout = st.slider("API timeout seconds", min_value=3, max_value=60, value=15)
        if st.button("Run selected adapters", type="primary", disabled=not subset):
            run_id = datetime.now(timezone.utc).strftime("workbench_%Y%m%d_%H%M%S")
            run_dir = REPO_ROOT / "data/processed/workbench" / run_id
            selected_subset = subset[:max_variants]
            progress = st.progress(0)
            results: list[dict[str, Any]] = []
            traces: list[dict[str, Any]] = []
            total = max(1, len(selected_subset) * len(tools))
            completed = 0

            for variant in selected_subset:
                trace = build_transformation_trace(variant, parsed.genome_build, tools)
                traces.append(trace.to_dict())
                for tool in tools:
                    tool_input = trace.tool_inputs.get(tool, "")
                    result = run_adapter(
                        tool=tool,
                        run_id=run_id,
                        variant=variant,
                        run_dir=run_dir,
                        tool_input=tool_input,
                        timeout=timeout,
                    )
                    results.append(result.to_dict())
                    completed += 1
                    progress.progress(completed / total)

            compact_rows = compact_result_rows(results)
            write_json(run_dir / "transformation_traces.json", traces)
            write_json(run_dir / "adapter_results.json", results)
            write_csv(run_dir / "normalized_comparison.csv", compact_rows)
            write_json(
                run_dir / "benchmark_summary.json",
                {
                    "run_id": run_id,
                    "source_label": parsed.source_label,
                    "genome_build": parsed.genome_build,
                    "variant_count": len(selected_subset),
                    "tools": tools,
                    "result_count": len(results),
                },
            )
            st.session_state["adapter_results"] = results
            st.session_state["last_run_dir"] = str(run_dir)
            st.success(f"Run complete: {run_dir}")

    results = st.session_state.get("adapter_results", [])

    with tabs[7]:
        if not results:
            st.info("Run annotation adapters to inspect raw payloads.")
        else:
            result_labels = [
                f"{row['rsid']} | {row['tool']} | {row['status']}" for row in results
            ]
            label = st.selectbox("Payload", result_labels)
            row = results[result_labels.index(label)]
            st.json({key: row[key] for key in row if key != "normalized_preview"})
            payload_path = row.get("raw_payload_path")
            if payload_path and Path(payload_path).exists():
                payload_text = Path(payload_path).read_text(encoding="utf-8", errors="replace")
                st.code(payload_text[:50000], language="json")
                st.download_button(
                    "Download raw payload",
                    payload_text,
                    file_name=Path(payload_path).name,
                )
            else:
                st.warning("No raw payload file for this result.")

    with tabs[8]:
        compact_rows = compact_result_rows(results)
        st.dataframe(compact_rows, use_container_width=True)
        if compact_rows:
            st.download_button(
                "Download normalized comparison CSV",
                rows_to_csv(compact_rows),
                file_name="normalized_comparison.csv",
                mime="text/csv",
            )

    with tabs[9]:
        st.subheader("Full SNP → InterVar")
        st.warning(
            "InterVar classification is evidence for review, not an automatic diagnosis. "
            "Pathogenic-looking rows must go through HITL review before being reported."
        )
        st.caption(
            "This tab runs the local DB route on the current Streamlit input: rsID extraction, "
            "convert2annovar, table_annovar, InterVar --skip_annovar, then join-back to genotype."
        )

        if parsed.mode != "consumer_file":
            st.info("Full run is disabled for manual rsID mode because it has no genotype/sample context.")
        else:
            if "hg18" in parsed.genome_build.lower() or "build36" in parsed.genome_build.lower():
                st.warning(
                    "Current input is not hg19/GRCh37. The local route maps rsIDs through hg19 dbSNP; "
                    "review coordinate assumptions before using this as a report finding."
                )

            max_sample_rsids = st.number_input(
                "Max sample rsIDs",
                min_value=1,
                max_value=1_000_000,
                value=min(max(parsed.summary.valid_genotype_rows, 1), 600_000),
                step=1_000,
            )

            if st.button("Run full SNP → InterVar pipeline", type="primary"):
                run_id = new_full_intervar_run_id()
                run_dir = DEFAULT_FULL_INTERVAR_OUTPUT_ROOT / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                try:
                    input_path = write_current_input_for_full_run(parsed, run_dir)
                    with st.spinner(
                        "Running full local DB pipeline. This can take a while on large SNP files..."
                    ):
                        run = run_full_intervar_pipeline(
                            input_path=input_path,
                            output_root=DEFAULT_FULL_INTERVAR_OUTPUT_ROOT,
                            genome_build=parsed.genome_build,
                            max_sample_rsids=int(max_sample_rsids),
                            run_id=run_id,
                        )
                    st.session_state["full_intervar_run_dir"] = str(run.run_dir)
                    st.success(f"Full InterVar run complete: {run.run_dir}")
                except FullIntervarPipelineError as exc:
                    st.error(str(exc))

            previous_runs = (
                sorted(
                    [path for path in DEFAULT_FULL_INTERVAR_OUTPUT_ROOT.glob("run_*") if path.is_dir()],
                    reverse=True,
                )
                if DEFAULT_FULL_INTERVAR_OUTPUT_ROOT.exists()
                else []
            )
            if previous_runs:
                with st.expander("Load previous full run"):
                    selected_run = st.selectbox(
                        "Completed run folder",
                        [str(path) for path in previous_runs],
                    )
                    if st.button("Load selected full run"):
                        st.session_state["full_intervar_run_dir"] = selected_run

        active_full_run = st.session_state.get("full_intervar_run_dir")
        if active_full_run:
            render_full_intervar_results(Path(active_full_run))

    with tabs[10]:
        run_dir = st.session_state.get("last_run_dir", "")
        st.text_input("Last run directory", value=run_dir, disabled=True)
        export_payload = {
            "source": parsed.source_label,
            "summary": parsed.summary.to_dict(),
            "inspection": parsed.inspection.to_dict(),
            "subset": [row.to_dict() for row in subset],
            "results": compact_result_rows(results),
        }
        st.download_button(
            "Download workbench report JSON",
            json.dumps(export_payload, indent=2, ensure_ascii=False),
            file_name="workbench_report.json",
            mime="application/json",
        )


if __name__ == "__main__":
    app()
