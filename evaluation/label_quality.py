"""Assess a frozen ESCI candidate against independently sourced reference labels."""

import argparse
from collections import Counter
import html
from html.parser import HTMLParser
import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np

LABELS = ("E", "S", "C", "I")


class _QueryText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def query_key(value):
    from hashlib import sha256

    if not isinstance(value, str) or not value.strip():
        raise ValueError("A non-empty original query is required.")
    text = unicodedata.normalize("NFKC", value)
    if re.search(r"</?[A-Za-z][^>]*>", text):
        parser = _QueryText()
        parser.feed(text)
        text = "".join(parser.parts)
    normalised = " ".join(html.unescape(text).lower().split())
    return sha256(normalised.encode()).hexdigest()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def checksum(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines() if line]


def indexed(rows):
    result = {}
    for row in rows:
        key = (row["query_id"], row["product_id"])
        if not all(isinstance(value, str) and value for value in key):
            raise ValueError(
                "Quality evidence needs non-empty string pair identifiers."
            )
        if key in result:
            raise ValueError("Duplicate query/product pair in quality evidence.")
        result[key] = row
    return result


def bootstrap(queries, numerators, denominators, repetitions, seed):
    """Resample whole normalised queries and retain the pair-weighted ratio."""
    unique, groups = np.unique(queries, return_inverse=True)
    sums = np.zeros((len(unique), 2))
    np.add.at(sums, groups, np.column_stack((numerators, denominators)))
    estimates = np.empty(repetitions)
    rng = np.random.default_rng(seed)
    for start in range(0, repetitions, 100):
        selected = rng.integers(
            len(unique), size=(min(100, repetitions - start), len(unique))
        )
        sampled = sums[selected].sum(axis=1)
        values = np.divide(
            sampled[:, 0],
            sampled[:, 1],
            out=np.full(len(sampled), np.nan),
            where=sampled[:, 1] != 0,
        )
        estimates[start : start + len(values)] = values
    if not np.isfinite(estimates).all():
        return None
    return np.quantile(estimates, [0.025, 0.975]).tolist()


def assess(inputs, references, predictions, manifest, audit, policy):
    if (
        manifest.get("kind") != "esci-label-quality-cohort"
        or manifest.get("reservation_confirmed") is not True
        or not manifest.get("reservation_sha256")
        or audit.get("kind") != "esci-query-independence-audit"
        or audit.get("audit_complete") is not True
        or audit.get("normalisation") != "nfkc_html_whitespace_v1"
    ):
        raise ValueError(
            "A frozen cohort and complete independence audit are required."
        )
    if (
        policy.get("kind") != "esci-label-quality-policy"
        or policy.get("schema_version") != 1
    ):
        raise ValueError("A current frozen quality policy is required.")
    cohort = manifest.get("cohort")
    if cohort not in policy["required_cohorts"]:
        raise ValueError("Quality cohort must be published or human-gap.")
    pairs, gold, observed = indexed(inputs), indexed(references), indexed(predictions)
    if not pairs or pairs.keys() != gold.keys() or pairs.keys() != observed.keys():
        raise ValueError(
            "Inputs, references and predictions must contain exactly the same pairs."
        )
    blocked = set(audit["excluded_query_keys"])
    allowed = set(manifest["query_keys"])
    queries, truth, emitted, failures = [], [], [], []
    from hashlib import sha256

    for key in sorted(pairs):
        pair, reference, prediction = pairs[key], gold[key], observed[key]
        identity = pair["query_key"]
        if identity != query_key(pair["request"]["query"]):
            raise ValueError(
                "Normalised query identity differs from its original input."
            )
        if identity in blocked or identity not in allowed:
            raise ValueError("Quality cohort overlaps excluded or unfrozen queries.")
        actual_input = {
            name: pair[name]
            for name in ("query_id", "product_id", "request", "product")
        }
        if (
            prediction.get("input_sha256")
            != sha256(canonical(actual_input)).hexdigest()
        ):
            raise ValueError("Prediction belongs to different frozen input bytes.")
        provenance = prediction.get("provenance", {})
        if (
            provenance.get("kind") != "model"
            or prediction.get("gate_eligible") is not False
            or provenance.get("model") != manifest["model"]
            or provenance.get("release_sha256") != manifest["release_sha256"]
            or provenance.get("policy_sha256") != manifest["model_policy_sha256"]
            or provenance.get("runtime_image") != manifest["runtime_image"]
        ):
            raise ValueError("Prediction model, release, runtime or policy differs.")
        expected_source = "published" if cohort == "published" else "human"
        if (
            reference.get("label") not in LABELS
            or reference.get("provenance", {}).get("kind") != expected_source
            or reference["provenance"].get("source_id")
            != manifest["reference_source_id"]
        ):
            raise ValueError("Reference labels need the independently pinned source.")
        if (
            cohort == "human-gap"
            and manifest.get("reference_blinded_to_predictions") is not True
        ):
            raise ValueError(
                "Gap reference labels must be independently and blindly assigned."
            )
        state, label = prediction.get("outcome"), prediction.get("label")
        if state not in ("labelled", "abstain", "error"):
            raise ValueError("Prediction outcome is invalid.")
        confidence = prediction.get("confidence")
        if state != "error":
            scores = prediction.get("probabilities")
            if (
                not isinstance(scores, list)
                or len(scores) != 4
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    or not 0 <= v <= 1
                    for v in scores
                )
                or not math.isclose(sum(scores), 1, abs_tol=1e-6)
            ):
                raise ValueError("Predictions require four valid mapped probabilities.")
            winner = LABELS[int(np.argmax(scores))]
            if confidence != max(scores) or (state == "labelled") != (
                confidence >= policy["acceptance_threshold"]
            ):
                raise ValueError("Prediction violates the frozen acceptance threshold.")
            if state == "labelled" and label != winner:
                raise ValueError(
                    "Accepted label differs from the mapped winning class."
                )
        queries.append(identity)
        truth.append(reference["label"])
        emitted.append(label if state == "labelled" else state)
        failures.append(state == "error")
    if set(queries) != allowed:
        raise ValueError("Frozen confirmation query membership differs.")
    truth, emitted = np.asarray(truth), np.asarray(emitted)
    accepted = np.isin(emitted, LABELS)
    correct = accepted & (emitted == truth)
    irrelevant = truth == "I"
    harmful = irrelevant & (emitted == "E")
    n_accepted, n_irrelevant = int(accepted.sum()), int(irrelevant.sum())
    repetitions, seed = policy["bootstrap_repetitions"], policy["bootstrap_seed"]
    accuracy_interval = bootstrap(queries, correct, accepted, repetitions, seed)
    harm_interval = bootstrap(queries, harmful, irrelevant, repetitions, seed)
    accuracy = float(correct.sum() / n_accepted) if n_accepted else None
    harm_rate = float(harmful.sum() / n_irrelevant) if n_irrelevant else None
    criteria = {
        "minimum_queries": len(allowed) >= policy["minimum_confirmation_queries"],
        "minimum_accepted_pairs": n_accepted >= policy["minimum_accepted_pairs"],
        "accuracy_lower_bound": accuracy_interval is not None
        and accuracy_interval[0] >= policy["minimum_accuracy_lower_bound"],
        "irrelevant_to_exact_rate": harm_rate is not None
        and harm_rate <= policy["maximum_irrelevant_to_exact_rate"],
        "inference_complete": not any(failures),
    }
    insufficient = (
        not criteria["minimum_queries"]
        or not criteria["minimum_accepted_pairs"]
        or accuracy_interval is None
        or harm_rate is None
        or any(failures)
    )
    status = (
        "inconclusive"
        if insufficient
        else "passed"
        if all(criteria.values())
        else "failed"
    )
    confusion = {
        gold_label: {
            name: int(((truth == gold_label) & (emitted == name)).sum())
            for name in (*LABELS, "abstain", "error")
        }
        for gold_label in LABELS
    }
    irrelevant_queries = {
        q for q, label in zip(queries, truth, strict=True) if label == "I"
    }
    harmful_queries = {q for q, yes in zip(queries, harmful, strict=True) if yes}
    return {
        "kind": "esci-label-quality-report",
        "cohort": cohort,
        "status": status,
        "gate_eligible": False,
        "model": manifest["model"],
        "release_sha256": manifest["release_sha256"],
        "pairs": len(inputs),
        "queries": len(allowed),
        "accepted": n_accepted,
        "accepted_queries": len(
            {q for q, yes in zip(queries, accepted, strict=True) if yes}
        ),
        "coverage": n_accepted / len(inputs),
        "accepted_accuracy": accuracy,
        "accepted_accuracy_query_bootstrap_95_interval": accuracy_interval,
        "irrelevant_pairs": n_irrelevant,
        "irrelevant_to_exact_errors": int(harmful.sum()),
        "irrelevant_to_exact_rate": harm_rate,
        "irrelevant_to_exact_query_bootstrap_95_interval": harm_interval,
        "irrelevant_queries": len(irrelevant_queries),
        "queries_with_irrelevant_to_exact": len(harmful_queries),
        "zero_harm_query_incidence_95_upper_bound": 1
        - 0.05 ** (1 / len(irrelevant_queries))
        if irrelevant_queries and not harmful_queries
        else None,
        "counts": dict(Counter(emitted.tolist())),
        "confusion": confusion,
        "criteria": criteria,
        "uncertainty": {
            "method": "whole-normalised-query percentile bootstrap; pair-weighted ratios",
            "repetitions": repetitions,
            "seed": seed,
            "zero_event_limit": "A zero-width bootstrap interval with no observed errors does not prove zero population risk. The separate zero-harm bound concerns independent query incident probability, not pair error probability.",
        },
        "qualification_limit": "One cohort does not qualify activation. Published and independently labelled gap evidence require separate review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "inputs",
        "references",
        "predictions",
        "manifest",
        "audit",
        "policy",
        "reservation",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = read_json(args.manifest)
    for name in ("inputs", "references", "audit", "policy", "reservation"):
        if checksum(getattr(args, name)) != manifest[name + "_sha256"]:
            raise ValueError(
                "Frozen " + name + " bytes differ from the cohort manifest."
            )
    result = assess(
        read_rows(args.inputs),
        read_rows(args.references),
        read_rows(args.predictions),
        manifest,
        read_json(args.audit),
        read_json(args.policy),
    )
    result["hashes"] = {
        name: checksum(getattr(args, name))
        for name in (
            "inputs",
            "references",
            "predictions",
            "manifest",
            "audit",
            "policy",
            "reservation",
        )
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(canonical(result))
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "cohort",
                    "status",
                    "pairs",
                    "queries",
                    "accepted",
                    "coverage",
                    "accepted_accuracy",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
