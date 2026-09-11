"""Validate and inspect RRT observation traces using only Python's standard library."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

MAX_LINE = 65536
MAX_BYTES = 512 * 1024 * 1024
MAX_EVENTS = 1_000_000

class TraceError(ValueError):
    pass

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TraceError('duplicate JSON member')
        result[key] = value
    return result

def integer(value, field, minimum=0):
    if type(value) is not int or value < minimum or value > 2**64-1:
        raise TraceError(f'invalid {field}')
    return value

def inspect_stream(stream, *, frame=None, allow_incomplete=False):
    header = footer = None
    methods, resource_types, frames = Counter(), Counter(), {}
    bindings = Counter({'fixed':0,'vertex_only':0,'pixel_only':0,'vertex_and_pixel':0,'unknown':0})
    draw_methods, input_updates = Counter(), Counter()
    constant_payloads = Counter({'complete':0,'missing_or_truncated':0})
    inventory, live, dead, timeline = {}, set(), set(), []
    count = total_bytes = presentations = draws = shader_draws = fixed_draws = failures = 0
    next_frame = 0
    while True:
        line = stream.readline(MAX_LINE + 1)
        if not line:
            break
        total_bytes += len(line.encode('utf-8'))
        if total_bytes > MAX_BYTES or len(line) > MAX_LINE:
            raise TraceError('trace or record exceeds reader limit')
        if not line.endswith('\n'):
            raise TraceError('truncated final record')
        try:
            record = json.loads(line, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(TraceError('non-finite number')))
        except (ValueError, RecursionError, UnicodeError) as error:
            raise TraceError('malformed JSON record') from error
        if not isinstance(record, dict):
            raise TraceError('record must be an object')
        if footer is not None:
            raise TraceError('data after footer')
        if header is None:
            if record.get('type') != 'header' or record.get('schema') != 'rrt-observation' or type(record.get('version')) is not int or record['version'] != 1:
                raise TraceError('unsupported or missing schema header')
            integer(record.get('start_frame'), 'start_frame')
            integer(record.get('frame_count'), 'frame_count')
            if record.get('pointer_bits') not in (32,64):
                raise TraceError('invalid pointer_bits')
            header = record
            next_frame = header['start_frame']
            continue
        if record.get('type') == 'footer':
            if record.get('reason') not in ('finished','frame_limit','byte_limit'):
                raise TraceError('invalid completion reason')
            if integer(record.get('events'), 'events') != count:
                raise TraceError('footer event count mismatch')
            integer(record.get('present_count'), 'present_count')
            if count and record['present_count'] != next_frame:
                raise TraceError('footer frame count mismatch')
            footer = record
            continue
        if record.get('type') != 'event':
            raise TraceError('unexpected record type')
        if count >= MAX_EVENTS:
            raise TraceError('event limit exceeded')
        if integer(record.get('seq'), 'seq') != count:
            raise TraceError('event sequence gap')
        event_frame = integer(record.get('frame'), 'frame')
        if event_frame != next_frame:
            raise TraceError('frame boundary mismatch')
        if event_frame - header['start_frame'] >= header['frame_count']:
            raise TraceError('event outside capture range')
        oid = integer(record.get('object'), 'object', 1)
        integer(record.get('thread_id'), 'thread_id', 1)
        method, hr, args = record.get('method'), record.get('hr'), record.get('args')
        if not isinstance(method,str) or not method.isidentifier() or len(method) > 128:
            raise TraceError('invalid method')
        if type(hr) is not int or not -(2**31) <= hr < 2**31 or not isinstance(args,dict):
            raise TraceError('invalid result or arguments')
        if any(not isinstance(k,str) or type(v) not in (int,float,str,type(None)) for k,v in args.items()):
            raise TraceError('invalid argument value')
        if method == 'ObjectCreated':
            if oid in live or oid in dead:
                raise TraceError('duplicate object identity')
            interface = args.get('interface')
            if not isinstance(interface,str) or not interface.startswith('IDirect3D') or len(interface)>80:
                raise TraceError('invalid interface name')
            live.add(oid)
            inventory[oid] = {'interface':interface, 'created_frame':event_frame}
            resource_types[interface] += 1
        elif oid not in live:
            if oid in dead or header['start_frame'] == 0:
                raise TraceError('event references unknown/destroyed object')
            # Frame-selected traces are observation slices, not full snapshots.
            live.add(oid)
            inventory[oid] = {'interface':'external_to_capture', 'created_frame':None}
        if method == 'ObjectDestroyed':
            live.remove(oid); dead.add(oid)
        if hr >= 0 and method.startswith('Create'):
            for key, value in args.items():
                if key.startswith(('pp','pSwap')) and type(value) is int and value in inventory:
                    inventory[value]['creation'] = {'method':method, 'args':args}
        methods[method] += 1
        if hr >= 0 and method in ('SetStreamSource','SetStreamSourceFreq','SetIndices','SetFVF','SetVertexDeclaration',
                                   'CreateVertexDeclaration','CreateVertexShader','CreatePixelShader','SetTransform',
                                   'SetVertexShaderConstantF','SetPixelShaderConstantF',
                                   'SetVertexShaderConstantI','SetPixelShaderConstantI',
                                   'SetVertexShaderConstantB','SetPixelShaderConstantB'):
            input_updates[method] += 1
            if method.endswith('ConstantF'):
                vectors=args.get('Vector4fCount')
                payload=args.get('constants')
                complete=(type(vectors) is int and vectors>=0 and isinstance(payload,str)
                          and len(payload)==vectors*32 and all(c in '0123456789abcdefABCDEF' for c in payload))
                constant_payloads['complete' if complete else 'missing_or_truncated'] += 1
        bucket = frames.setdefault(event_frame, {'events':0,'draws':0,'fixed_draws':0,'shader_draws':0,'presents':0})
        bucket['events'] += 1
        if hr < 0:
            failures += 1
        if method.startswith('Draw') and hr >= 0:
            draws += 1; bucket['draws'] += 1
            draw_methods[method] += 1
            vs,ps=args.get('vertex_shader_bound'),args.get('pixel_shader_bound')
            if type(vs) is int and type(ps) is int and vs in (0,1) and ps in (0,1):
                bindings[('fixed','pixel_only','vertex_only','vertex_and_pixel')[vs*2+ps]] += 1
            else:
                bindings['unknown'] += 1
            if args.get('vertex_shader_bound') or args.get('pixel_shader_bound'):
                shader_draws += 1; bucket['shader_draws'] += 1
            else:
                fixed_draws += 1; bucket['fixed_draws'] += 1
        if method in ('Present','PresentEx') and hr == 0:
            presentations += 1; bucket['presents'] += 1; next_frame += 1
        if frame is not None and event_frame == frame:
            timeline.append(record)
        count += 1
    if header is None:
        raise TraceError('empty trace')
    if footer is None and not allow_incomplete:
        raise TraceError('missing footer (interrupted capture); use --allow-incomplete for a complete-record prefix')
    result = {'schema_version':1,'completion':footer['reason'] if footer else 'incomplete',
              'events':count,'presents':presentations,'draws':draws,'fixed_draws':fixed_draws,
              'shader_draws':shader_draws,'failed_calls':failures,'methods':dict(sorted(methods.items())),
              'resource_types':dict(sorted(resource_types.items())), 'objects':inventory,
              'frames':frames,'live_objects_at_end':len(live)}
    if frame is not None:
        result['timeline'] = timeline
    result['shader_profile']={'draw_bindings':dict(bindings),'draw_methods':dict(sorted(draw_methods.items())),
                              'successful_input_updates':dict(sorted(input_updates.items())),
                              'float_constant_payloads':dict(constant_payloads),
                              'scope':'observed events only; no inferred initial state or geometry reconstruction'}
    return result

def inspect(path, **options):
    try:
        with Path(path).open('r',encoding='utf-8',newline='') as stream:
            return inspect_stream(stream, **options)
    except (OSError, UnicodeError) as error:
        raise TraceError(str(error)) from error

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--json', action='store_true', help='machine-readable summary and optional timeline')
    parser.add_argument('--frame', type=int, help='include the ordered call timeline for this frame')
    parser.add_argument('--allow-incomplete', action='store_true')
    parser.add_argument('--shader-profile',action='store_true',help='Print bounded shader-input evidence only')
    args = parser.parse_args()
    try:
        report = inspect(args.trace, frame=args.frame, allow_incomplete=args.allow_incomplete)
    except TraceError as error:
        print(f'Trace rejected: {error}',file=sys.stderr)
        return 2
    if args.shader_profile:
        print(json.dumps(report['shader_profile'],indent=2))
    elif args.json:
        print(json.dumps(report,indent=2))
    else:
        print(f"Capture: {report['completion']}; {report['events']} events, {report['presents']} presents")
        print(f"Draws: {report['draws']} ({report['fixed_draws']} fixed-function, {report['shader_draws']} shader); failed calls: {report['failed_calls']}")
        for name, count in report['resource_types'].items():
            print(f'  {name}: {count}')
        if args.frame is not None:
            for event in report['timeline']:
                print(f"  #{event['seq']} object={event['object']} {event['method']} hr={event['hr']} {event['args']}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
