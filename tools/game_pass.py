"""Prepare and run a reversible, provenance-checked D3D9 game observation pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid

from inspect_trace import inspect, TraceError


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pe_info(path):
    with Path(path).open('rb') as stream:
        header = stream.read(64)
        need(len(header) == 64 and header[:2] == b'MZ', 'not a PE executable')
        offset = struct.unpack_from('<I', header, 60)[0]
        need(64 <= offset <= 1024 * 1024, 'PE header outside bound')
        stream.seek(offset)
        coff = stream.read(26)
        need(len(coff) == 26 and coff[:4] == b'PE\0\0', 'invalid PE header')
        machine = struct.unpack_from('<H', coff, 4)[0]
        magic = struct.unpack_from('<H', coff, 24)[0]
        return {'machine': machine, 'pointer_bits': 32 if machine == 0x14c and magic == 0x10b else 64 if machine == 0x8664 and magic == 0x20b else 0}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    # Windows readers can briefly deny delete-sharing while polling this file.
    # Retry only that transient access/share failure, with a fixed 200 ms bound.
    for attempt in range(21):
        try:
            os.replace(temporary, path)
            break
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32,33) or attempt==20:
                raise
            time.sleep(.01)


def argument_list(text):
    result = json.loads(text)
    need(isinstance(result, list) and len(result) <= 64 and all(isinstance(item, str) and '\0' not in item and len(item) <= 4096 for item in result), 'arguments must be a bounded JSON string array')
    return result


def deployment_path(executable, subdir):
    need(subdir in ('', 'bin'), 'proxy subdirectory must be empty or bin')
    root = Path(executable).parent
    folder = root / subdir
    need(folder.is_dir() and folder.resolve() == folder, 'proxy directory missing or redirected')
    return folder / 'd3d9.dll'


def prepare(executable, proxy, output, title, arguments, baseline_arguments=None, proxy_subdir=''):
    argument_list(json.dumps(arguments))
    if baseline_arguments is not None:
        argument_list(json.dumps(baseline_arguments))
    executable, proxy, output = (Path(p).absolute() for p in (executable, proxy, output))
    need(executable.is_file() and proxy.is_file(), 'executable/proxy file missing')
    executable, proxy = executable.resolve(), proxy.resolve()
    need(pe_info(executable)['pointer_bits'] == pe_info(proxy)['pointer_bits'] == 32, 'first pass requires x86 PE executable and proxy')
    destination = deployment_path(executable, proxy_subdir)
    need(not os.path.lexists(destination), f'existing d3d9.dll must be preserved: {destination}')
    need(not output.exists(), 'pass directory already exists')
    plan = {'schema': 'rrt-game-pass', 'version': 1, 'title': title or executable.stem,
            'executable': str(executable), 'executable_sha256': digest(executable), 'executable_pe': pe_info(executable),
            'proxy': str(proxy), 'proxy_sha256': digest(proxy), 'destination': str(destination), 'proxy_subdir': proxy_subdir,
            'arguments': arguments, 'baseline_arguments': arguments if baseline_arguments is None else baseline_arguments,
            'platform': platform.platform(), 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'scope': 'baseline-and-d3d9-observation', 'game_compatibility': 'unassessed'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'runs').mkdir()
    write_json(output / 'plan.json', plan)
    return plan


def load_plan(directory):
    plan = json.loads((Path(directory) / 'plan.json').read_text(encoding='utf-8'))
    need(plan.get('schema') == 'rrt-game-pass' and plan.get('version') == 1, 'unknown pass plan')
    executable, proxy = Path(plan['executable']), Path(plan['proxy'])
    need(executable.is_absolute() and proxy.is_absolute() and executable.resolve() == executable and proxy.resolve() == proxy, 'plan paths changed')
    need(Path(plan['destination']) == deployment_path(executable, plan.get('proxy_subdir', '')), 'proxy destination does not match executable')
    need(digest(executable) == plan['executable_sha256'] and digest(proxy) == plan['proxy_sha256'], 'executable or proxy changed since preparation')
    argument_list(json.dumps(plan['arguments'])); argument_list(json.dumps(plan['baseline_arguments']))
    return plan


def remove_owned_proxy(plan):
    destination = Path(plan['destination'])
    need(not destination.is_symlink() and destination.is_file(), 'deployed proxy missing/replaced; manual review required')
    need(digest(destination) == plan['proxy_sha256'], 'deployed DLL changed; refusing cleanup')
    destination.unlink()


def run_pass(directory, mode, name=None, start_frame=0, frames=300, max_bytes=64*1024*1024, scene_frame=None, note='', wait_trigger=False, shader_inventory=False, position_capture=False, position_frames=False, position_selection=None, position_multi_draw=False, position_render_state=False, position_clear_evidence=False, position_write_evidence=False, position_surface_scope=False, position_color_replay=False, position_material_inputs=False, position_pixel_material=False, position_texture_inputs=False, position_texture_assets=False, position_compressed_textures=False, position_texture_uploads=False, position_dirty_textures=False, position_surface_uploads=False, position_surface_locks=False):
    need(mode in ('baseline','proxy','disabled'), 'unknown pass mode')
    directory = Path(directory).resolve()
    plan = load_plan(directory)
    name = name or mode
    need(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name), 'run name must be a short lowercase identifier')
    need(0 <= start_frame <= 1_000_000 and 1 <= frames <= 10000 and 4096 <= max_bytes <= 64*1024*1024, 'trace bounds invalid')
    need(scene_frame is None or (mode == 'proxy' and 0 <= scene_frame <= 1_000_000), 'scene capture requires proxy mode and a bounded frame')
    need(not wait_trigger or (mode=='proxy' and scene_frame is None), 'trigger mode requires proxy observation without scene capture')
    need(not shader_inventory or (mode=='proxy' and wait_trigger), 'shader inventory requires triggered proxy mode')
    need(not position_capture or (mode=='proxy' and wait_trigger and shader_inventory), 'position capture requires triggered shader inventory')
    need(not position_frames or position_capture, 'position frame sampling requires position capture')
    need(not position_multi_draw or position_selection is not None,'multi-draw capture requires explicit selection')
    need(not position_render_state or position_multi_draw,'render-state capture requires multi-draw capture')
    need(not position_clear_evidence or position_render_state,'clear evidence requires render-state capture')
    need(not position_write_evidence or position_clear_evidence,'write evidence requires clear evidence')
    need(not position_surface_scope or position_write_evidence,'surface scope requires write evidence')
    need(not position_color_replay or position_surface_scope,'color replay requires surface scope')
    need(not position_material_inputs or position_color_replay,'material inputs require color replay evidence')
    need(not position_pixel_material or position_material_inputs,'pixel material requires material inputs')
    need(not position_texture_inputs or position_pixel_material,'texture inputs require pixel material')
    need(not position_texture_assets or position_texture_inputs,'texture assets require texture inputs')
    need(not position_compressed_textures or position_texture_assets,'compressed textures require texture assets')
    need(not position_texture_uploads or position_compressed_textures,'texture uploads require compressed texture capture')
    need(not position_dirty_textures or position_texture_uploads,'dirty texture evidence requires texture uploads')
    need(not position_surface_uploads or position_dirty_textures,'surface uploads require dirty texture evidence')
    need(not position_surface_locks or position_surface_uploads,'surface locks require surface uploads')
    if position_selection is not None:
        need(position_frames and isinstance(position_selection,str) and len(position_selection)<=32 and re.fullmatch(r'(any|[1-9][0-9]*x[1-9][0-9]*):[1-9][0-9]*',position_selection), 'selection requires frame sampling and WIDTHxHEIGHT:MIN_TRIANGLES or any:MIN_TRIANGLES')
        dimensions,minimum=position_selection.split(':')
        if dimensions!='any':
            width,height=map(int,dimensions.split('x'));need(width<=16384 and height<=16384,'position selection bounds')
        need(int(minimum)<=4096,'position selection bounds')
    destination = Path(plan['destination'])
    need(not os.path.lexists(destination), 'existing d3d9.dll blocks this run; nothing overwritten')
    if mode != 'baseline':
        baseline_path = directory / 'runs' / 'baseline' / 'report.json'
        need(baseline_path.is_file(), 'run the untouched baseline first')
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        need(baseline.get('exit_code') == 0 and baseline.get('mode') == 'baseline' and baseline.get('executable_sha256') == plan['executable_sha256'], 'successful matching baseline is required')
    run_directory = directory / 'runs' / name
    if run_directory.exists():
        need(False, f"run name '{name}' already exists in this bundle; choose a new --name")
    run_directory.mkdir(exist_ok=False)
    report = {'schema': 'rrt-game-pass-run', 'version': 1, 'mode': mode, 'name': name, 'note': note,
              'executable_sha256': plan['executable_sha256'], 'proxy_sha256': plan['proxy_sha256'],
              'installed_by_runner': False, 'proxy_removed': False, 'exit_code': None,
              'status': 'starting', 'compatibility': 'unassessed', 'trace': None}
    report_path = run_directory / 'report.json'
    write_json(report_path, report)
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('RRT_')}
    if mode == 'proxy':
        if wait_trigger:
            report['trigger_file']=str(run_directory/'capture.trigger')
            environment['RRT_TRACE_TRIGGER_FILE']=report['trigger_file']
        if shader_inventory:
            report['shader_inventory_file']=str(run_directory/'shader-inventory.jsonl')
            environment.update(RRT_SHADER_INVENTORY_FILE=report['shader_inventory_file'],
                               RRT_SHADER_INVENTORY_TRIGGER_FILE=report['trigger_file'],
                               RRT_SHADER_INVENTORY_DRAWS='4096')
        if position_capture:
            report['position_capture_file']=str(run_directory/'position-capture.jsonl')
            environment.update(RRT_POSITION_CAPTURE_FILE=report['position_capture_file'],RRT_POSITION_TRIGGER_FILE=report['trigger_file'])
            report['position_frame_sampling']=bool(position_frames)
            if position_frames:environment['RRT_POSITION_FRAME_SAMPLING']='1'
            if position_selection is not None:
                environment['RRT_POSITION_SELECTION']=position_selection
                report['position_selection']=position_selection
            if position_multi_draw:
                environment['RRT_POSITION_MULTI_DRAW']='1'
                report['position_multi_draw']=True
            if position_render_state:
                environment['RRT_POSITION_RENDER_STATE']='1'
                report['position_render_state']=True
            if position_clear_evidence:
                environment['RRT_POSITION_CLEAR_EVIDENCE']='1'
                report['position_clear_evidence']=True
            if position_write_evidence:
                environment['RRT_POSITION_WRITE_EVIDENCE']='1'
                report['position_write_evidence']=True
            if position_surface_scope:
                environment['RRT_POSITION_SURFACE_SCOPE']='1'
                report['position_surface_scope']=True
            if position_color_replay:
                environment['RRT_POSITION_COLOR_REPLAY']='1'
                report['position_color_replay']=True
            if position_material_inputs:
                environment['RRT_POSITION_MATERIAL_INPUTS']='1'
                report['position_material_inputs']=True
            if position_pixel_material:
                environment['RRT_POSITION_PIXEL_MATERIAL']='1'
                report['position_pixel_material']=True
            if position_texture_inputs:
                environment['RRT_POSITION_TEXTURE_INPUTS']='1'
                report['position_texture_inputs']=True
            if position_texture_assets:
                environment['RRT_POSITION_TEXTURE_ASSETS']='1'
                report['position_texture_assets']=True
                report['texture_asset_directory']=environment['RRT_POSITION_CAPTURE_FILE']+'.assets'
            if position_compressed_textures:
                environment['RRT_POSITION_COMPRESSED_TEXTURES']='1'
                report['position_compressed_textures']=True
            if position_texture_uploads:
                environment['RRT_POSITION_TEXTURE_UPLOADS']='1'
                report['position_texture_uploads']=True
            if position_dirty_textures:
                environment['RRT_POSITION_DIRTY_TEXTURES']='1'
                report['position_dirty_textures']=True
            if position_surface_uploads:
                environment['RRT_POSITION_SURFACE_UPLOADS']='1'
                report['position_surface_uploads']=True
            if position_surface_locks:
                environment['RRT_POSITION_SURFACE_LOCKS']='1'
                report['position_surface_locks']=True
        environment.update(RRT_TRACE_FILE=str(run_directory / 'trace.jsonl'), RRT_TRACE_START_FRAME=str(start_frame),
                           RRT_TRACE_FRAME_COUNT=str(frames), RRT_TRACE_MAX_BYTES=str(max_bytes))
        if scene_frame is not None:
            environment.update(RRT_SCENE_FILE=str(run_directory / 'scene.rrscene'), RRT_SCENE_FRAME=str(scene_frame))
    elif mode == 'disabled':
        environment['RRT_PROXY_DISABLE'] = '1'
    installed = False
    process = None
    start = time.monotonic()
    try:
        if mode != 'baseline':
            # Exclusive creation preserves existing mods, even after preflight.
            with destination.open('xb') as target, Path(plan['proxy']).open('rb') as source:
                installed = True
                report['installed_by_runner'] = True
                shutil.copyfileobj(source, target)
            need(digest(destination) == plan['proxy_sha256'], 'deployed DLL checksum mismatch')
            write_json(report_path, report)
        arguments = plan['baseline_arguments'] if mode == 'baseline' else plan['arguments']
        report['command'] = [plan['executable'], *arguments]
        # Direct launch only: no shell, Steam configuration edits, injection,
        # forced termination or launcher/DRM workarounds.
        process = subprocess.Popen(report['command'], cwd=str(Path(plan['executable']).parent), env=environment,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        report['pid'] = process.pid; report['status'] = 'running'
        write_json(report_path, report)
        report['exit_code'] = process.wait()
        report['status'] = 'exited'
    except BaseException as error:
        report['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'launch-error'
        report['error'] = str(error)
        raise
    finally:
        report['wall_seconds'] = round(time.monotonic() - start, 3)
        if installed and (process is None or process.poll() is not None):
            try:
                remove_owned_proxy(plan)
                report['proxy_removed'] = True
            except (OSError, ValueError) as error:
                report['cleanup_error'] = str(error)
        elif installed:
            report['cleanup_error'] = 'Process still running; close it, then use cleanup --game-closed.'
        write_json(report_path, report)
    trace = run_directory / 'trace.jsonl'
    if trace.exists():
        try:
            summary = inspect(trace, allow_incomplete=True)
            write_json(run_directory / 'trace-summary.json', summary)
            report['trace'] = {key: summary[key] for key in ('completion', 'events', 'presents', 'draws', 'fixed_draws', 'shader_draws', 'failed_calls')}
            report['status'] = 'observation-ready-for-review' if summary['draws'] else 'no-draws-observed'
        except TraceError as error:
            report['status'] = 'trace-rejected'; report['trace_error'] = str(error)
    elif mode == 'proxy':
        report['status'] = 'proxy-load-unconfirmed'
    report['scene_capture_exists'] = (run_directory / 'scene.rrscene').is_file()
    report['executable_unchanged'] = digest(plan['executable']) == plan['executable_sha256']
    write_json(report_path, report)
    return report


def trigger_capture(directory, name):
    directory=Path(directory).resolve()
    load_plan(directory)
    need(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name), 'invalid run name')
    run_directory=directory/'runs'/name
    report_path=run_directory/'report.json'
    if not report_path.is_file():
        runs_directory=directory/'runs'
        existing=sorted(entry.name for entry in runs_directory.iterdir() if (entry/'report.json').is_file()) if runs_directory.is_dir() else []
        known=f"existing runs: {', '.join(existing)}" if existing else 'no runs exist in this bundle yet'
        raise ValueError(f"no run named '{name}' in this bundle ({known}); start it first with --name {name}")
    report=json.loads(report_path.read_text(encoding='utf-8'))
    marker=run_directory/'capture.trigger'
    need(report.get('mode')=='proxy' and report.get('status')=='running' and report.get('trigger_file')==str(marker),
         f"run '{name}' is not armed for capture (status: {report.get('status')}); start it with --wait-trigger and trigger while its report says running")
    with marker.open('x',encoding='ascii') as stream:
        stream.write('capture\n')
    return {'trigger_requested': True, 'marker': str(marker)}


def reuse_baseline(directory, source):
    directory,source=Path(directory).resolve(),Path(source).resolve()
    plan=load_plan(directory)
    old=json.loads((source/'plan.json').read_text(encoding='utf-8'))
    for key in ('executable','executable_sha256','baseline_arguments'):
        need(plan[key]==old[key], 'baseline executable/arguments differ')
    source_report=source/'runs'/'baseline'/'report.json'
    report=json.loads(source_report.read_text(encoding='utf-8'))
    need(report.get('mode')=='baseline' and report.get('exit_code')==0 and report.get('executable_unchanged') is True and report.get('installed_by_runner') is False, 'source is not a successful native baseline')
    need(report.get('executable_sha256')==plan['executable_sha256'] and report.get('command')==[plan['executable'],*plan['baseline_arguments']], 'baseline provenance mismatch')
    report['reused_from']=str(source_report)
    report['source_report_sha256']=digest(source_report)
    output=directory/'runs'/'baseline'
    output.mkdir(exist_ok=False)
    write_json(output/'report.json',report)
    return report


def cleanup(directory, name, game_closed):
    need(game_closed, 'close the game and acknowledge --game-closed before recovery cleanup')
    need(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name), 'invalid run name')
    plan = load_plan(directory)
    report_path = Path(directory) / 'runs' / name / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    need(report.get('installed_by_runner') and not report.get('proxy_removed') and report.get('proxy_sha256') == plan['proxy_sha256'], 'run does not own an outstanding proxy installation')
    remove_owned_proxy(plan)
    report['proxy_removed'] = True; report['cleanup_acknowledged_game_closed'] = True
    report.pop('cleanup_error', None); write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    create.add_argument('--exe', type=Path, required=True); create.add_argument('--proxy', type=Path, required=True)
    create.add_argument('--out', type=Path, required=True); create.add_argument('--title', default='')
    create.add_argument('--args-json', default='[]'); create.add_argument('--baseline-args-json')
    create.add_argument('--proxy-subdir', choices=('', 'bin'), default='')
    launch = commands.add_parser('run'); launch.add_argument('directory', type=Path)
    launch.add_argument('--mode', choices=('baseline','proxy','disabled'), required=True); launch.add_argument('--name')
    launch.add_argument('--start-frame', type=int, default=0); launch.add_argument('--frames', type=int, default=300)
    launch.add_argument('--max-bytes', type=int, default=64*1024*1024); launch.add_argument('--scene-frame', type=int); launch.add_argument('--note', default='')
    launch.add_argument('--wait-trigger', action='store_true')
    launch.add_argument('--shader-inventory', action='store_true')
    launch.add_argument('--position-capture', action='store_true')
    launch.add_argument('--position-frames', action='store_true', help='one accepted position draw per successful-Present interval (v3)')
    launch.add_argument('--position-selection', metavar='WIDTHxHEIGHT:MIN_TRIANGLES|any:MIN_TRIANGLES', help='explicit target-size filter, or any:MIN to accept any render-target extent (v4; requires --position-frames, and --position-multi-draw for any:MIN)')
    launch.add_argument('--position-multi-draw', action='store_true', help='up to4 selected draws per interval,16 total (v5)')
    launch.add_argument('--position-render-state', action='store_true', help='surface identity and selected composition-state evidence (v6; requires multi-draw)')
    launch.add_argument('--position-clear-evidence', action='store_true', help='bounded latest successful clear payload (v7; requires render-state)')
    launch.add_argument('--position-write-evidence', action='store_true', help='bounded ordered observed write calls and gaps (v8; requires clear evidence)')
    launch.add_argument('--position-surface-scope', action='store_true', help='closed standalone color-target scope evidence (v9; requires write evidence)')
    launch.add_argument('--position-color-replay', action='store_true', help='pixel program, RGBA constant and color replay state (v10; requires surface scope)')
    launch.add_argument('--position-material-inputs', action='store_true', help='initialized pinned VS UV/color/fog inputs (v11; requires color replay evidence)')
    launch.add_argument('--position-pixel-material', action='store_true', help='paired PS constants and sampler/texture descriptors (v12; requires material inputs)')
    launch.add_argument('--position-texture-inputs', action='store_true', help='initialized bounded managed 2D mip bytes (v13; requires pixel material)')
    launch.add_argument('--position-texture-assets', action='store_true', help='external hashed mip assets (v14; requires texture inputs)')
    launch.add_argument('--position-compressed-textures', action='store_true', help='DXT1/DXT3/DXT5 block capture (v15; requires texture assets)')
    launch.add_argument('--position-texture-uploads', action='store_true', help='proven whole-chain SYSTEMMEM to DEFAULT uploads (v16; requires compressed textures)')
    launch.add_argument('--position-dirty-textures', action='store_true', help='explicit full-dirty proof and SYSTEMMEM NO_DIRTY_UPDATE writes (v17; requires texture uploads)')
    launch.add_argument('--position-surface-uploads', action='store_true', help='bounded UpdateSurface mip rectangles (v18; requires dirty texture evidence)')
    launch.add_argument('--position-surface-locks', action='store_true', help='observed managed/SYSTEMMEM texture-mip surface locks (v19; requires surface uploads)')
    recover = commands.add_parser('cleanup'); recover.add_argument('directory', type=Path); recover.add_argument('--name', required=True)
    recover.add_argument('--game-closed', action='store_true')
    trigger=commands.add_parser('trigger'); trigger.add_argument('directory',type=Path); trigger.add_argument('--name',required=True)
    reuse=commands.add_parser('reuse-baseline'); reuse.add_argument('directory',type=Path); reuse.add_argument('--from-pass',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            report = prepare(args.exe,args.proxy,args.out,args.title,argument_list(args.args_json),None if args.baseline_args_json is None else argument_list(args.baseline_args_json),args.proxy_subdir)
        elif args.command == 'run':
            report = run_pass(args.directory,args.mode,args.name,args.start_frame,args.frames,args.max_bytes,args.scene_frame,args.note,args.wait_trigger,args.shader_inventory,args.position_capture,args.position_frames,args.position_selection,args.position_multi_draw,args.position_render_state,args.position_clear_evidence,args.position_write_evidence,args.position_surface_scope,args.position_color_replay,args.position_material_inputs,args.position_pixel_material,args.position_texture_inputs,args.position_texture_assets,args.position_compressed_textures,args.position_texture_uploads,args.position_dirty_textures,args.position_surface_uploads,args.position_surface_locks)
        elif args.command == 'trigger':
            report=trigger_capture(args.directory,args.name)
        elif args.command == 'reuse-baseline':
            report=reuse_baseline(args.directory,args.from_pass)
        else:
            report = cleanup(args.directory,args.name,args.game_closed)
        print(json.dumps(report,indent=2))
        if args.command == 'run':
            return 0 if report['exit_code'] == 0 and not report.get('cleanup_error') and report['status'] in ('exited','observation-ready-for-review') else 2
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(f'Game pass stopped: {error}',file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
