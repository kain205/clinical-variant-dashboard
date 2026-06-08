import json
import subprocess
from pathlib import Path

from src.workbench.input_parser import parse_consumer_text
from src.workbench.intervar_pipeline import (
    build_full_intervar_commands,
    filter_avinput_to_primary_contigs,
    get_full_intervar_paths,
    normalize_intervar_results,
    run_full_intervar_pipeline,
    write_current_input_for_full_run,
)


INTERVAR_HEADER = "\t".join(
    [
        "#Chr",
        "Start",
        "End",
        "Ref",
        "Alt",
        "Ref.Gene",
        "Func.refGene",
        "ExonicFunc.refGene",
        "clinvar: Clinvar ",
        " InterVar: InterVar and Evidence ",
        "Otherinfo",
    ]
)


def write_intervar_fixture(path: Path) -> None:
    rows = [
        [
            "1",
            "100",
            "100",
            "A",
            "G",
            "GENE1",
            "exonic",
            "nonsynonymous SNV",
            "clinvar: UNK ",
            " InterVar: Benign PVS1=0 ",
            "rsBenign",
        ],
        [
            "2",
            "200",
            "200",
            "C",
            "T",
            "GENE2",
            "exonic",
            "synonymous SNV",
            "clinvar: Likely_benign ",
            " InterVar: Likely benign PVS1=0 ",
            "rsLikelyBenign",
        ],
        [
            "3",
            "300",
            "300",
            "G",
            "A",
            "GENE3",
            "exonic",
            "nonsynonymous SNV",
            "clinvar: Conflicting_interpretations ",
            " InterVar: Uncertain significance PM=[1,0,0,0,0,0,0] ",
            "rsVus",
        ],
        [
            "4",
            "400",
            "400",
            "T",
            "C",
            "GENE4",
            "exonic",
            "nonsynonymous SNV",
            "clinvar: drug_response ",
            " InterVar: Likely pathogenic PS=[1,0,0,0,0] ",
            "rsLikelyPathogenic",
        ],
    ]
    path.write_text(
        INTERVAR_HEADER + "\n" + "\n".join("\t".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_join_back_fixture(path: Path) -> None:
    header = [
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
    ]
    rows = [
        [
            "3",
            "rsVus",
            "3",
            "300",
            "GA",
            "GRCh37/hg19",
            "chr3",
            "300",
            "300",
            "G",
            "A",
            "mapped",
            "",
            "annovar.txt",
            "intervar.txt",
            "sample_carries_alt",
        ],
        [
            "4",
            "rsLikelyPathogenic",
            "4",
            "400",
            "TC",
            "GRCh37/hg19",
            "chr4",
            "400",
            "400",
            "T",
            "C",
            "mapped",
            "",
            "annovar.txt",
            "intervar.txt",
            "sample_carries_alt",
        ],
    ]
    path.write_text(
        "\t".join(header) + "\n" + "\n".join("\t".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_normalize_intervar_results_parses_summary_and_review_queue(tmp_path: Path) -> None:
    intervar_path = tmp_path / "intervar_child1.hg19_multianno.txt.intervar"
    join_back_path = tmp_path / "join_back.tsv"
    manifest_path = tmp_path / "conversion_manifest.json"
    converted = tmp_path / "converted.avinput"
    write_intervar_fixture(intervar_path)
    write_join_back_fixture(join_back_path)
    manifest_path.write_text(json.dumps({"selected_count": 4}), encoding="utf-8")
    converted.write_text("chr3\t300\t300\tG\tA\trsVus\n", encoding="utf-8")

    result = normalize_intervar_results(
        intervar_path,
        join_back_path,
        manifest_path=manifest_path,
    )

    assert result["classification_counts"]["Benign"] == 1
    assert result["classification_counts"]["Likely benign"] == 1
    assert result["classification_counts"]["Uncertain significance"] == 1
    assert result["classification_counts"]["Likely pathogenic"] == 1
    assert result["metrics"]["selected_rsids"] == 4
    assert result["metrics"]["avinput_rows"] == 1
    assert result["metrics"]["intervar_rows"] == 4

    review_rows = {row["rsid"]: row for row in result["review_queue"]}
    assert review_rows["rsVus"]["review_required"] is False
    assert review_rows["rsLikelyPathogenic"]["review_required"] is True
    assert review_rows["rsLikelyPathogenic"]["gene"] == "GENE4"
    assert review_rows["rsLikelyPathogenic"]["original_genotype"] == "TC"
    assert review_rows["rsLikelyPathogenic"]["genotype_match_status"] == "sample_carries_alt"


def test_normalize_intervar_results_marks_missing_join_back(tmp_path: Path) -> None:
    intervar_path = tmp_path / "intervar_child1.hg19_multianno.txt.intervar"
    join_back_path = tmp_path / "join_back.tsv"
    intervar_path.write_text(
        INTERVAR_HEADER
        + "\n"
        + "\t".join(
            [
                "5",
                "500",
                "500",
                "A",
                "C",
                "GENE5",
                "exonic",
                "nonsynonymous SNV",
                "clinvar: UNK ",
                " InterVar: Likely pathogenic PVS1=1 ",
                "rsMissing",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_join_back_fixture(join_back_path)

    result = normalize_intervar_results(intervar_path, join_back_path)

    assert result["metrics"]["missing_join_back"] == 1
    assert result["review_queue"][0]["mapping_status"] == "missing_join_back"
    assert "No join_back row matched" in result["review_queue"][0]["mapping_warning"]


def test_build_full_intervar_commands_uses_expected_phases(tmp_path: Path) -> None:
    annovar_dir = tmp_path / "tools/annovar"
    intervar_dir = tmp_path / "tools/InterVar"
    commands = build_full_intervar_commands(
        tmp_path / "run_20260101_000000",
        annovar_dir=annovar_dir,
        intervar_dir=intervar_dir,
        use_wsl=False,
    )

    assert [command.name for command in commands] == [
        "convert_rsid_to_avinput",
        "table_annovar",
        "intervar_skip_annovar",
    ]
    assert "convert2annovar.pl" in commands[0].bash_command
    assert "-format rsid" in commands[0].bash_command
    assert "table_annovar.pl" in commands[1].bash_command
    assert "-protocol refGene,clinvar_20240917" in commands[1].bash_command
    assert "Intervar.py" in commands[2].bash_command
    assert "--skip_annovar" in commands[2].bash_command


def test_write_current_input_for_full_run_persists_uploaded_text(tmp_path: Path) -> None:
    parsed = parse_consumer_text(
        "rsid,chromosome,position,genotype\nrsTest,1,100,AG\n",
        source_label="uploaded file.csv",
        genome_build="GRCh37/hg19",
    )

    output_path = write_current_input_for_full_run(parsed, tmp_path / "run_test")

    assert output_path.exists()
    assert output_path.name == "uploaded_file.csv"
    assert "rsTest" in output_path.read_text(encoding="utf-8")


def test_filter_avinput_to_primary_contigs_skips_alt_contigs(tmp_path: Path) -> None:
    avinput_path = tmp_path / "converted.avinput"
    avinput_path.write_text(
        "\n".join(
            [
                "chr1\t100\t100\tA\tG\trsPrimary",
                "chr17_ctg5_hap1\t7344\t7344\tG\tA\trsAlt",
                "chrUn_gl000223\t1\t1\tC\tT\trsUn",
                "chrX\t200\t200\tC\tT\trsX",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = filter_avinput_to_primary_contigs(
        avinput_path,
        skipped_path=tmp_path / "converted.non_primary_contigs.avinput",
        log_path=tmp_path / "avinput_primary_contig_filter.json",
    )

    assert summary["kept_primary_contig_rows"] == 2
    assert summary["skipped_non_primary_contig_rows"] == 2
    filtered = avinput_path.read_text(encoding="utf-8")
    assert "rsPrimary" in filtered
    assert "rsX" in filtered
    assert "rsAlt" not in filtered
    assert "rsUn" not in filtered


def test_run_full_intervar_pipeline_with_mocked_subprocess(tmp_path: Path) -> None:
    annovar_dir = tmp_path / "tools/annovar"
    humandb = annovar_dir / "humandb"
    intervar_dir = tmp_path / "tools/InterVar"
    (intervar_dir / "intervardb").mkdir(parents=True)
    humandb.mkdir(parents=True)
    for path in [
        annovar_dir / "convert2annovar.pl",
        annovar_dir / "table_annovar.pl",
        humandb / "hg19_refGene.txt",
        humandb / "hg19_clinvar_20240917.txt",
        intervar_dir / "Intervar.py",
        intervar_dir / "intervardb/mim2gene.txt",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    (humandb / "hg19_snp138.txt").write_text("chr1\t100\t100\tA\tG\trsTest\n", encoding="utf-8")

    input_path = tmp_path / "input.csv"
    input_path.write_text(
        "rsid,chromosome,position,genotype\nrsTest,1,100,AG\n",
        encoding="utf-8",
    )

    output_root = tmp_path / "runs"
    run_dir = output_root / "run_test"
    paths = get_full_intervar_paths(run_dir, annovar_dir, intervar_dir)
    calls: list[str] = []

    def fake_runner(command, cwd=None, text=None, capture_output=None):
        bash_command = command[-1]
        calls.append(bash_command)
        if "convert2annovar.pl" in bash_command:
            paths["converted_avinput"].write_text(
                "chr1\t100\t100\tA\tG\trsTest\n",
                encoding="utf-8",
            )
        elif "table_annovar.pl" in bash_command:
            paths["annovar_multianno"].write_text("header\nrow\n", encoding="utf-8")
        elif "Intervar.py" in bash_command:
            paths["intervar_output"].write_text(
                INTERVAR_HEADER
                + "\n"
                + "\t".join(
                    [
                        "1",
                        "100",
                        "100",
                        "A",
                        "G",
                        "GENE1",
                        "exonic",
                        "nonsynonymous SNV",
                        "clinvar: UNK ",
                        " InterVar: Benign PVS1=0 ",
                        "rsTest",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    run = run_full_intervar_pipeline(
        input_path,
        output_root=output_root,
        run_id="run_test",
        annovar_dir=annovar_dir,
        intervar_dir=intervar_dir,
        command_runner=fake_runner,
        use_wsl=False,
        max_sample_rsids=1,
    )

    assert run.run_dir == run_dir
    assert run.join_back_path.exists()
    assert run.line_counts_path.exists()
    assert paths["intervar_multianno"].exists()
    assert [command.name for command in run.commands] == [
        "convert_rsid_to_avinput",
        "table_annovar",
        "intervar_skip_annovar",
    ]
    assert len(calls) == 3
