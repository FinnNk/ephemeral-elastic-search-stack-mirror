"""Human review text for an exact, validated deployment proposal."""
import json


INTENTS = {'ranking-change': 'Intentional ranking change',
           'preserve-results': 'Preserve current results'}


def configuration(settings):
    """Describe recorded field weights without using a hash as the label."""
    boosts = (settings or {}).get('field_boosts')
    if boosts:
        return 'Search field weights: ' + ', '.join(f'{key} {value}' for key, value in sorted(boosts.items()))
    return 'Configuration details not recorded'


def description(target, deployment, current, reference, report, intent=None, rollback=False):
    """Keep review context readable while retaining complete evidence identities."""
    fields = deployment['fields']
    run = deployment['build_run']
    baseline_run = report.get('baseline_build_run', current.get('build_run'))
    baseline_variant = report.get('baseline_variant', 'default')
    build = lambda n: f'[Build {n}](https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/{n})' if n else 'Build not recorded'
    def version_label(value):
        return (value.get('software_version') or 'Version not recorded') + ' · ' + (
            value['source_sha'][:12] if value.get('source_sha') else 'Commit not recorded')
    version = version_label(fields)
    old_version = version_label(current.get('fields', {}))
    settings = json.loads(fields.get('variant_config_json') or '{}')
    checks = report.get('checks') or []
    lines = [f'## {"Rollback" if rollback else "Promote"} build {run} to {target.title()}', '',
        '**Checks passed; human approval is required before deployment.**', '',
        '| Role | Release | Version | Behaviour |', '| --- | --- | --- | --- |',
        f'| Current {target.title()} baseline | {build(baseline_run)} | {old_version} | {baseline_variant} |',
        f'| Candidate | {build(run)} | {version} | {", ".join(row["variant"] for row in checks) or settings.get("default_variant", "default")} |', '',
        f'[Open release dashboard](https://control.localhost:34443/release-dashboard?run={run})', '',
        '### What to review', '',
        f'- Catalogue: **{fields.get("dataset_release", "Not recorded")}**; Elasticsearch {fields.get("engine", "Not recorded")}.',
        '- Compare relevance scores, result changes and judgement coverage separately. Model labels do not establish independent label accuracy.',
        '- Review the performance profile and measured budgets. A probe is not a production load test.',
        '- Approve this exact PR commit, then use **Deploy approved proposal** in the lab dashboard. Approval alone does not deploy it.', '',
        '### Compared configurations', '',
        f'Baseline **{baseline_variant}** — {configuration(report.get("baseline_pin", {}).get("settings"))}', '']
    for row in checks:
        name = row['variant']
        lines.extend([f'- **{name}** — {INTENTS.get(row["intent"], row["intent"])}; check **{row["state"]}**. '
                      + configuration(settings.get('variants', {}).get(name)), ''])
    if intent:
        lines.extend([f'Change intent: **{INTENTS.get(intent, intent)}**.', ''])
    old_source = current.get('fields', {}).get('source_sha')
    if old_source:
        lines.extend([f'[Review source changes](https://gitea.localhost:34443/elastic-agent/delivery-source/compare/{old_source}...{fields["source_sha"]})', ''])
    lines.extend(['<details>', '<summary>Exact source and evidence identifiers</summary>', '',
        f'- Source commit: `{fields["source_sha"]}`.',
        f'- Release: `{fields["software_release_id"]}`.',
        f'- Baseline deployment: `{current["fingerprint"]}`.',
        f'- Candidate deployment: `{deployment["fingerprint"]}`.',
        f'- Evidence SHA-256: `{reference["sha256"]}`.', f'- Evidence location: `{reference["blob"]}`.', '',
        '</details>', '', 'This production target is a local simulation.'])
    return '\n'.join(lines)
