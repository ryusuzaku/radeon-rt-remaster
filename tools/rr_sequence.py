"""Bounded stationary RR history research; execution is not quality acceptance."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess

from inspect_rr_inputs import decode_inputs, FILE_BYTES
from rr_dispatch import read_exact, check_dispatch_report, decode_output, OUTPUT_BYTES, half
from rr_worker import assess, strict_json, verify_sdk

HEADER = struct.Struct('<8s4I')
MAX_BYTES = HEADER.size+8*FILE_BYTES+32


def validate_frames(raw_frames):
    if not 2 <= len(raw_frames) <= 8:
        raise ValueError('RR sequence requires 2..8 frames')
    frames = [decode_inputs(raw) for raw in raw_frames]
    for i, frame in enumerate(frames):
        if frame['reset']:
            if frame['frame_index'] or frame['random_index']:
                raise ValueError('reset segment must start at zero')
        else:
            if not i:
                raise ValueError('missing initial reset')
            previous=frames[i-1]
            if (frame['frame_index'],frame['random_index'],frame['seed']) != (previous['frame_index']+1,previous['random_index']+1,previous['seed']):
                raise ValueError('frame/seed discontinuity')
            m,p=frame['matrices'],previous['matrices']
            if any(m[key]!=p[key] for key in ('inverse_view_projection','view','projection')):
                raise ValueError('stationary camera changed')
            vp=[sum(p['view'][row*4+k]*p['projection'][k*4+col] for k in range(4)) for row in range(4) for col in range(4)]
            if any(abs(a-b)>=.0005 for a,b in zip(m['previous_view'],p['view'])) or any(abs(a-b)>=.0005 for a,b in zip(m['previous_view_projection'],vp)):
                raise ValueError('previous camera mismatch')
            for a,b in zip(frame['records'],previous['records']):
                if a[4:15]!=b[4:15] or a[19:]!=b[19:]:
                    raise ValueError('stationary direct lighting/material/geometry changed')
                if a[15]!=a[7] or any(abs(x)>1e-5 for x in a[16:19]):
                    raise ValueError('stationary motion invalid')
    return frames


def encode_sequence(raw_frames):
    validate_frames(raw_frames)
    data=HEADER.pack(b'RRTRRS01',1,len(raw_frames),FILE_BYTES,0)+b''.join(raw_frames)
    return data+sha256(data).digest()


def decode_sequence(raw):
    if not HEADER.size+2*FILE_BYTES+32 <= len(raw) <= MAX_BYTES:
        raise ValueError('sequence length invalid')
    magic,version,count,stride,reserved=HEADER.unpack_from(raw)
    if (magic,version,stride,reserved)!=(b'RRTRRS01',1,FILE_BYTES,0) or not 2<=count<=8:
        raise ValueError('sequence header invalid')
    if len(raw)!=HEADER.size+count*FILE_BYTES+32 or sha256(raw[:-32]).digest()!=raw[-32:]:
        raise ValueError('sequence count/checksum invalid')
    parts=[raw[HEADER.size+i*FILE_BYTES:HEADER.size+(i+1)*FILE_BYTES] for i in range(count)]
    return parts,validate_frames(parts)


def read_sequence(path):
    with Path(path).open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    decode_sequence(raw)
    return raw


def assess_sequence(envelope, raw, *, budget_mib=64, external_mib=8):
    unavailable=dict(status='unavailable',rr_rendering=False,quality_acceptance='not-evaluated')
    try:
        parts,frames=decode_sequence(raw)
        context=assess(envelope,cycles=1,budget_mib=budget_mib,allow_workaround=True,expected_dispatches=len(frames))
        if not context['status'].startswith('context-ready'):
            return dict(unavailable,reason=context['reason'],context=context)
        root=strict_json(envelope['stdout']); report=root['sequence_test']
        if report['input_sha256']!=raw[-32:].hex() or type(report['frames']) is not list or len(report['frames'])!=len(frames):
            raise ValueError('sequence report identity/count mismatch')
        for i,(part,frame,item) in enumerate(zip(parts,frames,report['frames'])):
            check_dispatch_report(item,frame,part[-32:],external_mib=external_mib,submissions=2*(i+1),releases=0)
        check_dispatch_report(root['dispatch_test'],frames[-1],parts[-1][-32:],external_mib=external_mib,submissions=2*len(frames))
        final=dict(report['frames'][-1],resources_released=8)
        if root['dispatch_test']!=final:
            raise ValueError('sequence final report mismatch')
        return dict(status='sequence-report-ready',rr_rendering=False,quality_acceptance='not-evaluated',context=context,sequence=report)
    except (ValueError,KeyError,TypeError,IndexError,RecursionError,OverflowError):
        return dict(unavailable,reason='invalid-sequence-report')


def decode_sequence_output(output, raw):
    parts,frames=decode_sequence(raw)
    if len(output)!=88+len(frames)*OUTPUT_BYTES or HEADER.unpack_from(output)!=(b'RRTRRT01',1,len(frames),OUTPUT_BYTES,0):
        raise ValueError('sequence output contract mismatch')
    if output[24:56]!=raw[-32:] or sha256(output[:-32]).digest()!=output[-32:]:
        raise ValueError('sequence output identity/checksum mismatch')
    chunks=[output[56+i*OUTPUT_BYTES:56+(i+1)*OUTPUT_BYTES] for i in range(len(frames))]
    rows=[decode_output(chunk,frame,part[-32:]) for chunk,frame,part in zip(chunks,frames,parts)]
    return chunks,rows


def run_sequence(probe,sdk_bin,input_path,output_path,*,budget_mib=64,external_mib=8,fail_allocation=None):
    probe,sdk_bin,input_path=(Path(p).resolve(strict=True) for p in (probe,sdk_bin,input_path))
    output_path=Path(output_path).resolve()
    if not probe.is_file() or not sdk_bin.is_dir() or output_path.exists() or not output_path.parent.is_dir():
        raise ValueError('probe/SDK/new output path invalid')
    if type(budget_mib) is not int or not 1<=budget_mib<=64 or type(external_mib) is not int or not 1<=external_mib<=8:
        raise ValueError('invalid GPU budgets')
    if fail_allocation is not None and (type(fail_allocation) is not int or not 1<=fail_allocation<=31):
        raise ValueError('invalid failure ordinal')
    raw=read_sequence(input_path); parts,frames=decode_sequence(raw); hashes=verify_sdk(sdk_bin)
    command=[str(probe),'--isolated-sequence','--sdk-bin',str(sdk_bin),'--input',str(input_path),'--output',str(output_path),
             '--debug','--budget-mib',str(budget_mib),'--external-budget-mib',str(external_mib)]
    if fail_allocation is not None: command+=['--fail-allocation',str(fail_allocation)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1024*1024: raise RuntimeError('RR isolation host failed')
    envelope=strict_json(process.stdout); decision=assess_sequence(envelope,raw,budget_mib=budget_mib,external_mib=external_mib)
    if decision['status']=='sequence-report-ready':
        if fail_allocation is not None: raise ValueError('failure injection not observed')
        output=read_exact(output_path,88+len(frames)*OUTPUT_BYTES)
        _,rows=decode_sequence_output(output,raw)
        for frame,pixels,report in zip(frames,rows,decision['sequence']['frames']):
            changed=sum(bool(s[23]) and any(o[c]!=half(s[c]) for c in range(3)) for s,o in zip(frame['records'],pixels))
            if changed!=report['changed_pixels']: raise ValueError('changed pixel count mismatch')
        decision.update(status='sequence-executed-with-workarounds',rr_rendering=True,raw_sdk_acceptance=decision['context']['raw_sdk_acceptance'])
    return dict(decision=decision,worker=envelope,sdk_sha256=hashes,output=str(output_path),input_sha256=raw[-32:].hex())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    pack=sub.add_parser('pack'); pack.add_argument('--output',type=Path,required=True); pack.add_argument('frames',nargs='+',type=Path)
    run=sub.add_parser('run')
    for key in ('probe','sdk-bin','input','output'): run.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='pack':
            if not 2<=len(args.frames)<=8: raise ValueError('requires 2..8 frames')
            raw=encode_sequence([read_exact(path,FILE_BYTES) for path in args.frames])
            with args.output.open('xb') as stream: stream.write(raw)
            print(json.dumps(dict(result='packed',frames=len(args.frames),rr_rendering=False)))
            return 0
        report=run_sequence(args.probe,args.sdk_bin,args.input,args.output); print(json.dumps(report))
        return 0 if report['decision']['rr_rendering'] else 1
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error),rr_rendering=False)))
        return 1


if __name__=='__main__': raise SystemExit(main())
