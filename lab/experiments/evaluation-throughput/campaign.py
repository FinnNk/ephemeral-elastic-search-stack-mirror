"""Counterbalanced finite captures; never generates an arrival-rate load profile."""
import argparse
import json
from pathlib import Path
import time
from run import Experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('transport', 'scheduling', 'confirmation', 'judgements', 'resources'))
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    instance = Experiment(args.directory)
    if args.stage == 'resources':
        try:
            while not (args.directory / 'stop-resources').exists():
                from common import k
                value = {'epoch': time.time(), 'nodes': k('top', 'nodes', check=False).stdout,
                         'pods': k('top', 'pods', '-n', instance.namespace, check=False).stdout}
                with (args.directory / 'resource-ledger.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(value) + '\n')
                time.sleep(10)
        except KeyboardInterrupt:
            pass
        return
    options = [('original', 'thread-query', 'urllib', 8),
               ('pooled-es', 'thread-query', 'urllib', 8),
               ('pooled-both', 'thread-query', 'httpx', 8)]
    if args.stage == 'transport':
        modes = ['original', 'cached-tls', 'pooled-es', 'pooled-both']
        for mode in modes:
            instance.capture(mode, label='transport-warmup')
        for block in range(2):
            for mode in (modes if block == 0 else list(reversed(modes))):
                instance.capture(mode, label='transport-screen-' + str(block), seed=20261002 + block)
    elif args.stage == 'scheduling':
        options = [(mode, 'thread-query', 'urllib', limit)
                   for mode in ('original', 'pooled-es') for limit in (16, 32)]
        options += [('pooled-both', strategy, 'httpx', 8) for strategy in
                    ('thread-query', 'thread-flat', 'async-query', 'async-flat')]
        options += [('pooled-both', 'async-flat', 'httpx', limit) for limit in (16, 32)]
        options += [('pooled-both', 'adaptive', 'httpx', 32)]
        for block in range(2):
            for mode, strategy, client, limit in (options if block == 0 else list(reversed(options))):
                instance.capture(mode, strategy, client, limit,
                                 label='scheduling-screen-' + str(block), seed=20261004 + block)
    elif args.stage == 'confirmation':
        for block in range(6):
            order = options[block % 3:] + options[:block % 3]
            if block >= 3:
                order = list(reversed(order))
            for mode, strategy, client, limit in order:
                instance.capture(mode, strategy, client, limit,
                                 label='confirmation-' + str(block), seed=20261010 + block)
        for block in range(2):
            for mode, strategy, client, limit in ([options[0], options[2]] if block == 0 else [options[2], options[0]]):
                instance.capture(mode, strategy, client, limit, variants=3,
                                 label='three-variant-' + str(block), seed=20261020 + block)
    else:
        from judge_run import capture
        for block, order in enumerate(([1, 2, 4], [4, 2, 1], [2, 1, 4])):
            for limit in order:
                capture(instance, limit, 'judgement-screen-' + str(block))


if __name__ == '__main__':
    main()
