"""Independent CPU checks of fresh RR input preparation; no SDK dispatch."""
import argparse
import copy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from verify_dxr import fixture, encode_scene
from inspect_rr_inputs import load_inputs, decode_inputs, HEADER
from material_inputs import compile_materials


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def scale(a, b): return tuple(x*b for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return scale(a, 1/math.sqrt(dot(a, a)))
def transform(a, m): return tuple(sum(a[i]*m[i*4+j] for i in range(4)) for j in range(4))
def linear(x): return x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4
def rgb(x): return tuple(linear(((x >> shift) & 255)/255) for shift in (16, 8, 0))


def hash32(x):
    x &= 0xffffffff
    x = ((x ^ (x >> 16))*0x7feb352d) & 0xffffffff
    x = ((x ^ (x >> 15))*0x846ca68b) & 0xffffffff
    return x ^ (x >> 16)


class Random:
    def __init__(self, x): self.state = x
    def next(self):
        self.state = hash32(self.state+0x9e3779b9)
        return (self.state >> 8)/16777216


def basis(n, local):
    t = norm(cross((0, 0, 1) if abs(n[2]) < .999 else (0, 1, 0), n))
    return add(add(scale(t, local[0]), scale(cross(n, t), local[1])), scale(n, local[2]))


class Oracle:
    def __init__(self, scene, materials=None, light=(-.4, .6, -1), intensity=.85, ambient=.15, radius=.04):
        self.scene, self.materials = scene, materials or {}
        self.light, self.intensity, self.ambient, self.radius = norm(light), intensity, ambient, radius
        self.triangles = []
        for index, draw in enumerate(scene['draws']):
            vertices = []
            for v in draw['vertices']:
                p = transform((*v[:3], 1), draw['world'])
                vertices.append((p[:3], rgb(v[3]), v[4:6]))
            for k in range(0, len(draw['indices']), 3):
                self.triangles.append((index, *(vertices[j] for j in draw['indices'][k:k+3])))

    def trace(self, origin, direction, tmin, tmax, pixel=None):
        best = None
        for index, a, b, c in self.triangles:
            draw = self.scene['draws'][index]
            if pixel is not None and draw['render'][23]:
                left, top, right, bottom = draw['scissor']
                if not (left <= pixel[0] < right and top <= pixel[1] < bottom): continue
            e1, e2 = sub(b[0], a[0]), sub(c[0], a[0])
            p = cross(direction, e2); determinant = dot(e1, p)
            if abs(determinant) < 1e-10: continue
            t = sub(origin, a[0]); u = dot(t, p)/determinant
            q = cross(t, e1); v = dot(direction, q)/determinant
            distance = dot(e2, q)/determinant
            if u < 0 or v < 0 or u+v > 1 or not tmin <= distance <= tmax: continue
            n = norm(cross(e1, e2))
            if dot(n, direction) > 0: n = scale(n, -1)
            uv = tuple((1-u-v)*a[2][j]+u*b[2][j]+v*c[2][j] for j in range(2))
            vc = tuple((1-u-v)*a[1][j]+u*b[1][j]+v*c[1][j] for j in range(3))
            color = tuple(x*y for x, y in zip(vc, self.texture(draw, uv)))
            material = self.materials.get(index)
            if material: color = tuple(x*y for x, y in zip(color, material['base_color']))
            best = dict(index=index, normal=n, color=color, material=material, distance=distance,
                        position=add(origin, scale(direction, distance)), edge=min(u, v, 1-u-v))
            tmax = distance
        return best

    def texture(self, d, uv):
        w, h = d['texture_width'], d['texture_height']
        def address(x, extent, kind):
            if kind == 3: return min(max(x, 0), extent-1)
            x %= extent*2 if kind == 2 else extent
            return extent*2-1-x if x >= extent else x
        def texel(x, y):
            x, y = address(x, w, d['sampler'][0]), address(y, h, d['sampler'][1])
            return rgb(struct.unpack_from('<I', d['texture'], (y*w+x)*4)[0])
        x, y = uv[0]*w, uv[1]*h
        if d['sampler'][4] == 1: return texel(math.floor(x), math.floor(y))
        x -= .5; y -= .5; ix, iy = math.floor(x), math.floor(y); fx, fy = x-ix, y-iy
        return tuple(sum(texel(ix+dx, iy+dy)[j]*(fx if dx else 1-fx)*(fy if dy else 1-fy)
                         for dx in (0, 1) for dy in (0, 1)) for j in range(3))

    def sun(self, rng):
        radius, angle = self.radius*math.sqrt(rng.next()), 2*math.pi*rng.next()
        return norm(basis(self.light, (radius*math.cos(angle), radius*math.sin(angle), 1)))

    def direct(self, s, view, light):
        nl = max(0, dot(s['normal'], light)); m = s['material']; c = s['color']
        if self.trace(add(s['position'], scale(s['normal'], .0001)), light, .0001, 100000): nl = 0
        emission = m['emission'] if m else (0, 0, 0)
        if not m: return scale(c, self.intensity*nl)
        nv = max(0, dot(s['normal'], view))
        if nl <= 0 or nv <= 0: return tuple(emission)
        half = norm(add(view, light)); nh = max(0, dot(s['normal'], half)); vh = max(0, dot(view, half))
        a2 = m['roughness']**4; metal = m['metallic']; power = (1-vh)**5
        distribution = a2/(math.pi*(1-nh*nh+nh*nh*a2)**2)
        visibility = .5/(nl*math.sqrt(nv*nv*(1-a2)+a2)+nv*math.sqrt(nl*nl*(1-a2)+a2))
        return tuple(emission[j]+self.intensity*nl*(c[j]*(1-metal)*.96*(1-power)/math.pi+
                     distribution*visibility*((.04*(1-metal)+c[j]*metal)*(1-power)+power)) for j in range(3))

    def check(self, data):
        matrices = data['matrices']; maximum = 0; count = 0
        def close(a, b, label, tolerance=.0005):
            nonlocal maximum
            error = max(abs(x-y)/max(1, abs(y)) for x, y in zip(a, b)); maximum = max(maximum, error)
            need(error < tolerance, (label, error, a, b))
        for axis in range(4):
            unit = tuple(float(j == axis) for j in range(4))
            projected = transform(transform(unit, matrices['view']), matrices['projection'])
            close(transform(projected, matrices['inverse_view_projection']), unit, 'camera matrix convention')
            close(transform(transform(unit, matrices['previous_view']), matrices['projection']),
                  transform(unit, matrices['previous_view_projection']), 'previous camera convention')
        for i, row in enumerate(data['records']):
            x, y = i%128, i//128; ndc = ((x+.5)/64-1, 1-(y+.5)/48)
            near = transform((*ndc, 0, 1), matrices['inverse_view_projection'])
            far = transform((*ndc, 1, 1), matrices['inverse_view_projection'])
            origin, end = scale(near[:3], 1/near[3]), scale(far[:3], 1/far[3])
            direction = norm(sub(end, origin))
            s = self.trace(origin, direction, 0, math.sqrt(dot(sub(end, origin), sub(end, origin))), (x, y))
            need(row[23] == (s['index']+1 if s else 0), ('primary ID', i, row[23], s))
            if not s:
                close(row[4:7], rgb(self.scene['clear_color']), 'background'); continue
            count += 1
            close(row[20:23], s['position'], 'primary position')
            n = s['normal']; p = [n[j]/sum(abs(v) for v in n) for j in (0, 1)]
            if n[2] < 0: p = [(1-abs(p[1-j]))*(1 if p[j] >= 0 else -1) for j in (0, 1)]
            close(row[8:10], [(v+1)/2 for v in p], 'oct normal')
            m = s['material']; metal = m['metallic'] if m else 0
            close(row[10:12], (m['roughness'] if m else 1, 0), 'roughness/class')
            close(row[12:15], scale(s['color'], 1-metal), 'diffuse albedo')
            z = transform((*s['position'], 1), matrices['view'])[2]
            close(row[19:20], [z], 'view depth')
            clip = transform((*s['position'], 1), matrices['previous_view_projection'])
            valid = not data['reset'] and clip[3] > 1e-8
            need(bool(row[15]) == valid, 'motion validity')
            motion = (0, 0, 0)
            if valid:
                motion = (clip[0]/clip[3]*.5+.5-(x+.5)/128, .5-clip[1]/clip[3]*.5-(y+.5)/96,
                          transform((*s['position'], 1), matrices['previous_view'])[2]-z)
            close(row[16:19], motion, 'motion')
            rng = Random(hash32(i)^hash32(data['random_index']+0x1234567)^hash32(data['seed']))
            close(row[4:7], self.direct(s, scale(direction, -1), self.sun(rng)), 'direct/emission')
            u, angle = rng.next(), 2*math.pi*rng.next()
            bounce = basis(n, (math.sqrt(u)*math.cos(angle), math.sqrt(u)*math.sin(angle), math.sqrt(1-u)))
            secondary = self.trace(add(s['position'], scale(n, .0001)), bounce, .0001, 100000)
            # Avoid ambiguous triangle ownership at FP32 secondary edges only.
            if secondary and secondary['edge'] < .0001: continue
            incoming = self.direct(secondary, scale(bounce, -1), self.sun(rng)) if secondary else (self.ambient,)*3
            throughput = s['color']
            if m:
                vh = min(1, max(0, dot(scale(direction, -1), norm(add(scale(direction, -1), bounce)))))
                throughput = scale(throughput, (1-metal)*.96*(1-(1-vh)**5))
            close(row[:3], tuple(a*b for a, b in zip(throughput, incoming)), 'fresh diffuse')
            close(row[3:4], [secondary['distance'] if secondary else 100000], 'bounce distance')
        need(count > 1000, 'insufficient primary coverage')
        return dict(primary_hits=count, maximum_normalized_error=maximum)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--dxr', type=Path, required=True); args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='rr-inputs-', dir=args.dxr.parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith('RRT_')}
    def run(command, ok=True):
        process = subprocess.run([str(args.dxr), *map(str, command)], text=True, capture_output=True, env=env, timeout=60)
        need((process.returncode == 0) == ok, (command, process.stdout, process.stderr))
        return json.loads(process.stdout) if ok else None
    probe = run(['--probe'])
    if not probe['supported']: return 77
    debug = ['--debug'] if probe['debug_available'] else []
    results = {}
    def render(name, scene, extra=(), mats=None):
        source = folder/(name+'.rrscene'); source.write_bytes(encode_scene(scene))
        inputs, pixels, signals = [folder/(name+ext) for ext in ('.rrinputs', '.pixels', '.signals')]
        command = [source, '--mode', 'gi', '--pixels', pixels, '--signals', signals, *debug, *extra]
        if mats:
            entries = [dict(target=scene['draws'][index]['material_id'], base_color=m['base_color'],
                            roughness=m['roughness'], metallic=m['metallic'], emissive=m['emission']) for index, m in mats.items()]
            sidecar = folder/(name+'.rrmat'); sidecar.write_bytes(compile_materials(dict(schema='rrt-materials', version=1, materials=entries), scene))
            command += ['--materials', sidecar]
        report = run([*command, '--rr-inputs', inputs]); data = load_inputs(inputs)
        need(report['rr_dispatches'] == 0 and report['rr_input_preparations'] == 1, 'false RR dispatch report')
        need(report['requested_buffer_bytes'] <= report['requested_buffer_limit_bytes'] and report['scene_build_submissions'] == 1, 'budget/submission accounting')
        results[name] = dict(report=report, oracle=Oracle(scene, mats).check(data))
        return data, command, inputs
    # Decoded scenes contain immutable tuples in several fields, not just vertices.
    def mutable(value):
        if isinstance(value, dict): return {k:mutable(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)): return [mutable(v) for v in value]
        return value
    scene = mutable(fixture())
    single, command, path = render('single', scene)
    repeat, _, repeat_path = render('repeat', scene)
    need(path.read_bytes() == repeat_path.read_bytes(), 'input nondeterminism')
    many, _, _ = render('many', scene, ['--samples', 8])
    need(not many['reset'] and any(a[:4] != b[:4] for a, b in zip(single['records'], many['records'])), 'not fresh per-sample lighting')
    need(all(a[8:15] == b[8:15] and a[20:] == b[20:] for a, b in zip(single['records'], many['records'])), 'noisy primary guides')
    render('seed', scene, ['--seed', 23])
    render('motion', scene, ['--motion-test'])
    render('cut', scene, ['--temporal', '--samples', 2, '--temporal-test', 'cut'])
    render('reset', scene, ['--temporal', '--samples', 2, '--temporal-test', 'reset'])
    tilted = copy.deepcopy(scene)
    for d in tilted['draws']:
        d['vertices'] = [list(v) for v in d['vertices']]
        for v in d['vertices']: v[2] += .06*v[0]+.04*v[1]
    render('tilted', tilted, ['--yaw', 7, '--pitch', -3])
    tilted_motion, _, _ = render('tilted-motion', tilted, ['--yaw', 7, '--pitch', -3, '--motion-test'])
    need(any(abs(r[18]) > .001 for r in tilted_motion['records']), 'view-Z motion not exercised')
    right_handed = copy.deepcopy(scene)
    for d in right_handed['draws']:
        d['projection'][10] = -1
        for v in d['vertices']: v[2] *= -1
    signed, _, _ = render('negative-z', right_handed)
    need(any(r[19] < 0 for r in signed['records']), 'negative view Z not exercised')
    scissored = copy.deepcopy(scene)
    scissored['draws'][0]['render'][23] = 1; scissored['draws'][0]['scissor'] = [20,15,100,80]
    render('scissor', scissored)
    invalid_projection = copy.deepcopy(scene)
    for d in invalid_projection['draws']: d['projection'] = [-x for x in d['projection']]
    invalid_motion, _, _ = render('invalid-projection', invalid_projection, ['--samples', 2])
    need(not any(r[15] or any(r[16:19]) for r in invalid_motion['records']), 'invalid projection produced valid motion')
    perspective = copy.deepcopy(scene); perspective['draws'] = perspective['draws'][:1]; perspective['attempted'] = 1
    perspective['draws'][0]['projection'] = [1.,0,0,0, 0,1.3,0,0, 0,0,2/1.9,1, 0,0,-.2/1.9,0]
    render('perspective', perspective, ['--motion-test'])
    colored = copy.deepcopy(scene); d = colored['draws'][0]
    d['vertices'] = [list(v) for v in d['vertices']]
    d['texture_width']=d['texture_height']=2; d['texture']=bytes([20,80,240,255, 200,20,60,255, 120,200,30,255, 10,40,100,255])
    d['sampler'][4]=d['sampler'][5]=2
    for v in d['vertices']: v[3] = 0xffb080e0
    render('linear-filtering', colored)
    mats = {0:dict(base_color=[.7,.8,.9], roughness=.4, metallic=.2, emission=[.01,.02,.03]),
            1:dict(base_color=[1,1,1], roughness=.6, metallic=0, emission=[2,1,.5])}
    render('pbr', scene, mats=mats)
    # A new diagnostic export must not change ordinary pixels or signal bytes.
    baseline_pixels, baseline_signals = folder/'baseline.pixels', folder/'baseline.signals'
    baseline = run([folder/'single.rrscene', '--mode', 'gi', '--pixels', baseline_pixels, '--signals', baseline_signals, *debug])
    need(baseline_pixels.read_bytes() == (folder/'single.pixels').read_bytes(), 'legacy pixel mutation')
    need(baseline_signals.read_bytes() == (folder/'single.signals').read_bytes(), 'legacy signal mutation')
    need(results['single']['report']['requested_buffer_bytes']-baseline['requested_buffer_bytes'] == 2*128*96*96+512, 'unexpected input allocation')
    run([*command, '--rr-inputs', path], False) # Refuse overwriting.
    run([folder/'single.rrscene', '--rr-inputs', folder/'wrong-mode'], False)
    run([folder/'single.rrscene', '--mode', 'gi', '--rr-inputs', folder/'same', '--pixels', folder/'same'], False)
    bad_view = copy.deepcopy(scene)
    for d in bad_view['draws']: d['view'][0] = 2
    bad_view_path=folder/'bad-view.rrscene'; bad_view_path.write_bytes(encode_scene(bad_view))
    run([bad_view_path, '--mode', 'gi', '--rr-inputs', folder/'bad-view.rrinputs'], False)
    from verify_dxr_resolution import resized
    large=folder/'large.rrscene'; large.write_bytes(encode_scene(resized(257, 129)))
    run([large, '--mode', 'gi', '--rr-inputs', folder/'large.rrinputs'], False)
    need(not (folder/'bad-view.rrinputs').exists() and not (folder/'large.rrinputs').exists(), 'rejected input created output')
    invalid = []
    original = path.read_bytes()
    invalid.extend((original[:-1], original+b'x', original[:500]+bytes([original[500]^1])+original[501:]))
    for offset, fmt, value in ((8, '<I', 2), (12, '<I', 1920), (36, '<I', 2), (40, '<f', math.nan),
                               (HEADER.size+12, '<f', 0), (HEADER.size+7*4, '<f', 1),
                               (HEADER.size+24*4*(48*128+64)+8*4, '<f', 2)):
        candidate=bytearray(original); struct.pack_into(fmt, candidate, offset, value)
        candidate[-32:]=sha256(candidate[:-32]).digest(); invalid.append(bytes(candidate))
    for candidate in invalid:
        try: decode_inputs(candidate)
        except ValueError: pass
        else: raise AssertionError('corrupt input accepted')
    report = dict(result='pass', rr_rendering=False, rejected_files=len(invalid), cases=results, artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(result='pass', cases=len(results), artifacts=str(folder))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
