from src.preprocessing.snp_to_vcf import (
    extract_resolved_alleles,
    genotype_to_vcf_gt,
    convert_variant_to_vcf_row,
)
from src.workbench.input_parser import parse_consumer_text


def test_genotype_to_vcf_gt_for_heterozygous_ref_alt():
    assert genotype_to_vcf_gt("AG", "A", ["G"]) == "0/1"


def test_extract_myvariant_hgvs_ids():
    payload = {"hits": [{"_id": "chr1:g.752721A>G"}, {"_id": "bad"}]}

    alleles = extract_resolved_alleles(payload)

    assert len(alleles) == 1
    assert alleles[0].chrom == "1"
    assert alleles[0].pos == 752721
    assert alleles[0].ref == "A"
    assert alleles[0].alt == "G"


def test_convert_variant_to_vcf_row_matches_forward_ref_alt():
    parsed = parse_consumer_text(
        "# rsid,chromosome,position,genotype\nrs3131972,1,752721,AG\n",
        "sample.csv",
        genome_build="GRCh37/hg19",
    )
    alleles = extract_resolved_alleles(
        {
            "hits": [
                {"_id": "chr1:g.752721A>T"},
                {"_id": "chr1:g.752721A>C"},
                {"_id": "chr1:g.752721A>G"},
            ]
        }
    )

    row = convert_variant_to_vcf_row(parsed.variants[0], alleles)

    assert row.status == "converted"
    assert row.vcf_chrom == "1"
    assert row.vcf_pos == 752721
    assert row.vcf_ref == "A"
    assert row.vcf_alt == "G"
    assert row.vcf_gt == "0/1"
