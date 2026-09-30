"""Export local-only reference canaries from the already-opened round-two cohort."""

from pathlib import Path

from .contract import clean, map_scores, model_state, outcome
from .release import content_digest, read_json, sha256, verify_bundle, write_json


def export_canaries(
    research: Path, bundle: Path, output: Path, count: int = 64
) -> dict:
    import numpy as np
    import pandas as pd

    manifest = verify_bundle(bundle)
    mapping, policy = (
        read_json(bundle / "score-mapping.json"),
        read_json(bundle / "policy.json"),
    )
    source = research / "artifacts/evaluations/round-2"
    metadata = source / "cohorts-v2/confirmation.parquet"
    signals = source / "signals/v3_8192/confirmation.parquet"
    archive = source / "decision-confirmation/probabilities.npz"
    rows = pd.read_parquet(metadata).sort_values("input_hash").reset_index(drop=True)
    raw = pd.read_parquet(signals).sort_values("input_hash").reset_index(drop=True)
    if not rows.input_hash.equals(raw.input_hash) or not rows.label.equals(raw.gold):
        raise ValueError("Research input identity/label alignment failed.")
    expected = np.load(archive)["v3_8192:scores:C0.1"]
    mapped = np.array(
        [map_scores(list(values), mapping) for values in raw.probabilities]
    )
    if mapped.shape != expected.shape or not np.allclose(
        mapped, expected, rtol=0, atol=1e-12
    ):
        raise ValueError(
            "Exported mapping does not reproduce the frozen research probabilities."
        )
    if not 8 <= count <= min(len(rows), 128):
        raise ValueError("Use 8–128 spread canaries.")
    canaries = []
    for index in np.linspace(0, len(rows) - 1, count, dtype=int):
        row = rows.iloc[index]
        pair = {
            "query_id": f"canary-{index}",
            "product_id": row.product_id,
            "request": {"query": row["query"]},
            "product": {
                "title": row["title"],
                "taxonomy_path": list(row["taxonomy_path"]),
            },
        }
        # The prepared cohort stores the full path; the v3 signal records the
        # separate hash of its leaf-only input. Verify that actual model input.
        leaf = [clean(part) for part in list(row["taxonomy_path"])[-1:] if clean(part)]
        canonical = {
            "schema_version": "esci-title_leaf_category-v1",
            "query": clean(row["query"]),
            "title": clean(row["title"]),
            "taxonomy_path": leaf,
            "locale": clean(row["locale"]) if row["locale"] else None,
        }
        if content_digest(canonical) != raw.iloc[index]["model_input_hash"]:
            raise ValueError(
                "Serving input differs from the saved v3 model-input hash."
            )
        expected_state = (
            f"Query:\n{canonical['query']}\n\nProduct title:\n{canonical['title']}"
            f"\n\nProduct category:\n{' > '.join(leaf) if leaf else 'Unknown'}"
        )
        if model_state(pair) != expected_state:
            raise ValueError("Serving text differs from the saved v3 model input.")
        canaries.append(
            {"input": pair, "expected": outcome(mapped[index].tolist(), policy)}
        )
    result = {
        "origin": "frozen-research-scores",
        "release_sha256": manifest["release_sha256"],
        "source_sha256": {
            p.relative_to(source).as_posix(): sha256(p)
            for p in (metadata, signals, archive)
        },
        "mapping_verification": {
            "rows": len(rows),
            "max_probability_delta": float(np.abs(mapped - expected).max()),
        },
        "rows": canaries,
    }
    if output.exists():
        raise FileExistsError("Preserve existing canaries; choose a new output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return {
        "rows": len(canaries),
        "mapping_verification": result["mapping_verification"],
        "reference_sha256": sha256(output),
    }
