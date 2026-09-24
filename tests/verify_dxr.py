"""Standalone DXR acceptance: ray visibility, real shadow occlusion and imports.

No installed game or pre-existing capture artifacts are required.
"""
import argparse
import copy
import json
import os
import struct
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from scene_io import encode_scene, decode_scene
from export_gltf import png
from inspect_signals import load_signals, summarize, HEADER


def fixture():
    identity = [float(i%5==0) for i in range(16)]
    rs = [0]*34
    rs[1]=3; rs[2]=2; rs[7]=1; rs[10]=8; rs[16]=1; rs[18]=1; rs[21]=15; rs[22]=1
    rs[25]=1; rs[26]=0xffffffff; rs[27]=0xffffffff; rs[31]=2; rs[32]=1; rs[33]=1
    draw = dict(ordinal=0, texture_width=1, texture_height=1, world=identity, view=identity,
        projection=identity, viewport=[0,0,128,96,0.0,1.0], scissor=[0,0,128,96], render=rs,
        texture_states=[4,2,0,2,2,0,0,0], sampler=[1,1,1,0,1,1,0,0,0,1,0,0,0],
        vertices=[[-.9,-.9,.8,0xffffffff,0,1],[-.9,.9,.8,0xffffffff,0,0],[.9,-.9,.8,0xffffffff,1,1],[.9,.9,.8,0xffffffff,1,0]],
        indices=[0,1,2,2,1,3], texture=bytes([176,176,176,255]))
    occluder=copy.deepcopy(draw); occluder['ordinal']=1
    occluder['vertices']=[[-.2,-.2,.3,0xffffffff,0,1],[0,.2,.3,0xffffffff,.5,0],[.2,-.2,.3,0xffffffff,1,1]]
    occluder['indices']=[0,1,2]; occluder['texture']=bytes([32,128,240,255])
    return decode_scene(encode_scene(dict(frame=0,width=128,height=96,clear_color=0xff142850,attempted=2,cleared=True,complete=True,rejected=[],draws=[draw,occluder])))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dxr',type=Path,required=True); parser.add_argument('--replay',type=Path,required=True)
    args=parser.parse_args()
    folder=Path(tempfile.mkdtemp(prefix='dxr-',dir=args.dxr.parent))
    env={k:v for k,v in os.environ.items() if not k.startswith('RRT_')}
    def run(command,success=True):
        result=subprocess.run([str(x) for x in command],env=env,text=True,capture_output=True,timeout=60)
        assert (result.returncode==0)==success, f'{command}\n{result.stdout}\n{result.stderr}'
        return result
    probe=json.loads(run([args.dxr,'--probe']).stdout)
    (folder/'capabilities.json').write_text(json.dumps(probe,indent=2)+'\n')
    if not probe['supported']:
        print('SKIP: hardware DXR 1.1 / SM 6.5 unavailable'); return 77
    debug=['--debug'] if probe['debug_available'] else []
    original=fixture(); path=folder/'source.rrscene'; path.write_bytes(encode_scene(original))
    def render(name,scene_path=path,mode='albedo',extra=()):
        pixels=folder/(name+'.pixels')
        report=json.loads(run([args.dxr,scene_path,'--mode',mode,'--pixels',pixels,*debug,*extra]).stdout)
        assert all(report[k]>=0 for k in ('gpu_build_ms','gpu_trace_ms','gpu_copy_ms'))
        assert report['requested_buffer_bytes']<=report['requested_buffer_limit_bytes']
        data=pixels.read_bytes(); assert len(data)==128*96*3
        bgra=bytearray(128*96*4)
        for i in range(128*96):
            bgra[i*4:i*4+3]=data[i*3:i*3+3]; bgra[i*4+3]=255
        (folder/(name+'.png')).write_bytes(png(128,96,bgra))
        return data,report
    albedo,report=render('albedo')
    repeated,_=render('repeat')
    assert albedo==repeated,'DXR output not deterministic'
    raster=folder/'raster.pixels'; run([args.replay,path,'--pixels',raster])
    baseline=raster.read_bytes()
    changed=sum(albedo[i:i+3]!=baseline[i:i+3] for i in range(0,len(albedo),3))
    assert changed/(128*96)<.02, f'DXR/raster visibility mismatch: {changed} pixels'
    # Interior samples distinguish nearest geometry, ground and background.
    def pixel(data,x,y): return data[(y*128+x)*3:(y*128+x+1)*3]
    assert pixel(albedo,64,48)==bytes([32,128,240])
    assert pixel(albedo,30,30)==bytes([176]*3)
    assert pixel(albedo,0,0)==bytes([80,40,20])
    normals,_=render('normals',mode='normals')
    assert pixel(normals,64,48)==bytes([0,128,128])
    relit,lighting=render('relit',mode='relit',extra=['--light','.6','.3','-1'])
    no_shadow,_=render('no-shadow',mode='relit',extra=['--no-shadows','--light','.6','.3','-1'])
    shadow_pixels=sum(relit[i:i+3]!=no_shadow[i:i+3] for i in range(0,len(relit),3))
    assert 50<shadow_pixels<1500, f'no localized shadow: {shadow_pixels}'
    assert all(a<=b for a,b in zip(relit,no_shadow)), 'shadows brightened pixels'
    assert pixel(relit,45,57)[0]<pixel(no_shadow,45,57)[0]-50, 'expected ground shadow absent'
    assert pixel(relit,0,0)==pixel(albedo,0,0)
    # Progressive floating-point accumulation is repeatable for a given seed,
    # improves over a single sample, and never rebuilds/reuploads the scene.
    gi_one,one_report=render('gi-one',mode='gi',extra=['--samples','1'])
    gi_many,many_report=render('gi-32',mode='gi',extra=['--samples','32'])
    gi_reference,reference_report=render('gi-256',mode='gi',extra=['--samples','256'])
    gi_repeat,_=render('gi-repeat',mode='gi',extra=['--samples','32'])
    gi_seed,_=render('gi-seed',mode='gi',extra=['--samples','32','--seed','2'])
    assert gi_many==gi_repeat and gi_many!=gi_seed,'progressive RNG seed/repeatability failure'
    def mse(a,b): return sum((x-y)**2 for x,y in zip(a,b))/len(a)
    single_error=mse(gi_one,gi_reference); accumulated_error=mse(gi_many,gi_reference)
    assert accumulated_error<single_error*.25,(single_error,accumulated_error)
    assert one_report['requested_buffer_bytes']==many_report['requested_buffer_bytes']==reference_report['requested_buffer_bytes']
    for target,info in ((1,one_report),(32,many_report),(256,reference_report)):
        assert info['samples']==info['dispatches']==target and info['scene_build_submissions']==1 and info['history_resets']==0
    history_pixels,history_report=render('history',mode='gi',extra=['--samples','8','--history-test'])
    history_fresh,_=render('history-fresh',mode='gi',extra=['--samples','8'])
    assert history_pixels==history_fresh and history_report['history_test']
    assert history_report['history_resets']==18 and history_report['dispatches']==19*8 and history_report['scene_build_submissions']==1
    assert history_report['requested_buffer_bytes']==one_report['requested_buffer_bytes']
    # Exported float signals remain independent of presentation filtering.
    raw_signal_path=folder/'raw.signals'; filtered_signal_path=folder/'filtered.signals'
    raw_pixels,raw_info=render('signals-raw',mode='gi',extra=['--signals',raw_signal_path])
    filtered_pixels,filtered_info=render('signals-filtered',mode='gi',extra=['--denoise','--signals',filtered_signal_path])
    raw_signals=load_signals(raw_signal_path); filtered_signals=load_signals(filtered_signal_path)
    assert raw_pixels==gi_one and filtered_info['denoised'] and not raw_info['denoised']
    assert raw_info['signal_stride']==144 and raw_info['gpu_filter_ms']>=0 and filtered_info['gpu_filter_ms']>=0
    assert raw_info['requested_buffer_bytes']==filtered_info['requested_buffer_bytes']
    assert raw_signals.samples==1 and raw_signals.flags==0 and filtered_signals.flags==1 and raw_signals.mode==filtered_signals.mode==3
    for raw_row,filtered_row in zip(raw_signals.records(),filtered_signals.records()):
        assert raw_row[:16]==filtered_row[:16],'filter altered raw radiance or guides'
        assert raw_row[:4]==raw_row[16:20],'disabled filter changed float output'
        assert raw_row[14]==0,'first frame has valid previous-camera motion'
        if raw_row[11]==0: assert filtered_row[:4]==filtered_row[16:20],'filter changed background'
    ground=raw_signals.pixel(30,30); front=raw_signals.pixel(64,48)
    assert abs(ground[7]-.8)<1e-6 and abs(front[7]-.3)<1e-6
    assert ground[4:7]==front[4:7]==(0,0,-1)
    assert all(abs(v-176/255)<1e-6 for v in ground[8:11])
    assert ground[15]==1 and front[15]==2
    filter_error=mse(filtered_pixels,gi_reference)
    assert filter_error<single_error*.65,('filter quality',single_error,filter_error)
    filtered_repeat,_=render('filter-repeat',mode='gi',extra=['--denoise'])
    assert filtered_repeat==filtered_pixels
    stable_path=folder/'stable.signals'
    filtered_8,_=render('filter-eight',mode='gi',extra=['--denoise','--samples','8','--signals',stable_path])
    stable=load_signals(stable_path)
    valid=[r for r in stable.records() if r[14]]
    assert len(valid)>1000 and max(abs(v) for r in valid for v in r[12:14])<.0001
    filtered_history,_=render('filtered-history',mode='gi',extra=['--denoise','--samples','8','--history-test'])
    assert filtered_history==filtered_8
    motion_path=folder/'motion.signals'
    motion_pixels,motion_info=render('motion',extra=['--motion-test','--signals',motion_path])
    motion=load_signals(motion_path); motion_ground=motion.pixel(30,30)
    assert motion_info['dispatches']==2 and motion_info['history_resets']==1 and motion_info['scene_build_submissions']==1
    assert motion_ground[14]==1 and abs(motion_ground[12]-6.4)<.0001 and abs(motion_ground[13]+4.8)<.0001
    expected_motion,_=render('motion-expected',extra=['--camera-offset','.1','.1','0'])
    assert motion_pixels==expected_motion,'motion diagnostic did not render the translated camera'
    wide=copy.deepcopy(original); wide['draws'][0]['vertices']=[list(v) for v in wide['draws'][0]['vertices']]
    for v in wide['draws'][0]['vertices']: v[0]*=2; v[1]*=2
    wide_path=folder/'wide.rrscene'; wide_path.write_bytes(encode_scene(wide))
    wide_signal_path=folder/'wide.signals'
    render('wide-motion',wide_path,extra=['--motion-test','--signals',wide_signal_path])
    wide_signals=load_signals(wide_signal_path)
    assert wide_signals.pixel(127,20)[11]==1 and wide_signals.pixel(127,20)[12:15]==(0,0,0),'outside-previous-frame projection marked valid'
    assert wide_signals.pixel(30,30)[14]==1
    # Strong albedo edges must not blur into a neighbouring material colour.
    checker=copy.deepcopy(original); floor=checker['draws'][0]
    floor['texture_width']=2; floor['texture']=bytes([0,0,0,255,255,255,255,255])
    checker_path=folder/'checker.rrscene'; checker_path.write_bytes(encode_scene(checker))
    checker_signal_path=folder/'checker.signals'
    render('checker-filtered',checker_path,mode='gi',extra=['--denoise','--signals',checker_signal_path])
    checker_signals=load_signals(checker_signal_path)
    assert checker_signals.pixel(63,20)[16:19]==(0,0,0),'filter bled white across black albedo edge'
    # Fail-closed, bounded signal reader and no-overwrite export behavior.
    encoded=raw_signal_path.read_bytes(); corrupt=[]
    corrupt.append(encoded[:12]); corrupt.append(encoded[:-1]); corrupt.append(encoded+b'x')
    changed_header=bytearray(encoded); struct.pack_into('<I',changed_header,20,64); corrupt.append(changed_header)
    nonfinite=bytearray(encoded); struct.pack_into('<f',nonfinite,HEADER.size,float('nan')); corrupt.append(nonfinite)
    invalid_validity=bytearray(encoded); struct.pack_into('<f',invalid_validity,HEADER.size+11*4,.5); corrupt.append(invalid_validity)
    oversized=bytearray(encoded[:HEADER.size]); struct.pack_into('<I',oversized,12,0xffffffff); corrupt.append(oversized)
    for i,data in enumerate(corrupt):
        invalid_path=folder/f'invalid-{i}.signals'; invalid_path.write_bytes(data)
        try: load_signals(invalid_path)
        except ValueError: pass
        else: raise AssertionError(f'accepted malformed signal {i}')
    run([args.dxr,path,'--signals',raw_signal_path],success=False)
    assert raw_signal_path.read_bytes()==encoded
    signal_summary=json.loads(run([sys.executable,ROOT/'tools/inspect_signals.py',motion_path]).stdout)
    assert signal_summary==summarize(motion)
    window_pixels,window_report=render('window',mode='gi',extra=['--samples','8','--window-test'])
    assert window_pixels==history_fresh and window_report['history_resets']==4
    assert window_report['samples']==8 and window_report['dispatches']==4*8+1 and window_report['scene_build_submissions']==1
    assert window_report['requested_buffer_bytes']==one_report['requested_buffer_bytes']
    moved,_=render('camera-offset',extra=['--camera-offset','.1','0','0'])
    rotated,_=render('camera-yaw',extra=['--yaw','8','--pitch','3'])
    assert moved!=albedo and rotated!=albedo
    # An edge-on coloured wall is invisible to the orthographic primary rays,
    # but must tint the adjacent ground through a real secondary diffuse hit.
    bounce=copy.deepcopy(original); wall=copy.deepcopy(bounce['draws'][0]); wall['ordinal']=2
    wall['vertices']=[[.4,-.9,-.4,0xffffffff,0,0],[.4,.9,-.4,0xffffffff,0,1],
                      [.4,-.9,.8,0xffffffff,1,0],[.4,.9,.8,0xffffffff,1,1]]
    wall['texture']=bytes([0,0,255,255]); bounce['draws'].append(wall); bounce['attempted']=3
    bounce_path=folder/'bounce-red.rrscene'; bounce_path.write_bytes(encode_scene(bounce))
    bounce_red,_=render('bounce-red',bounce_path,mode='gi',extra=['--samples','256','--sun-radius','0'])
    wall['texture']=bytes([255,0,0,255])
    blue_path=folder/'bounce-blue.rrscene'; blue_path.write_bytes(encode_scene(bounce))
    bounce_blue,_=render('bounce-blue',blue_path,mode='gi',extra=['--samples','256','--sun-radius','0'])
    red_albedo,_=render('bounce-red-albedo',bounce_path); blue_albedo,_=render('bounce-blue-albedo',blue_path)
    assert red_albedo==blue_albedo,'edge-on bounce wall unexpectedly visible to primary rays'
    region=[(x,y) for y in range(24,72) for x in range(76,87)]
    red_gain=sum(pixel(bounce_red,x,y)[2]-pixel(bounce_blue,x,y)[2] for x,y in region)/len(region)
    blue_gain=sum(pixel(bounce_blue,x,y)[0]-pixel(bounce_red,x,y)[0] for x,y in region)/len(region)
    assert red_gain>5 and blue_gain>5,(red_gain,blue_gain)
    # Use the real mod compiler: its self-contained output must import in DXR.
    texture=folder/'green.png'; texture.write_bytes(png(1,1,bytes([0,255,0,255])))
    manifest=folder/'mod.json'; modified=folder/'modified.rrscene'
    run([sys.executable,ROOT/'tools/mod_scene.py','make','--kind','texture','--target',original['draws'][1]['texture_id'],
         '--asset',texture.name,'--id','dxr-green','--output',manifest])
    run([sys.executable,ROOT/'tools/mod_scene.py','apply',path,'--mod',manifest,'--output',modified])
    mod_pixels,_=render('modified',modified)
    assert pixel(mod_pixels,64,48)==bytes([0,255,0])
    assert pixel(mod_pixels,30,30)==pixel(albedo,30,30)
    # Exercise nonidentity world/view/perspective, literal texels, interpolated
    # vertex colour, point/linear filtering and primary-ray scissor admission.
    camera_metrics=[]
    for filtering in (1,2):
        camera=copy.deepcopy(original)
        projection=[1.0,0,0,0, 0,1.3,0,0, 0,0,2/1.9,1, 0,0,-.2/1.9,0]
        for draw in camera['draws']:
            draw['projection']=projection
            draw['view']=list(draw['view']); draw['view'][12]=.05; draw['view'][13]=-.02; draw['view'][14]=.1
            draw['world']=list(draw['world']); draw['world'][0]=.8; draw['world'][5]=.7; draw['world'][12]=-.03
            draw['sampler']=list(draw['sampler']); draw['sampler'][4]=draw['sampler'][5]=filtering
        floor=camera['draws'][0]; floor['texture_width']=floor['texture_height']=2
        floor['texture']=bytes([20,40,240,255, 40,240,20,255, 240,20,40,255, 240,240,240,255])
        floor['vertices']=[list(v) for v in floor['vertices']]; floor['vertices'][0][3]=0xff80ffff
        front=camera['draws'][1]; front['render']=list(front['render']); front['render'][23]=1; front['scissor']=[0,0,64,96]
        camera_path=folder/f'camera-{filtering}.rrscene'; camera_path.write_bytes(encode_scene(camera))
        traced,_=render(f'camera-{filtering}',camera_path)
        ref=folder/f'camera-raster-{filtering}.pixels'; run([args.replay,camera_path,'--pixels',ref])
        oracle=ref.read_bytes()
        errors=[abs(a-b) for a,b in zip(traced,oracle)]
        large=sum(max(errors[i:i+3])>2 for i in range(0,len(errors),3))
        assert large/(128*96)<.02 and sum(errors)/len(errors)<1.0, (filtering,large,sum(errors)/len(errors))
        camera_metrics.append(dict(filter=filtering,pixels_over_two_levels=large,mean_channel_error=sum(errors)/len(errors)))
    # Material/camera combinations outside the initial contract must fail closed.
    mutations=[]
    for label,slot,value in [('blend',12,1),('cull',7,3),('flat',2,1),('srgb',28,1)]:
        scene=copy.deepcopy(original); scene['draws'][0]['render']=list(scene['draws'][0]['render']); scene['draws'][0]['render'][slot]=value; mutations.append((label,scene))
    scene=copy.deepcopy(original); scene['draws'][0]['projection']=[0.0]*16; scene['draws'][1]['projection']=[0.0]*16; mutations.append(('singular',scene))
    scene=copy.deepcopy(original); scene['draws'][1]['view']=list(scene['draws'][1]['view']); scene['draws'][1]['view'][12]=.1; mutations.append(('multiple-cameras',scene))
    scene=copy.deepcopy(original); scene['rejected']=[dict(ordinal=0xffffffff,reason='unsupported_frame_operation')]; mutations.append(('partial',scene))
    scene=copy.deepcopy(original); scene['draws'][0]['world']=list(scene['draws'][0]['world']); scene['draws'][0]['world'][12]=2e6; mutations.append(('geometry-range',scene))
    for label,scene in mutations:
        invalid=folder/(label+'.rrscene'); invalid.write_bytes(encode_scene(scene))
        output=folder/(label+'.pixels'); run([args.dxr,invalid,'--pixels',output],success=False); assert not output.exists()
    existing=folder/'albedo.pixels'; before=existing.read_bytes()
    run([args.dxr,path,'--pixels',existing],success=False); assert existing.read_bytes()==before
    run([args.dxr,path,'--light','0','0','0'],success=False)
    run([args.dxr,'--probe','--adapter','31'],success=False)
    for invalid_args in (['--samples','0'],['--samples','4097'],['--samples','-1'],['--samples',''],
                         ['--seed','4294967296'],['--sun-radius','nan'],['--sun-radius','1.1'],
                         ['--camera-offset','inf','0','0'],['--pitch','90'],['--yaw','361'],
                         ['--light','','0','1'],['--adapter',''],['--window-test','--yaw','1'],
                         ['--motion-test'],['--motion-test','--signals',folder/'invalid-motion.signals','--samples','2'],
                         ['--signals',''],['--pixels',''],['--signals',folder/'same.out','--pixels',folder/'SAME.out'],
                         ['--interactive','--history-test']):
        run([args.dxr,path,*invalid_args],success=False)
    summary=dict(result='pass',capabilities=probe,albedo_changed_pixels=changed,albedo_changed_fraction=changed/(128*96),
        shadow_pixels=shadow_pixels,camera_comparisons=camera_metrics,debug_layer_tested=bool(debug),render=report,relit=lighting,
        progressive=dict(single_sample_mse=single_error,accumulated_32_mse=accumulated_error,reference_samples=256,
                         red_bounce_gain=red_gain,blue_bounce_gain=blue_gain,render=many_report,history=history_report,window=window_report),
        signals=dict(filtered_single_mse=filter_error,raw_single_mse=single_error,motion=signal_summary,render=filtered_info),artifacts=str(folder))
    (folder/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    return 0


if __name__=='__main__':
    sys.exit(main())
