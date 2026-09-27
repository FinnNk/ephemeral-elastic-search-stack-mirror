"""Operate portable release previews and reviewed local delivery targets."""
import argparse
import json
from pathlib import Path
import socket
import sys
import time

from delivery_runtime import (TARGETS, checkout, expire_previews, preview, read_target,
                              remove_preview, resolve, writer)
from delivery_gates import evaluate
from delivery_promote import (RECORDS, bootstrap, demonstrate_merge, propose, validate_pr,
                              verify_target, watch_once)
from delivery_provider import DESIRED, git
from common import STATE


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest='command', required=True)
    for name in ('bootstrap', 'preview'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--run', type=int, required=True)
        cmd.add_argument('--dataset', default='retail-gb-10k-v1')
        cmd.add_argument('--recipe', help='Pinned index recipe SHA-256; blank uses the current shared recipe')
        cmd.add_argument('--query-manifest', help='Selected query-suite manifest SHA-256')
        cmd.add_argument('--judgement-manifest', help='Matching judgement-set manifest SHA-256')
    cmd = commands.add_parser('evaluate')
    cmd.add_argument('--baseline-run', type=int, required=True)
    cmd.add_argument('--candidate-run', type=int, required=True)
    cmd.add_argument('--dataset', default='retail-gb-10k-v1')
    cmd.add_argument('--baseline-recipe')
    cmd.add_argument('--candidate-recipe')
    cmd.add_argument('--query-manifest', help='Query-suite manifest for both public API checks')
    cmd.add_argument('--judgement-manifest', help='Matching judgement-set manifest')
    cmd.add_argument('--intent', choices=('preserve-results', 'ranking-change'), default='preserve-results')
    cmd.add_argument('--profile', choices=('probe', 'smoke'), default='probe')
    cmd = commands.add_parser('promote')
    cmd.add_argument('target', choices=TARGETS)
    cmd.add_argument('--run', type=int, required=True)
    cmd.add_argument('--dataset', default='retail-gb-10k-v1')
    cmd.add_argument('--recipe')
    cmd.add_argument('--query-manifest')
    cmd.add_argument('--judgement-manifest')
    cmd.add_argument('--evidence', type=Path, required=True)
    cmd.add_argument('--intent', choices=('preserve-results', 'ranking-change'), default='preserve-results')
    cmd = commands.add_parser('rollback')
    cmd.add_argument('target', choices=TARGETS)
    cmd.add_argument('--fingerprint', required=True)
    cmd.add_argument('--evidence', type=Path, required=True)
    for name in ('validate', 'demonstrate-merge'):
        cmd = commands.add_parser(name)
        cmd.add_argument('pr', type=int)
    cmd = commands.add_parser('verify')
    cmd.add_argument('target', choices=TARGETS)
    cmd = commands.add_parser('delete-preview')
    cmd.add_argument('name')
    commands.add_parser('expire-previews')
    commands.add_parser('status')
    cmd = commands.add_parser('watch')
    cmd.add_argument('--once', action='store_true')
    return root


def execute(args):
    if args.command == 'bootstrap':
        return bootstrap(resolve(args.run, args.dataset, args.recipe,
                                 query_manifest_sha=args.query_manifest,
                                 judgement_manifest_sha=args.judgement_manifest))
    if args.command == 'preview':
        return preview(resolve(args.run, args.dataset, args.recipe,
                               query_manifest_sha=args.query_manifest,
                               judgement_manifest_sha=args.judgement_manifest))
    if args.command == 'evaluate':
        baseline = resolve(args.baseline_run, args.dataset, args.baseline_recipe)
        candidate = resolve(args.candidate_run, args.dataset, args.candidate_recipe,
                            query_manifest_sha=args.query_manifest,
                            judgement_manifest_sha=args.judgement_manifest)
        value = evaluate(baseline, candidate, args.intent, args.profile)
        RECORDS.mkdir(exist_ok=True)
        path = RECORDS / ('evidence-' + value['sha256'] + '.json')
        path.write_text(json.dumps(value, indent=2), encoding='utf-8')
        return {**value, 'reference_file': str(path)}
    if args.command == 'promote':
        return propose(args.target, resolve(args.run, args.dataset, args.recipe,
                                            query_manifest_sha=args.query_manifest,
                                            judgement_manifest_sha=args.judgement_manifest),
                       json.loads(args.evidence.read_text()), args.intent)
    if args.command == 'rollback':
        if len(args.fingerprint) != 64 or any(c not in '0123456789abcdef' for c in args.fingerprint):
            raise ValueError('Invalid rollback fingerprint.')
        checkout()
        deployment = json.loads(git(DESIRED, 'show',
            'HEAD:history/' + args.target + '/' + args.fingerprint + '.json'))
        return propose(args.target, deployment, json.loads(args.evidence.read_text()), rollback=True)
    if args.command == 'validate':
        return validate_pr(args.pr)
    if args.command == 'demonstrate-merge':
        return demonstrate_merge(args.pr)
    if args.command == 'verify':
        checkout()
        return verify_target(args.target)
    if args.command == 'delete-preview':
        remove_preview(args.name)
        return {'deleted': args.name}
    if args.command == 'expire-previews':
        expire_previews()
        return {'expired_previews_removed': True}
    if args.command == 'status':
        checkout()
        return {target: {'desired': read_target(target), 'observed': json.loads(
            (RECORDS / (target + '.json')).read_text()) if (RECORDS / (target + '.json')).exists() else None}
            for target in TARGETS}
    if args.command == 'watch':
        expire_previews()
        return watch_once()


def main():
    args = parser().parse_args()
    if args.command == 'watch' and not args.once:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as singleton:
            singleton.bind(('127.0.0.1', 18087))
            singleton.listen(1)
            while True:
                if (STATE / 'control-drain').exists():
                    return
                try:
                    with writer():
                        result = execute(args)
                    if result:
                        print(json.dumps(result), flush=True)
                except Exception as error:
                    print(json.dumps({'error': type(error).__name__, 'detail': str(error)[:180]}), flush=True)
                time.sleep(30)
    else:
        with writer():
            result = execute(args)
            print(json.dumps(result, indent=2))
            if isinstance(result, dict) and result.get('passed') is False:
                sys.exit(1)


if __name__ == '__main__':
    main()
