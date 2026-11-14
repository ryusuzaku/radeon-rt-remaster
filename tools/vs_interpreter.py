"""An independent Python reading of the vs_2_0 position interpreter (docs/VS_INTERPRETER.md), for the ledger reader.

It parses the same token stream as src/shader/vs_interpreter.cpp, takes the same backward slice of oPos and refuses the same
things, but it is a separate implementation: it evaluates in double precision and carries, for every value, a bound on how much
float32 rounding could have moved it (`magnitude`). The reader accepts a recorded clip component when it lies within the usual
relative 2e-4 plus F32_ROUNDING times that bound. A mova whose input lies too close to a rounding boundary for that bound to
decide is refused as ambiguous, never guessed. Pure Python, standard library only.
"""
import math
import struct

F32_ROUNDING = 8 * 2.0 ** -24
TEMP, INPUT, CONST, ADDR, RASTOUT, ATTROUT, TEXOUT = 0, 1, 2, 3, 4, 5, 6
MOV, ADD, MAD, MUL, DP3, DP4, MIN, MAX, ABS, MOVA = 1, 2, 4, 5, 8, 9, 10, 11, 35, 46
SUPPORTED = {MOV, ADD, MAD, MUL, DP3, DP4, MIN, MAX, ABS, MOVA}
SOURCES = {MAD: 3, ADD: 2, MUL: 2, DP3: 2, DP4: 2, MIN: 2, MAX: 2}
FLOW_OPEN, FLOW_ELSE, FLOW_CLOSE = {40, 41, 27, 38}, {42}, {43, 29, 39}


class Refused(ValueError):
    pass


def _type(t): return ((t >> 28) & 7) | ((t >> 8) & 0x18)


def _camera(body):
    camera = {}
    if len(body) < 8 or body[0] != 0x42415443: return camera
    data = struct.pack('<%dI' % (len(body) - 1), *body[1:])
    u32 = lambda at: struct.unpack_from('<I', data, at)[0] if at + 4 <= len(data) else 0
    u16 = lambda at: struct.unpack_from('<H', data, at)[0] if at + 2 <= len(data) else 0
    count, info = u32(12), u32(16)
    if count > 256 or info >= len(data): return camera
    for i in range(count):
        at = info + i * 20; name = u32(at)
        if name >= len(data): continue
        text = data[name:data.index(b'\0', name) if b'\0' in data[name:] else len(data)][:64].decode('latin-1')
        if u16(at + 4) != 2: continue
        index, registers = u16(at + 6), u16(at + 8)
        if text == 'cViewProj' and registers >= 4: camera['view_projection'] = index
        elif text == 'cModelViewProj' and registers >= 4: camera['model_view_projection'] = index
        elif text == 'cModel' and registers >= 3: camera['model'] = index
    return camera


def analyse(tokens):
    """Parse and slice a vs_2_0 program; returns a dict or raises Refused naming the reason, as the C++ analysis does."""
    if not tokens or tokens[0] != 0xfffe0200: raise Refused('unsupported_shader_model')
    code, defs, declared, camera = [], {}, {}, {}
    i, depth = 1, 0
    def dst(t):
        if (t >> 20) & 15 & ~3: raise Refused('unsupported_result_modifier')
        if (t >> 24) & 15: raise Refused('unsupported_result_shift')
        if t & (1 << 13): raise Refused('relative_destination')
        return dict(type=_type(t), reg=t & 0x7ff, mask=(t >> 16) & 15, saturate=bool((t >> 20) & 1))
    while i < len(tokens):
        t = tokens[i]; op = t & 0xffff
        if op == 0xffff: break
        if op == 0xfffe:
            n = (t >> 16) & 0x7fff
            if i + 1 + n > len(tokens): raise Refused('truncated_program')
            camera.update(_camera(tokens[i + 1:i + 1 + n])); i += 1 + n; continue
        n = (t >> 24) & 15
        if i + 1 + n > len(tokens): raise Refused('truncated_program')
        if t & (1 << 28): raise Refused('predicated_instruction')
        params = tokens[i + 1:i + 1 + n]
        if op in (25, 26, 28, 30): raise Refused('subroutines')
        if op == 31:
            if n != 2: raise Refused('malformed_dcl')
            d = dst(params[1])
            if d['type'] == INPUT: declared[d['reg']] = (params[0] & 31, (params[0] >> 16) & 15)
            i += 1 + n; continue
        if op == 81:
            if n != 5: raise Refused('malformed_def')
            d = dst(params[0])
            if d['type'] != CONST or d['reg'] >= 256: raise Refused('malformed_def')
            defs[d['reg']] = struct.unpack('<4f', struct.pack('<4I', *params[1:5])); i += 1 + n; continue
        if op in (47, 48): i += 1 + n; continue
        if op in FLOW_OPEN: depth += 1; i += 1 + n; continue
        if op in FLOW_ELSE:
            if not depth: raise Refused('malformed_flow_control')
            i += 1 + n; continue
        if op in FLOW_CLOSE:
            if not depth: raise Refused('malformed_flow_control')
            depth -= 1; i += 1 + n; continue
        if op in (44, 45) or n == 0: i += 1 + n; continue
        ins = dict(op=op, dst=dst(params[0]), src=[], depth=depth, slice=False); k = 1
        while k < len(params):
            s = params[k]; k += 1
            src = dict(type=_type(s), reg=s & 0x7ff, swizzle=[(s >> (16 + 2 * c)) & 3 for c in range(4)], modifier=(s >> 24) & 15, relative=None)
            if s & (1 << 13):
                if k >= len(params): raise Refused('truncated_program')
                a = params[k]; k += 1
                if _type(a) != ADDR or a & 0x7ff: raise Refused('unsupported_relative_address')
                src['relative'] = (a >> 16) & 3
            ins['src'].append(src)
        code.append(ins); i += 1 + n
    if depth: raise Refused('malformed_flow_control')
    needed, inputs, constants, relative, wrote = {}, {}, set(), [], False
    for ins in reversed(code):
        d = ins['dst']
        if d['type'] == RASTOUT and d['reg'] == 0: want = d['mask']; wrote = True
        elif d['type'] in (TEMP, ADDR):
            key = (d['type'], d['reg']); want = needed.get(key, 0) & d['mask']
            if key in needed: needed[key] &= ~d['mask']
        else: want = 0
        if not want: continue
        ins['slice'] = True
        if ins['depth']: raise Refused('position_in_flow_control')
        if ins['op'] not in SUPPORTED: raise Refused('unsupported_slice_opcode')
        if len(ins['src']) != SOURCES.get(ins['op'], 1): raise Refused('malformed_instruction')
        if d['saturate']: raise Refused('unsupported_result_modifier')
        for s in ins['src']:
            if s['modifier'] not in (0, 1): raise Refused('unsupported_source_modifier')
            if ins['op'] == DP4: comps = {s['swizzle'][c] for c in range(4)}
            elif ins['op'] == DP3: comps = {s['swizzle'][c] for c in range(3)}
            else: comps = {s['swizzle'][c] for c in range(4) if want >> c & 1}
            mask = sum(1 << c for c in comps)
            if s['relative'] is not None:
                if s['type'] != CONST: raise Refused('unsupported_relative_address')
                needed[(ADDR, 0)] = needed.get((ADDR, 0), 0) | 1 << s['relative']; relative.append(s['reg']); continue
            if s['type'] in (TEMP, ADDR): needed[(s['type'], s['reg'])] = needed.get((s['type'], s['reg']), 0) | mask
            elif s['type'] == INPUT:
                if s['reg'] >= 16 or s['reg'] not in declared: raise Refused('undeclared_input')
                usage, index = declared[s['reg']]
                inputs.setdefault(s['reg'], dict(reg=s['reg'], usage=usage, usage_index=index, mask=0))['mask'] |= mask
            elif s['type'] == CONST:
                if s['reg'] >= 256: raise Refused('constant_range')
                if s['reg'] not in defs: constants.add(s['reg'])
            else: raise Refused('unsupported_slice_register')
    if not wrote: raise Refused('no_position_output')
    if any(m and k[0] == TEMP for k, m in needed.items()): raise Refused('uninitialised_temporary')
    if needed.get((ADDR, 0)): raise Refused('uninitialised_address')
    return dict(code=code, defs=defs, inputs=sorted(inputs.values(), key=lambda x: x['reg']), constants=constants, relative=relative, camera=camera)


INPUT_SIZE = {0: 4, 1: 8, 2: 12, 3: 16, 4: 4, 5: 4, 6: 4, 7: 8, 8: 4, 9: 4, 10: 8, 11: 4, 12: 8}


def convert(decl_type, raw):
    """(value, magnitude) of one input register, as the device presents it; normalised types carry their division's rounding."""
    exact = lambda v: (list(v), [0.0] * 4)
    rounded = lambda v: (list(v), [abs(x) for x in v])
    if decl_type in (0, 1, 2, 3):
        v = list(struct.unpack('<%df' % (decl_type + 1), raw)) + [0.0, 0.0, 0.0, 1.0][decl_type + 1:]; return exact(v)
    b = raw
    if decl_type == 4: return rounded([b[2] / 255, b[1] / 255, b[0] / 255, b[3] / 255])
    if decl_type == 5: return exact([float(x) for x in b[:4]])
    if decl_type == 6: s = struct.unpack('<2h', raw); return exact([float(s[0]), float(s[1]), 0.0, 1.0])
    if decl_type == 7: return exact([float(x) for x in struct.unpack('<4h', raw)])
    if decl_type == 8: return rounded([x / 255 for x in b[:4]])
    if decl_type == 9: s = struct.unpack('<2h', raw); return rounded([s[0] / 32767, s[1] / 32767, 0.0, 1.0])
    if decl_type == 10: return rounded([x / 32767 for x in struct.unpack('<4h', raw)])
    if decl_type == 11: s = struct.unpack('<2H', raw); return rounded([s[0] / 65535, s[1] / 65535, 0.0, 1.0])
    if decl_type == 12: return rounded([x / 65535 for x in struct.unpack('<4H', raw)])
    raise Refused('unsupported_input_type')


def evaluate(program, inputs, constants):
    """(clip, magnitude, relative reads) for one vertex. `inputs[reg]` is (value, magnitude); `constants(reg)` returns a 4-tuple or
    None when unknown, which refuses the vertex."""
    temps, address, position, pmag, reads = {}, [0, 0, 0, 0], [0.0] * 4, [0.0] * 4, []
    def read(s):
        if s['type'] == TEMP: v, m = temps.get(s['reg'], ([0.0] * 4, [0.0] * 4))
        elif s['type'] == INPUT: v, m = inputs[s['reg']]
        elif s['type'] == CONST:
            index = s['reg'] + (address[s['relative']] if s['relative'] is not None else 0)
            if not 0 <= index < 256: raise Refused('constant_range')
            if s['relative'] is not None: reads.append(index)
            raw = program['defs'].get(index) or constants(index)
            if raw is None: raise Refused('unknown position constant')
            if not all(map(math.isfinite, raw)): raise Refused('nonfinite constant')
            v, m = list(raw), [0.0] * 4
        else: raise Refused('unsupported_slice_register')
        sign = -1.0 if s['modifier'] == 1 else 1.0
        return [sign * v[s['swizzle'][c]] for c in range(4)], [m[s['swizzle'][c]] for c in range(4)]
    for ins in program['code']:
        if not ins['slice']: continue
        src = [read(s) for s in ins['src']]; op = ins['op']
        (a, ma) = src[0]
        if op == MOVA:
            for c in range(4):
                if ins['dst']['mask'] >> c & 1:
                    x = a[c]; nearest = math.floor(x + 0.5)
                    if abs(abs(x - math.floor(x)) - 0.5) <= F32_ROUNDING * ma[c] + 1e-12: raise Refused('ambiguous_address')
                    address[c] = int(nearest)
            continue
        if op == MOV: v, m = a, ma
        elif op == ABS: v, m = [abs(x) for x in a], ma
        elif op == ADD:
            (b, mb) = src[1]; v = [a[c] + b[c] for c in range(4)]; m = [ma[c] + mb[c] + abs(v[c]) for c in range(4)]
        elif op == MUL:
            (b, mb) = src[1]; v = [a[c] * b[c] for c in range(4)]; m = [ma[c] * abs(b[c]) + abs(a[c]) * mb[c] + abs(v[c]) for c in range(4)]
        elif op == MAD:
            (b, mb), (cc, mc) = src[1], src[2]; p = [a[c] * b[c] for c in range(4)]
            v = [p[c] + cc[c] for c in range(4)]; m = [ma[c] * abs(b[c]) + abs(a[c]) * mb[c] + abs(p[c]) + mc[c] + abs(v[c]) for c in range(4)]
        elif op in (MIN, MAX):
            (b, mb) = src[1]; pick = (lambda x, y: x < y) if op == MIN else (lambda x, y: x >= y)
            v = [a[c] if pick(a[c], b[c]) else b[c] for c in range(4)]; m = [max(ma[c], mb[c]) for c in range(4)]
        elif op in (DP3, DP4):
            (b, mb) = src[1]; n = 3 if op == DP3 else 4; total, mag = 0.0, 0.0
            for c in range(n):
                p = a[c] * b[c]; total += p; mag += ma[c] * abs(b[c]) + abs(a[c]) * mb[c] + abs(p) + abs(total)
            v, m = [total] * 4, [mag] * 4
        else: raise Refused('unsupported_slice_opcode')
        d = ins['dst']
        for c in range(4):
            if d['mask'] >> c & 1:
                if d['type'] == TEMP:
                    tv, tm = temps.setdefault(d['reg'], ([0.0] * 4, [0.0] * 4)); tv[c] = v[c]; tm[c] = m[c]
                else: position[c] = v[c]; pmag[c] = m[c]
    return position, pmag, reads


def matches(recorded, clip, magnitude):
    return all(abs(x - y) <= 2e-4 * (1 + abs(y)) + F32_ROUNDING * m for x, y, m in zip(recorded, clip, magnitude))
