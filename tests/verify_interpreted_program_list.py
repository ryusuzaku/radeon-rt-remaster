"""Contract: the interpreted-program list compiled into the proxy equals the one the reader uses.

docs/schemas/interpreted-vertex-programs.json is what tools/position_interpreted.py admits; src/shader/interpreted_programs.h
is what the proxy admits. A digest in one but not the other would either capture draws the reader then refuses, or let the
reader accept draws the proxy never claimed to verify. Pure Python, no build needed. `--write` regenerates the header.
"""
import json
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
schema = json.loads((root / 'docs/schemas/interpreted-vertex-programs.json').read_text(encoding='utf-8'))
header = root / 'src/shader/interpreted_programs.h'


def render():
    lines = ['#pragma once', '// Vertex programs captured through the vs_2_0 interpreter (docs/VS_INTERPRETER.md). Generated from, and checked against,',
             '// docs/schemas/interpreted-vertex-programs.json by tests/verify_interpreted_program_list.py. Each passed the GPU point oracle.',
             '#include <array>', '#include <string_view>', 'namespace rrt::shader::vsi {',
             f'constexpr std::array<std::string_view,{len(schema["programs"])}> InterpretedPrograms={{']
    lines += [f'    "{p["sha256"]}", // {p["bytes"]} bytes, {p["family"]}' for p in schema['programs']]
    return '\n'.join(lines + ['};', '}', ''])


assert schema['schema'] == 'rrt-interpreted-vertex-programs' and schema['version'] == 1
digests = [p['sha256'] for p in schema['programs']]
assert all(re.fullmatch(r'[0-9a-f]{64}', d) for d in digests) and len(set(digests)) == len(digests), 'digests must be unique lowercase SHA-256'
assert all(isinstance(p['bytes'], int) and 8 <= p['bytes'] <= 16384 and p['bytes'] % 4 == 0 for p in schema['programs'])
hand = {'0c16f3b5a2ba1f9f33162727e7eda81e02d599e20d95743f05a3daab846798d2', 'a84edfd28843f7c8aeac78bcb48c03184326c007593e8d49e99777c8cf1f11dc',
        'c3c0fcaab126f410ba5d7e63fe4215dc022535708d52ae18ccfa4d7ddbff4be2'}
assert not hand & set(digests), 'the three hand-admitted programs keep their own evaluators and must not also be interpreted'
if '--write' in sys.argv:
    header.write_bytes(render().encode()); print('wrote', header)
else:
    assert header.read_bytes().decode() == render(), f'{header} is out of date: run python tests/verify_interpreted_program_list.py --write'
    compiled = re.findall(r'"([0-9a-f]{64})"', header.read_text(encoding='utf-8'))
    assert compiled == digests
    print(f'PASS interpreted program list: {len(digests)} digests, header and schema agree')
