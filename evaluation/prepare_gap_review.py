"""Prepare input-only ESCI review packets from frozen, unresolved API pairs.

This creates no reference labels, confirmation reservation or model activation.
Only the reviewer directory should be shared with independent human reviewers.
"""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

from label_quality import canonical, checksum, indexed, query_key, read_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab/search-app"))
from search_filters import validate_filters  # noqa: E402


PRODUCT_FIELDS = ("title", "brand", "description", "bullets", "category_path")
INSTRUCTIONS = """# Review search relevance

Judge how well each product meets the query using its original catalogue text.
Category information can help distinguish the requested product from an accessory.
The market and filters provide search context; they are not model predictions.

1. Read an item in `items.jsonl` and find its `pair_id` in a copy of `labels.csv`.
2. Enter one label: E (Exact), S (Substitute), C (Complement) or I (Irrelevant).
   - Exact: the product satisfies the query.
   - Substitute: a useful alternative with a meaningful difference.
   - Complement: useful with the requested product, rather than a replacement.
   - Irrelevant: does not satisfy or complement the query.
3. If the available information is insufficient, leave the label blank and enter
   `yes` in `uncertain`. Give a short reason for every decision.
4. Return your completed copy to the operator. Keep the pair IDs unchanged.

Do this independently, without model predictions, another reviewer's answers or
the operator directory. Do not infer a label from a missing description or
category alone. Leave unresolved decisions visible for a second review and
adjudication. Do not use a model to supply these human reference labels.

This is a review packet, not a completed quality assessment. Its files do not
establish independent reservation, adequate statistical support or gate eligibility.
"""


def _review_item(row, pair_id):
    product = {
        key: row["product"][key] for key in PRODUCT_FIELDS if key in row["product"]
    }
    request = row["request"]
    for key, value in product.items():
        if key == "category_path":
            valid = isinstance(value, list) and all(
                isinstance(part, str) for part in value
            )
        elif key == "bullets":
            valid = (
                value is None
                or isinstance(value, str)
                or (
                    isinstance(value, list)
                    and all(isinstance(part, str) for part in value)
                )
            )
        else:
            valid = value is None or isinstance(value, str)
        if not valid:
            raise ValueError(
                "Reviewer product fields must contain original text, not nested evidence."
            )
    for key in ("country", "currency"):
        if key in request and (
            not isinstance(request[key], str) or not request[key].strip()
        ):
            raise ValueError("Reviewer market fields must be non-empty text.")
    filters = validate_filters(request.get("filters", {}))
    return {
        "pair_id": pair_id,
        "query": request["query"],
        "market": {
            key: request[key] for key in ("country", "currency") if key in request
        },
        "filters": filters,
        "product": product,
    }


def prepare(inputs_path, exclusions_path, output, queries, seed):
    frozen, audit = read_json(inputs_path), read_json(exclusions_path)
    if frozen.get("kind") != "judgement-pass-inputs":
        raise ValueError("Use the current frozen judgement-pass-inputs contract.")
    context = frozen.get("context")
    if not isinstance(context, dict) or context.get("rubric") != "esci-v1":
        raise ValueError("Frozen gap inputs must retain their ESCI source context.")
    if audit.get("audit_complete") is not True or audit.get(
        "inputs_sha256"
    ) != checksum(inputs_path):
        raise ValueError(
            "A complete exclusion audit must match the frozen input bytes."
        )
    if (
        not isinstance(seed, str)
        or not seed.strip()
        or type(queries) is not int
        or queries <= 0
    ):
        raise ValueError(
            "Choose a non-empty seed and a positive whole-query sample size."
        )
    rows = list(indexed(frozen["pairs"]).values())
    if not rows:
        raise ValueError("The unresolved input pool is empty.")
    groups, identities = defaultdict(list), {}
    for row in rows:
        _review_item(row, "")
        identity = query_key(row["request"]["query"])
        if row["query_id"] in identities and identities[row["query_id"]] != identity:
            raise ValueError(
                "One query identifier refers to different normalised queries."
            )
        identities[row["query_id"]] = identity
        if row["product"].get("product_id") != row["product_id"]:
            raise ValueError("The catalogue product identifier differs from its pair.")
        if (
            not isinstance(row["product"].get("title"), str)
            or not row["product"]["title"].strip()
        ):
            raise ValueError("Every review product needs its original title.")
        groups[identity].append(row)
    excluded_ids = audit.get("query_ids")
    if not isinstance(excluded_ids, list) or any(
        not isinstance(value, str) or value not in identities for value in excluded_ids
    ):
        raise ValueError(
            "The exclusion audit must name query identifiers in this pool."
        )
    # Exclude every alias of a protected normalised query, not just its recorded ID.
    blocked = {identities[value] for value in excluded_ids}
    eligible = set(groups) - blocked
    if queries > len(eligible):
        raise ValueError(
            "The sample exceeds the number of eligible normalised queries."
        )

    def order(identity):
        return hashlib.sha256(canonical([seed, identity])).hexdigest(), identity

    selected = sorted(eligible, key=order)[:queries]
    items, membership, inference_inputs = [], [], []
    for identity in selected:
        for row in sorted(
            groups[identity], key=lambda value: (value["query_id"], value["product_id"])
        ):
            pair_id = hashlib.sha256(
                canonical([seed, row["query_id"], row["product_id"]])
            ).hexdigest()
            items.append(_review_item(row, pair_id))
            membership.append(
                {
                    "pair_id": pair_id,
                    "query_id": row["query_id"],
                    "product_id": row["product_id"],
                    "query_key": identity,
                }
            )
            inference_inputs.append(
                {
                    **{
                        key: row[key]
                        for key in ("query_id", "product_id", "request", "product")
                    },
                    "query_key": identity,
                }
            )
    target = Path(output)
    target.mkdir(parents=True, exist_ok=False)
    operator, reviewer = target / "operator", target / "reviewer"
    operator.mkdir()
    reviewer.mkdir()
    for path, values in [
        (reviewer / "items.jsonl", items),
        (operator / "membership.jsonl", membership),
        (operator / "inputs.jsonl", inference_inputs),
    ]:
        with path.open("xb") as stream:
            for value in values:
                stream.write(canonical(value))
    with (reviewer / "labels.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["pair_id", "label", "uncertain", "reason"])
        writer.writerows([item["pair_id"], "", "", ""] for item in items)
    (reviewer / "README.md").write_text(INSTRUCTIONS, encoding="utf-8")
    manifest = {
        "kind": "esci-blinded-gap-review-packet",
        "status": "prepared-without-reference-labels",
        "inputs_sha256": checksum(inputs_path),
        "exclusions_sha256": checksum(exclusions_path),
        "tool_sha256": checksum(__file__),
        "context": context,
        "selection": {
            "method": "sha256-seeded-whole-query-order",
            "seed": seed,
            "normalisation": "nfkc_html_whitespace_v1",
            "eligible_queries": len(eligible),
            "eligible_pairs": sum(len(groups[key]) for key in eligible),
            "excluded_queries": len(blocked),
            "excluded_pairs": sum(len(groups[key]) for key in blocked),
            "selected_queries": len(selected),
            "selected_pairs": len(items),
            "query_keys": selected,
            "query_inclusion_fraction": queries / len(eligible),
            "all_pairs_for_selected_queries": True,
        },
        "review_product_fields": list(PRODUCT_FIELDS),
        "files_sha256": {
            str(path.relative_to(target)).replace("\\", "/"): checksum(path)
            for path in sorted(target.rglob("*"))
            if path.is_file()
        },
        "reference_labels_created": 0,
        "confirmation_reservation_confirmed": False,
        "gate_eligible": False,
    }
    (operator / "manifest.json").write_bytes(canonical(manifest))
    return {
        "queries": len(selected),
        "pairs": len(items),
        "reference_labels_created": 0,
        "gate_eligible": False,
        "manifest_sha256": checksum(operator / "manifest.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "exclusions", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--queries", type=int, required=True)
    parser.add_argument("--seed", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.inputs, args.exclusions, args.output, args.queries, args.seed),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
