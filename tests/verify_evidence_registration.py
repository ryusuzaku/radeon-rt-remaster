"""Exercise real CTest skip/pass/fail transitions without a GPU or game content."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command, expected=0):
    result = subprocess.run(command, text=True, capture_output=True)
    output = result.stdout + result.stderr
    assert result.returncode == expected, (command, result.returncode, output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--ctest', default='ctest')
    parser.add_argument('--test-dir', type=Path)
    parser.add_argument('--config', default='Release')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.test_dir:
        metadata = json.loads(run([args.ctest, '--test-dir', str(args.test_dir),
                                   '-C', args.config, '-L', 'local_evidence', '--show-only=json-v1']))
        expected = {'hl2_position', 'position_capture', 'recorded_position_oracle',
                    'position_reconstruction', 'capture_position_scene', 'position_groups'}
        expected.update(f'texture_{kind}' for kind in
                        ('compressed', 'upload', 'dirty', 'surface', 'locks', 'scope', 'selection'))
        assert {test['name'] for test in metadata['tests']} == expected, metadata
        for test in metadata['tests']:
            properties = {item['name']: item['value'] for item in test['properties']}
            assert properties['SKIP_RETURN_CODE'] == 77, test
            assert any(arg.endswith('/tests/run_evidence_test.py') for arg in test['command']), test
            if test['name'] == 'position_capture' or test['name'].startswith('texture_'):
                assert properties['RESOURCE_LOCK'] == ['native_texture_fixture'], test
    with tempfile.TemporaryDirectory(prefix='rrt evidence ') as temporary_raw:
        # Resolve 8.3 short names (RUNNER~1) so paths match what cmake/ctest print.
        temporary = str(Path(temporary_raw).resolve())
        source = Path(temporary) / 'source with spaces'
        build = Path(temporary) / 'build with spaces'
        (source / 'tests').mkdir(parents=True)
        shutil.copyfile(root / 'tests/run_evidence_test.py', source / 'tests/run_evidence_test.py')
        evidence = source / 'owned evidence.json'
        validator = source / 'validator.py'
        validator.write_text(
            'import json, pathlib, sys\n'
            'assert sys.argv[2:] == ["argument with spaces", "--flag"]\n'
            'assert json.loads(pathlib.Path(sys.argv[1]).read_text()) == {"valid": True}\n'
            'print("original validator ran")\n', encoding='utf-8')
        (source / 'CMakeLists.txt').write_text(
            'cmake_minimum_required(VERSION 3.25)\n'
            'project(EvidenceRegistration NONE)\n'
            'enable_testing()\n'
            f'set(Python3_EXECUTABLE "{Path(sys.executable).as_posix()}")\n'
            f'include("{(root / "cmake/EvidenceTests.cmake").as_posix()}")\n'
            'set(OWNED_CAPTURE "${PROJECT_SOURCE_DIR}/owned evidence.json")\n'
            'rrt_add_evidence_test(qualification OWNED_CAPTURE "${Python3_EXECUTABLE}" '
            '"${PROJECT_SOURCE_DIR}/validator.py" "${OWNED_CAPTURE}" "argument with spaces" --flag)\n',
            encoding='utf-8')
        run([args.cmake, '-S', str(source), '-B', str(build)])
        ctest = [args.ctest, '--test-dir', str(build), '-C', 'Release']
        metadata = json.loads(run(ctest + ['--show-only=json-v1']))
        assert [test['name'] for test in metadata['tests']] == ['qualification']
        properties = {item['name']: item['value'] for item in metadata['tests'][0]['properties']}
        assert properties['SKIP_RETURN_CODE'] == 77
        assert properties['LABELS'] == ['local_evidence']

        # The same generated CTest entry must respond to evidence changes without
        # another configure, while retaining the original validator's failures.
        for state in ('missing', 'directory', 'valid', 'malformed', 'invalid', 'valid', 'removed'):
            if evidence.is_file():
                evidence.unlink()
            elif evidence.is_dir():
                evidence.rmdir()
            if state == 'directory':
                evidence.mkdir()
            elif state == 'valid':
                evidence.write_text('{"valid": true}', encoding='utf-8')
            elif state == 'malformed':
                evidence.write_text('not json', encoding='utf-8')
            elif state == 'invalid':
                evidence.write_text('{"valid": false}', encoding='utf-8')
            failure = state in ('malformed', 'invalid')
            output = run(ctest + ['-V'], expected=8 if failure else 0)
            if state in ('missing', 'directory', 'removed'):
                assert '***Skipped' in output and 'original validator ran' not in output, output
                assert '-DOWNED_CAPTURE=<file>' in output and evidence.as_posix() in output, output
            elif failure:
                assert '***Failed' in output and 'SKIP qualification' not in output, output
            else:
                assert 'Passed' in output and 'original validator ran' in output, output

        # Preserve the child exit code, not just success/failure. Even without
        # evidence, malformed invocations must fail rather than report a skip.
        wrapper = [sys.executable, str(source / 'tests/run_evidence_test.py'),
                   '--test-name', 'qualification', '--evidence-variable', 'OWNED_CAPTURE',
                   '--evidence', str(evidence)]
        run(wrapper + ['--'], expected=2)
        evidence.write_text('{}', encoding='utf-8')
        run(wrapper + ['--', sys.executable, '-c', 'raise SystemExit(23)'], expected=23)
    print('Evidence registration: missing/directory/restored/invalid/removed CTest transitions pass')


if __name__ == '__main__':
    main()
