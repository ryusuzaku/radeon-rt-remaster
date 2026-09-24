"""Pinned, isolated single-frame RR dispatch. Execution acceptance is not quality acceptance."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import subprocess

from inspect_rr_inputs import decode_inputs, FILE_BYTES, MAX_FILE_BYTES
from rr_worker import assess, strict_json, verify_sdk
from rr_scale import validate_scale,scaled,scaled_distance,scaled_matrices
from rr_guides import validate_guide,material_type

OUTPUT_BYTES = 56+128*96*16+32


def output_bytes(data): return 56+data['width']*data['height']*16+32


def staging_bytes(width,height):
    offset=0
    for row_bytes in (width*4,)+(width*8,)*5:
        offset=(offset+511)//512*512
        offset+=((row_bytes+255)//256*256)*height
    return offset


def read_exact(path, size):
    with Path(path).open('rb') as stream:
        raw=stream.read(size+1)
    if len(raw)!=size:
        raise ValueError('RR file size mismatch')
    return raw


def half(value):
    return struct.unpack('<e', struct.pack('<e', value))[0]


def validate_albedo_encoding(value):
    if type(value) is not str or value not in ('linear','sqrt'):
        raise ValueError('albedo encoding must be linear or sqrt')
    return value


def encoded_albedo(value,encoding):
    # Match native double sqrt -> float32 -> binary16 packing, not a
    # direct double-to-half shortcut near rounding boundaries.
    return struct.unpack('<f',struct.pack('<f',math.sqrt(value)))[0] if encoding=='sqrt' else value


def packed_hashes(data,albedo_encoding='linear',coordinate_scale='none',guide_preset='none'):
    validate_albedo_encoding(albedo_encoding)
    _,scale=validate_scale(coordinate_scale)
    validate_guide(guide_preset)
    planes=[bytearray() for _ in range(6)]
    for r in data['records']:
        distance=scaled_distance(r[3],scale)
        planes[0] += struct.pack('<f',scaled(r[19],scale))
        planes[1] += struct.pack('<4e',r[16],r[17],scaled(r[18],scale),0)
        planes[2] += struct.pack('<4e',*r[8:11],material_type(r,guide_preset))
        planes[3] += struct.pack('<4e',*[encoded_albedo(v,albedo_encoding) for v in r[12:15]],0)
        planes[4] += struct.pack('<4e',*r[:3],min(distance,65504))
        planes[5] += struct.pack('<4e',-1234,-1234,-1234,min(distance,65504))
    return [sha256(p).hexdigest() for p in planes]


def decode_output(raw, input_data, input_digest,coordinate_scale='none'):
    _,scale=validate_scale(coordinate_scale)
    width,height=input_data['width'],input_data['height']; version=1 if width==128 else 2
    if len(raw)!=output_bytes(input_data) or raw[:8]!=(b'RRTRRO01' if version==1 else b'RRTRRO02') or struct.unpack_from('<4I',raw,8)!=(version,width,height,16):
        raise ValueError('RR output contract mismatch')
    if raw[24:56] != input_digest or sha256(raw[:-32]).digest() != raw[-32:]:
        raise ValueError('RR output input-identity/checksum mismatch')
    rows = list(struct.iter_unpack('<4f', raw[56:-32]))
    for output, source in zip(rows, input_data['records']):
        if not all(math.isfinite(x) for x in output) or any(x < 0 or x > 65504 for x in output[:3]):
            raise ValueError('RR output nonfinite/invalid lighting')
        distance=scaled_distance(source[3],scale)
        if output[3] != half(min(distance, 65504)):
            raise ValueError('RR output alpha changed')
        if not source[23] and output[:3] != (0, 0, 0):
            raise ValueError('RR output background changed')
    return rows


def check_dispatch_report(report, input_data, input_digest, *, external_mib=8, submissions=2, releases=8, frame_index=None, camera_delta=(0,0,0), albedo_encoding='linear',coordinate_scale='none',guide_preset='none'):
    validate_albedo_encoding(albedo_encoding)
    scale_id,scale=validate_scale(coordinate_scale)
    guide_id=validate_guide(guide_preset)
    width,height=input_data['width'],input_data['height']; pixels=width*height
    exact = dict(dispatch_code=0, completed=True, input_sha256=input_digest.hex(), external_bytes=1900544 if width==128 else 6553600,
                 external_limit=external_mib*1024*1024, resources_released=releases, textures=6, reset=input_data['reset'],
                 frame_index=(0 if input_data['reset'] else input_data['frame_index']) if frame_index is None else frame_index, submissions=submissions,
                 uploads_verified=True, inputs_unchanged=True,
                 distance_clamps=sum(r[3]>=100000 or (r[3]>=0 and scaled(r[3],scale)>65504) for r in input_data['records']), output_floats=pixels*4,
                 staging_bytes=staging_bytes(width,height), packed_sha256=packed_hashes(input_data,albedo_encoding,coordinate_scale,guide_preset),
                 formats=['R32_FLOAT']+['RGBA16_FLOAT']*5)
    if width!=128: exact.update(width=width,height=height)
    # Legacy reports predate encoding metadata and are linear-only. Partial
    # metadata is invalid; sqrt never inherits a missing/default encoding.
    if albedo_encoding!='linear' or 'albedo_encoding' in report or 'dispatch_flags' in report:
        exact.update(albedo_encoding=albedo_encoding,dispatch_flags=int(input_data['reset'])|(2 if albedo_encoding=='linear' else 0))
    if scale_id: exact['coordinate_scale']=coordinate_scale
    if guide_id: exact['guide_preset']=guide_preset
    if scale_id:
        view,projection=scaled_matrices(input_data['matrices'],scale)
        exact.update(scaled_view_sha256=sha256(struct.pack('<16f',*view)).hexdigest(),
                     scaled_projection_sha256=sha256(struct.pack('<16f',*projection)).hexdigest())
    for key, value in exact.items():
        if type(report[key]) is not type(value) or report[key] != value:
            raise ValueError('dispatch field mismatch: '+key)
    if scale_id:
        bounds=report.get('linear_depth_bounds')
        expected=(scaled(.001,scale),scaled(10000,scale))
        if type(bounds) is not list or len(bounds)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x-y)>1e-6*max(1,abs(y)) for x,y in zip(bounds,expected)):
            raise ValueError('linear depth bounds mismatch')
    delta=report['camera_delta']
    camera_delta=tuple(scaled(x,scale) for x in camera_delta)
    if type(delta) is not list or len(delta)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x-y)>1e-6*max(1,abs(y)) for x,y in zip(delta,camera_delta)):
        raise ValueError('camera delta mismatch')
    if type(external_mib) is not int or not 1 <= external_mib <= 8 or report['external_bytes'] > report['external_limit']:
        raise ValueError('external budget mismatch')
    if type(report['changed_pixels']) is not int or not 0 <= report['changed_pixels'] <= pixels:
        raise ValueError('invalid changed pixel count')


def assess_dispatch(envelope, input_data, input_digest, *, budget_mib=64, external_mib=8):
    context = assess(envelope, cycles=1, budget_mib=budget_mib, allow_workaround=True, expected_dispatches=1,
                     width=input_data['width'],height=input_data['height'])
    result = dict(status='unavailable', reason='invalid-dispatch-report', rr_rendering=False, quality_acceptance='not-evaluated')
    if not context['status'].startswith('context-ready'):
        return dict(result, reason=context['reason'], context=context)
    try:
        report = strict_json(envelope['stdout'])['dispatch_test']
        if not input_data['reset']:
            raise ValueError('single dispatch must reset')
        check_dispatch_report(report,input_data,input_digest,external_mib=external_mib)
        return dict(status='dispatch-report-ready', reason=None, rr_rendering=False, quality_acceptance='not-evaluated',
                    context=context, dispatch=report)
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        return result


def run_dispatch(probe, sdk_bin, input_path, output_path, *, budget_mib=64, external_mib=8, fail_allocation=None):
    probe, sdk_bin, input_path = (Path(p).resolve(strict=True) for p in (probe, sdk_bin, input_path))
    output_path = Path(output_path).resolve()
    if not probe.is_file() or not sdk_bin.is_dir() or output_path.exists() or not output_path.parent.is_dir():
        raise ValueError('probe/SDK/new output path invalid')
    if type(budget_mib) is not int or not 1 <= budget_mib <= 64 or type(external_mib) is not int or not 1 <= external_mib <= 8:
        raise ValueError('invalid GPU budgets')
    if fail_allocation is not None and (type(fail_allocation) is not int or not 1 <= fail_allocation <= 31):
        raise ValueError('invalid failure ordinal')
    input_size=input_path.stat().st_size
    if not 392 < input_size <= MAX_FILE_BYTES:
        raise ValueError('invalid input size')
    raw = read_exact(input_path,input_size); data = decode_inputs(raw); digest = raw[-32:]
    if not data['reset']:
        raise ValueError('first isolated dispatch requires a reset input; no SDK history exists')
    hashes = verify_sdk(sdk_bin)
    command = [str(probe), '--isolated-dispatch', '--sdk-bin', str(sdk_bin), '--input', str(input_path),
               '--output', str(output_path), '--debug', '--budget-mib', str(budget_mib), '--external-budget-mib', str(external_mib)]
    if fail_allocation is not None:
        command += ['--fail-allocation', str(fail_allocation)]
    process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=45,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode or len(process.stdout) > 1024*1024:
        raise RuntimeError('RR isolation host failed')
    envelope = strict_json(process.stdout)
    decision = assess_dispatch(envelope, data, digest, budget_mib=budget_mib, external_mib=external_mib)
    if decision['status'] == 'dispatch-report-ready':
        if fail_allocation is not None:
            decision = dict(status='unavailable', reason='failure-injection-not-observed', rr_rendering=False)
        else:
            if output_path.stat().st_size != output_bytes(data):
                raise ValueError('RR output size mismatch')
            pixels = decode_output(read_exact(output_path,output_bytes(data)),data,digest)
            changed = sum(bool(s[23]) and any(o[c] != half(s[c]) for c in range(3)) for s, o in zip(data['records'], pixels))
            if changed != decision['dispatch']['changed_pixels']:
                raise ValueError('RR changed-pixel count mismatch')
            decision.update(status='dispatch-executed-with-workarounds', rr_rendering=True,
                            quality_acceptance='not-evaluated', raw_sdk_acceptance=decision['context']['raw_sdk_acceptance'])
    return dict(decision=decision, worker=envelope, sdk_sha256=hashes, output=str(output_path), input_sha256=digest.hex())


def preview(input_path, output_path, destination):
    from export_gltf import png
    input_path=Path(input_path); data_raw=read_exact(input_path,input_path.stat().st_size); data=decode_inputs(data_raw)
    output=decode_output(read_exact(output_path,output_bytes(data)), data, data_raw[-32:])
    # Side-by-side raw/composited RR; common exposure 1, sRGB transfer, no claim
    # of HDR display fidelity. These generated pixels are only a research view.
    width,height=data['width'],data['height']; image=bytearray(2*width*height*4)
    def display(x):
        x=max(0,min(1,x)); return round(255*(12.92*x if x<=.0031308 else 1.055*x**(1/2.4)-.055))
    for i, source in enumerate(data['records']):
        for side, indirect in enumerate((source[:3],output[i][:3])):
            rgb=[display(source[4+c]+indirect[c]) for c in range(3)]
            offset=((i//width)*(2*width)+i%width+side*width)*4
            image[offset:offset+4]=bytes([rgb[2],rgb[1],rgb[0],255])
    with Path(destination).open('xb') as stream:
        stream.write(png(2*width,height,image))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('probe','sdk-bin','input','output'): parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--preview', type=Path)
    args=parser.parse_args()
    try:
        if args.preview and (args.preview.exists() or args.preview.resolve() in (args.input.resolve(),args.output.resolve())):
            raise ValueError('preview requires a distinct new path')
        report=run_dispatch(args.probe,args.sdk_bin,args.input,args.output)
        if args.preview and report['decision']['rr_rendering']:
            preview(args.input,args.output,args.preview)
        print(json.dumps(report))
        return 0 if report['decision']['rr_rendering'] else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(decision=dict(status='unavailable',reason=str(error),rr_rendering=False))))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
