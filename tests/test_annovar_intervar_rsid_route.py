import json

from src.preprocessing.build_annovar_intervar_testset import (
    OriginalVariantRecord,
    extract_dbsnp_subset,
    join_avinput_to_originals,
    parse_avinput,
    parse_intervar_output,
    build_route_inputs,
)


def test_build_route_inputs_preserves_original_context(tmp_path):
    input_path = tmp_path / "child.csv"
    input_path.write_text(
        "\n".join(
            (
                "rsid,chromosome,position,genotype",
                "rs6025,1,169549811,AG",
                "rsNoCall,1,10,--",
                "rsDuplicate,1,20,AA",
                "rsDuplicate,1,20,AA",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = build_route_inputs(
        input_path=input_path,
        output_dir=tmp_path / "route",
        genome_build="GRCh37/hg19",
        max_sample_rsids=1,
        benchmark_rsids=("rs6025", "rs4244285"),
        dbsnp_file=tmp_path / "missing_hg19_snp138.txt",
        extract_subset=False,
    )

    manifest_json = json.loads((tmp_path / "route" / "conversion_manifest.json").read_text())
    original_tsv = (tmp_path / "route" / "original_variants.tsv").read_text()
    rsids = (tmp_path / "route" / "rsids.txt").read_text().splitlines()

    assert manifest.selected_count == 3
    assert manifest_json["duplicate_rsid_rows"] == 1
    assert "row_index\trsid\toriginal_chromosome" in original_tsv
    assert "rs6025" in original_tsv
    assert rsids == ["rs6025", "rsDuplicate", "rs4244285"]


def test_extract_dbsnp_subset_counts_multiple_mappings(tmp_path):
    dbsnp = tmp_path / "hg19_snp138.txt"
    dbsnp.write_text(
        "\n".join(
            (
                "1\t100\t100\tA\tG\trs6025",
                "1\t101\t101\tA\tT\trs6025",
                "1\t200\t200\tC\tT\trs4244285",
                "1\t300\t300\tG\tA\trsOther",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    subset = tmp_path / "selected.txt"

    counts = extract_dbsnp_subset(dbsnp, ["rs6025", "rs4244285", "rsMissing"], subset)

    assert counts == {"rs6025": 2, "rs4244285": 1, "rsMissing": 0}
    assert subset.read_text(encoding="utf-8").count("rs6025") == 2
    assert "rsOther" not in subset.read_text(encoding="utf-8")


def test_join_back_flags_multiple_mapping_and_genotype_mismatch(tmp_path):
    avinput = tmp_path / "converted.avinput"
    avinput.write_text(
        "\n".join(
            (
                "1 100 100 A G rs6025",
                "1 101 101 C T rs6025",
                "1 200 200 C T rsExternal",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    originals = [
        OriginalVariantRecord(
            row_index=7,
            rsid="rs6025",
            original_chromosome="1",
            original_position="100",
            original_genotype="AG",
            genome_build="GRCh37/hg19",
            source_kind="sample",
            selection_kind="benchmark_present",
        )
    ]

    joined = join_avinput_to_originals(parse_avinput(avinput), originals)

    assert joined[0].mapping_status == "multi_mapping"
    assert joined[0].genotype_match_status == "sample_carries_alt"
    assert joined[1].mapping_status == "multi_mapping"
    assert joined[1].genotype_match_status == "genotype_ref_alt_mismatch"
    assert joined[2].mapping_status == "no_sample_context"
    assert joined[2].genotype_match_status == "no_sample_genotype"


def test_parse_intervar_output_keeps_classification_as_evidence_only(tmp_path):
    intervar = tmp_path / "sample.intervar"
    intervar.write_text(
        "\t".join(
            (
                "#Chr",
                "Start",
                "End",
                "Ref",
                "Alt",
                "InterVar: InterVar and Evidence",
            )
        )
        + "\n"
        + "\t".join(
            (
                "1",
                "100",
                "100",
                "A",
                "G",
                "InterVar: Benign PVS1=0 PS=[0, 0, 0, 0, 0] BA1=1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    parsed = parse_intervar_output(intervar)

    assert parsed[0].intervar_classification == "Benign"
    assert "BA1=1" in parsed[0].acmg_evidence_raw
    assert parsed[0].clinical_interpretation == "evidence_only_not_diagnosis"
