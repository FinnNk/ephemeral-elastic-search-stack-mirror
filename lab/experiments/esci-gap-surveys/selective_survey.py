"""Run a fixed CPU-only survey on exposed development labels, never confirmation."""

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evaluation"))
from label_quality import LABELS, canonical, indexed, query_key

STATE = Path(
    os.environ.get("LAB_STATE_DIR", Path(__file__).resolve().parents[3] / ".lab")
)
DEVELOPMENT = STATE / "esci-packaging/label-calibration-20261003"
SEED = "esci-selective-survey-v1"
STOP = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
KNOWN_BRANDS = {
    "apple",
    "samsung",
    "sony",
    "nokia",
    "adidas",
    "nike",
    "lenovo",
    "dell",
    "hp",
    "canon",
    "nikon",
    "bose",
    "logitech",
    "asus",
    "acer",
    "lego",
    "bosch",
    "dewalt",
    "makita",
    "whirlpool",
    "frigidaire",
    "craftsman",
    "microsoft",
}
ACCESSORIES = {
    "case",
    "cover",
    "covers",
    "charger",
    "cable",
    "replacement",
    "adapter",
    "accessory",
    "accessories",
    "mount",
    "holder",
    "refill",
}


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower())) - STOP


def features(pair):
    """Use request and catalogue fields only; reference labels are not available here."""
    product = pair["product"]
    query = tokens(pair["request"]["query"])
    title = tokens(product.get("title", ""))
    brand = tokens(product.get("brand", ""))
    models = {word for word in query if any(char.isdigit() for char in word)}
    category = product.get("category_path", [])
    category_tokens = tokens(" ".join(str(value) for value in category))
    requested_brands = query & KNOWN_BRANDS
    brand_conflict = (
        bool(requested_brands)
        and bool(brand)
        and not bool(requested_brands & brand)
        and not bool(requested_brands & title)
    )
    return {
        "query_length": len(query),
        "overlap": len(query & title) / len(query) if query else 0,
        "brand_in_query": bool(brand) and brand <= query,
        "model_query": bool(models),
        "model_compatible": not models or models <= title,
        "accessory_query": bool(query & ACCESSORIES),
        "accessory_product": bool(title & ACCESSORIES),
        "category_available": bool(category),
        "category_depth": len(category),
        "requested_brand": bool(requested_brands),
        "brand_conflict": brand_conflict,
        "brand_missing": not bool(brand),
        "positive_category": bool(query & category_tokens),
    }


def rules():
    """Predeclared small survey; no rules are generated from reference outcomes."""
    result = [
        {"name": "baseline-090", "thresholds": [0.9] * 4},
        {"name": "baseline-095", "thresholds": [0.95] * 4},
    ]
    for threshold in (0.9, 0.95):
        for margin in (0.25, 0.5):
            result.append(
                {
                    "name": f"all-{threshold}-margin-{margin}",
                    "thresholds": [threshold] * 4,
                    "margin": margin,
                }
            )
        for entropy in (0.25, 0.5):
            result.append(
                {
                    "name": f"all-{threshold}-entropy-{entropy}",
                    "thresholds": [threshold] * 4,
                    "entropy": entropy,
                }
            )
        for veto in (
            "overlap-025",
            "overlap-050",
            "model-mismatch",
            "accessory-mismatch",
            "model-or-accessory",
            "overlap-model-accessory",
        ):
            result.append(
                {
                    "name": f"all-{threshold}-exact-veto-{veto}",
                    "thresholds": [threshold] * 4,
                    "exact_veto": veto,
                }
            )
    for label in ("S", "C", "I"):
        for threshold in (0.7, 0.8, 0.9, 0.95):
            selected = [None] * 4
            selected[LABELS.index(label)] = threshold
            result.append(
                {"name": f"specialist-{label}-{threshold}", "thresholds": selected}
            )
    for threshold in (0.7, 0.8, 0.9):
        result.append(
            {
                "name": f"exact-095-nonexact-{threshold}",
                "thresholds": [0.95, threshold, threshold, threshold],
            }
        )
    for slice_name in (
        "short-query",
        "long-query",
        "brand-present",
        "model-query",
        "accessory-query",
        "category-available",
        "category-depth-2",
    ):
        result.append(
            {
                "name": "slice-095-" + slice_name,
                "thresholds": [0.95] * 4,
                "slice": slice_name,
            }
        )
    return result


def accepts(scores, observable, rule):
    winner = int(np.argmax(scores))
    threshold = rule["thresholds"][winner]
    if threshold is None or max(scores) < threshold:
        return False
    ordered = sorted(scores, reverse=True)
    if ordered[0] - ordered[1] < rule.get("margin", 0):
        return False
    entropy = -sum(p * math.log(p) for p in scores if p) / math.log(4)
    if entropy > rule.get("entropy", 1):
        return False
    veto = rule.get("exact_veto", "")
    model_mismatch = observable["model_query"] and not observable["model_compatible"]
    accessory_mismatch = (
        observable["accessory_query"] != observable["accessory_product"]
    )
    if winner == 0:
        if veto == "overlap-025" and observable["overlap"] < 0.25:
            return False
        if veto == "overlap-050" and observable["overlap"] < 0.5:
            return False
        if veto == "model-mismatch" and model_mismatch:
            return False
        if veto == "accessory-mismatch" and accessory_mismatch:
            return False
        if veto in ("model-or-accessory", "overlap-model-accessory") and (
            model_mismatch or accessory_mismatch
        ):
            return False
        if veto == "overlap-model-accessory" and observable["overlap"] < 0.25:
            return False
        if veto in ("numeric-brand", "numeric-brand-category") and (
            model_mismatch or observable["brand_conflict"]
        ):
            return False
        if veto == "numeric-brand-category" and not observable["positive_category"]:
            return False
        if (
            veto in ("numeric", "numeric-brand", "numeric-brand-category")
            and model_mismatch
        ):
            return False
    slices = {
        "short-query": observable["query_length"] <= 3,
        "long-query": observable["query_length"] >= 6,
        "brand-present": observable["brand_in_query"],
        "model-query": observable["model_query"],
        "accessory-query": observable["accessory_query"],
        "category-available": observable["category_available"],
        "category-depth-2": observable["category_depth"] >= 2,
    }
    return slices.get(rule.get("slice"), True)


def intervals(queries, numerator, denominator, repetitions=2000):
    _, groups = np.unique(queries, return_inverse=True)
    n = int(groups.max()) + 1
    sums = np.column_stack(
        [
            np.bincount(groups, weights=values, minlength=n)
            for values in (numerator, denominator)
        ]
    )
    rng = np.random.default_rng(20261003)
    samples = sums[rng.integers(n, size=(repetitions, n))].sum(axis=1)
    if np.any(samples[:, 1] == 0):
        return None
    return np.quantile(samples[:, 0] / samples[:, 1], [0.025, 0.975]).tolist()


def metrics(queries, truth, emitted, baseline):
    accepted = emitted >= 0
    correct = accepted & (emitted == truth)
    harmful = (truth == 3) & (emitted == 0)
    irrelevant, exact = truth == 3, emitted == 0
    extra = accepted & (baseline < 0)
    n, count = len(truth), int(accepted.sum())
    harmful_count = int(harmful.sum())
    i_queries = len(set(queries[irrelevant]))
    e_queries = len(set(queries[exact]))
    return {
        "pairs": n,
        "queries": len(set(queries)),
        "accepted": count,
        "coverage": count / n,
        "correct": int(correct.sum()),
        "precision": int(correct.sum()) / count if count else None,
        "precision_query_bootstrap_95": intervals(queries, correct, accepted),
        "coverage_query_bootstrap_95": intervals(queries, accepted, np.ones(n)),
        "harmful_I_to_E": harmful_count,
        "I_to_E_rate": harmful_count / int(irrelevant.sum())
        if irrelevant.any()
        else None,
        "I_to_E_query_bootstrap_95": intervals(queries, harmful, irrelevant),
        "exact_contamination": harmful_count / int(exact.sum())
        if exact.any()
        else None,
        "exact_contamination_query_bootstrap_95": intervals(queries, harmful, exact),
        "I_queries": i_queries,
        "accepted_E_queries": e_queries,
        "zero_I_to_E_query_incidence_95_upper": 1 - 0.05 ** (1 / i_queries)
        if i_queries and not harmful_count
        else None,
        "zero_exact_contamination_query_incidence_95_upper": 1 - 0.05 ** (1 / e_queries)
        if e_queries and not harmful_count
        else None,
        "extra_accepted_vs_095": int(extra.sum()),
        "extra_correct_vs_095": int((extra & correct).sum()),
        "extra_wrong_vs_095": int((extra & ~correct).sum()),
        "correct_change_vs_095": int(
            correct.sum() - ((baseline >= 0) & (baseline == truth)).sum()
        ),
        "accepted_classes": {
            label: int((emitted == c).sum()) for c, label in enumerate(LABELS)
        },
        "confusion": {
            label: {
                out: int(((truth == c) & (emitted == k)).sum())
                for k, out in enumerate(LABELS)
            }
            | {"abstain": int(((truth == c) & (emitted < 0)).sum())}
            for c, label in enumerate(LABELS)
        },
    }


def survey(inputs, references, predictions, declared_rules):
    pairs, gold, observed = indexed(inputs), indexed(references), indexed(predictions)
    if not pairs or pairs.keys() != gold.keys() or pairs.keys() != observed.keys():
        raise ValueError("Exactly matching development pairs are required.")
    keys = sorted(pairs)
    observables, scores, queries, truth = [], [], [], []
    for key in keys:
        pair, prediction = pairs[key], observed[key]
        if pair["query_key"] != query_key(pair["request"]["query"]):
            raise ValueError("Query identity differs from input.")
        actual_input = {
            name: pair[name]
            for name in ("query_id", "product_id", "request", "product")
        }
        if prediction["input_sha256"] != sha256(canonical(actual_input)).hexdigest():
            raise ValueError("Prediction input differs.")
        if (
            gold[key]["provenance"]["kind"] != "published"
            or gold[key]["label"] not in LABELS
        ):
            raise ValueError("Published development references are required.")
        values = prediction["probabilities"]
        if (
            len(values) != 4
            or any(
                not isinstance(v, (float, int))
                or isinstance(v, bool)
                or not math.isfinite(v)
                or not 0 <= v <= 1
                for v in values
            )
            or not math.isclose(sum(values), 1, abs_tol=1e-6)
        ):
            raise ValueError(
                "Four valid probabilities required; inference must be complete."
            )
        observables.append(features(pair))
        scores.append(values)
        queries.append(pair["query_key"])
        truth.append(LABELS.index(gold[key]["label"]))
    queries, truth = np.array(queries), np.array(truth)
    split = np.array(
        [int(sha256((SEED + key).encode()).hexdigest(), 16) % 2 for key in queries]
    )
    baseline = np.array(
        [int(np.argmax(value)) if max(value) >= 0.95 else -1 for value in scores]
    )
    results = []
    for rule in declared_rules:
        emitted = np.array(
            [
                int(np.argmax(value)) if accepts(value, observable, rule) else -1
                for value, observable in zip(scores, observables, strict=True)
            ]
        )
        result = {
            "rule": rule,
            "all": metrics(queries, truth, emitted, baseline),
            "halves": {
                str(half): metrics(
                    queries[split == half],
                    truth[split == half],
                    emitted[split == half],
                    baseline[split == half],
                )
                for half in (0, 1)
            },
        }
        results.append(result)
    return {
        "kind": "esci-selective-development-survey",
        "gate_eligible": False,
        "confirmation_read": False,
        "split_seed": SEED,
        "pairs": len(keys),
        "queries": len(set(queries)),
        "rules": results,
        "feature_counts": {
            name: sum(bool(value[name]) for value in observables)
            for name in (
                "brand_in_query",
                "model_query",
                "accessory_query",
                "category_available",
            )
        },
        "limits": [
            "Development evidence only: rules are screened, not qualified, and query halves are not independent confirmation.",
            "Zero-event query bounds concern query incident probability, not pair risk.",
            "Published development pairs need not represent unlabelled search-result gaps.",
            "Lexical mismatch is a veto, never a generated Irrelevant reference label.",
        ],
    }


def followup_rules():
    """Second-stage rules are declared before measuring their development outcomes."""
    result = []
    for threshold in (0.90, 0.925, 0.95, 0.975):
        for veto in (None, "numeric", "numeric-brand", "numeric-brand-category"):
            result.append(
                {
                    "name": f"exact-{threshold}-{veto or 'plain'}",
                    "thresholds": [threshold, None, None, None],
                    **({"exact_veto": veto} if veto else {}),
                }
            )
    return result


def gap_projection(inputs, saved_pass, declared_rules):
    """Count hypothetical labels using saved gap inputs/scores, with no ground truth."""
    if saved_pass.get("complete") is not True or len(saved_pass["records"]) != 6920:
        raise ValueError("The complete, frozen 6,920-pair lab pass is required.")
    pairs, observed = indexed(inputs["pairs"]), indexed(saved_pass["records"])
    if not observed.keys() <= pairs.keys() or len(pairs) - len(observed) != 49:
        raise ValueError("Saved records must retain exactly the specialist exclusions.")
    known = {tuple(pair) for pair in inputs["known"]}
    if known & observed.keys():
        raise ValueError("A gap record overlaps an already known pair.")
    keys = sorted(observed)
    observables, scores = [], []
    for key in keys:
        pair, prediction = pairs[key], observed[key]
        actual = {
            name: pair[name]
            for name in ("query_id", "product_id", "request", "product")
        }
        if sha256(canonical(actual)).hexdigest() != prediction["input_sha256"]:
            raise ValueError("Saved gap prediction belongs to different input.")
        values = prediction["probabilities"]
        if (
            len(values) != 4
            or any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or not 0 <= v <= 1
                for v in values
            )
            or not math.isclose(sum(values), 1, abs_tol=1e-6)
        ):
            raise ValueError("All saved gap probabilities must be valid.")
        observables.append(features(pair))
        scores.append(values)
    projections = []
    baseline_095 = {
        key for key, value in zip(keys, scores, strict=True) if max(value) >= 0.95
    }
    for rule in declared_rules:
        accepted = {
            key
            for key, values, observable in zip(keys, scores, observables, strict=True)
            if accepts(values, observable, rule)
        }
        sides = {}
        for name, raw_pairs in inputs["sides"].items():
            side = {tuple(pair) for pair in raw_pairs}
            before = len(side & known)
            added = len(side & accepted)
            required = len(side)
            sides[name] = {
                "required": required,
                "actual_gate_eligible": before,
                "actual_gate_coverage": before / required,
                "hypothetical_added_if_qualified": added,
                "hypothetical_coverage_if_qualified": (before + added) / required,
                "remaining_to_80_if_qualified": max(
                    0, math.ceil(0.8 * required) - before - added
                ),
            }
        projections.append(
            {
                "rule": rule,
                "accepted_gap_pairs": len(accepted),
                "accepted_gap_queries": len(
                    {pairs[key]["query_id"] for key in accepted}
                ),
                "extra_vs_095": len(accepted - baseline_095),
                "removed_vs_095": len(baseline_095 - accepted),
                "sides": sides,
            }
        )
    return {
        "gate_eligible": False,
        "reference_labels_read": False,
        "eligible_pairs": len(observed),
        "specialist_pairs_excluded": len(pairs) - len(observed),
        "rules": projections,
        "observable_counts": {
            name: sum(bool(feature[name]) for feature in observables)
            for name in (
                "model_query",
                "model_compatible",
                "requested_brand",
                "brand_conflict",
                "brand_missing",
                "category_available",
                "positive_category",
            )
        },
    }


def run_followup(development, output):
    gaps = STATE / "esci-packaging/progressive-20261003"
    paths = {
        "inputs": development / "inputs.jsonl",
        "references": development / "references.jsonl",
        "predictions": development / "inference-01/predictions.jsonl",
        "manifest": development / "manifest.json",
        "gap_inputs": gaps / "inputs.json",
        "gap_pass": gaps / "first-pass/pass.json",
    }
    declared = followup_rules()
    hashes = {
        name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()
    }
    plan = {
        "kind": "esci-selective-followup-plan",
        "rules": declared,
        "hashes": hashes,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "split_seed": SEED,
        "bootstrap_repetitions": 2000,
        "reason": "Preserved initial44-rule survey suggested numeric-model veto; this fixed follow-up is development only.",
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(canonical(plan))
    manifest = json.loads(paths["manifest"].read_bytes())
    if (
        manifest.get("selection_role") != "development"
        or manifest.get("cohort") != "published"
    ):
        raise ValueError("Published, exposed development data only.")
    for name in ("inputs", "references"):
        if hashes[name] != manifest[name + "_sha256"]:
            raise ValueError("Frozen development bytes differ.")
    rows = {
        name: [
            json.loads(line) for line in paths[name].read_bytes().splitlines() if line
        ]
        for name in ("inputs", "references", "predictions")
    }
    report = survey(rows["inputs"], rows["references"], rows["predictions"], declared)
    gap_inputs, gap_pass = (
        json.loads(paths["gap_inputs"].read_bytes()),
        json.loads(paths["gap_pass"].read_bytes()),
    )
    if hashes["gap_inputs"] != gap_pass["inputs_sha256"]:
        raise ValueError("Saved pass belongs to different gap inputs.")
    report["gap_projection"] = gap_projection(gap_inputs, gap_pass, declared)
    report["plan_sha256"] = sha256(canonical(plan)).hexdigest()
    (output / "report.json").write_bytes(canonical(report))
    print(
        json.dumps(
            {
                "pairs": report["pairs"],
                "queries": report["queries"],
                "rules": len(declared),
                "output": str(output),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, default=DEVELOPMENT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--followup", action="store_true")
    args = parser.parse_args()
    if args.development.resolve() != DEVELOPMENT.resolve():
        raise ValueError(
            "This survey may read only the authorised exposed development cohort."
        )
    if args.followup:
        run_followup(args.development, args.output)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    paths = {
        name: args.development / filename
        for name, filename in {
            "inputs": "inputs.jsonl",
            "references": "references.jsonl",
            "predictions": "inference-01/predictions.jsonl",
            "manifest": "manifest.json",
        }.items()
    }
    manifest = json.loads(paths["manifest"].read_bytes())
    if (
        manifest.get("selection_role") != "development"
        or manifest.get("cohort") != "published"
    ):
        raise ValueError("An exposed, published development cohort is required.")
    declared = rules()
    hashes = {
        name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()
    }
    for name in ("inputs", "references"):
        if hashes[name] != manifest[name + "_sha256"]:
            raise ValueError("Frozen development bytes differ.")
    plan = {
        "kind": "esci-selective-survey-plan",
        "rules": declared,
        "hashes": hashes,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "bootstrap_repetitions": 2000,
        "split_seed": SEED,
    }
    (args.output / "plan.json").write_bytes(canonical(plan))
    rows = {
        name: [
            json.loads(line) for line in paths[name].read_bytes().splitlines() if line
        ]
        for name in ("inputs", "references", "predictions")
    }
    report = survey(rows["inputs"], rows["references"], rows["predictions"], declared)
    report["plan_sha256"] = sha256(canonical(plan)).hexdigest()
    (args.output / "report.json").write_bytes(canonical(report))
    print(
        json.dumps(
            {
                "pairs": report["pairs"],
                "queries": report["queries"],
                "rules": len(declared),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
