"""Local workbench UI over the tested game-pass runner.

Serves a small page on localhost and drives `tools/game_pass.py` as a subprocess.
The runner keeps every provenance, deployment and cleanup guard; this tool adds no
resource handling of its own, so a UI action can never be safer or more dangerous
than the equivalent CLI command.

    python tools/workbench.py --port 8765

Bundle actions are confined to the repository's build/game-passes directory, and
only one pass can be active at a time.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PASS_ROOT = (ROOT / 'build' / 'game-passes').resolve()
RUNNER = Path(__file__).resolve().with_name('game_pass.py')
sys.path.insert(0, str(ROOT / 'tools'))

# Only these run options may be passed through from the page.
RUN_FLAGS = {'--mode', '--name', '--start-frame', '--frames', '--max-bytes', '--note'}
RUN_SWITCHES = {'--wait-trigger', '--shader-inventory', '--position-capture', '--position-frames',
                '--position-multi-draw', '--position-render-state', '--position-clear-evidence',
                '--position-write-evidence', '--position-surface-scope', '--position-color-replay',
                '--position-material-inputs', '--position-pixel-material', '--position-texture-inputs',
                '--position-texture-assets', '--position-compressed-textures', '--position-texture-uploads',
                '--position-dirty-textures', '--position-surface-uploads', '--position-surface-locks'}
SELECTION = re.compile(r'(any|[1-9][0-9]{0,4}x[1-9][0-9]{0,4}):[1-9][0-9]{0,3}\Z')


class Failure(Exception):
    """A client-visible refusal; the message is safe to show."""


def pass_directory(value):
    """Resolve a bundle path, refusing anything outside the pass root."""
    if not isinstance(value, str) or not value:
        raise Failure('a pass directory is required')
    resolved = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if resolved != PASS_ROOT and PASS_ROOT not in resolved.parents:
        raise Failure(f'pass directories must be inside {PASS_ROOT}')
    return resolved


def run_runner(arguments, timeout=120):
    """Run the game-pass runner once and return its parsed JSON report."""
    completed = subprocess.run([sys.executable, str(RUNNER), *arguments],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    text = completed.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise Failure((completed.stderr or text or 'runner produced no report').strip()[:2000])


def suggest_run_name(resolved, name):
    """First free run name derived from a taken one: X, X2, X3, ..."""
    candidate, index = str(name), 2
    while (resolved / 'runs' / candidate).exists():
        candidate = f'{name}{index}'
        index += 1
    return candidate


def build_run_arguments(resolved, name, extra):
    """Assemble runner argv for a run, always carrying the UI's run name."""
    requested = extra or []
    if not isinstance(requested, list) or len(requested) > 40:
        raise Failure('extra arguments must be a short list')
    arguments = ['run', str(resolved)]
    pending = list(requested)
    while pending:
        item = pending.pop(0)
        if item == '--name':
            raise Failure('pass the run name in the Run name field, not as an extra option')
        if item in RUN_SWITCHES:
            arguments.append(item)
        elif item in RUN_FLAGS:
            if not pending:
                raise Failure(f'{item} needs a value')
            arguments += [item, str(pending.pop(0))]
        elif item == '--position-selection':
            if not pending:
                raise Failure('--position-selection needs a value')
            value = str(pending.pop(0))
            if not SELECTION.match(value):
                raise Failure('selection must be WIDTHxHEIGHT:MIN or any:MIN')
            arguments += [item, value]
        else:
            raise Failure(f'unsupported run option: {item}')
    arguments += ['--name', str(name)]
    return arguments


def describe_trigger_state(resolved, name):
    """Explain why a trigger would not fire; None means the run is armed."""
    run_directory = resolved / 'runs' / str(name)
    report_path = run_directory / 'report.json'
    if not report_path.is_file():
        existing = sorted(entry.name for entry in (resolved / 'runs').iterdir()
                          if (entry / 'report.json').is_file()) if (resolved / 'runs').is_dir() else []
        known = f"existing runs: {', '.join(existing)}" if existing else 'no runs exist in this bundle yet'
        return f"no run named '{name}' in this bundle ({known}); press Start first with the same Run name"
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None  # let the runner read it and report the real problem
    marker = run_directory / 'capture.trigger'
    if report.get('mode') != 'proxy' or report.get('trigger_file') != str(marker):
        return (f"run '{name}' was not started with --wait-trigger (status: {report.get('status')}); "
                'Start a new run with Wait for a trigger checked, then trigger while it is running')
    if report.get('status') != 'running':
        return (f"run '{name}' is no longer armed (status: {report.get('status')}); "
                'the game already exited — Start a new run with a fresh name such as '
                f"'{suggest_run_name(resolved, name)}', then trigger while it is running")
    if marker.exists():
        return f"run '{name}' was already triggered; give the game a moment, then check its trace"
    return None


def describe_cleanup_state(resolved, name):
    """Explain why a cleanup would not run; None means the runner should decide."""
    report_path = resolved / 'runs' / str(name) / 'report.json'
    if not report_path.is_file():
        return f"no run named '{name}' in this bundle; nothing to clean up"
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if report.get('proxy_removed'):
        return (f"run '{name}' has nothing to clean up (its proxy is already removed); "
                'just Start a new run with a fresh name')
    return None


def summarise(resolved):
    """Describe one bundle: its plan, its runs and the newest capture's counters."""
    plan = json.loads((resolved / 'plan.json').read_text(encoding='utf-8'))
    runs = []
    for report in sorted((resolved / 'runs').glob('*/report.json')):
        try:
            row = json.loads(report.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            continue
        entry = {key: row.get(key) for key in ('mode', 'name', 'status', 'exit_code', 'proxy_removed',
                                               'executable_unchanged', 'scene_capture_exists', 'wall_seconds')}
        entry['trace'] = row.get('trace')
        entry['selection'] = row.get('position_selection')
        entry['surface_locks'] = row.get('position_surface_locks')
        marker = report.parent / 'capture.trigger'
        trigger_capable = row.get('mode') == 'proxy' and row.get('trigger_file') == str(marker)
        entry['owns_proxy'] = bool(row.get('installed_by_runner')) and not bool(row.get('proxy_removed'))
        entry['armed'] = bool(trigger_capable and row.get('status') == 'running' and not marker.exists())
        entry['triggered'] = bool(marker.exists())
        entry['needs_cleanup'] = bool(entry['owns_proxy'] and row.get('status') != 'running')
        ledger = report.with_name('position-capture.jsonl')
        if ledger.is_file() and ledger.stat().st_size:
            try:
                from inspect_position_capture import inspect
                summary = inspect(ledger)
                entry['ledger'] = {key: summary.get(key) for key in
                                   ('version', 'completion', 'attempts_total', 'captures', 'rejections',
                                    'selection', 'evidence_failures', 'texture_diagnostics')}
            except Exception as error:      # a partly written ledger is normal mid-run
                entry['ledger'] = {'error': str(error)[:200]}
        else:
            entry['ledger'] = None
        entry['trigger'] = (report.parent / 'capture.trigger').exists()
        runs.append(entry)
    return {'directory': str(resolved), 'title': plan.get('title', ''), 'executable': plan.get('executable', ''),
            'baseline_reused': (resolved / 'runs' / 'baseline' / 'report.json').is_file(), 'runs': runs}


def bundles():
    if not PASS_ROOT.is_dir():
        return []
    return [summarise(entry) for entry in sorted(PASS_ROOT.iterdir()) if (entry / 'plan.json').is_file()]


class Workbench:
    """Single-active-pass state shared by the request handlers."""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = None          # {'process':Popen,'directory':str,'name':str,'log':list[str]}

    def start(self, resolved, arguments, name):
        with self.lock:
            if self.active and self.active['process'].poll() is None:
                raise Failure(f"a pass is already running: {self.active['name']} in {self.active['directory']}")
            log = []
            process = subprocess.Popen([sys.executable, str(RUNNER), *arguments], cwd=str(ROOT),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.active = {'process': process, 'directory': str(resolved), 'name': name, 'log': log}
            threading.Thread(target=self._drain, args=(process, log), daemon=True).start()
            return {'directory': str(resolved), 'name': name, 'pid': process.pid}

    @staticmethod
    def _drain(process, log):
        for line in process.stdout:
            log.append(line.rstrip('\n'))
            del log[:-400]

    def status(self):
        with self.lock:
            if not self.active:
                return None
            process = self.active['process']
            return {'directory': self.active['directory'], 'name': self.active['name'], 'pid': process.pid,
                    'running': process.poll() is None, 'exit_code': process.returncode,
                    'log': '\n'.join(self.active['log'][-200:])}


WORKBENCH = Workbench()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'rrt-workbench'

    def log_message(self, *_):      # keep the runner's own output as the record
        pass

    def _send(self, status, payload, content_type='application/json'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > 64 * 1024:
            raise Failure('request body too large')
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise Failure('request body must be JSON')

    def do_GET(self):
        route = urlparse(self.path).path
        try:
            if route == '/':
                return self._send(200, PAGE.encode(), 'text/html; charset=utf-8')
            if route == '/api/state':
                return self._send(200, {'pass_root': str(PASS_ROOT), 'bundles': bundles(),
                                        'active': WORKBENCH.status()})
            return self._send(404, {'error': 'unknown route'})
        except Failure as error:
            return self._send(400, {'error': str(error)})
        except Exception as error:
            return self._send(500, {'error': f'{type(error).__name__}: {error}'})

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            body = self._body()
            if route == '/api/prepare':
                arguments = ['prepare', '--exe', str(body.get('executable', '')), '--proxy', str(body.get('proxy', '')),
                             '--out', str(pass_directory(body.get('out'))), '--title', str(body.get('title', ''))[:120],
                             '--args-json', json.dumps(body.get('arguments') or []),
                             '--proxy-subdir', 'bin' if body.get('proxy_subdir') == 'bin' else '']
                return self._send(200, run_runner(arguments))
            if route == '/api/reuse-baseline':
                arguments = ['reuse-baseline', str(pass_directory(body.get('directory'))), '--from-pass',
                             str(pass_directory(body.get('from_pass')))]
                return self._send(200, run_runner(arguments))
            if route == '/api/trigger':
                resolved = pass_directory(body.get('directory'))
                problem = describe_trigger_state(resolved, str(body.get('name', 'material')))
                if problem is not None:
                    raise Failure(problem)
                return self._send(200, run_runner(['trigger', str(resolved), '--name', str(body.get('name', 'material'))]))
            if route == '/api/cleanup':
                resolved = pass_directory(body.get('directory'))
                problem = describe_cleanup_state(resolved, str(body.get('name', 'material')))
                if problem is not None:
                    raise Failure(problem)
                arguments = ['cleanup', str(resolved), '--name', str(body.get('name', 'material'))]
                if body.get('game_closed'):
                    arguments.append('--game-closed')
                return self._send(200, run_runner(arguments, timeout=300))
            if route == '/api/run':
                return self._send(200, self._run(body))
            return self._send(404, {'error': 'unknown route'})
        except Failure as error:
            return self._send(400, {'error': str(error)})
        except subprocess.TimeoutExpired:
            return self._send(504, {'error': 'runner timed out'})
        except Exception as error:
            return self._send(500, {'error': f'{type(error).__name__}: {error}'})

    @staticmethod
    def _run(body):
        resolved = pass_directory(body.get('directory'))
        if not (resolved / 'plan.json').is_file():
            raise Failure('the pass directory has no plan.json')
        name = body.get('name') or 'material'
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', str(name)):
            raise Failure('run name must be a short lowercase identifier')
        name = str(name)
        if (resolved / 'runs' / name).exists():
            raise Failure(f"run name '{name}' already exists in this bundle; "
                          f"pick a new name — e.g. '{suggest_run_name(resolved, name)}'")
        return WORKBENCH.start(resolved, build_run_arguments(resolved, name, body.get('extra')), name)


PAGE = """<!doctype html><meta charset="utf-8"><title>Radeon RT Remaster workbench</title>
<style>
 body{font:14px/1.5 system-ui,sans-serif;margin:0;background:#12151a;color:#e6e9ef}
 header{padding:14px 20px;background:#1b2029;border-bottom:1px solid #2b323d}
 h1{font-size:16px;margin:0;font-weight:600}
 main{display:grid;grid-template-columns:340px 1fr;gap:18px;padding:18px}
 section{background:#1b2029;border:1px solid #2b323d;border-radius:8px;padding:14px}
 h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#93a0b4;margin:0 0 10px}
 label{display:block;margin:8px 0 2px;color:#93a0b4;font-size:12px}
 input,select,button{font:inherit;width:100%;box-sizing:border-box;padding:7px 9px;border-radius:6px;
  border:1px solid #2b323d;background:#0f1216;color:#e6e9ef}
 button{cursor:pointer;background:#2f6df6;border-color:#2f6df6;font-weight:600;margin-top:10px}
 button.ghost{background:#232a35;border-color:#2b323d;font-weight:500}
 button:disabled{opacity:.45;cursor:not-allowed}
 .row{display:flex;gap:8px}.row>*{flex:1}
 ul.bundles{list-style:none;margin:0;padding:0;max-height:340px;overflow:auto}
 li.bundle{padding:9px;border:1px solid #2b323d;border-radius:6px;margin-bottom:8px;cursor:pointer}
 li.bundle.sel{border-color:#2f6df6;background:#171d27}
 .muted{color:#93a0b4}
 pre{background:#0f1216;border:1px solid #2b323d;border-radius:6px;padding:10px;overflow:auto;
  max-height:300px;white-space:pre-wrap;word-break:break-word;margin:0}
 .pill{display:inline-block;padding:1px 7px;border-radius:99px;font-size:12px;background:#232a35;color:#93a0b4}
 .pill.ok{background:#14361f;color:#5ddc9a}.pill.bad{background:#3a1a1c;color:#ff8a8a}
 .err{color:#ff8a8a;margin-top:10px;white-space:pre-wrap}
</style>
<header><h1>Radeon RT Remaster — capture workbench</h1></header>
<main>
 <div>
  <section><h2>Bundles</h2><ul class="bundles" id="bundles"></ul>
   <button class="ghost" onclick="refresh()">Refresh</button></section>
  <section><h2>Prepare a bundle</h2>
   <label>Game executable</label><input id="exe" placeholder="D:\\Games\\Game\\game.exe">
   <label>Bundle name</label><input id="out" placeholder="game-observation-1">
   <label>Title</label><input id="title" placeholder="Game observation">
   <label>Launch arguments (JSON list)</label><input id="args" value="[]">
   <label>Proxy directory</label><select id="subdir"><option value="bin">game bin/</option><option value="">game root</option></select>
   <button onclick="prepare()">Prepare</button></section>
 </div>
 <div>
  <section><h2 id="sel">No bundle selected</h2>
   <div id="detail" class="muted">Pick a bundle to see its plan, runs and capture counters.</div></section>
  <section><h2>Run</h2>
   <div class="row"><div><label>Mode</label><select id="mode"><option>proxy</option><option>baseline</option><option>disabled</option></select></div>
    <div><label>Run name</label><input id="name" value="material"></div></div>
   <div class="row"><div><label>Trace presents</label><input id="frames" value="60"></div>
    <div><label>Selection</label><input id="selection" value="any:3"></div></div>
   <label><input type="checkbox" id="wait_trigger" checked style="width:auto"> Wait for a trigger (arm, then capture on demand)</label>
   <label><input type="checkbox" id="chain" checked style="width:auto"> Full material/texture evidence chain (v19)</label>
   <div class="row"><button id="startBtn" onclick="start()">Start</button><button id="triggerBtn" class="ghost" onclick="trigger()">Trigger</button>
    <button id="cleanupBtn" class="ghost" onclick="cleanup()">Cleanup</button></div>
   <div id="runhint" class="muted" style="margin-top:10px">Select a bundle to begin.</div>
   <div id="active" class="muted" style="margin-top:10px"></div>
   <div id="err" class="err"></div>
   <pre id="log" style="margin-top:10px">no active run</pre></section>
 </div>
</main>
<script>
const CHAIN=['--shader-inventory','--position-capture','--position-frames','--position-multi-draw',
 '--position-render-state','--position-clear-evidence','--position-write-evidence','--position-surface-scope',
 '--position-color-replay','--position-material-inputs','--position-pixel-material','--position-texture-inputs',
 '--position-texture-assets','--position-compressed-textures','--position-texture-uploads',
 '--position-dirty-textures','--position-surface-uploads','--position-surface-locks'];
let current=null,state=null;
const $=id=>document.getElementById(id);
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify(body)}:undefined);const d=await r.json().catch(()=>({error:'bad response'}));
 if(!r.ok)throw new Error(d.error||('HTTP '+r.status));return d;}
function fail(e){$('err').textContent=String(e.message||e);}
function clearErr(){$('err').textContent='';}
async function refresh(){try{clearErr();state=await api('/api/state');render();}catch(e){fail(e);}}
function render(){
 const list=$('bundles');list.innerHTML='';
 for(const b of state.bundles){const li=document.createElement('li');li.className='bundle'+(current===b.directory?' sel':'');
  const last=b.runs[b.runs.length-1];const ok=last&&last.exit_code===0;
  li.innerHTML=`<b>${b.directory.split(/[\\\\/]/).pop()}</b> <span class="pill ${ok?'ok':'bad'}">`+
   `${last?(ok?'exit 0':'exit '+last.exit_code):'no runs'}</span><br><span class="muted">${b.title||''}</span>`;
  li.onclick=()=>{current=b.directory;render();};list.appendChild(li);}
 const b=state.bundles.find(x=>x.directory===current);
 $('sel').textContent=b?b.directory: 'No bundle selected';
 if(b){const last=b.runs[b.runs.length-1];const led=last&&last.ledger;
  const pills=r=>{const p=[`<span class="pill">${r.status||'?'}</span>`];
   if(r.armed)p.push('<span class="pill ok">armed</span>');
   if(r.triggered)p.push('<span class="pill">triggered</span>');
   if(r.needs_cleanup)p.push('<span class="pill bad">cleanup needed</span>');
   return p.join(' ');};
  const overview=b.runs.length?b.runs.map(r=>`<div><b>${r.name}</b> (${r.mode}) ${pills(r)}`+
   (r.needs_cleanup?` <button class="ghost" style="width:auto;padding:2px 10px;margin:2px 0" onclick="cleanupRun('${r.name}')">Cleanup '${r.name}'</button>`:'')+
   `</div>`).join(''):'<p class="muted">No runs yet.</p>';
  const freeName=base=>{const taken=new Set(b.runs.map(r=>r.name));if(!taken.has(base))return base;
   let i=2;while(taken.has(base+i))i++;return base+i;};
  const nm=(($('name').value||'material').trim()||'material');
  const run=b.runs.find(r=>r.name===nm);
  const busy=state.active&&state.active.running;
  let hint='';
  if(busy)hint=`${state.active.name} is running (pid ${state.active.pid}) — get into gameplay, press Trigger, then exit the game normally so its proxy is removed.`;
  else if(run&&run.armed)hint=`'${nm}' is armed — press Trigger, then alt-tab back and play.`;
  else if(run&&run.triggered)hint=`'${nm}' already triggered — play on, then exit the game normally.`;
  else if(run)hint=`'${nm}' finished (${run.status||'?'}) — Start a fresh name such as '${freeName(nm)}'.`;
  else hint=`No run named '${nm}' yet — press Start to create it. Close any hand-launched game first; the runner launches its own instance.`;
  if(run&&!busy&&!(run.armed||run.triggered))hint+=` (Run name '${nm}' is taken — Start would refuse it.)`;
  const stale=b.runs.find(r=>r.needs_cleanup);
  if(stale)hint+=` '${stale.name}' still owns its proxy — close the game, then press its Cleanup button.`;
  $('runhint').textContent=hint;
  $('startBtn').disabled=!!busy;
  $('triggerBtn').disabled=!(run&&run.armed);
  $('detail').innerHTML='<p><b>Runs</b></p>'+overview+
   (b.baseline_reused?'<p>Baseline reused under provenance.</p>':'<p class="muted">No recorded baseline.</p>')+
   `<p>Executable: <span class="muted">${b.executable}</span></p>`+
   (last?`<p>Last run <b>${last.name}</b> (${last.mode}) — ${last.status||'?'}`+
     (last.selection?`, selection <code>${last.selection}</code>`:'')+
     (last.surface_locks?', v19 surface locks':'')+`</p>`+
     (last.trace?`<p>Trace: ${last.trace.presents} presents, ${last.trace.events} events, ${last.trace.shader_draws} shader draws, ${last.trace.failed_calls} failed</p>`:'')+
     (led?`<p>Ledger: version ${led.version}, ${led.attempts_total} attempts, `+
       `<b>${(led.captures||[]).length} captures</b>, rejections ${JSON.stringify(led.rejections||{})}</p>`+
       (led.evidence_failures&&led.evidence_failures.length?`<p>Failures: ${JSON.stringify(led.evidence_failures)}</p>`:'')+
       (led.selection?`<p>Selection policy: <code>${JSON.stringify(led.selection)}</code></p>`:'')
      :'<p class="muted">No ledger yet.</p>')
    :'<p class="muted">No runs yet.</p>');}
 else{$('runhint').textContent='Select a bundle on the left first.';$('startBtn').disabled=true;$('triggerBtn').disabled=true;}
 const a=state.active;
 $('active').textContent=a?`${a.name} — ${a.running?'running':'finished'}`+(a.running?` (pid ${a.pid})`:' (exit '+a.exit_code+')'):'idle';
 $('log').textContent=a&&a.log?a.log:'no active run';
}
async function prepare(){try{clearErr();await api('/api/prepare',{executable:$('exe').value,proxy:'build/x86-vs/Release/d3d9.dll',
 out:$('out').value,title:$('title').value,arguments:JSON.parse($('args').value||'[]'),proxy_subdir:$('subdir').value});
 current=null;await refresh();}catch(e){fail(e);}}
function extra(){const x=['--mode',$('mode').value,'--frames',$('frames').value,'--note','workbench run'];
 if($('wait_trigger').checked)x.push('--wait-trigger');
 if($('chain').checked){x.push('--position-selection',$('selection').value);x.push(...CHAIN);}
 return x;}
async function start(){try{clearErr();if(!current)throw new Error('select a bundle first');
 await api('/api/run',{directory:current,name:$('name').value,extra:extra()});await refresh();}catch(e){fail(e);}}
async function trigger(){try{clearErr();if(!current)throw new Error('select a bundle first');
 await api('/api/trigger',{directory:current,name:$('name').value});await refresh();}catch(e){fail(e);}}
async function cleanup(){try{clearErr();if(!current)throw new Error('select a bundle first');
 await api('/api/cleanup',{directory:current,name:$('name').value,game_closed:true});await refresh();}catch(e){fail(e);}}
async function cleanupRun(name){try{clearErr();if(!current)throw new Error('select a bundle first');
 $('name').value=name;await api('/api/cleanup',{directory:current,name:name,game_closed:true});await refresh();}catch(e){fail(e);}}
$('name').addEventListener('input',()=>{if(state)render();});
refresh();setInterval(refresh,2000);
</script>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='127.0.0.1')
    arguments = parser.parse_args()
    PASS_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((arguments.host, arguments.port), Handler)
    print(f'workbench on http://{arguments.host}:{arguments.port}  (passes in {PASS_ROOT})', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
