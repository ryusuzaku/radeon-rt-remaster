"""Coherent coordinate-scale provenance and execution contracts."""
import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

from verify_dxr import fixture,encode_scene
from rr_recorded_dispatch import run_recording,assess_recording,decode_recording_output
from rr_quality import analyze


def need(value,why):
    if not value: raise AssertionError(why)


def rejects(call):
    try: call()
    except (ValueError,KeyError,TypeError): return
    raise AssertionError('invalid scale/provenance accepted')


def main():
    parser=argparse.ArgumentParser()
    for name in ('probe','sdk-bin','dxr'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); folder=Path(tempfile.mkdtemp(prefix='rr-scale-',dir=args.probe.parent))
    scene=folder/'source.rrscene'; scene.write_bytes(encode_scene(fixture())); shader=args.dxr.parent/'rrt_rr_inputs.dxil'
    recording=folder/'moving.rrcapture'
    p=subprocess.run([str(args.dxr),str(scene),'--mode','gi','--samples','4','--rr-record',str(recording),'--rr-step','.04','.01','0','--sun-radius','0','--debug'],capture_output=True,text=True,timeout=45)
    need(p.returncode==0,(p.stdout,p.stderr)); raw=recording.read_bytes(); results={}; chunks={}
    for preset in ('none','unit-tenth','unit-one','unit-ten'):
        output=folder/f'{preset}.rrrecordout'; execution=folder/f'{preset}-execution.json'
        worker=run_recording(args.probe,args.sdk_bin,recording,output,scene=scene,shader=shader,coordinate_scale=preset)
        need(worker['decision']['rr_rendering'],worker); execution.write_text(json.dumps(worker),encoding='utf-8')
        chunks[preset],rows=decode_recording_output(output.read_bytes(),raw,coordinate_scale=preset)
        need(all(frame.get('coordinate_scale','none')==preset for frame in worker['decision']['sequence']['frames']),'frame scale provenance mismatch')
        results[preset]=dict(output_sha256=sha256(output.read_bytes()).hexdigest(),changed=[f['changed_pixels'] for f in worker['decision']['sequence']['frames']])
    need(chunks['unit-one']==chunks['none'],'unit-one changed inner SDK frame bytes')
    need(chunks['unit-tenth']!=chunks['none'] and chunks['unit-ten']!=chunks['none'],'nontrivial scale had no SDK response')
    # Scale and the existing single-key setting have independent provenance.
    combined=folder/'combined.rrrecordout'; combined_execution=folder/'combined-execution.json'
    combined_worker=run_recording(args.probe,args.sdk_bin,recording,combined,scene=scene,shader=shader,
                                  coordinate_scale='unit-one',filter_setting='stability-zero')
    combined_execution.write_text(json.dumps(combined_worker),encoding='utf-8')
    decode_recording_output(combined.read_bytes(),raw,coordinate_scale='unit-one',filter_setting='stability-zero')
    rejects(lambda:decode_recording_output(combined.read_bytes(),raw,coordinate_scale='unit-one'))
    for actual in ('unit-tenth','unit-one','unit-ten'):
        output=(folder/f'{actual}.rrrecordout').read_bytes()
        for expected in ('none','unit-tenth','unit-one','unit-ten'):
            if expected!=actual: rejects(lambda output=output,expected=expected:decode_recording_output(output,raw,coordinate_scale=expected))
    one=json.loads((folder/'unit-one-execution.json').read_text()); root=json.loads(one['worker']['stdout'])
    mutations=[]
    for key,value in [('coordinate_scale','unit-ten'),('coordinate_scale',None),('scaled_view_sha256','0'*64),
                      ('scaled_projection_sha256','0'*64),('linear_depth_bounds',[.002,9000])]:
        changed=copy.deepcopy(root); frame=changed['sequence_test']['frames'][1]
        if value is None: del frame[key]
        else: frame[key]=value
        mutations.append(changed)
    for changed in mutations:
        envelope=copy.deepcopy(one['worker']); envelope['stdout']=json.dumps(changed)
        need(assess_recording(envelope,raw,coordinate_scale='unit-one')['status']=='unavailable','malformed scale report accepted')
    need(assess_recording(one['worker'],raw)['status']=='unavailable','configured scale implicitly accepted as none')
    with patch('rr_recorded_dispatch.subprocess.run',side_effect=AssertionError('invalid preset launched worker')):
        for value in (None,True,1,[],{},'tenth','nan'):
            rejects(lambda value=value:run_recording(args.probe,args.sdk_bin,recording,folder/'invalid.out',scene=scene,shader=shader,coordinate_scale=value))
    for options in (['--coordinate-scale','unit-one'],['--isolated-context','--coordinate-scale','unit-one'],
                    ['--isolated-recording','--coordinate-scale','bad'],
                    ['--isolated-recording','--coordinate-scale','unit-one','--coordinate-scale','unit-ten']):
        command=[str(args.probe),'--sdk-bin',str(args.sdk_bin.resolve()),*options]
        p=subprocess.run(command,capture_output=True,text=True,timeout=45)
        need(p.returncode!=0,'invalid native scale options accepted')
    report,arrays=analyze(recording,folder/'unit-one.rrrecordout',scene,shader,folder/'unit-one-execution.json',
                          samples=64,fallback=True,coordinate_scale='unit-one')
    need(report['coordinate_scale']=='unit-one' and report['quality_acceptance']=='not-qualified' and arrays['recording_sha256'].tobytes()==raw[-32:],
         'quality scale provenance mismatch')
    # A sealed header mutation must not alias another fixed preset.
    damaged=bytearray((folder/'unit-ten.rrrecordout').read_bytes()); struct.pack_into('<I',damaged,20,1<<16); damaged[-32:]=sha256(damaged[:-32]).digest()
    rejects(lambda:decode_recording_output(damaged,raw,coordinate_scale='unit-ten'))
    summary=dict(result='pass',scope='coherent-coordinate-scale-contract',quality_acceptance='not-qualified',
                 unit_one_inner_frames_exact=True,report_mutations=len(mutations),results=results,artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('result','scope','quality_acceptance','unit_one_inner_frames_exact','artifacts')}))


if __name__=='__main__': main()
