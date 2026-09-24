"""Workbench API contract: confined paths, validated options and one active pass.

Runs the real local server against the real runner. Nothing launches a game here:
the run endpoint is only exercised for its refusals, and the single-pass guard is
checked against a stub process.
"""
import argparse
import json
import shutil
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import workbench

_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--fixture', type=Path)
_parser.add_argument('--proxy', type=Path)
_arguments, _ = _parser.parse_known_args()
SAMPLE = _arguments.fixture or ROOT / 'build' / 'x86-vs' / 'Release' / 'd3d9_smoke_sample.exe'
PROXY = _arguments.proxy or ROOT / 'build' / 'x86-vs' / 'Release' / 'd3d9.dll'
# The stand-in game must not share a directory with the proxy: the runner refuses to
# deploy over an existing d3d9.dll, which is exactly the guard we want it to keep.
GAME_DIR = ROOT / 'build' / 'workbench-fixture'
GAME = GAME_DIR / 'self-test.exe'
NAME = 'workbench-selftest'
BUNDLE = workbench.PASS_ROOT / NAME
OVERWRITE = workbench.PASS_ROOT / 'workbench-overwrite'


class WorkbenchApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(p) for p in (SAMPLE, PROXY) if not p.is_file()]
        if missing:
            raise unittest.SkipTest('release fixtures missing: ' + ', '.join(missing))
        for directory in (BUNDLE, OVERWRITE):
            shutil.rmtree(directory, ignore_errors=True)
        shutil.rmtree(GAME_DIR, ignore_errors=True)
        GAME_DIR.mkdir(parents=True)
        shutil.copyfile(SAMPLE, GAME)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), workbench.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.port = cls.server.server_address[1]
        # One bundle prepared directly so every test is independent of ordering.
        workbench.run_runner(['prepare', '--exe', str(GAME), '--proxy', str(PROXY), '--out', str(BUNDLE),
                              '--title', 'self test', '--args-json', '[]', '--proxy-subdir', ''])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        for directory in (BUNDLE, OVERWRITE):
            shutil.rmtree(directory, ignore_errors=True)
        shutil.rmtree(GAME_DIR, ignore_errors=True)

    def call(self, method, path, body=None, content_type='application/json'):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=180)
        payload = None if body is None else json.dumps(body).encode()
        headers = {} if payload is None else {'Content-Type': content_type}
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, (json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw)

    def test_page_and_state_are_served(self):
        status, page = self.call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'capture workbench', page)
        status, state = self.call('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(str(workbench.PASS_ROOT), state['pass_root'])
        self.assertIsInstance(state['bundles'], list)
        for bundle in state['bundles']:
            self.assertTrue(bundle['directory'].startswith(str(workbench.PASS_ROOT)))

    def test_unknown_route_is_rejected(self):
        self.assertEqual(404, self.call('GET', '/api/nope')[0])
        self.assertEqual(404, self.call('POST', '/api/nope', {})[0])

    def test_prepare_refuses_to_overwrite_and_confines_paths(self):
        status, report = self.call('POST', '/api/prepare', {'executable': str(GAME), 'proxy': str(PROXY),
                                                            'out': str(OVERWRITE), 'title': 'overwrite probe',
                                                            'arguments': ['-steam', '-game', 'x'], 'proxy_subdir': ''})
        self.assertEqual(status, 200, report)
        plan = json.loads((OVERWRITE / 'plan.json').read_text(encoding='utf-8'))
        self.assertEqual(['-steam', '-game', 'x'], plan['arguments'])
        self.assertEqual('', plan['proxy_subdir'])
        self.assertTrue(plan['executable_sha256'] and plan['proxy_sha256'])
        marker = plan['created_utc']
        status, error = self.call('POST', '/api/prepare', {'executable': str(GAME), 'proxy': str(PROXY),
                                                           'out': str(OVERWRITE), 'title': 'again'})
        self.assertEqual(400, status, error)
        self.assertIn('exist', error['error'])
        self.assertEqual(marker, json.loads((OVERWRITE / 'plan.json').read_text(encoding='utf-8'))['created_utc'])
        # A proxy subdirectory must already exist next to the executable; the runner refuses otherwise.
        status, error = self.call('POST', '/api/prepare', {'executable': str(GAME), 'proxy': str(PROXY),
                                                           'out': str(OVERWRITE) + '-bin', 'proxy_subdir': 'bin'})
        self.assertEqual(400, status, error)
        self.assertIn('missing or redirected', error['error'])
        for outside in ('../escape', str(ROOT / 'src'), 'build/x86-vs'):
            status, error = self.call('POST', '/api/prepare', {'executable': str(GAME), 'proxy': str(PROXY), 'out': outside})
            self.assertEqual(400, status, (outside, error))
            self.assertIn('build', error['error'])
        self.assertFalse((ROOT / 'escape').exists())
        self.assertFalse((ROOT.parent / 'escape').exists())

    def test_reuse_baseline_confines_both_paths(self):
        status, error = self.call('POST', '/api/reuse-baseline', {'directory': str(BUNDLE), 'from_pass': '../elsewhere'})
        self.assertEqual(400, status, error)
        self.assertIn('build', error['error'])

    def test_run_validates_options_and_directory(self):
        for body, expected in (
            ({'directory': str(workbench.PASS_ROOT / 'does-not-exist'), 'name': 'material'}, 'plan.json'),
            ({'directory': '../escape', 'name': 'material'}, 'build'),
            ({'directory': str(BUNDLE), 'name': 'material', 'extra': ['--exe', 'x']}, 'unsupported'),
            ({'directory': str(BUNDLE), 'name': 'material', 'extra': ['--position-selection', 'bogus']}, 'selection'),
            ({'directory': str(BUNDLE), 'name': 'material', 'extra': ['--position-selection']}, 'needs a value'),
            ({'directory': str(BUNDLE), 'name': 'Material'}, 'lowercase'),
            ({'directory': str(BUNDLE), 'name': 'material', 'extra': ['--frames', '1'] * 40}, 'short list'),
        ):
            status, error = self.call('POST', '/api/run', body)
            self.assertEqual(400, status, (body, error))
            self.assertIn(expected, error['error'], body)

    def test_trigger_and_cleanup_require_a_known_bundle(self):
        for route in ('/api/trigger', '/api/cleanup'):
            status, error = self.call('POST', route, {'directory': '../escape', 'name': 'material'})
            self.assertEqual(400, status, (route, error))
            self.assertIn('build', error['error'])

    def test_only_one_pass_may_be_active(self):
        bench = workbench.Workbench()

        class Running:
            returncode = None
            pid = 4242

            def poll(self):
                return None

        bench.active = {'process': Running(), 'directory': str(BUNDLE), 'name': 'first', 'log': []}
        with self.assertRaises(workbench.Failure) as caught:
            bench.start(BUNDLE, ['run', str(BUNDLE)], 'second')
        self.assertIn('already running', str(caught.exception))
        self.assertEqual('first', bench.active['name'])
        status = bench.status()
        self.assertTrue(status['running'])
        self.assertEqual(4242, status['pid'])

    def test_finished_pass_no_longer_blocks(self):
        bench = workbench.Workbench()

        class Finished:
            returncode = 0
            pid = 1

            def poll(self):
                return 0

        bench.active = {'process': Finished(), 'directory': str(BUNDLE), 'name': 'first', 'log': ['{"a":1}']}
        self.assertFalse(bench.status()['running'])
        self.assertEqual('{"a":1}', bench.status()['log'])

    def test_run_forwards_name_to_runner(self):
        arguments = workbench.build_run_arguments(BUNDLE, 'material2', ['--mode', 'proxy', '--wait-trigger'])
        self.assertIn('--name', arguments)
        self.assertEqual('material2', arguments[arguments.index('--name') + 1])

    def test_run_refuses_taken_name_with_suggestion(self):
        stub = BUNDLE / 'runs' / 'taken-probe'
        stub.mkdir(parents=True, exist_ok=True)
        (stub / 'report.json').write_text('{}', encoding='utf-8')
        self.addCleanup(shutil.rmtree, stub, True)
        status, error = self.call('POST', '/api/run', {'directory': str(BUNDLE), 'name': 'taken-probe',
                                                       'extra': ['--mode', 'proxy']})
        self.assertEqual(400, status, error)
        self.assertIn('already exists', error['error'])
        self.assertIn('taken-probe2', error['error'])

    def test_trigger_explains_finished_and_unknown_runs(self):
        stub = BUNDLE / 'runs' / 'trig-probe'
        stub.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, stub, True)
        (stub / 'report.json').write_text(json.dumps(
            {'mode': 'proxy', 'name': 'trig-probe', 'status': 'trace-rejected',
             'trigger_file': str(stub / 'capture.trigger')}), encoding='utf-8')
        status, error = self.call('POST', '/api/trigger', {'directory': str(BUNDLE), 'name': 'trig-probe'})
        self.assertEqual(400, status, error)
        self.assertIn('trace-rejected', error['error'])
        status, error = self.call('POST', '/api/trigger', {'directory': str(BUNDLE), 'name': 'no-such-run'})
        self.assertEqual(400, status, error)
        self.assertIn('no-such-run', error['error'])

    def test_state_reports_armed_and_cleanup_flags(self):
        armed = BUNDLE / 'runs' / 'armed-probe'
        armed.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, armed, True)
        (armed / 'report.json').write_text(json.dumps(
            {'mode': 'proxy', 'name': 'armed-probe', 'status': 'running',
             'trigger_file': str(armed / 'capture.trigger'),
             'installed_by_runner': True, 'proxy_removed': False}), encoding='utf-8')
        stale = BUNDLE / 'runs' / 'stale-probe'
        stale.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, stale, True)
        (stale / 'report.json').write_text(json.dumps(
            {'mode': 'proxy', 'name': 'stale-probe', 'status': 'interrupted',
             'installed_by_runner': True, 'proxy_removed': False}), encoding='utf-8')
        status, state = self.call('GET', '/api/state')
        self.assertEqual(200, status, state)
        bundle = next(entry for entry in state['bundles'] if entry['directory'] == str(BUNDLE))
        armed_row = next(row for row in bundle['runs'] if row['name'] == 'armed-probe')
        self.assertTrue(armed_row['armed'])
        self.assertFalse(armed_row['triggered'])
        self.assertFalse(armed_row['needs_cleanup'])
        stale_row = next(row for row in bundle['runs'] if row['name'] == 'stale-probe')
        self.assertFalse(stale_row['armed'])
        self.assertTrue(stale_row['needs_cleanup'])

    def test_empty_body_is_a_clean_refusal(self):
        status, error = self.call('POST', '/api/prepare', None)
        self.assertEqual(400, status, error)
        self.assertIn('error', error)

    def test_malformed_json_body_is_rejected(self):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=60)
        connection.request('POST', '/api/run', body=b'{not json', headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        self.assertEqual(400, response.status, raw)
        self.assertIn('JSON', json.loads(raw)['error'])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
