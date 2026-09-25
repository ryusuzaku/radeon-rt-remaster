"""Contract: the shadow-budget analysis reads the cap from source and refuses to guess.

`tools/analyse_shadow_budget.py` exists to turn one game pass into a policy
decision, so it has to be trusted on two points above all:

  * it must not invent a cap. The 128 MiB figure is read from the proxy source, so
    a change there shows up here instead of silently analysing against a stale
    number;
  * it must not answer the policy question from a ledger that cannot answer it. The
    stop split is not a substitute for the peak split, and a tool that quietly
    analysed the stop values would produce a confident wrong recommendation, which
    is worse than producing none.

The second point is the reason this test exists. A missing-field case that returns
a plausible-looking answer is exactly the failure that would not be noticed.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'analyse_shadow_budget.py'
assert TOOL.is_file(), f'missing {TOOL}'


def ledger(directory, name, footer, header=None):
    path = directory / f'{name}.jsonl'
    header = header or {'kind': 'header', 'schema': 'rrt-position-capture', 'version': 19}
    path.write_text(json.dumps(header) + '\n' + json.dumps({'kind': 'end', **footer}) + '\n',
                    encoding='utf-8')
    return path


def run(path, *extra):
    return subprocess.run([sys.executable, str(TOOL), str(path), *extra],
                          capture_output=True, text=True, cwd=ROOT)


def need(condition, message):
    assert condition, message


# The cap must come from the source, not from a literal in the tool.
source = (ROOT / 'src' / 'shader' / 'intercept.cpp').read_text(encoding='utf-8')
tracking = (ROOT / 'src' / 'shader' / 'texture_tracking.inc').read_text(encoding='utf-8')
need('c.positionMode?128:16)*1024*1024' in source,
     'the buffer-cap expression changed; analyse_shadow_budget.shadow_cap() needs updating')
need('reservation>128*1024*1024' in tracking,
     'the texture-cap expression changed; analyse_shadow_budget.shadow_cap() needs updating')

with tempfile.TemporaryDirectory(prefix='shadow-budget-') as raw:
    directory = Path(raw)

    # 1. A ledger that predates the peak instrument must not be analysed as if it
    #    could answer the question. Exit 3, and say why.
    stop_only = ledger(directory, 'stop-only', dict(
        reason='capture_limit', captured=16, attempts=924,
        retained=104499516, retained_buffers=22664152, retained_textures=81835364,
        live_textures=636))
    result = run(stop_only)
    need(result.returncode == 3, f'a stop-only ledger must not answer, got {result.returncode}')
    need('no peak fields' in result.stdout and 'cannot answer' in result.stdout, result.stdout)
    need('99.66 MiB' in result.stdout, f'the stop split should still be reported:\n{result.stdout}')

    # 2. With peak fields, report both moments and name the dominant kind.
    textured = ledger(directory, 'textured', dict(
        reason='capture_limit', captured=16, attempts=924,
        retained=104499516, retained_buffers=22664152, retained_textures=81835364,
        live_textures=636,
        retained_peak=126000000, peak_buffers=24000000, peak_textures=102000000))
    result = run(textured, '--refused-bytes', str(20 * 4718592))
    need(result.returncode == 0, f'peak analysis should succeed: {result.stdout}{result.stderr}')
    need('at PEAK' in result.stdout, result.stdout)
    need('textures-dominated' in result.stdout, result.stdout)
    need('needs a cap of at least 210.16 MiB' in result.stdout,
         f'the cap needed to admit the refused demand should be reported:\n{result.stdout}')
    need('1.64x' in result.stdout, result.stdout)

    # 3. The dominant kind must actually drive the recommendation.
    buffered = ledger(directory, 'buffered', dict(
        reason='capture_limit', captured=16, attempts=924,
        retained=90000000, retained_buffers=30000000, retained_textures=60000000,
        live_textures=400,
        retained_peak=130000000, peak_buffers=90000000, peak_textures=40000000))
    result = run(buffered)
    need(result.returncode == 0, result.stdout + result.stderr)
    need('buffers-dominated' in result.stdout, result.stdout)
    need('partition buffers/textures  worth it' in result.stdout,
         f'a buffer-dominated peak should make partitioning worth it:\n{result.stdout}')

    # 4. A peak below the stop value is impossible; refuse rather than report it.
    broken = ledger(directory, 'broken', dict(
        reason='capture_limit', captured=1, attempts=1,
        retained=100000000, retained_buffers=1, retained_textures=99999999, live_textures=1,
        retained_peak=50000000, peak_buffers=1, peak_textures=49999999))
    result = run(broken)
    need(result.returncode == 1, f'a peak below the stop must be refused, got {result.returncode}')
    need('below the stop value' in result.stderr, result.stderr)

    # 5. A split that does not sum is a broken ledger, not a rounding question.
    unsplit = ledger(directory, 'unsplit', dict(
        reason='capture_limit', captured=1, attempts=1,
        retained=100000000, retained_buffers=1, retained_textures=1, live_textures=1))
    result = run(unsplit)
    need(result.returncode == 1, f'a split that does not sum must be refused, got {result.returncode}')
    need('does not sum' in result.stderr, result.stderr)

    # 6. A ledger with no footer at all has nothing to attribute.
    truncated = directory / 'truncated.jsonl'
    truncated.write_text(json.dumps({'kind': 'header'}) + '\n', encoding='utf-8')
    result = run(truncated)
    need(result.returncode == 1, f'a ledger with no footer must be refused, got {result.returncode}')
    need('no footer' in result.stderr, result.stderr)

    # 7. A pass directory resolves to the newest ledger under runs/.
    runs = directory / 'pass' / 'runs' / 'material5'
    runs.mkdir(parents=True)
    (runs / 'position-capture.jsonl').write_text(
        json.dumps({'kind': 'header'}) + '\n' + json.dumps({'kind': 'end',
            'reason': 'capture_limit', 'captured': 16, 'attempts': 924,
            'retained': 104499516, 'retained_buffers': 22664152, 'retained_textures': 81835364,
            'live_textures': 636, 'retained_peak': 126000000, 'peak_buffers': 24000000,
            'peak_textures': 102000000}) + '\n', encoding='utf-8')
    result = run(directory / 'pass')
    need(result.returncode == 0, f'pass-directory mode should find the ledger: {result.stderr}')
    need('material5' in result.stdout, result.stdout)

print('PASS shadow-budget analysis: cap read from source, stop-only ledgers refused, '
      'peak split drives the recommendation, malformed ledgers rejected')
