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


# The capture-evidence ladder, declared once.
#
# It is ordered and cumulative: each level requires the one before it. That is
# what the proxy's environment parser enforces, what the version numbers in
# docs/schemas/capture-version.json describe, and what makes the ledger header a
# fold over the flags rather than an independent set.
#
# This table is consumed by four places that used to repeat the ladder by hand:
# the argument definitions, the prerequisite checks, the environment/report
# construction, and the call into run_pass. Adding a level is now one edit here
# plus the run_pass signature, instead of five edits spread over four places with
# the order silently load-bearing in two of them.
#
# `requires` is compared against the predecessor's *unset* value rather than its
# truthiness, because position_selection is a string: an empty one must fall
# through to the selection-format error rather than being reported as a missing
# multi-draw prerequisite, which is the message the original code produced.
CAPTURE_LEVELS = (
    dict(name='position_multi_draw', requires='position_selection', unset=None,
         message='multi-draw capture requires explicit selection',
         help='up to4 selected draws per interval,16 total (v5)'),
    dict(name='position_render_state', requires='position_multi_draw',
         message='render-state capture requires multi-draw capture',
         help='surface identity and selected composition-state evidence (v6; requires multi-draw)'),
    dict(name='position_clear_evidence', requires='position_render_state',
         message='clear evidence requires render-state capture',
         help='bounded latest successful clear payload (v7; requires render-state)'),
    dict(name='position_write_evidence', requires='position_clear_evidence',
         message='write evidence requires clear evidence',
         help='bounded ordered observed write calls and gaps (v8; requires clear evidence)'),
    dict(name='position_surface_scope', requires='position_write_evidence',
         message='surface scope requires write evidence',
         help='closed standalone color-target scope evidence (v9; requires write evidence)'),
    dict(name='position_color_replay', requires='position_surface_scope',
         message='color replay requires surface scope',
         help='pixel program, RGBA constant and color replay state (v10; requires surface scope)'),
    dict(name='position_material_inputs', requires='position_color_replay',
         message='material inputs require color replay evidence',
         help='initialized pinned VS UV/color/fog inputs (v11; requires color replay evidence)'),
    dict(name='position_pixel_material', requires='position_material_inputs',
         message='pixel material requires material inputs',
         help='paired PS constants and sampler/texture descriptors (v12; requires material inputs)'),
    dict(name='position_texture_inputs', requires='position_pixel_material',
         message='texture inputs require pixel material',
         help='initialized bounded managed 2D mip bytes (v13; requires pixel material)'),
    dict(name='position_texture_assets', requires='position_texture_inputs',
         message='texture assets require texture inputs',
         help='external hashed mip assets (v14; requires texture inputs)'),
    dict(name='position_compressed_textures', requires='position_texture_assets',
         message='compressed textures require texture assets',
         help='DXT1/DXT3/DXT5 block capture (v15; requires texture assets)'),
    dict(name='position_texture_uploads', requires='position_compressed_textures',
         message='texture uploads require compressed texture capture',
         help='proven whole-chain SYSTEMMEM to DEFAULT uploads (v16; requires compressed textures)'),
    dict(name='position_dirty_textures', requires='position_texture_uploads',
         message='dirty texture evidence requires texture uploads',
         help='explicit full-dirty proof and SYSTEMMEM NO_DIRTY_UPDATE writes (v17; requires texture uploads)'),
    dict(name='position_surface_uploads', requires='position_dirty_textures',
         message='surface uploads require dirty texture evidence',
         help='bounded UpdateSurface mip rectangles (v18; requires dirty texture evidence)'),
    dict(name='position_surface_locks', requires='position_surface_uploads',
         message='surface locks require surface uploads',
         help='observed managed/SYSTEMMEM texture-mip surface locks (v19; requires surface uploads)'),
)


def capture_environment_name(level):
    """position_render_state -> RRT_POSITION_RENDER_STATE."""
    return 'RRT_POSITION_' + level[len('position_'):].upper()


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
    # The parameters are the flag set, so read them from the scope rather than
    # listing them again -- a second hand-maintained list is what CAPTURE_LEVELS
    # exists to remove. This snapshot is taken before `flags` is bound, so it
    # holds the parameters and nothing else.
    flags = locals()
    for level in CAPTURE_LEVELS:
        need(not flags[level['name']] or flags[level['requires']] is not level.get('unset', False),
             level['message'])
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
            for level in CAPTURE_LEVELS:
                if flags[level['name']]:
                    environment[capture_environment_name(level['name'])]='1'
                    report[level['name']]=True
            # The one level with a side effect beyond its own flag: the asset directory
            # sits beside the capture file, so it is recorded alongside it.
            if position_texture_assets:
                report['texture_asset_directory']=environment['RRT_POSITION_CAPTURE_FILE']+'.assets'
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
    for level in CAPTURE_LEVELS:
        launch.add_argument('--'+level['name'].replace('_','-'), action='store_true', help=level['help'])
    recover = commands.add_parser('cleanup'); recover.add_argument('directory', type=Path); recover.add_argument('--name', required=True)
    recover.add_argument('--game-closed', action='store_true')
    trigger=commands.add_parser('trigger'); trigger.add_argument('directory',type=Path); trigger.add_argument('--name',required=True)
    reuse=commands.add_parser('reuse-baseline'); reuse.add_argument('directory',type=Path); reuse.add_argument('--from-pass',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            report = prepare(args.exe,args.proxy,args.out,args.title,argument_list(args.args_json),None if args.baseline_args_json is None else argument_list(args.baseline_args_json),args.proxy_subdir)
        elif args.command == 'run':
            # Ladder levels come from the table so this call does not need editing when a
            # level is added; argparse has already turned each --a-b flag into args.a_b.
            report = run_pass(args.directory, args.mode,
                              name=args.name, start_frame=args.start_frame, frames=args.frames,
                              max_bytes=args.max_bytes, scene_frame=args.scene_frame, note=args.note,
                              wait_trigger=args.wait_trigger, shader_inventory=args.shader_inventory,
                              position_capture=args.position_capture, position_frames=args.position_frames,
                              position_selection=args.position_selection,
                              **{level['name']: getattr(args, level['name']) for level in CAPTURE_LEVELS})
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
