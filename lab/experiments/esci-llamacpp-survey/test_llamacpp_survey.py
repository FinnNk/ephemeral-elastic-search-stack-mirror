"""Isolated CPU survey boundaries retain exact contracts and reject unsafe inputs."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "llamacpp_survey", Path(__file__).with_name("llamacpp_survey.py")
)
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def test_archive_paths_cannot_escape_runtime(tmp_path):
    for name in (
        "../outside.dll",
        "nested/../../outside.dll",
        "C:/outside.dll",
        "nested\\outside.dll",
    ):
        with pytest.raises(ValueError, match="archive|Archive"):
            survey.safe_archive_target(tmp_path, name)
    assert (
        survey.safe_archive_target(tmp_path, "bin/llama-server.exe")
        == (tmp_path / "bin/llama-server.exe").resolve()
    )


def test_existing_download_hash_mismatch_never_overwrites(tmp_path):
    destination = tmp_path / "runtime.zip"
    destination.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="pinned"):
        survey.download("https://invalid.example", destination, "a" * 64, 5)
    assert destination.read_bytes() == b"wrong"


def test_frozen_prompt_contract_handles_nullable_original_data():
    original, _ = survey.original_contracts()
    row = {
        "request": {"query": "phone case"},
        "product": {
            "title": "Case",
            "category_path": None,
            "brand": None,
            "description": None,
            "bullets": None,
        },
    }
    for contract in original.CONTRACTS:
        system, query, product = original.prompt_parts(row, contract)
        assert "phone case" in query
        assert "E:" in system
        assert "Case" in product
    assert survey.GRAMMAR == 'root ::= "E" | "S" | "C" | "I"'


def test_official_assets_fit_download_budget():
    assert survey.ARCHIVE_SIZE + survey.MODEL_SIZE < 1500 * 1024**2
    assert "win-cpu-x64" in survey.ARCHIVE_URL
    assert survey.MODEL_REVISION in survey.MODEL_URL


def test_paired_diagnostic_counts_transitions_and_retains_query_clustering():
    spec = importlib.util.spec_from_file_location(
        "package_evidence", Path(__file__).with_name("package_evidence.py")
    )
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    result = package.paired(
        ["E"] * 10 + ["I"] * 10,
        ["I"] * 10 + ["E"] * 10,
        ["I"] * 20,
        ["query-a"] * 10 + ["query-b"] * 10,
        1000,
        20261004,
    )
    assert result["changed"] == 20
    assert result["left_wrong_right_right"] == 10
    assert result["left_right_right_wrong"] == 10
    assert result["query_groups"] == 2
    assert result["descriptive_query_bootstrap_95_interval"] == [-1, 1]


def test_paired_diagnostic_rejects_mismatched_membership():
    spec = importlib.util.spec_from_file_location(
        "package_evidence", Path(__file__).with_name("package_evidence.py")
    )
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    with pytest.raises(ValueError, match="matched"):
        package.paired(["E"], [], ["E"], ["query"], 1000, 1)
