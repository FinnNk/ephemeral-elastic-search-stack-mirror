"""Materialise a reserved official-training pool after label-free pair freezing."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evaluation"))
from label_quality import query_key

NORMALISATION = "nfkc_html_whitespace_v1"
SEED = "esci-gap-fitting-products-25-20261004-v1"
CAPACITY_SHA = "b0dd414dac8aefdb4004da6af62af317410e2c58885e81f74e8fb4a2df326008"
CATALOGUE_SHA = "dfe6cecbc7d745a728fbed59679be10af0532be69583f65dc078c8108c25ff50"
RESERVATION_SHA = "27ad8493537e0425b0139e23fbdeab0c48777e9efb66e713cdf51d93e3ac31dc"


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    with Path(path).open("xb") as f:
        f.write(canonical(value))


def query_set(value):
    values = value.get("query_hashes")
    if value.get("normalisation") != NORMALISATION or not isinstance(values, list):
        raise ValueError("Query exclusion metadata has a different contract.")
    if len(values) != len(set(values)) or any(
        not isinstance(q, str) or not re.fullmatch(r"[a-f0-9]{64}", q) for q in values
    ):
        raise ValueError("Invalid or duplicate query hashes.")
    return set(values)


def require_hash(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError("Pinned metadata or source bytes changed: " + Path(path).name)
    return actual


def verify(reservation_path, audit_directory, capacity_directory):
    require_hash(reservation_path, RESERVATION_SHA)
    reservation = read(reservation_path)
    if (
        reservation.get("selection_role") != "fitting"
        or reservation.get("status") != "reserved_for_fitting_only"
        or reservation.get("exclude_from_future_independent_confirmation") is not True
        or any(
            reservation.get(k) is not False
            for k in (
                "labels_read",
                "reference_labels_read",
                "prediction_outputs_read",
                "sealed_row_file_opened",
                "lab_activation_authorised",
            )
        )
        or reservation.get("source_filter")
        != {"large_version": 1, "product_locale": "us", "split": "train"}
    ):
        raise ValueError(
            "Reservation does not authorise this label-free fitting selection."
        )
    selected = query_set(reservation)
    if len(selected) != 1000 or reservation["query_groups"] != 1000:
        raise ValueError("Expected the complete 1,000-query fitting reservation.")
    audit = audit_directory / "selection-audit.json"
    require_hash(audit, reservation["selection_audit_sha256"])
    if query_set(read(audit)) != selected:
        raise ValueError("Owner audit and reservation differ.")
    receipt = read(audit_directory / "verification-receipt.json")
    if (
        receipt.get("reservation_sha256") != RESERVATION_SHA
        or receipt.get("selection_audit_sha256") != digest(audit)
        or receipt.get("excluded_overlap") != 0
        or receipt.get("reference_labels_read") is not False
    ):
        raise ValueError("Owner reservation verification is incomplete.")
    require_hash(audit_directory / "source.py", reservation["sampling_code_sha256"])
    capacity_path = capacity_directory / "audit-receipt.json"
    require_hash(capacity_path, CAPACITY_SHA)
    capacity = read(capacity_path)
    if (
        capacity.get("normalisation") != NORMALISATION
        or capacity.get("labels_read") is not False
        or capacity.get("sealed_row_file_opened") is not False
        or capacity.get("prediction_columns_read") is not False
        or capacity.get("historical_source_inventory_complete") is not True
        or capacity.get("available_official_test_query_groups") != 0
    ):
        raise ValueError("Owner capacity guard is incomplete.")
    exclusions_path = capacity_directory / "exclusions.json"
    available_path = capacity_directory / "available-query-hashes.json"
    require_hash(exclusions_path, capacity["guard_sha256"])
    require_hash(available_path, capacity["available_query_hashes_sha256"])
    excluded = query_set(read(exclusions_path))
    available = query_set(read(available_path))
    if not selected <= available or selected & excluded:
        raise ValueError(
            "Fitting queries overlap protected capacity or are unavailable."
        )
    inventories = {}
    for key in ("reservation_sources_sha256", "exposure_amendments_sha256"):
        declared = reservation[key]
        for path, expected in declared.items():
            require_hash(Path(path), expected)
        directories = {Path(path).parent for path in declared}
        if key == "reservation_sources_sha256":
            directories.add(reservation_path.parent)
        for directory in directories:
            for path in sorted(directory.glob("*.json")):
                if path.resolve() == reservation_path.resolve():
                    continue
                metadata = read(path)
                excluded.update(query_set(metadata))
                inventories[str(path.resolve())] = digest(path)
    if selected & excluded:
        raise ValueError(
            "Fitting queries overlap a current reservation or exposure amendment."
        )
    source = Path(reservation["source_examples_path"])
    require_hash(source, reservation["source_examples_sha256"])
    if capacity["source_examples_sha256"] != reservation["source_examples_sha256"]:
        raise ValueError("Owner source identities differ.")
    return (
        reservation,
        capacity,
        {
            "reservation_sha256": RESERVATION_SHA,
            "selection_audit_sha256": digest(audit),
            "owner_verification_sha256": digest(
                audit_directory / "verification-receipt.json"
            ),
            "capacity_receipt_sha256": CAPACITY_SHA,
            "capacity_exclusions_sha256": digest(exclusions_path),
            "available_query_hashes_sha256": digest(available_path),
            "current_exclusion_metadata_sha256": inventories,
            "excluded_query_groups": len(excluded),
            "overlap_query_groups": 0,
            "historical_exposure_guard_inherited": True,
            "historical_research_row_files_opened": False,
        },
    )


def sample_pairs(metadata, selected, limit=25):
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("Use at most 25 products per query.")
    grouped = {q: {} for q in selected}
    cache = {}
    for row in metadata:
        if "esci_label" in row or "label" in row:
            raise ValueError("Pair selection cannot inspect reference labels.")
        raw = row["query"]
        if raw not in cache:
            cache[raw] = query_key(raw)
        q = cache[raw]
        if q not in grouped:
            continue
        p = row["product_id"]
        old = grouped[q].get(p)
        if old is None or int(row["example_id"]) < int(old["example_id"]):
            grouped[q][p] = row
    if any(not values for values in grouped.values()):
        raise ValueError(
            "Some reserved queries have no eligible official-training pairs."
        )
    result = []
    for q, products in sorted(grouped.items()):
        selected_products = sorted(
            products,
            key=lambda p: (
                hashlib.sha256((SEED + ":" + q + ":" + p).encode()).hexdigest(),
                p,
            ),
        )[:limit]
        for p in selected_products:
            r = products[p]
            result.append(
                {
                    "query_key": q,
                    "query": r["query"],
                    "query_id": str(r["query_id"]),
                    "product_id": p,
                    "source_example_id": int(r["example_id"]),
                }
            )
    if len({r["source_example_id"] for r in result}) != len(result) or len(
        {(r["query_id"], r["product_id"]) for r in result}
    ) != len(result):
        raise ValueError("Selected example or API pair identities are duplicated.")
    return result


def scan_metadata(source, expected_rows):
    import pyarrow as pa
    import pyarrow.dataset as ds

    pa.set_cpu_count(2)
    scanner = ds.dataset(source, format="parquet").scanner(
        columns=["query", "query_id", "product_id", "example_id"],
        filter=(ds.field("split") == "train")
        & (ds.field("large_version") == 1)
        & (ds.field("product_locale") == "us"),
        batch_size=32768,
        use_threads=False,
    )
    seen = 0
    for batch in scanner.to_batches():
        seen += batch.num_rows
        yield from batch.to_pylist()
    if seen != expected_rows:
        raise ValueError("Official-training metadata row count changed.")


def materialise_catalogue(catalogue, selected):
    required = {r["product_id"] for r in selected}
    products = {}
    with gzip.open(catalogue, "rt", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            if p["product_id"] in required:
                if p["product_id"] in products:
                    raise ValueError("Duplicate frozen catalogue product.")
                products[p["product_id"]] = p
    if set(products) != required:
        raise ValueError(
            "Selected published products are absent from the actual catalogue."
        )
    return [
        {
            "query_id": r["query_id"],
            "product_id": r["product_id"],
            "query_key": r["query_key"],
            "request": {
                "query": r["query"],
                "country": "GB",
                "currency": "GBP",
                "filters": {},
            },
            "product": products[r["product_id"]],
        }
        for r in selected
    ]


def selected_references(source, selected, source_sha):
    import pyarrow.dataset as ds

    mapping = {r["source_example_id"]: r for r in selected}
    scanner = ds.dataset(source, format="parquet").scanner(
        columns=["query", "query_id", "product_id", "example_id", "esci_label"],
        filter=(ds.field("split") == "train")
        & (ds.field("large_version") == 1)
        & (ds.field("product_locale") == "us")
        & ds.field("example_id").isin(list(mapping)),
        batch_size=32768,
        use_threads=False,
    )
    refs = {}
    for batch in scanner.to_batches():
        for row in batch.to_pylist():
            r = mapping[int(row["example_id"])]
            if (str(row["query_id"]), row["product_id"], query_key(row["query"])) != (
                r["query_id"],
                r["product_id"],
                r["query_key"],
            ) or row["esci_label"] not in ("E", "S", "C", "I"):
                raise ValueError(
                    "Selected published reference identity or label differs."
                )
            if r["source_example_id"] in refs:
                raise ValueError("Duplicate selected source reference.")
            refs[r["source_example_id"]] = {
                "query_id": r["query_id"],
                "product_id": r["product_id"],
                "label": row["esci_label"],
                "source_example_id": r["source_example_id"],
                "provenance": {
                    "kind": "published",
                    "source_id": source_sha,
                    "source_split": "train",
                },
            }
    if set(refs) != set(mapping):
        raise ValueError("Selected reference labels are incomplete.")
    return [refs[r["source_example_id"]] for r in selected]


def run(args):
    started = time.monotonic()
    reservation, capacity, exposure = verify(
        args.reservation, args.audit_directory, args.capacity_directory
    )
    require_hash(args.catalogue, CATALOGUE_SHA)
    args.output.mkdir(parents=True, exist_ok=False)
    source = Path(reservation["source_examples_path"])
    selected = sample_pairs(
        scan_metadata(source, capacity["official_train_rows"]), query_set(reservation)
    )
    inputs = materialise_catalogue(args.catalogue, selected)
    with (args.output / "inputs.jsonl").open("xb") as f:
        for row in inputs:
            f.write(canonical(row))
    selection = {
        "kind": "esci-fitting-pair-selection",
        "schema_version": 1,
        "role": "fitting",
        "normalisation": NORMALISATION,
        "seed": SEED,
        "max_products_per_query": 25,
        "query_groups": len(query_set(reservation)),
        "pairs": len(selected),
        "membership": selected,
        "source_sha256": reservation["source_examples_sha256"],
        "catalogue_sha256": CATALOGUE_SHA,
        "source_code_sha256": digest(__file__),
        "input_sha256": digest(args.output / "inputs.jsonl"),
        "references_opened": False,
        "gate_eligible": False,
        "owner": exposure,
    }
    write_new(args.output / "selection-before-labels.json", selection)
    frozen_selection_sha = digest(args.output / "selection-before-labels.json")
    # Recheck ownership and every input byte immediately before opening selected gold.
    verify(args.reservation, args.audit_directory, args.capacity_directory)
    require_hash(args.output / "inputs.jsonl", selection["input_sha256"])
    refs = selected_references(source, selected, reservation["source_examples_sha256"])
    require_hash(args.output / "selection-before-labels.json", frozen_selection_sha)
    with (args.output / "references.jsonl").open("xb") as f:
        for row in refs:
            f.write(canonical(row))
    exposure.update(
        {
            "kind": "esci-fitting-overlap-exposure-receipt",
            "role": "fitting",
            "query_groups": 1000,
            "exclude_from_future_confirmation": True,
            "official_test_rows_materialised": 0,
            "selected_published_labels_opened": len(refs),
            "reserved_reference_outputs_opened": False,
            "gate_eligible": False,
            "selection_before_labels_sha256": frozen_selection_sha,
        }
    )
    write_new(args.output / "overlap-exposure-receipt.json", exposure)
    manifest = {
        "kind": "esci-fitting-pool",
        "schema_version": 1,
        "role": "fitting",
        "query_groups": 1000,
        "pairs": len(inputs),
        "unique_products": len({r["product_id"] for r in inputs}),
        "normalisation": NORMALISATION,
        "max_products_per_query": 25,
        "class_counts": dict(sorted(Counter(r["label"] for r in refs).items())),
        "files_sha256": {
            name: digest(args.output / name)
            for name in (
                "inputs.jsonl",
                "references.jsonl",
                "selection-before-labels.json",
                "overlap-exposure-receipt.json",
            )
        },
        "source_sha256": reservation["source_examples_sha256"],
        "catalogue_sha256": CATALOGUE_SHA,
        "source_code_sha256": digest(__file__),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "gate_eligible": False,
        "limits": [
            "Published official-training labels, not independent confirmation.",
            "Products retain canonical API fields. Synthetic price, stock and popularity must never enter relevance features.",
            "No labels or example/query/product identifiers may enter model features.",
            "Owner historical exposure guard is inherited; protected research row files were not opened.",
        ],
    }
    write_new(args.output / "manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "limits"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "reservation",
        "audit-directory",
        "capacity-directory",
        "catalogue",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
