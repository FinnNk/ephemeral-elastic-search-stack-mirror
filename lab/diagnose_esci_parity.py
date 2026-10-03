"""Prepare exposed research inputs, collect HTTP outputs and describe paired drift.

Examples remain in ignored local storage. This tool does not activate a model or
manage GPU ownership; use the checkpointed qualification procedure first.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judgements"))
from esci.contract import clean, map_scores, model_state, outcome
from esci.diagnostics import summarise
from esci.release import content_digest, read_json, sha256, write_json


def prepare(research, bundle, exclusions, output):
    import pandas as pd
    sys.path.insert(0, str(research / "esci-tfm-experiment/src"))
    from esci_tfm.lexical import normalize

    if output.exists():
        raise FileExistsError("Preserve the frozen diagnostic inputs.")
    release, mapping, policy = [read_json(bundle / name) for name in
                                ("release.json", "score-mapping.json", "policy.json")]
    reserved = read_json(exclusions)
    if reserved["normalisation"] != "nfkc_html_whitespace_v1" or not reserved["query_hashes"]:
        raise ValueError("Require non-empty, normalised protected-query hashes.")
    excluded = set(reserved["query_hashes"])
    source = research / "artifacts/evaluations/round-2"
    metadata = source / "cohorts-v2/confirmation.parquet"
    signals = source / "signals/v3_8192/confirmation.parquet"
    archive = source / "decision-confirmation/probabilities.npz"
    original = pd.read_parquet(metadata)
    rows = original.sort_values("input_hash").reset_index(drop=True)
    raw = pd.read_parquet(signals).sort_values("input_hash").reset_index(drop=True)
    if not rows.input_hash.equals(raw.input_hash) or not rows.label.equals(raw.gold):
        raise ValueError("Frozen input and score identities differ.")
    mapped = np.array([map_scores(list(values), mapping) for values in raw.probabilities])
    if not np.allclose(mapped, np.load(archive)["v3_8192:scores:C0.1"], atol=1e-12, rtol=0):
        raise ValueError("Mapping differs from the frozen research result.")
    selected, lookup = [], {}
    for i, row in rows.iterrows():
        query_hash = hashlib.sha256(normalize(row["query"]).encode()).hexdigest()
        if query_hash in excluded:
            continue
        pair = {"query_id": query_hash, "product_id": row.product_id,
                "request": {"query": row["query"]},
                "product": {"title": row.title, "taxonomy_path": list(row.taxonomy_path)}}
        leaf = [clean(p) for p in list(row.taxonomy_path)[-1:] if clean(p)]
        canonical = {"schema_version": "esci-title_leaf_category-v1", "query": clean(row["query"]),
                     "title": clean(row.title), "taxonomy_path": leaf,
                     "locale": clean(row.locale) if row.locale else None}
        if content_digest(canonical) != raw.iloc[i].model_input_hash:
            raise ValueError("Model input hash differs from the frozen scores.")
        state = f"Query:\n{canonical['query']}\n\nProduct title:\n{canonical['title']}\n\nProduct category:\n{' > '.join(leaf) if leaf else 'Unknown'}"
        if model_state(pair) != state:
            raise ValueError("Rendered model input differs.")
        lookup[row.input_hash] = len(selected)
        selected.append({"input_hash": row.input_hash, "query_hash": query_hash,
                         "input": pair, "state": state, "reference_raw": list(raw.iloc[i].probabilities),
                         "reference": outcome(mapped[i].tolist(), policy)})
    if len(selected) < 1000:
        raise ValueError("Too few unreserved pairs for the larger diagnostic.")
    groups = defaultdict(list)
    for i, row in enumerate(selected):
        groups[row["query_hash"]].append(i)
    singletons = []
    for offset in range(max(map(len, groups.values()))):
        for query in sorted(groups):
            if offset < len(groups[query]):
                singletons.append(groups[query][offset])
                if len(singletons) == 1024:
                    break
        if len(singletons) == 1024:
            break
    # Retain complete original groups only: never infer on a protected companion.
    original_groups = []
    for start in range(0, len(original), 8):
        chunk = list(original.iloc[start:start+8].input_hash)
        if len(chunk) == 8 and all(key in lookup for key in chunk):
            original_groups.append([lookup[key] for key in chunk])
    original_groups.sort(key=lambda group: content_digest([selected[i]["input_hash"] for i in group]))
    result = {"format": "esci-parity-diagnostic-inputs-v1", "release_sha256": release["release_sha256"],
              "source_sha256": {str(p.relative_to(source)): sha256(p) for p in (metadata, signals, archive)},
              "exclusions_sha256": sha256(exclusions), "normalisation": reserved["normalisation"],
              "original_pairs": len(rows), "excluded_pairs": len(rows)-len(selected),
              "pairs": len(selected), "queries": len(groups), "rows": selected,
              "singleton_indices": singletons, "original_groups": original_groups[:64],
              "selection": "All exposed confirmation pairs outside protected normalised query membership."}
    write_json(output, result)
    print(json.dumps({key:result[key] for key in ("pairs", "queries", "excluded_pairs")}))
    print("Fully eligible original groups:", len(original_groups), flush=True)


def collect(endpoint, inputs, receipt, output, arrangement):
    if output.exists():
        raise FileExistsError("Use a new output path for each repeated run.")
    frozen, registration = read_json(inputs), read_json(receipt)
    if frozen["release_sha256"] != registration["release_sha256"]:
        raise ValueError("The registration describes another release.")
    identity = {key:registration[key] for key in ("name", "version", "artifact_sha256")}
    indices = list(range(len(frozen["rows"])))
    if arrangement == "reversed":
        indices.reverse()
    if arrangement == "singletons":
        indices = frozen["singleton_indices"]
    size = 1 if arrangement == "singletons" else 128
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"header": {"input_sha256": sha256(inputs), "model": identity,
                                            "arrangement": arrangement}}) + "\n")
        for start in range(0, len(indices), size):
            batch = indices[start:start+size]
            request = urllib.request.Request(endpoint, method="POST",
                data=json.dumps({"instances": [frozen["rows"][i]["input"] for i in batch]}).encode(),
                headers={"Content-Type": "application/json"})
            tick = time.monotonic()
            with urllib.request.urlopen(request, timeout=600) as response:
                result = json.load(response)
            if result["model"] != identity or len(result["predictions"]) != len(batch):
                raise ValueError("Returned identity or row count differs.")
            stream.write(json.dumps({"indices": batch, "predictions": result["predictions"],
                                     "seconds": time.monotonic()-tick}) + "\n")
            stream.flush()
            if (start + size) % 512 == 0 or start + size >= len(indices):
                print(f"{arrangement}: {min(start+size,len(indices))}/{len(indices)}; {time.monotonic()-started:.1f}s", flush=True)


def scores(path, frozen):
    result = {}
    with path.open(encoding="utf-8") as stream:
        header = json.loads(next(stream))["header"]
        if header["input_sha256"] != sha256(frozen):
            raise ValueError("Outputs describe different frozen inputs.")
        for line in stream:
            chunk = json.loads(line)
            for i, row in zip(chunk["indices"], chunk["predictions"], strict=True):
                if i in result:
                    raise ValueError("A pair occurs more than once in a run.")
                result[i] = row["probabilities"]
    inputs = read_json(frozen)
    expected = (set(inputs["singleton_indices"]) if header["arrangement"] == "singletons"
                else set(range(inputs["pairs"])))
    if set(result) != expected:
        raise ValueError("The run is incomplete or contains unexpected pair identities.")
    return result


def report(inputs, runs, output):
    if output.exists():
        raise FileExistsError("Preserve earlier diagnostic reports.")
    frozen = read_json(inputs)
    reference = {i:row["reference"]["probabilities"] for i,row in enumerate(frozen["rows"])}
    collected = {name:scores(path, inputs) for name,path in runs.items()}
    comparisons = {}
    pairs = [("reference", name) for name in collected]
    pairs += [("batch", name) for name in collected if name != "batch"]
    if "singletons" in collected and "singletons-repeat" in collected:
        pairs.append(("singletons", "singletons-repeat"))
    sources = {"reference": reference, **collected}
    for first, second in pairs:
        indices = sorted(set(sources[first]) & set(sources[second]))
        comparisons[first+"__"+second] = summarise(
            [sources[first][i] for i in indices], [sources[second][i] for i in indices],
            [frozen["rows"][i]["query_hash"] for i in indices])
    value = {"input_sha256": sha256(inputs), "pairs": frozen["pairs"], "queries": frozen["queries"],
             "runs_sha256": {name:sha256(path) for name,path in runs.items()}, "comparisons": comparisons}
    write_json(output, value)
    print(json.dumps({name:{key:result[key] for key in
          ("pairs", "max_absolute_delta", "p95_max_absolute_delta", "above_tolerance_pairs", "changed_labels_or_abstentions")}
          for name,result in comparisons.items()}, indent=2), flush=True)


def probe_report(inputs, runs, output):
    """Compare raw inference separately from calibration and request handling."""
    if output.exists():
        raise FileExistsError("Preserve earlier probe reports.")
    frozen = read_json(inputs)
    sources, metadata = {}, {}
    for name, path in runs.items():
        with path.open(encoding="utf-8") as stream:
            header = json.loads(next(stream))["metadata"]
            if header["input_sha256"] != sha256(inputs):
                raise ValueError("Probe inputs differ.")
            metadata[name] = header
            for line in stream:
                chunk = json.loads(line)
                key = name+":"+chunk["run"]
                destination = sources.setdefault(key, {})
                for i, raw, mapped in zip(chunk["indices"], chunk["raw"], chunk["mapped"], strict=True):
                    if i in destination:
                        raise ValueError("Repeated probe pair identity.")
                    destination[i] = {"raw": raw, "mapped": mapped}
    expected = {i for group in frozen["original_groups"] for i in group}
    if any(set(rows) != expected for rows in sources.values()):
        raise ValueError("Incomplete probe.")
    sources["reference"] = {i: {"raw": row["reference_raw"],
                                "mapped": row["reference"]["probabilities"]}
                            for i, row in enumerate(frozen["rows"]) if i in expected}
    pairs = [("reference", key) for key in sources if key != "reference"]
    for name in runs:
        pairs += [(name+":original", name+":"+arrangement)
                  for arrangement in ("original-repeat", "singletons")]
        if name+":upstream-original" in sources:
            pairs.append((name+":upstream-original", name+":original"))
    names = list(runs)
    for n, name in enumerate(names):
        pairs += [(name+":"+arrangement, other+":"+arrangement)
                  for other in names[n+1:] for arrangement in ("original", "singletons")]
    comparisons = {}
    indices = sorted(expected)
    for first, second in pairs:
        comparisons[first+"__"+second] = {
            kind: summarise([sources[first][i][kind] for i in indices],
                            [sources[second][i][kind] for i in indices],
                            [frozen["rows"][i]["query_hash"] for i in indices])
            for kind in ("raw", "mapped")}
    result = {"input_sha256": sha256(inputs),
              "runs_sha256": {name: sha256(path) for name, path in runs.items()},
              "metadata": metadata, "comparisons": comparisons}
    write_json(output, result)
    print(json.dumps({name: {kind: {field: value[field] for field in
          ("max_absolute_delta", "above_tolerance_pairs", "changed_labels_or_abstentions")}
          for kind, value in values.items()} for name, values in comparisons.items()}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    for name in ("research", "bundle", "exclusions", "output"):
        prep.add_argument("--"+name, type=Path, required=True)
    run = commands.add_parser("collect")
    run.add_argument("--endpoint", required=True)
    run.add_argument("--arrangement", choices=("batch", "reversed", "singletons"), required=True)
    for name in ("inputs", "receipt", "output"):
        run.add_argument("--"+name, type=Path, required=True)
    summary = commands.add_parser("report")
    for name in ("inputs", "output"):
        summary.add_argument("--"+name, type=Path, required=True)
    summary.add_argument("--run", action="append", required=True, help="NAME=JSONL")
    probes = commands.add_parser("probe-report")
    for name in ("inputs", "output"):
        probes.add_argument("--"+name, type=Path, required=True)
    probes.add_argument("--run", action="append", required=True, help="NAME=JSONL")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.research, args.bundle, args.exclusions, args.output)
    elif args.command == "collect":
        collect(args.endpoint, args.inputs, args.receipt, args.output, args.arrangement)
    elif args.command == "report":
        report(args.inputs, {name:Path(path) for name,path in (item.split("=", 1) for item in args.run)}, args.output)
    else:
        probe_report(args.inputs, {name:Path(path) for name,path in
                                  (item.split("=", 1) for item in args.run)}, args.output)


if __name__ == "__main__":
    main()
