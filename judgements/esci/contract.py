"""The frozen v3 input format, four-score mapping and abstention rule."""

import math

LABELS = ("E", "S", "C", "I")
OPTIONS = ("Exact", "Substitute", "Complement", "Irrelevant")
QUESTION = (
    "Classify the product relative to what the shopper seeks, not shared words.\n"
    "Exact: the product itself fills the requested role and matches explicit brand, model, "
    "size or function.\n"
    "Substitute: another product that fills the same role or need instead.\n"
    "Complement: an accessory, part, refill, consumable or companion item that goes with "
    "the requested product or intent, rather than replacing it. A name or model in "
    "'for X' or 'compatible with X' supports compatibility, not Exact; if the query seeks "
    "that accessory itself, it may be Exact.\n"
    "Irrelevant: no supported Exact, Substitute or Complement relationship."
)


def clean(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Query, title and category must be strings.")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def model_state(pair: dict) -> str:
    """Use the lab's category string or an explicit taxonomy path's final element."""
    query = clean(pair["request"]["query"])
    product = pair["product"]
    title = clean(product["title"])
    if not query or not title:
        raise ValueError("A non-empty query and product title are required.")
    if "taxonomy_path" in product:
        path = product["taxonomy_path"]
        if not isinstance(path, list) or not all(isinstance(p, str) for p in path):
            raise ValueError("taxonomy_path must be a list of strings.")
        # Match JudgementInput.build: choose the leaf before removing empty values.
        category = clean(path[-1]) if path else ""
    else:
        category = clean(product.get("category") or "")
    return f"Query:\n{query}\n\nProduct title:\n{title}\n\nProduct category:\n{category or 'Unknown'}"


def probabilities(values: list[float]) -> list[float]:
    if len(values) != 4 or any(not math.isfinite(v) or v < 0 or v > 1 for v in values):
        raise ValueError("Expected four finite E/S/C/I probabilities.")
    if abs(sum(values) - 1) > 1e-5:
        raise ValueError("ESCI probabilities must sum to one.")
    return values


def validate_mapping(mapping: dict) -> None:
    if mapping.get("format") != "esci-logistic-scores-v1" or mapping.get(
        "labels"
    ) != list(LABELS):
        raise ValueError("Unsupported score mapping or label order.")
    if mapping.get("clip_min") != 1e-6:
        raise ValueError("Unexpected score transformation.")
    vectors = [
        mapping["mean"],
        mapping["scale"],
        mapping["intercept"],
        *mapping["coef"],
    ]
    if len(mapping["coef"]) != 4 or any(len(v) != 4 for v in vectors):
        raise ValueError("Score mapping requires four input and four output classes.")
    if any(not math.isfinite(v) for row in vectors for v in row):
        raise ValueError("Non-finite mapping parameter.")
    if any(v <= 0 for v in mapping["scale"]):
        raise ValueError("Mapping scales must be positive.")


def map_scores(raw: list[float], mapping: dict) -> list[float]:
    probabilities(raw)
    x = [
        (math.log(max(value, mapping["clip_min"])) - mean) / scale
        for value, mean, scale in zip(
            raw, mapping["mean"], mapping["scale"], strict=True
        )
    ]
    logits = [
        sum(w * v for w, v in zip(row, x, strict=True)) + intercept
        for row, intercept in zip(mapping["coef"], mapping["intercept"], strict=True)
    ]
    exps = [math.exp(v - max(logits)) for v in logits]
    return [v / sum(exps) for v in exps]


def validate_policy(policy: dict) -> None:
    if policy.get("format") != "esci-abstention-v1" or policy.get("labels") != list(
        LABELS
    ):
        raise ValueError("Unsupported abstention policy or label order.")
    if set(policy["thresholds"]) != set(LABELS):
        raise ValueError("All class thresholds must be explicit.")
    if any(
        not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
        for v in policy["thresholds"].values()
    ):
        raise ValueError("Invalid abstention threshold.")


def outcome(scores: list[float], policy: dict) -> dict:
    probabilities(scores)
    index = max(range(4), key=scores.__getitem__)
    label, confidence = LABELS[index], scores[index]
    accepted = confidence >= policy["thresholds"][label]
    return {
        "outcome": "labelled" if accepted else "abstain",
        "label": label if accepted else None,
        "confidence": confidence,
        "probabilities": scores,
    }
