"""Synthetic compressed payload qualification; does not admit capture evidence."""
import copy
import hashlib
import json
import struct
import subprocess
from replay_pixel_material import payload, probe

FORMATS = {name: int.from_bytes(name.encode(), 'little') for name in ('DXT1', 'DXT3', 'DXT5')}


def blocks(name, width, height, level, slot, alpha='mixed'):
    data = bytearray()
    for y in range((height + 3) // 4):
        for x in range((width + 3) // 4):
            # Exercise every color selector, both DXT5 alpha endpoint modes,
            # and variation between block rows, slots and mip levels.
            seed = x + y * 7 + level * 3 + slot * 5
            selectors = sum(((i + seed) % 4) << (i * 2) for i in range(16))
            if name == 'DXT1':
                if alpha == 'opaque':
                    selectors = sum(min((i + seed) % 4, 2) << (i * 2) for i in range(16))
                elif alpha == 'zero':
                    selectors = 0xffffffff
                data += struct.pack('<HHI', 0x07e0, 0xf800, selectors)
            else:
                if name == 'DXT3':
                    bits = sum(((i + seed + 8) % 16) << (i * 4) for i in range(16))
                    data += (0xffffffffffffffff if alpha == 'opaque' else 0 if alpha == 'zero' else bits).to_bytes(8, 'little')
                else:
                    indices = sum(((i + seed) % 8) << (i * 3) for i in range(16))
                    data += (b'\xff\xff' + b'\0' * 6 if alpha == 'opaque' else b'\0' * 8 if alpha == 'zero'
                             else bytes((224, 32) if seed % 2 else (32, 224)) + indices.to_bytes(6, 'little'))
                data += struct.pack('<HHI', 0xf800 - (seed % 8) * 0x800, 0x07e0, selectors)
    return bytes(data)


def qualify(first, fixture, clean, root):
    report = {'scope': 'synthetic_compressed_isolated_draw', 'capture_admitted': False, 'cases': [], 'rejected': []}
    for name, fmt in FORMATS.items():
        for variant in range(4):
            row = copy.deepcopy(first)
            for slot, sampler in enumerate(row['pixel_material']['samplers']):
                width, height = ((16, 8) if slot == 0 else (32, 16))
                levels = width.bit_length()
                texture = sampler['texture']
                texture.update(levels=levels, lod=levels - 1 if variant == 3 else variant % 2, descriptors=[])
                sampler['states'][4:7] = [1 + variant % 2, 1 + variant % 2, variant % 3]
                sampler['states'][10] = variant % 2
                mips = row['texture_inputs'][slot]['mips'] = []
                for level in range(levels):
                    w, h = max(1, width >> level), max(1, height >> level)
                    texture['descriptors'].append([w, h, fmt, 0, 1, 0, 0])
                    raw = blocks(name, w, h, level, slot)
                    assert len(raw) == ((w + 3) // 4) * ((h + 3) // 4) * (8 if name == 'DXT1' else 16)
                    mips.append({'bytes': raw.hex(), 'sha256': hashlib.sha256(raw).hexdigest()})
            result = probe(row, fixture)
            assert result['status'] == 'matched', (name, variant, result)
            entry = dict(result, format=name, variant=variant)
            report['cases'].append(entry)
            if variant != 0:
                continue
            for control in ('texel', 'alpha', 'lod'):
                changed = probe(row, fixture, control)
                assert changed['status'] == 'different', (name, control, changed)
                entry[control] = changed
            # Fully transparent versus opaque blocks must affect output alpha.
            for alpha in ('opaque', 'zero'):
                changed = copy.deepcopy(row)
                texture = changed['pixel_material']['samplers'][0]['texture']
                for level, (mip, desc) in enumerate(zip(changed['texture_inputs'][0]['mips'], texture['descriptors'])):
                    raw = blocks(name, *desc[:2], level, 0, alpha)
                    mip.update(bytes=raw.hex(), sha256=hashlib.sha256(raw).hexdigest())
                measured = probe(changed, fixture)
                assert measured['status'] == 'matched', (name, alpha, measured)
                if alpha == 'zero':
                    assert measured['native_alpha_sum'] == 0, (name, measured)
                else:
                    assert measured['native_alpha_sum'] > result['native_alpha_sum'] > 0, (name, result, measured)
                entry[alpha] = measured
            for mutation in ('short_tail', 'long_block', 'dxt2', 'dxt4', 'base_alignment', 'extra_mip'):
                changed = copy.deepcopy(row)
                texture = changed['pixel_material']['samplers'][0]['texture']
                mips = changed['texture_inputs'][0]['mips']
                if mutation == 'short_tail':
                    mips[-1]['bytes'] = mips[-1]['bytes'][:-2]
                elif mutation == 'long_block':
                    mips[0]['bytes'] += '00'
                elif mutation in ('dxt2', 'dxt4'):
                    texture['descriptors'][0][2] = int.from_bytes(mutation.upper().encode(), 'little')
                elif mutation == 'base_alignment':
                    texture['descriptors'][0][0] = 15
                else:
                    texture['levels'] += 1
                    mips.append(copy.deepcopy(mips[-1]))
                native = subprocess.run([str(fixture), '--pixel-replay'], input=payload(changed),
                                        env=clean, capture_output=True, text=True, timeout=30)
                assert native.returncode != 0 and 'pixel ' in native.stderr, (name, mutation, native.stdout, native.stderr)
                report['rejected'].append(name + ':' + mutation)
    (root / 'pixel-compressed-comparison.json').write_text(json.dumps(report, indent=2))

