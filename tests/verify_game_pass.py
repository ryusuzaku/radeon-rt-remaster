"""Exercise the real deployment/launch/cleanup path in a disposable game directory."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from game_pass import prepare, run_pass, load_plan, remove_owned_proxy, digest, reuse_baseline, trigger_capture


def need(value, message):
    if not value: raise AssertionError(message)


def rejected(action):
    try: action()
    except (OSError,ValueError): return
    raise AssertionError('unsafe/invalid operation accepted')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--sample',type=Path,required=True)
    parser.add_argument('--proxy',type=Path,required=True); parser.add_argument('--replay',type=Path,required=True)
    args=parser.parse_args()
    root=Path(tempfile.mkdtemp(prefix='game-pass-',dir=args.sample.parent)); game=root/'game'; game.mkdir()
    executable=game/'game.exe'; shutil.copyfile(args.sample,executable)
    original=digest(executable); destination=game/'d3d9.dll'; bundle=root/'pass'
    baseline_pixels=root/'baseline.bgr'; proxy_pixels=root/'proxy.bgr'
    common=['--scene-fixture','--frames','12']
    plan=prepare(executable,args.proxy,bundle,'D3D9 game-pass fixture',common+['--pixels',str(proxy_pixels)],common+['--runtime','system','--pixels',str(baseline_pixels)])
    need(not destination.exists(),'prepare changed game directory')
    rejected(lambda: run_pass(bundle,'proxy'))
    rejected(lambda: run_pass(bundle,'baseline',shader_inventory=True))
    rejected(lambda: run_pass(bundle,'proxy',shader_inventory=True))
    rejected(lambda: run_pass(bundle,'proxy',wait_trigger=True,position_capture=True))
    rejected(lambda: run_pass(bundle,'proxy',position_selection='128x96:1'))
    rejected(lambda: run_pass(bundle,'proxy',position_multi_draw=True))
    rejected(lambda: run_pass(bundle,'proxy',position_render_state=True))
    rejected(lambda: run_pass(bundle,'proxy',position_clear_evidence=True))
    rejected(lambda: run_pass(bundle,'proxy',position_write_evidence=True))
    rejected(lambda: run_pass(bundle,'proxy',position_surface_scope=True))
    rejected(lambda: run_pass(bundle,'proxy',position_color_replay=True))
    rejected(lambda: run_pass(bundle,'proxy',position_material_inputs=True))
    rejected(lambda: run_pass(bundle,'proxy',position_pixel_material=True))
    rejected(lambda: run_pass(bundle,'proxy',position_texture_inputs=True))
    rejected(lambda: run_pass(bundle,'proxy',position_texture_assets=True))
    rejected(lambda: run_pass(bundle,'proxy',position_compressed_textures=True))
    rejected(lambda: run_pass(bundle,'proxy',position_texture_uploads=True))
    rejected(lambda: run_pass(bundle,'proxy',position_dirty_textures=True))
    rejected(lambda: run_pass(bundle,'proxy',position_surface_uploads=True))
    for invalid in ('0x96:1','128x96:0','16385x96:1','128x96:4097','0128x96:1'):
        rejected(lambda: run_pass(bundle,'proxy',wait_trigger=True,shader_inventory=True,position_capture=True,position_frames=True,position_selection=invalid))
    baseline=run_pass(bundle,'baseline',note='synthetic baseline')
    need(baseline['exit_code']==0, f'native baseline failed; inspect {bundle / "runs" / "baseline" / "report.json"}: exit={baseline["exit_code"]}')
    need(baseline['trace'] is None and not baseline['installed_by_runner'],'baseline was instrumented')
    observed=run_pass(bundle,'proxy',start_frame=2,frames=3,scene_frame=1,note='synthetic four-quadrant scene')
    need(observed['exit_code']==0 and observed['proxy_removed'] and not destination.exists(),'proxy lifecycle failed')
    need(observed['trace']['presents']==3 and observed['trace']['fixed_draws']>0 and observed['scene_capture_exists'],'bounded observation/capture missing')
    need(baseline_pixels.read_bytes()==proxy_pixels.read_bytes(),'game-pass proxy changed pixels')
    saved_proxy=root/'proxy-saved.bgr'; proxy_pixels.rename(saved_proxy)
    disabled=run_pass(bundle,'disabled')
    need(disabled['exit_code']==0 and disabled['trace'] is None and disabled['proxy_removed'],'disabled baseline failed')
    need(baseline_pixels.read_bytes()==proxy_pixels.read_bytes(),'disabled proxy changed pixels')
    need(digest(executable)==original,'executable was changed')
    inspected=subprocess.run([str(args.replay),str(bundle/'runs'/'proxy'/'scene.rrscene'),'--inspect'],capture_output=True,text=True)
    need(inspected.returncode==0,(inspected.stdout,inspected.stderr))
    reused=root/'reused-pass'
    prepare(executable,args.proxy,reused,'reused',plan['arguments'],plan['baseline_arguments'])
    reused_report=reuse_baseline(reused,bundle)
    need(reused_report['source_report_sha256']==digest(bundle/'runs'/'baseline'/'report.json'),'baseline reuse provenance lost')
    rejected(lambda: reuse_baseline(reused,bundle))
    rejected(lambda: trigger_capture(bundle,'proxy'))
    never=run_pass(reused,'proxy',name='untriggered',wait_trigger=True,shader_inventory=True,position_capture=True)
    need(not Path(never['position_capture_file']).exists(),'untriggered position capture wrote evidence')
    need(not Path(never['shader_inventory_file']).exists(),'untriggered inventory wrote evidence')
    need(never['proxy_removed'] and never['trace']['events']==0,'untriggered run captured events')
    armed_bundle=root/'armed-pass'
    prepare(executable,args.proxy,armed_bundle,'armed',['--scene-fixture','--frames','1000'],plan['baseline_arguments'])
    reuse_baseline(armed_bundle,bundle)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(run_pass,armed_bundle,'proxy',frames=3,wait_trigger=True,shader_inventory=True,position_capture=True,position_frames=True,position_selection='128x96:1',position_multi_draw=True,position_render_state=True,position_clear_evidence=True,position_write_evidence=True,position_surface_scope=True,position_color_replay=True,position_material_inputs=True,position_pixel_material=True,position_texture_inputs=True,position_texture_assets=True,position_compressed_textures=True,position_texture_uploads=True,position_dirty_textures=True,position_surface_uploads=True)
        armed_report=armed_bundle/'runs'/'proxy'/'report.json'
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and not future.done():
            # Atomic report replacement can briefly deny a Windows reader.
            # Retry publication races within the same deadline, not parse errors
            # or trigger failures; the final capture assertions remain mandatory.
            try: status=json.loads(armed_report.read_text(encoding='utf-8')).get('status')
            except (FileNotFoundError,PermissionError): status=None
            if status=='running':
                trigger_capture(armed_bundle,'proxy')
                break
            time.sleep(.005)
        triggered=future.result(timeout=30)
    need(triggered['proxy_removed'] and triggered['trace']['presents']==3 and triggered['trace']['draws']>0,'live trigger failed')
    from inspect_shader_inventory import inspect as inspect_inventory
    inventory=inspect_inventory(triggered['shader_inventory_file'])
    need(inventory['draws']>0 and inventory['failed_draws']==0,'triggered inventory missing draws')
    from inspect_position_capture import inspect as inspect_position
    position=inspect_position(triggered['position_capture_file'])
    need(position['version']==18 and position['frame_sampling'] and triggered['position_frame_sampling'] and triggered['position_selection']=='128x96:1' and triggered['position_multi_draw'] and triggered['position_render_state'] and triggered['position_clear_evidence'] and triggered['position_write_evidence'] and triggered['position_surface_scope'] and triggered['position_color_replay'] and triggered['position_material_inputs'] and triggered['position_pixel_material'] and triggered['position_texture_inputs'] and triggered['position_texture_assets'] and triggered['position_compressed_textures'] and triggered['position_texture_uploads'] and triggered['position_dirty_textures'] and triggered['position_surface_uploads'],'runner did not enable surface uploads')
    need(Path(triggered['texture_asset_directory']).is_dir() and not list(Path(triggered['texture_asset_directory']).iterdir()),'fixed-function asset directory should be empty')
    need(position['attempts_recorded']>0 and not position['captures'],'fixed-function fixture incorrectly captured HL2 geometry')
    rejected(lambda: trigger_capture(armed_bundle,'proxy'))
    destination.write_bytes(b'existing unrelated mod')
    rejected(lambda: prepare(executable,args.proxy,root/'blocked','',[]))
    rejected(lambda: run_pass(bundle,'proxy',name='blocked'))
    rejected(lambda: remove_owned_proxy(plan))
    need(destination.read_bytes()==b'existing unrelated mod','existing mod was overwritten/deleted')
    # Keep the deliberate conflict artifact; no broad cleanup is performed.
    rejected(lambda: run_pass(bundle,'baseline',name='../escape'))
    altered=game/'changed.exe'; shutil.copyfile(executable,altered)
    other=game/'other'; other.mkdir(); other_exe=other/'game.exe'; shutil.copyfile(altered,other_exe)
    changed=prepare(other_exe,args.proxy,root/'changed-pass','',[])
    with other_exe.open('ab') as stream: stream.write(b'changed')
    rejected(lambda: load_plan(root/'changed-pass'))
    bin_dir=game/'bin'; bin_dir.mkdir()
    bin_dll=bin_dir/'d3d9.dll'
    bin_bundle=root/'bin-pass'
    bin_plan=prepare(executable,args.proxy,bin_bundle,'bin deployment',common+['--runtime',str(bin_dll)],common+['--runtime','system'],proxy_subdir='bin')
    need(not bin_dll.exists(),'bin prepare deployed a DLL')
    need(run_pass(bin_bundle,'baseline')['exit_code']==0,'bin baseline failed')
    bin_result=run_pass(bin_bundle,'proxy',frames=3)
    need(bin_result['proxy_removed'] and bin_result['trace']['presents']==3 and not bin_dll.exists(),'bin deployment/cleanup failed')
    need(destination.read_bytes()==b'existing unrelated mod','bin run touched root mod')
    rejected(lambda: prepare(executable,args.proxy,root/'traversal','',[],proxy_subdir='../escape'))
    tampered=dict(bin_plan); tampered['destination']=str(destination)
    from game_pass import write_json
    write_json(bin_bundle/'plan.json',tampered)
    rejected(lambda: load_plan(bin_bundle))
    report={'result':'pass','baseline_proxy_pixels_equal':True,'disabled_pixels_equal':True,'scene_valid':True,
            'existing_mod_preserved':True,'changed_executable_rejected':True,'artifacts':str(root)}
    (root/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__': main()
