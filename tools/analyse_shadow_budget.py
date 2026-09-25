"""Report what the shared shadow-budget policy decision needs from a capture ledger.

The 128 MiB cap is a priority limit, not an accounting defect: `Retained()` is
charged in two places, released in two places, and has no leak. What it does not
have is a policy for which resources deserve the space, and that choice is blocked
on one number.

The footer written when a capture stops reports the split at the stop. That is the
wrong moment. A reservation that was *refused* proves the total was higher when the
refusal was decided than it was at the stop, so the split that decides policy is
the one at the **peak**. The proxy now samples `retained_peak`, `peak_buffers` and
`peak_textures` for exactly this reason.

This tool prefers the peak fields, reports both moments side by side, and says
plainly when a ledger predates the instrument rather than quietly analysing the
stop values as if they answered the question.

Usage:
    python tools/analyse_shadow_budget.py PATH

PATH may be a capture ledger (`.jsonl`) or a pass directory, in which case the
newest `position-capture.jsonl` under `runs/` is used.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('path', type=Path, help='capture ledger, or a pass directory')
parser.add_argument('--refused-bytes', type=int, default=0,
                    help='bytes of demand that were refused at the cap, if known; '
                         'the tool then reports what cap would have admitted them')
parser.add_argument('--json', action='store_true', help='emit machine-readable output')
args = parser.parse_args()

path = args.path
if path.is_dir():
    candidates = sorted(path.glob('runs/*/position-capture.jsonl'),
                        key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(f'no position-capture.jsonl under {path}/runs/')
    path = candidates[-1]

if not path.is_file():
    raise SystemExit(f'not a file: {path}')


def shadow_cap():
    """Read the cap from the proxy source so it cannot drift from this report."""
    source = (REPO / 'src' / 'shader' / 'intercept.cpp').read_text(encoding='utf-8')
    tracking = (REPO / 'src' / 'shader' / 'texture_tracking.inc').read_text(encoding='utf-8')
    # Buffer charges: (c.positionMode?128:16)*1024*1024 -- a capture is always in
    # position mode, so the 128 arm is the one that applies here.
    buffers = re.search(r'\(c\.positionMode\?(\d+):\d+\)\*1024\*1024', source)
    # Texture charges: a flat 128*1024*1024, against the same Retained() counter.
    textures = re.search(r'reservation>(\d+)\*1024\*1024', tracking)
    if not buffers or not textures:
        raise SystemExit('could not read the shadow-budget cap from the proxy source')
    if buffers.group(1) != textures.group(1):
        raise SystemExit(f'the buffer and texture caps disagree '
                         f'({buffers.group(1)} vs {textures.group(1)} MiB) and the counter is '
                         f'shared, so this needs a look before the tool can reason about it')
    return int(buffers.group(1)) * 1024 * 1024


cap = shadow_cap()

footer = None
with path.open(encoding='utf-8', errors='ignore') as stream:
    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get('kind') == 'end':
            footer = record
if footer is None:
    raise SystemExit(f'no footer (kind "end") in {path} -- the capture did not stop '
                     f'cleanly, so there is nothing to attribute')

mib = 1024 * 1024


def share(value):
    return f'{value / mib:7.2f} MiB  {100.0 * value / cap:5.1f}% of the {cap // mib} MiB cap'


report = {'ledger': str(path), 'cap_bytes': cap, 'reason': footer.get('reason'),
          'captured': footer.get('captured'), 'attempts': footer.get('attempts'),
          'live_textures': footer.get('live_textures')}

stop = {'total': footer.get('retained'), 'buffers': footer.get('retained_buffers'),
        'textures': footer.get('retained_textures')}
if None not in stop.values() and stop['buffers'] + stop['textures'] != stop['total']:
    raise SystemExit(f'stop split does not sum: {stop}')
report['at_stop'] = stop

has_peak = 'retained_peak' in footer
if has_peak:
    peak = {'total': footer['retained_peak'], 'buffers': footer['peak_buffers'],
            'textures': footer['peak_textures']}
    if peak['buffers'] + peak['textures'] != peak['total']:
        raise SystemExit(f'peak split does not sum: {peak}')
    if peak['total'] < stop['total']:
        raise SystemExit(f'peak {peak["total"]} is below the stop value {stop["total"]}')
    report['at_peak'] = peak

if not args.json:
    print(f'ledger      : {path}')
    print(f'stop reason : {report["reason"]}   captured {report["captured"]} '
          f'from {report["attempts"]} attempts, {report["live_textures"]} live textures')
    print()
    print('  at stop   : total ' + share(stop['total']))
    print(f'              buffers {share(stop["buffers"])}')
    print(f'              textures {share(stop["textures"])}')
    if has_peak:
        peak = report['at_peak']
        print('  at PEAK   : total ' + share(peak['total']))
        print(f'              buffers {share(peak["buffers"])}')
        print(f'              textures {share(peak["textures"])}')
        print()
        print(f'  peak leaves {share(cap - peak["total"])} unused')
    print()

if not has_peak:
    print('This ledger has no peak fields, so it cannot answer the policy question.')
    print('The stop split is not a substitute: a refused reservation proves the total was')
    print('higher at the moment of refusal than it was at the stop, and this capture did')
    print(f'stop at {stop["total"] / mib:.2f} MiB against a {cap // mib} MiB cap, which cannot')
    print('refuse anything. Re-run with a proxy built after the peak instrument landed.')
    sys.exit(3)

peak = report['at_peak']
dominant = 'textures' if peak['textures'] > peak['buffers'] else 'buffers'
report['dominant_at_peak'] = dominant

if not args.json:
    print(f'The peak is {dominant}-dominated '
          f'({100.0 * peak[dominant] / peak["total"]:.0f}% of the peak total).')
    if args.refused_bytes:
        needed = peak['total'] + args.refused_bytes
        report['refused_bytes'] = args.refused_bytes
        report['cap_to_admit'] = needed
        print(f'Admitting the refused {args.refused_bytes / mib:.1f} MiB on top of the peak')
        print(f'needs a cap of at least {needed / mib:.2f} MiB, i.e. {needed / mib / (cap // mib):.2f}x the current one.')
        print()
    print('Candidates this supports:')
    print(f'  raise the cap            {"plausible" if dominant == "textures" else "plausible"}: '
          f'smallest change; state the VRAM rationale')
    print(f'  partition buffers/textures  '
          f'{"worth it" if peak["buffers"] > 0.15 * cap else "buys little at this peak"}: '
          f'buffers are {100.0 * peak["buffers"] / cap:.1f}% of the cap at the peak')
    print(f'  reclaim instead of holding  needs a quality argument either way; '
          f'{report["live_textures"]} textures were live')

if args.json:
    print(json.dumps(report, indent=2))
