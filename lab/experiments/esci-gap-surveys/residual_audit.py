"""Audit frozen ESCI result gaps using published source metadata, never source labels."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evaluation"))
from label_quality import query_key

METADATA_COLUMNS = (
    "example_id",
    "query",
    "query_id",
    "product_id",
    "product_locale",
    "split",
)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def metadata_rows(path):
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    pa.set_cpu_count(2)
    for batch in pq.ParquetFile(path).iter_batches(
        batch_size=65536, columns=list(METADATA_COLUMNS)
    ):
        table = pa.Table.from_batches([batch])
        table = table.filter(pc.equal(table["product_locale"], "us"))
        yield from table.to_pylist()


def histogram(values):
    return {str(k): v for k, v in sorted(Counter(values).items())}


def analyse(
    observations, judgements, metadata, products, exclusions, exception, threshold=0.8
):
    if (
        observations.get("kind") != "search-variant-observation-set"
        or observations.get("schema_version") != 1
    ):
        raise ValueError("Current frozen variant observations are required.")
    if observations.get("errors") != []:
        raise ValueError("Incomplete capture cannot support a residual audit.")
    variants = sorted(observations["variants"])
    known = set()
    for record in judgements:
        if record.get("gate_eligible") is False or (
            record.get("provenance", {}).get("kind") == "model"
            and record.get("gate_eligible") is not True
        ):
            raise ValueError(
                "This audit requires published or qualified gate references only."
            )
        pair = (str(record["query_id"]), record["product_id"])
        if pair in known:
            raise ValueError("Duplicate frozen judgement pair.")
        known.add(pair)
    needed, positions, requests, normalised = {}, {}, {}, {}
    query_ids = set()
    for row in observations["observations"]:
        qid = row["query_id"]
        if qid in query_ids or set(row["results"]) != set(variants):
            raise ValueError("Duplicate query or incomplete variant capture.")
        query_ids.add(qid)
        requests[qid] = row["request"]["query"]
        normalised[qid] = query_key(requests[qid])
        for variant in variants:
            ids = row["results"][variant]["ids"]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate captured product.")
            needed.setdefault(variant, set()).update((qid, pid) for pid in ids)
            positions.setdefault(variant, {}).update(
                {(qid, pid): rank for rank, pid in enumerate(ids, 1)}
            )
    pooled = set().union(*needed.values())
    residual = pooled - known
    relevant_keys = {normalised[qid] for qid, _ in pooled}
    target = defaultdict(set)
    for qid, pid in pooled:
        target[(normalised[qid], pid)].add((qid, pid))
    source_exact, source_normalised, source_literal = set(), set(), set()
    source_splits, source_rows, alias_pairs = defaultdict(set), 0, set()
    normalisation_cache = {}
    for record in metadata:
        if record["product_locale"] != "us":
            continue
        source_rows += 1
        raw_query = record["query"]
        key = normalisation_cache.setdefault(raw_query, None)
        if key is None:
            key = query_key(raw_query)
            normalisation_cache[raw_query] = key
        if key not in relevant_keys:
            continue
        for pair in target.get((key, record["product_id"]), ()):
            source_normalised.add(pair)
            source_splits[str(record["split"])].add(pair)
            if str(record["query_id"]) == pair[0]:
                source_exact.add(pair)
            else:
                alias_pairs.add(pair)
            if raw_query == requests[pair[0]]:
                source_literal.add(pair)
    recalled_ids = {pid for _, pid in pooled}
    categories = {
        p["product_id"]: str(p.get("category") or "unknown")
        for p in products
        if p["product_id"] in recalled_ids
    }
    if not {pid for _, pid in pooled} <= set(categories):
        raise ValueError("Catalogue does not cover the frozen recall pool.")
    excluded = set(exclusions.get("query_ids", []))
    specialist = set(exception.get("query_ids", []))
    coverage = {}
    for variant in variants:
        pairs = needed[variant]
        judged, missing = pairs & known, pairs - known
        possible = missing & source_normalised
        coverage[variant] = {
            "returned": len(pairs),
            "gate_judged": len(judged),
            "gate_fraction": len(judged) / len(pairs),
            "residual_pairs": len(missing),
            "minimum_additional_labels_for_80_percent": max(
                0, math.ceil(threshold * len(pairs)) - len(judged)
            ),
            "exact_source_query_id_additional_pairs": len(missing & source_exact),
            "normalised_same_query_additional_pairs": len(possible),
            "conditional_metadata_coverage_upper_bound": (len(judged) + len(possible))
            / len(pairs),
            "remaining_required_after_all_metadata_matches": max(
                0, math.ceil(threshold * len(pairs)) - len(judged) - len(possible)
            ),
            "missing_per_query_histogram": histogram(
                sum((qid, pid) in missing for pid in row["results"][variant]["ids"])
                for row in observations["observations"]
                for qid in [row["query_id"]]
            ),
            "judged_per_query_histogram": histogram(
                sum((qid, pid) in judged for pid in row["results"][variant]["ids"])
                for row in observations["observations"]
                for qid in [row["query_id"]]
            ),
            "rank_distribution": {
                str(rank): {
                    "returned": sum(r == rank for r in positions[variant].values()),
                    "missing": sum(positions[variant][p] == rank for p in missing),
                    "metadata_matches": sum(
                        positions[variant][p] == rank for p in possible
                    ),
                }
                for rank in range(1, observations["captured_depth"] + 1)
            },
            "category_distribution": {
                category: {
                    "returned": sum(categories[pid] == category for _, pid in pairs),
                    "missing": sum(categories[pid] == category for _, pid in missing),
                    "metadata_matches": sum(
                        categories[pid] == category for _, pid in possible
                    ),
                }
                for category in sorted({categories[pid] for _, pid in pairs})
            },
        }
    deficits = [
        coverage[v]["minimum_additional_labels_for_80_percent"] for v in variants
    ]
    minimum = None
    if len(variants) == 2:
        shared = len((needed[variants[0]] - known) & (needed[variants[1]] - known))
        minimum = sum(deficits) - min(shared, *deficits)
    return {
        "kind": "esci-residual-source-metadata-audit",
        "schema_version": 1,
        "label_values_read_from_source": False,
        "gate_eligible": False,
        "normalisation": "nfkc_html_whitespace_v1",
        "source_metadata_columns": list(METADATA_COLUMNS),
        "query_count": len(query_ids),
        "normalised_query_groups": len(set(normalised.values())),
        "variants": coverage,
        "baseline_variant": observations["baseline_variant"],
        "pooled_unique_pairs": len(pooled),
        "pooled_gate_judged": len(pooled & known),
        "pooled_residual_pairs": len(residual),
        "unique_recalled_products": len({pid for _, pid in pooled}),
        "minimum_unique_labels_for_both_variants": minimum,
        "published_source_metadata": {
            "english_rows_scanned": source_rows,
            "exact_query_id_pairs": len(source_exact),
            "literal_query_pairs": len(source_literal),
            "normalised_query_pairs": len(source_normalised),
            "normalised_alias_query_id_pairs": len(alias_pairs),
            "additional_residual_pairs": len(residual & source_normalised),
            "additional_by_split": {
                split: len(pairs & residual)
                for split, pairs in sorted(source_splits.items())
            },
        },
        "reservation_constraints": {
            "missing_query_count": len({q for q, _ in residual}),
            "protected_overlap_queries": len({q for q, _ in residual if q in excluded}),
            "protected_overlap_pairs": sum(q in excluded for q, _ in residual),
            "specialist_excluded_queries": len(
                {q for q, _ in residual if q in specialist}
            ),
            "specialist_excluded_pairs": sum(q in specialist for q, _ in residual),
            "isolated_inference_exception_eligible_pairs": sum(
                q in excluded and q not in specialist for q, _ in residual
            ),
        },
        "limits": [
            "Metadata matches identify potential published source labels; their values, disagreement and admission were not inspected.",
            "Coverage upper bounds assume every matched additional source record can be admitted; no records have been imported.",
            "Normalisation permits only the documented same-query identity; no semantic propagation, translated labels or product substitution.",
            "The documented reservation exception permits isolated lab inference, not opening reserved research labels or declaring fresh confirmation.",
            "Missing labels remain unknown; unqualified exploratory predictions do not count towards the 80 percent gate.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "observations",
        "judgements",
        "judgement-manifest",
        "catalogue",
        "source-examples",
        "exclusions",
        "specialist-exclusions",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    started = time.monotonic()
    source_hash = checksum(args.source_examples)
    if source_hash != args.expected_source_sha256:
        raise ValueError("Published source bytes differ from the declared original.")
    manifest = json.loads(args.judgement_manifest.read_bytes())
    observations = json.loads(args.observations.read_bytes())
    if (
        manifest["producer"].get("selection") != "gate"
        or manifest["content"]["sha256"] != checksum(args.judgements)
        or manifest["dependencies"]
        != {
            "catalogue": observations["catalogue_sha256"],
            "query-suite": observations["query_suite_sha256"],
        }
    ):
        raise ValueError("Gate references differ from the frozen comparison.")
    if checksum(args.catalogue) != observations["catalogue_sha256"]:
        raise ValueError("Catalogue bytes differ from the frozen comparison.")
    result = analyse(
        observations,
        list(rows(args.judgements)),
        metadata_rows(args.source_examples),
        rows(args.catalogue),
        json.loads(args.exclusions.read_bytes()),
        json.loads(args.specialist_exclusions.read_bytes()),
    )
    result["source_sha256"] = source_hash
    result["file_sha256"] = {
        name: checksum(getattr(args, name))
        for name in (
            "observations",
            "judgements",
            "judgement_manifest",
            "catalogue",
            "exclusions",
            "specialist_exclusions",
        )
    }
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(
        json.dumps(
            {
                "pooled_residual_pairs": result["pooled_residual_pairs"],
                "minimum_unique_labels": result[
                    "minimum_unique_labels_for_both_variants"
                ],
                "additional_source_metadata_pairs": result["published_source_metadata"][
                    "additional_residual_pairs"
                ],
                "coverage": {
                    v: {
                        k: r[k]
                        for k in (
                            "gate_fraction",
                            "conditional_metadata_coverage_upper_bound",
                            "remaining_required_after_all_metadata_matches",
                        )
                    }
                    for v, r in result["variants"].items()
                },
                "elapsed_seconds": result["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
