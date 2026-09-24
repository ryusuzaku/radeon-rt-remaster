"""Source-verified moving-camera RR research; execution is not quality acceptance."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess

from inspect_rr_record import decode_record, verify_source, close, MAX_BYTES
from rr_dispatch import check_dispatch_report, decode_output, half, read_exact, OUTPUT_BYTES, output_bytes, validate_albedo_encoding
from rr_worker import assess, strict_json, verify_sdk
from rr_defaults import inspect_defaults
from rr_settings import PRESETS,validate_setting,check_settings
from rr_scale import PRESETS as SCALE_PRESETS,validate_scale
from rr_guides import PRESETS as GUIDE_PRESETS,validate_guide

IDENTITIES=('scene_sha256','material_sha256','shader_sha256','settings_sha256')


def eye(view):
    return tuple(-sum(view[12+k]*view[j*4+k] for k in range(3)) for j in range(3))


def admit_record(raw):
    data=decode_record(raw); first=data['frames'][0]['matrices']['view']; origin=eye(first); previous=origin; deltas=[]
    for frame,meta in zip(data['frames'],data['metadata']):
        view=frame['matrices']['view']; current=eye(view)
        if any(abs(x)>1e6 for matrix in frame['matrices'].values() for x in matrix):
            raise ValueError('matrix exceeds finite range')
        if not close([view[3],view[7],view[11],view[15]],[0,0,0,1]) or not close(
                [sum(view[r*4+k]*view[c*4+k] for k in range(3)) for r in range(3) for c in range(3)],
                [float(r==c) for r in range(3) for c in range(3)]):
            raise ValueError('view must be rigid affine')
        if not close([current[k]-origin[k] for k in range(3)],[meta['pose'][k]-data['settings']['pose'][k] for k in range(3)]):
            raise ValueError('camera/trajectory mismatch')
        if not close([view[r*4+c] for r in range(3) for c in range(3)],[first[r*4+c] for r in range(3) for c in range(3)]):
            raise ValueError('camera rotation changed')
        for row in frame['records']:
            if any(abs(x)>1e6 for x in row) or any(x>65504 for x in row[:3]+row[4:7]+row[12:15]):
                raise ValueError('input exceeds finite/half range')
            if row[23] and not .001<=abs(row[19])<=10000:
                raise ValueError('active depth out of bounds')
            if not frame['reset'] and (row[15]!=row[7] or any(abs(x)>65504 for x in row[16:19])):
                raise ValueError('motion invalid or unsupported; previous projection requires reset')
        deltas.append((0,0,0) if frame['reset'] else tuple(previous[k]-current[k] for k in range(3)))
        previous=current
    data['camera_deltas']=deltas
    return data


def assess_recording(envelope, raw, *, budget_mib=64, external_mib=8, albedo_encoding='linear', query_defaults=False, filter_setting='none',coordinate_scale='none',guide_preset='none'):
    unavailable=dict(status='unavailable',rr_rendering=False,quality_acceptance='not-evaluated')
    try:
        validate_albedo_encoding(albedo_encoding)
        setting_id=validate_setting(filter_setting)[0]
        scale_id,_=validate_scale(coordinate_scale)
        guide_id=validate_guide(guide_preset)
        if type(query_defaults) is not bool: raise ValueError('query-defaults must be boolean')
        data=admit_record(raw); count=data['count']
        segments=sum(frame['reset'] for frame in data['frames'])
        context=assess(envelope,cycles=segments,budget_mib=budget_mib,allow_workaround=True,expected_dispatches=count,recorded_segments=True,width=data['width'],height=data['height'])
        if not context['status'].startswith('context-ready'):
            return dict(unavailable,reason=context['reason'],context=context)
        root=strict_json(envelope['stdout']); report=root['sequence_test']
        defaults=inspect_defaults(root['context_tests'],required=query_defaults or bool(setting_id))
        check_settings(root['context_tests'],report,filter_setting,defaults)
        if report.get('albedo_encoding','linear')!=albedo_encoding:
            raise ValueError('recording encoding mismatch')
        if report.get('coordinate_scale','none')!=coordinate_scale:
            raise ValueError('recording coordinate scale mismatch')
        if report.get('guide_preset','none')!=guide_preset:
            raise ValueError('recording guide preset mismatch')
        if report['reset_policy']!='recreate-context':
            raise ValueError('recorded reset isolation policy mismatch')
        if report['input_sha256']!=raw[-32:].hex() or type(report['frames']) is not list or len(report['frames'])!=count:
            raise ValueError('recording report identity/count mismatch')
        if report['recording']!={key:data[key] for key in IDENTITIES}:
            raise ValueError('source/settings identity mismatch')
        for i,(part,frame,meta,delta,item) in enumerate(zip(data['parts'],data['frames'],data['metadata'],data['camera_deltas'],report['frames'])):
            check_dispatch_report(item,frame,part[-32:],external_mib=external_mib,submissions=2*(i+1),releases=0,
                                  frame_index=meta['segment_index'],camera_delta=delta,albedo_encoding=albedo_encoding,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
        check_dispatch_report(root['dispatch_test'],data['frames'][-1],data['parts'][-1][-32:],external_mib=external_mib,
                              submissions=2*count,frame_index=data['metadata'][-1]['segment_index'],camera_delta=data['camera_deltas'][-1],albedo_encoding=albedo_encoding,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
        if root['dispatch_test']!=dict(report['frames'][-1],resources_released=8):
            raise ValueError('recording final report mismatch')
        return dict(status='recording-report-ready',rr_rendering=False,quality_acceptance='not-evaluated',context=context,sequence=report,default_inspection=defaults)
    except (ValueError,KeyError,TypeError,IndexError,RecursionError,OverflowError):
        return dict(unavailable,reason='invalid-recording-report')


def decode_recording_output(output, raw, *, albedo_encoding='linear', filter_setting='none',coordinate_scale='none',guide_preset='none'):
    validate_albedo_encoding(albedo_encoding)
    setting_id=validate_setting(filter_setting)[0]
    scale_id,_=validate_scale(coordinate_scale)
    guide_id=validate_guide(guide_preset)
    data=admit_record(raw); count=data['count']
    frame_bytes=output_bytes(data['frames'][0]); native_v2=data['width']==256
    expected=(b'RRTRRD01',1,count,OUTPUT_BYTES,0) if albedo_encoding=='linear' else (b'RRTRRD02',2,count,OUTPUT_BYTES,1)
    if setting_id: expected=(b'RRTRRD03',3,count,OUTPUT_BYTES,(setting_id<<1)|int(albedo_encoding=='sqrt'))
    if scale_id: expected=(b'RRTRRD04',4,count,OUTPUT_BYTES,(scale_id<<16)|(setting_id<<1)|int(albedo_encoding=='sqrt'))
    if native_v2: expected=(b'RRTRRD05',5,count,frame_bytes,(1<<24)|(scale_id<<16)|(setting_id<<1)|int(albedo_encoding=='sqrt'))
    if guide_id: expected=(b'RRTRRD06',6,count,frame_bytes,((1<<31) if native_v2 else 0)|(guide_id<<24)|(scale_id<<16)|(setting_id<<1)|int(albedo_encoding=='sqrt'))
    if len(output)!=88+count*frame_bytes or struct.unpack_from('<8s4I',output)!=expected:
        raise ValueError('recording output contract mismatch')
    if output[24:56]!=raw[-32:] or sha256(output[:-32]).digest()!=output[-32:]:
        raise ValueError('recording output identity/checksum mismatch')
    chunks=[output[56+i*frame_bytes:56+(i+1)*frame_bytes] for i in range(count)]
    rows=[decode_output(chunk,frame,part[-32:],coordinate_scale) for chunk,frame,part in zip(chunks,data['frames'],data['parts'])]
    return chunks,rows


def run_recording(probe,sdk_bin,input_path,output_path,*,scene,shader,materials=None,budget_mib=64,external_mib=8,fail_allocation=None,albedo_encoding='linear',query_defaults=False,filter_setting='none',coordinate_scale='none',guide_preset='none'):
    validate_albedo_encoding(albedo_encoding)
    setting_id=validate_setting(filter_setting)[0]
    scale_id,_=validate_scale(coordinate_scale)
    guide_id=validate_guide(guide_preset)
    if type(query_defaults) is not bool: raise ValueError('query-defaults must be boolean')
    query_defaults=query_defaults or bool(setting_id)
    probe,sdk_bin,input_path=(Path(p).resolve(strict=True) for p in (probe,sdk_bin,input_path)); output_path=Path(output_path).resolve()
    if not probe.is_file() or not sdk_bin.is_dir() or output_path.exists() or not output_path.parent.is_dir():
        raise ValueError('probe/SDK/new output path invalid')
    if type(budget_mib) is not int or not 1<=budget_mib<=64 or type(external_mib) is not int or not 1<=external_mib<=8:
        raise ValueError('invalid GPU budgets')
    if fail_allocation is not None and (type(fail_allocation) is not int or not 1<=fail_allocation<=31):
        raise ValueError('invalid failure ordinal')
    with input_path.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    data=admit_record(raw)
    verify_source(scene,data['scene_sha256'],trailer=True); verify_source(shader,data['shader_sha256'])
    verified=['scene','shader']
    if data['material_sha256']!=bytes(32).hex():
        if materials is None: raise ValueError('recording requires the original material sidecar')
        verify_source(materials,data['material_sha256']); verified.append('materials')
    elif materials is not None: raise ValueError('recording did not use a material sidecar')
    hashes=verify_sdk(sdk_bin)
    command=[str(probe),'--isolated-recording','--sdk-bin',str(sdk_bin),'--input',str(input_path),'--output',str(output_path),
             '--debug','--budget-mib',str(budget_mib),'--external-budget-mib',str(external_mib),'--albedo-encoding',albedo_encoding]
    if fail_allocation is not None: command+=['--fail-allocation',str(fail_allocation)]
    if query_defaults: command+=['--query-defaults']
    if setting_id: command+=['--filter-setting',filter_setting]
    if scale_id: command+=['--coordinate-scale',coordinate_scale]
    if guide_id: command+=['--guide-preset',guide_preset]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1024*1024: raise RuntimeError('RR isolation host failed')
    envelope=strict_json(process.stdout); decision=assess_recording(envelope,raw,budget_mib=budget_mib,external_mib=external_mib,albedo_encoding=albedo_encoding,query_defaults=query_defaults,filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
    if decision['status']=='recording-report-ready':
        if fail_allocation is not None: raise ValueError('failure injection not observed')
        output=read_exact(output_path,88+data['count']*output_bytes(data['frames'][0])); _,rows=decode_recording_output(output,raw,albedo_encoding=albedo_encoding,filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)
        for frame,pixels,report in zip(data['frames'],rows,decision['sequence']['frames']):
            changed=sum(bool(s[23]) and any(o[c]!=half(s[c]) for c in range(3)) for s,o in zip(frame['records'],pixels))
            if changed!=report['changed_pixels']: raise ValueError('changed pixel count mismatch')
        decision.update(status='recording-executed-with-workarounds',rr_rendering=True,raw_sdk_acceptance=decision['context']['raw_sdk_acceptance'])
    return dict(decision=decision,worker=envelope,sdk_sha256=hashes,verified_sources=verified,output=str(output_path),input_sha256=raw[-32:].hex(),albedo_encoding=albedo_encoding,query_defaults=query_defaults,filter_setting=filter_setting,coordinate_scale=coordinate_scale,guide_preset=guide_preset)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('probe','sdk-bin','input','output','scene','shader'): parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--materials',type=Path)
    parser.add_argument('--albedo-encoding',choices=('linear','sqrt'),default='linear')
    parser.add_argument('--query-defaults',action='store_true',help='inspect six live-context scalar defaults without configuring them')
    parser.add_argument('--filter-setting',choices=PRESETS,default='none')
    parser.add_argument('--coordinate-scale',choices=SCALE_PRESETS,default='none')
    parser.add_argument('--guide-preset',choices=GUIDE_PRESETS,default='none'); args=parser.parse_args()
    try:
        report=run_recording(args.probe,args.sdk_bin,args.input,args.output,scene=args.scene,shader=args.shader,materials=args.materials,albedo_encoding=args.albedo_encoding,query_defaults=args.query_defaults,filter_setting=args.filter_setting,coordinate_scale=args.coordinate_scale,guide_preset=args.guide_preset)
        print(json.dumps(report)); return 0 if report['decision']['rr_rendering'] else 1
    except (OSError,ValueError,RuntimeError,OverflowError,subprocess.TimeoutExpired) as error:
        print(json.dumps(dict(result='unavailable',reason=str(error),rr_rendering=False))); return 1


if __name__=='__main__': raise SystemExit(main())
