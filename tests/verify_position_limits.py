"""The proxy's position-capture quotas: defaults, RRT_POSITION_LIMITS, and failing closed on anything else.

The bounded multi-draw window keeps 4 draws per present interval and 16 in total unless RRT_POSITION_LIMITS=PER_INTERVAL:TOTAL
raises them (at most 256 and 1024, PER_INTERVAL not above TOTAL, canonical decimal). The ledger header must report the quotas the
proxy actually applies. Any other value disables capture, so a typo can never produce a ledger that claims quotas it did not
use, and the game still runs and exits normally. Runs the D3D9 smoke fixture through the proxy; needs an interactive desktop.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

VALID = (None, '8:32', '1:1', '256:1024', '64:256', '16:16')
INVALID = ('8:32 ', ' 8:32', '032:1', '8:032', '8:4', '300:400', '257:1024', '4:1025', '0:16', '4:0', '8', '8:', ':32', '8:32:1', 'x', ':', '-8:32', '8,32', '8 :32')


def need(value, message):
    if not value: raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--sample', type=Path, required=True); args = parser.parse_args()
    sample = args.sample.resolve(); folder = Path(tempfile.mkdtemp(prefix='position-limits-', dir=sample.parent))
    base = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    counter = [0]

    def run(limits, multi_draw=True):
        counter[0] += 1; ledger = folder / f'run{counter[0]}.jsonl'
        env = dict(base, RRT_POSITION_CAPTURE_FILE=str(ledger), RRT_POSITION_FRAME_SAMPLING='1', RRT_POSITION_SELECTION='any:1')
        if multi_draw: env['RRT_POSITION_MULTI_DRAW'] = '1'
        if limits is not None: env['RRT_POSITION_LIMITS'] = limits
        process = subprocess.run([str(sample), '--runtime', 'proxy', '--frames', '6'], env=env, capture_output=True, text=True, timeout=60)
        need(process.returncode == 0, f'the game failed with RRT_POSITION_LIMITS={limits!r}: {process.stdout}\n{process.stderr}')
        return json.loads(ledger.read_text(encoding='utf-8').splitlines()[0]).get('limits') if ledger.exists() else None

    for value in VALID:
        expected = {'per_interval': 4, 'total': 16} if value is None else dict(zip(('per_interval', 'total'), map(int, value.split(':'))))
        need(run(value) == expected, f'RRT_POSITION_LIMITS={value!r}: the ledger header did not report {expected}')
    for value in INVALID:
        need(run(value) is None, f'RRT_POSITION_LIMITS={value!r} was accepted; a malformed quota must disable capture')
    need(run('8:32', multi_draw=False) is None, 'quotas were accepted without the multi-draw window')
    print(json.dumps(dict(result='pass', valid=len(VALID), invalid=len(INVALID) + 1, artifacts=str(folder))))
    return 0


if __name__ == '__main__': sys.exit(main())
