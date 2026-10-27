"""Local-evidence check: a real HL2 position ledger becomes a scene the renderer draws and the transport carries.

Converts the ledger's largest render group with tools/position_to_scene.py, renders the scene standalone with rrt_dxr, and
renders the same scene through the transport (`rrt_transport_host` driving `rrt_dxr --transport-serve`). Asserted:

  * the conversion's own gate held: projected clip positions match the ledger's captured positions;
  * rrt_dxr admits the scene and draws geometry (a non-trivial share of pixels differs from the clear colour);
  * the transported frame's digest equals the standalone render's, byte for byte.

The ledger is the user's own game capture and stays local: nothing here is committed, and the generated scene and
provenance are written under the ledger's build folder. Exits 77 when the ledger, the renderer or the host is missing, or
without DXR hardware.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import position_to_scene as p  # noqa: E402

SETTINGS = ['--mode', 'gi', '--samples', '1', '--seed', '7']
BACKGROUND = bytes([0x50, 0x28, 0x14])  # the scene clear colour, BGR


def need(value, message):
    if not value: raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--ledger', type=Path); parser.add_argument('--dxr', type=Path); parser.add_argument('--host', type=Path)
    parser.add_argument('--max-extent', type=int, default=1280); args = parser.parse_args()
    for label, path in (('ledger', args.ledger), ('renderer', args.dxr), ('transport host', args.host)):
        if not path or not path.is_file(): print(f'SKIP: {label} unavailable: {path!r}'); return 77
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    probe = json.loads(subprocess.run([str(args.dxr), '--probe'], capture_output=True, text=True, env=env, timeout=60).stdout)
    if not probe['supported']: print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable'); return 77

    folder = Path(tempfile.mkdtemp(prefix='position-scene-', dir=args.ledger.parent)); out = folder / 'scene'
    provenance = p.convert_ledger(args.ledger, out, max_extent=args.max_extent)
    scene = out / 'scene.rrscene'
    need(provenance['max_relative_clip_error'] <= 2e-4 and provenance['triangles'] > 0, f'conversion gate: {provenance}')

    pixels = folder / 'albedo.pixels'
    albedo = subprocess.run([str(args.dxr), str(scene), '--mode', 'albedo', '--pixels', str(pixels)], capture_output=True, text=True, env=env, timeout=120)
    need(albedo.returncode == 0, f'rrt_dxr rejected the converted scene: {albedo.stderr}')
    report = json.loads(albedo.stdout); width, height = report['width'], report['height']
    data = pixels.read_bytes(); need(len(data) == width * height * 3, 'unexpected pixel buffer size')
    covered = sum(data[i * 3:i * 3 + 3] != BACKGROUND for i in range(width * height))
    need(covered >= width * height // 200, f'only {covered} of {width * height} pixels show geometry')

    standalone = subprocess.run([str(args.dxr), str(scene), *SETTINGS], capture_output=True, text=True, env=env, timeout=120)
    need(standalone.returncode == 0, standalone.stderr); want = json.loads(standalone.stdout)['pixel_sha256_bgra']
    command = [str(args.host), '--renderer', str(args.dxr.resolve()), '--scene', str(scene), '--timeout-ms', '20000', '--', *SETTINGS]
    transported = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
    need(transported.returncode == 0, (transported.stdout, transported.stderr)); session = json.loads(transported.stdout)
    need(session['result'] == 'transport-session-pass' and session['frames'][0]['status'] == 0 and session['child_reaped'] is True, f'session: {session}')
    need(session['frames'][0]['output_sha256'] == want, f'transported digest {session["frames"][0]["output_sha256"]} != standalone {want}')
    (folder / 'result.json').write_text(json.dumps(dict(provenance=provenance, covered_pixels=covered, extent=[width, height], digest=want), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(result='pass', draws=len(provenance['draw_ordinals']), triangles=provenance['triangles'], extent=[width, height], covered_pixels=covered,
                          max_relative_clip_error=provenance['max_relative_clip_error'], digest=want, artifacts=str(folder))))
    return 0


if __name__ == '__main__': sys.exit(main())
