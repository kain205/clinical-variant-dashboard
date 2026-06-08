from src.workbench.benchmark import build_benchmark_subset, build_transformation_trace
from src.workbench.input_parser import parse_consumer_text, parse_manual_rsids


def test_parse_consumer_csv_with_comment_header():
    text = """# build 37
# rsid,chromosome,position,genotype
rs6025,1,169519049,AG
rs1,1,10,--
rs6025,1,169519049,AG
"""

    parsed = parse_consumer_text(text, "sample.csv")

    assert parsed.inspection.delimiter_name == "CSV"
    assert parsed.inspection.header_line_number == 2
    assert parsed.summary.total_data_rows == 3
    assert parsed.summary.valid_genotype_rows == 1
    assert parsed.summary.no_call_rows == 1
    assert parsed.summary.duplicate_rsid_rows == 1
    assert parsed.genome_build == "GRCh37/hg19"


def test_parse_manual_rsids_has_no_genotype_context():
    parsed = parse_manual_rsids("rs6025\nrs6025 rs4244285")

    assert parsed.mode == "manual_rsid_list"
    assert len(parsed.variants) == 2
    assert parsed.variants[0].skip_reason == "manual_no_genotype_context"
    assert parsed.summary.valid_genotype_rows == 0


def test_transformation_trace_keeps_raw_and_tool_input_separate():
    parsed = parse_consumer_text(
        "# rsid\tchromosome\tposition\tgenotype\nrs6025\t1\t169519049\tAG\n",
        "sample.tsv",
        genome_build="GRCh37/hg19",
    )
    subset = build_benchmark_subset(
        parsed.variants,
        top_n=1,
        include_sample_present=True,
        curated_group_names=[],
    )

    trace = build_transformation_trace(subset[0], "GRCh37/hg19")

    assert trace.original_row == "rs6025\t1\t169519049\tAG"
    assert trace.parsed_variant["genotype"] == "AG"
    assert "rs6025" in trace.tool_inputs["ClinVar E-utilities"]
    assert "rs6025" in trace.tool_inputs["MyVariant.info"]
    assert "rs6025" in trace.tool_inputs["GWAS Catalog"]
    assert "converted TSV" not in trace.tool_inputs["OpenCRAVAT"]
