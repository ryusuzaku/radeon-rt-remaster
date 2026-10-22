"""CPU controls for exact RR comparisons, independent of SDK availability."""
from pathlib import Path
import copy
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from rr_repeatability import CONTROL_KEYS, compare_frames, comparison, guide_digest


def need(ok, reason):
    if not ok:
        raise AssertionError(reason)


def main():
    zero = bytes(196696)
    changed = bytearray(zero)
    struct.pack_into('<f', changed, 56, .25)
    delta = compare_frames([zero], [bytes(changed)])
    need(not delta['rgba_byte_equal'] and delta['frames'][0]['pixels_different'] == 1 and
         delta['frames'][0]['components_different'] == 1 and delta['frames'][0]['maximum_rgb_difference'] == .25 and
         delta['frames'][0]['rgb_mse'] == .0625/(128*96*3), 'injected difference missed')
    # Equal RGB with a sign-bit change must still fail exact RGBA equality.
    signed = bytearray(zero)
    struct.pack_into('<I', signed, 56+12, 0x80000000)
    delta = compare_frames([zero], [bytes(signed)])
    need(not delta['rgba_byte_equal'] and delta['frames'][0]['components_different'] == 1 and
         delta['frames'][0]['rgb_mse'] == 0, 'bitwise alpha control missed')
    header = bytearray(zero)
    header[24] = 1
    need(compare_frames([zero], [bytes(header)])['rgba_byte_equal'], 'input identity treated as pixel difference')
    controls = [{key: key for key in CONTROL_KEYS}]
    equal = comparison([zero], [zero], ['a'], ['a'], controls, controls)
    need(all(equal[k] for k in ('rgba_byte_equal', 'input_records_and_matrices_equal', 'dispatch_controls_equal')), 'equal control failed')
    for key in CONTROL_KEYS:
        mutated = [dict(controls[0], **{key: 'changed'})]
        need(not comparison([zero], [zero], ['a'], ['a'], controls, mutated)['dispatch_controls_equal'], 'metadata mutation accepted')
    need(not comparison([zero], [zero], ['a'], ['b'], controls, controls)['input_records_and_matrices_equal'], 'input mismatch accepted')
    frame = dict(frame_index=0, random_index=0, seed=1, reset=True,
                 records=[(0.,)*24], matrices={key: (0.,)*16 for key in
                     ('inverse_view_projection', 'view', 'projection', 'previous_view', 'previous_view_projection')})
    changed = dict(frame, frame_index=4)
    need(guide_digest(frame) == guide_digest(changed), 'global ordinal was not omitted')
    for key, value in (('random_index', 1), ('seed', 2), ('reset', False)):
        need(guide_digest(frame) != guide_digest(dict(frame, **{key: value})), 'sample metadata was omitted')
    changed = copy.deepcopy(frame)
    changed['matrices']['previous_view_projection'] = (1.,)+(0.,)*15
    need(guide_digest(frame) != guide_digest(changed), 'previous matrix was omitted')
    changed = copy.deepcopy(frame)
    changed['records'] = [(-0.,)+(0.,)*23]
    need(guide_digest(frame) != guide_digest(changed), 'input float bits were lost')
    for a, b in (([], []), ([zero], []), ([b'bad'], [zero])):
        try:
            compare_frames(a, b)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid comparison accepted')
    try:
        comparison([zero], [zero], [], [], controls, controls)
    except ValueError:
        pass
    else:
        raise AssertionError('missing metadata accepted')
    print('RR exact comparison controls passed; no SDK/quality acceptance')


if __name__ == '__main__':
    main()
