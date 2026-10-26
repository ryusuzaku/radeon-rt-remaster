"""Both admitted pixel programs must reconstruct as faithfully as each other.

The renderer used to admit exactly one pixel program, so "the reconstruction matches"
was a single fact. There are two now, and the second one differs in the fog path:
it measures distance to the eye position in c10 instead of reading an interpolant.
The question this test answers is not "does the 1912-byte program match" but "does
it match as well as the program that was already accepted", measured on the same
draw with the same constants, textures and geometry.

It is deliberately a comparison of two comparisons. A test that only checked the
new program against its own reconstruction would pass just as happily if the
reconstruction were wrong in the same way twice; requiring the accepted program to
clear the same gate first is what makes the number mean something. The native
digests are also required to differ, so a fixture that silently ignored the program
substitution would fail rather than report a perfect match.

The program is extracted from a local shader inventory, which stores full program
bytes as hex. Game bytecode is never committed: without the inventory this test
reports skip 77.
"""
import argparse
import copy
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from inspect_position_capture import inspect_bytes  # noqa: E402
from texture_assets import TextureAssets  # noqa: E402
from replay_pixel_material import probe  # noqa: E402

CANDIDATE = 'dbca89ccb0e1d72bae02fb44cef4b80a6088cec6d163f0d4fe3dbf8661b199b0'
CANDIDATE_ROWS = [10, 11, 12, 29, 30]
GATE = 2e-4
SCAN_LIMIT = 16


def extract(inventory, digest):
    with inventory.open(encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get('kind') != 'draw':
                continue
            value = row.get('ps')
            if isinstance(value, str) and value != 'null':
                code = bytes.fromhex(value)
                if hashlib.sha256(code).hexdigest() == digest:
                    return code
    return None


def prepared(row, texels):
    """A replay row with the fixture's documented sampler/texture subset."""
    row = copy.deepcopy(row)
    row['texture_inputs'] = [{'mips': [{'bytes': texels.hex(), 'size': len(texels),
                                        'sha256': '0' * 64}]} for _ in range(2)]
    for slot, sampler in enumerate(row['pixel_material']['samplers']):
        sampler['states'] = [3, 3, 3, 0, 2, 2, 1, 0, 0, 1, 0, 0, 0]
        sampler['texture'] = {'id': slot + 1, 'type': 3, 'levels': 1, 'lod': 0,
                              'autogen_filter': 0, 'contents': 'unknown',
                              'descriptors': [[4, 4, 21, 0, 0, 0, 0]]}
    return row


def centroid(row):
    positions = bytes.fromhex(row['positions'])
    points = [struct.unpack_from('<3f', positions, i * 12)
              for i in range(len(positions) // 12)]
    return [sum(p[k] for p in points) / len(points) for k in range(3)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args()
    if not args.inventory.is_file() or not args.capture.is_file():
        print('SKIP: local pixel program inventory or pixel-material capture is absent')
        return 77

    candidate = extract(args.inventory, CANDIDATE)
    assert candidate is not None, 'the candidate program is not in the inventory'
    assert len(candidate) == 1912, len(candidate)

    assets = TextureAssets(args.capture)
    rows = inspect_bytes(args.capture.read_bytes(), include_records=True,
                         assets=assets)['records']
    rows = [r for r in rows if r.get('pixel_material') and r.get('color_replay')]
    assert rows, 'capture has no paired pixel-material draw'
    texels = bytes(((x * 37 + y * 11 + c * 53) % 256)
                   for y in range(4) for x in range(4) for c in range(4))

    checked = 0
    for row in rows[:SCAN_LIMIT]:
        base = prepared(row, texels)
        try:
            accepted = probe(base, args.fixture, normalized=True)
        except ValueError:
            continue
        # Only a draw the accepted program reconstructs within the gate can say
        # anything about the candidate. Skipping the rest is the point, not a dodge.
        if accepted['max_normalized_error'] > GATE:
            continue
        centre = centroid(base)
        candidate_row = copy.deepcopy(base)
        candidate_row['color_replay']['pixel_shader'] = candidate.hex()
        candidate_row['pixel_material']['constants'] = (
            struct.pack('<4f', *centre, 1.0).hex() + base['pixel_material']['constants'])
        candidate_row['pixel_material']['rows'] = CANDIDATE_ROWS
        measured = probe(candidate_row, args.fixture, normalized=True)
        assert measured['native_sha256'] != accepted['native_sha256'], \
            'program substitution changed nothing; the comparison is not exercising the candidate'
        assert measured['max_normalized_error'] <= GATE, (
            row['ordinal'], accepted['max_normalized_error'],
            measured['max_normalized_error'])
        checked += 1

    assert checked, 'no draw qualified for comparison'

    # Fail closed: one changed byte must be refused by the program table rather than
    # compared. Otherwise the gate above could be measuring a program we do not admit.
    tampered = bytearray(candidate)
    tampered[-4] ^= 0xff
    broken = copy.deepcopy(candidate_row)
    broken['color_replay']['pixel_shader'] = bytes(tampered).hex()
    try:
        probe(broken, args.fixture, normalized=True)
    except ValueError as error:
        assert 'pixel program not admitted' in str(error), error
    else:
        raise AssertionError('a tampered program was compared instead of refused')

    print(f'PASS: {checked} draw(s) under {GATE:g} for both programs; '
          f'candidate {len(candidate)} bytes, rows {CANDIDATE_ROWS}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
