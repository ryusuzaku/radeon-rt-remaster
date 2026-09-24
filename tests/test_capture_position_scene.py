"""Real ledger input into explicit, atomic offline scene updates."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from capture_position_scene import Capture
from position_scene import Scene

p = argparse.ArgumentParser()
p.add_argument('--capture', type=Path, required=True)
a = p.parse_args()
capture = Capture(a.capture)
assert capture.version == 1 and len(capture.candidates) == 4
report = capture.report()
assert capture.digest == hashlib.sha256(a.capture.read_bytes()).hexdigest()
assert all(c['correspondence'] == 'unresolved' and c['resource_provenance'] is None
           and c['device'] is None for c in report['candidates'])
assert sum(c['triangles'] for c in report['candidates']) == 57
ordinals = [c.ordinal for c in capture.candidates]
scene = Scene()
mapping = {ordinal: f'explicit-draw-{ordinal}' for ordinal in ordinals}
result = capture.apply(scene, 0, 0, capture.digest, mapping)
assert result['scene_delta']['instances'] == 4
before = scene.snapshot()
for c in capture.candidates:
    instance = before['instances'][mapping[c.ordinal]]
    assert instance.geometry.corners == c.geometry.corners and instance.constants == c.constants
result = capture.apply(scene, 0, 1, capture.digest, {ordinals[0]: mapping[ordinals[0]]})
assert result['scene_delta']['new_assets'] == 0 and result['scene_delta']['instances'] == 4
assert sum(c['correspondence'] == 'unresolved' for c in result['candidates']) == 3
before = scene.snapshot()
for digest, assignments in [
    ('0' * 64, mapping), (capture.digest, {4096: 'bad'}),
    (capture.digest, {True: 'bad'}),
    (capture.digest, {ordinals[0]: 'same', ordinals[1]: 'same'}),
    (capture.digest, {ordinals[0]: ''}),
]:
    try:
        capture.apply(scene, 0, 2, digest, assignments)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid assignment admitted')
    assert scene.snapshot() == before
for epoch, sequence, removes in [(0, 1, ()), (1, 2, ()), (0, 2, [mapping[ordinals[0]]])]:
    try:
        capture.apply(scene, epoch, sequence, capture.digest, mapping, removes)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid delta admitted')
    assert scene.snapshot() == before
tiny = Scene(max_geometry_bytes=1)
try:
    capture.apply(tiny, 0, 0, capture.digest, mapping)
except ValueError:
    pass
else:
    raise AssertionError('budget exceeded')
assert tiny.sequence == -1 and not tiny.snapshot()['instances']
capture.apply(scene, 0, 2, capture.digest, {}, list(mapping.values()))
assert not scene.snapshot()['geometry']
scene.reset()
capture.apply(scene, 1, 0, capture.digest, mapping)

with tempfile.TemporaryDirectory(prefix='capture-scene-') as directory:
    bad = Path(directory) / 'bad.jsonl'
    rows = a.capture.read_bytes().splitlines(keepends=True)
    for data in [b''.join(rows[:-1]), b''.join(rows[:-1]) +
                 (json.dumps(dict(json.loads(rows[-1]), reason='io_error')) + '\n').encode()]:
        bad.write_bytes(data)
        try:
            Capture(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('incomplete/error ledger admitted')

script = Path(__file__).resolve().parents[1] / 'tools/capture_position_scene.py'
def cli(*args):
    return subprocess.run([sys.executable, str(script), str(a.capture), *args],
                          capture_output=True, text=True, timeout=15)
r = cli()
assert r.returncode == 0 and json.loads(r.stdout)['source_sha256'] == capture.digest
assignment = f'{ordinals[0]}=chosen'
assert cli('--assign', assignment).returncode == 2
assert cli('--assign', assignment, '--assign', assignment).returncode == 2
r = cli('--assign', assignment, '--source-sha256', capture.digest)
assert r.returncode == 0 and json.loads(r.stdout)['scene_delta']['instances'] == 1
print('PASS real v1: 4 draws/57 triangles, explicit import, reuse, unresolved evidence, atomic failures, removal/reset and CLI digest guards')
