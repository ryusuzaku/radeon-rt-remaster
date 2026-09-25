"""Contract: the C++ capture-version ladder, its schema and the Python reader agree.

The capture ledger version is the project's central artifact contract. It is
produced by a fold over the proxy's opt-in evidence flags in
`src/shader/intercept.cpp` and validated by a separate accepted-version set in
`tools/inspect_position_capture.py`. Nothing linked the two, so a new level could
be added on one side and silently rejected on the other -- surfacing as an
"invalid header" in a test matrix rather than at the point of change.

This test reads all three sources and requires them to describe the same ladder:

  * `enum class CaptureLevel`  -- the level numbers
  * `Context::Level()`         -- the fold, which must cover every level exactly
                                  once and be ordered highest-first
  * `docs/schemas/capture-version.json` -- the documented ladder and evidence
  * `tools/inspect_position_capture.py` -- the reader's accepted version set

It parses source rather than driving the built proxy, deliberately: a
binary-level check would need the pinned HL2 inventory and would therefore be
skipped on a clean checkout, which is exactly where a divergence is most likely
to be introduced unnoticed. Behaviour is covered separately -- the `texture_*`
and `position_capture` suites assert specific emitted versions end to end.
"""
import argparse
import json
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                    help='repository root containing src/, tools/ and docs/')
args = parser.parse_args()
root = args.root.resolve()

cpp = root / 'src' / 'shader' / 'intercept.cpp'
reader = root / 'tools' / 'inspect_position_capture.py'
schema_path = root / 'docs' / 'schemas' / 'capture-version.json'
for required in (cpp, reader, schema_path):
    assert required.is_file(), f'missing required file: {required}'

source = cpp.read_text(encoding='utf-8')
reader_source = reader.read_text(encoding='utf-8')
schema = json.loads(schema_path.read_text(encoding='utf-8'))


def need(condition, message):
    assert condition, message


# --- the C++ enum -----------------------------------------------------------------
enum_body = re.search(r'enum class CaptureLevel\s*:\s*int\s*\{(.*?)\n\};', source, re.S)
need(enum_body, 'CaptureLevel enum not found in src/shader/intercept.cpp')
enum_entries = re.findall(r'^\s*([A-Za-z_]\w*)\s*=\s*(\d+)\s*,', enum_body.group(1), re.M)
need(enum_entries, 'CaptureLevel enum parsed as empty; the declaration format changed')
enum = {name: int(value) for name, value in enum_entries}
need(len(enum) == len(enum_entries), 'duplicate CaptureLevel names')
need(len(set(enum.values())) == len(enum), 'duplicate CaptureLevel values')
need(sorted(enum.values()) == list(range(min(enum.values()), max(enum.values()) + 1)),
     f'CaptureLevel values are not contiguous: {sorted(enum.values())}')

# --- the fold ---------------------------------------------------------------------
fold_body = re.search(r'CaptureLevel Level\(\)\s*const\s*\{(.*?)\n    \}', source, re.S)
need(fold_body, 'Context::Level() not found in src/shader/intercept.cpp')
fold = re.findall(r'\{\s*([A-Za-z_]\w*)\s*,\s*CaptureLevel::([A-Za-z_]\w*)\s*\}', fold_body.group(1))
need(fold, 'Context::Level() parsed as empty; the fold format changed')
fold_names = [name for _, name in fold]
need(len(fold_names) == len(set(fold_names)),
     f'a level appears more than once in the fold: {sorted(n for n in fold_names if fold_names.count(n) > 1)}')

# The lowest level is the fallback ("no evidence flag enabled"), so it is the
# return value rather than an entry. Requiring that explicitly is the point: it
# catches a new level added to the enum but forgotten in the fold, and a baseline
# that is no longer the lowest.
baseline = min(enum, key=lambda name: enum[name])
need(set(fold_names) == set(enum) - {baseline},
     f'fold and enum disagree: only in fold {sorted(set(fold_names) - set(enum))}, '
     f'only in enum (excluding the {baseline} fallback) {sorted(set(enum) - set(fold_names) - {baseline})}')
need(len(fold) == len(enum) - 1, f'fold has {len(fold)} entries for {len(enum) - 1} non-fallback levels')
need(re.search(rf'return\s+CaptureLevel::{baseline}\s*;', fold_body.group(1)),
     f'Context::Level() does not fall back to {baseline}, the lowest level')

# The fold scans highest-first and returns the first enabled flag, so the order is
# load-bearing: an out-of-order entry would silently report a lower version.
fold_versions = [enum[name] for _, name in fold]
need(fold_versions == sorted(fold_versions, reverse=True),
     f'Context::Level() is not ordered highest-first: {fold_versions}')

# Every flag the fold reads must be a real member of Context.
for flag, _ in fold:
    need(re.search(rf'\bbool [^\n;]*\b{re.escape(flag)}\b', source),
         f'fold reads {flag}, which is not declared as a bool member of Context')

# --- the schema -------------------------------------------------------------------
levels = schema['levels']
need(levels, 'schema has no levels')
schema_names = {entry['name'] for entry in levels}
schema_versions = {entry['version'] for entry in levels}
need(schema_names == set(enum),
     f'schema and enum disagree: only in schema {sorted(schema_names - set(enum))}, '
     f'only in enum {sorted(set(enum) - schema_names)}')
for entry in levels:
    need(enum[entry['name']] == entry['version'],
         f"{entry['name']}: enum says {enum[entry['name']]}, schema says {entry['version']}")
    need(entry['evidence'], f"{entry['name']} has no evidence description")
    flag = entry['flag']
    need(flag, f"{entry['name']} has no flag; every level is selected by one")
    # A documented flag that the proxy never reads would be a silent lie.
    need(flag in source, f"schema names {flag}, which does not appear in src/shader/intercept.cpp")

# --- the reader -------------------------------------------------------------------
accepted_match = re.search(r'version\s+in\s+\(([\d,\s]+)\)', reader_source)
need(accepted_match, 'the accepted version set was not found in tools/inspect_position_capture.py')
accepted = {int(value) for value in accepted_match.group(1).split(',') if value.strip()}

documented = {entry['version'] for entry in schema.get('legacy', [])}
documented |= {entry['version'] for entry in schema.get('other_headers', [])}
documented |= schema_versions
need(accepted == documented,
     f'reader and schema disagree: reader only {sorted(accepted - documented)}, '
     f'schema only {sorted(documented - accepted)}')

# The non-ladder headers must actually be emitted somewhere.
for entry in schema.get('other_headers', []):
    need(f'"version":{entry["version"]}' in source or f'version\\":{entry["version"]}' in source,
         f'schema documents header version {entry["version"]}, which intercept.cpp never emits')

# --- the CLI ladder, a fourth description of the same thing -----------------------
# tools/game_pass.py declares the ladder once in CAPTURE_LEVELS and derives the
# argparse flags, the prerequisite checks, the environment it exports and the
# report it writes from that one table. So it is now a fourth description that has
# to agree with the other three, and the order matters for the same reason it does
# in the fold: the ladder is cumulative.
sys.path.insert(0, str(root / 'tools'))
import game_pass  # noqa: E402  (path has to be set up first)

cli = [(level['name'], game_pass.capture_environment_name(level['name']))
       for level in game_pass.CAPTURE_LEVELS]
need(len(cli) == len(levels),
     f'the CLI ladder has {len(cli)} levels against {len(levels)} in the schema')
for (name, env), entry in zip(cli, levels):
    need(env == entry['flag'],
         f'CLI level {name} exports {env}, but the schema has {entry["flag"]} at '
         f'v{entry["version"]}; the two ladders are out of step')
    need(f'L"{env}"' in source,
         f'the CLI exports {env}, which the proxy never reads')
# The CLI's prerequisites must mirror the proxy's, which refuses a level whose
# predecessor is not enabled.
need(cli[0][1] == 'RRT_POSITION_MULTI_DRAW',
     'the CLI ladder must start at the multi-draw baseline')

print(f'PASS capture version contract: {len(enum)} ladder levels '
      f'({min(enum.values())}..{max(enum.values())}), '
      f'{len(schema.get("other_headers", []))} other headers, '
      f'{len(schema.get("legacy", []))} legacy, '
      f'reader accepts {len(accepted)} versions, '
      f'CLI ladder agrees on all {len(cli)}')
