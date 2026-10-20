"""Contract: a restored tree is either faithful to its manifest or it is reported.

Recovering evidence from a preservation image is only worth doing if the result is
checkable. The dangerous failure is a verifier that compares a file with itself, or
that walks the extracted tree and calls whatever it finds correct — both would
report success on a truncated extraction. Every case below therefore asserts a
specific problem string, not merely a non-zero exit.

The extra-file case matters for the opposite reason: an extraction that leaves
stale files behind is not the tree the manifest describes, even if every declared
file matches.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'verify_restored_tree.py'
assert TOOL.is_file(), f'missing {TOOL}'


def run(*arguments):
    result = subprocess.run([sys.executable, str(TOOL), *map(str, arguments)],
                            capture_output=True, text=True, cwd=ROOT)
    payload = json.loads(result.stdout) if result.stdout.strip() else None
    return result.returncode, payload, result.stderr


def build(folder):
    tree = folder / 'restored' / 'build' / 'game-passes' / 'pass-a'
    tree.mkdir(parents=True)
    files = {
        'build\\game-passes\\pass-a\\ledger.jsonl': b'{"kind":"header"}\n',
        'build\\game-passes\\pass-a\\report.json': b'{"status":"exited"}\n',
        'build\\game-passes\\pass-a\\empty.bin': b'',
    }
    for name, data in files.items():
        (folder / 'restored' / Path(name.replace('\\', '/'))).write_bytes(data)
    manifest = folder / 'manifest.jsonl'
    with manifest.open('w', encoding='utf-8', newline='\n') as handle:
        for name, data in files.items():
            handle.write(json.dumps({'path': name, 'bytes': len(data),
                                     'sha256': hashlib.sha256(data).hexdigest()}) + '\n')
        handle.write(json.dumps({'path': 'docs\\unrelated.md', 'bytes': 3,
                                 'sha256': hashlib.sha256(b'abc').hexdigest()}) + '\n')
    return folder / 'restored', manifest, files


def main():
    folder = Path(tempfile.mkdtemp(prefix='restored-tree-'))
    restored, manifest, files = build(folder)
    prefix = 'build\\game-passes\\'

    code, report, error = run(manifest, restored, '--prefix', prefix)
    assert code == 0, (report, error)
    assert report['declared'] == 3 and report['verified'] == 3 and report['problem_count'] == 0

    # A changed byte must name the file, not just fail the run. Same length, so
    # this exercises the digest comparison rather than the size check.
    target = restored / 'build' / 'game-passes' / 'pass-a' / 'report.json'
    target.write_bytes(b'{"status":"exitee"}\n')
    code, report, _ = run(manifest, restored, '--prefix', prefix)
    assert code == 1 and report['problem_count'] == 1, report
    assert 'sha256 mismatch: build\\game-passes\\pass-a\\report.json' in report['problems'], report
    target.write_bytes(files['build\\game-passes\\pass-a\\report.json'])

    # A missing file is a truncated extraction, not a smaller tree.
    absent = restored / 'build' / 'game-passes' / 'pass-a' / 'empty.bin'
    absent.unlink()
    code, report, _ = run(manifest, restored, '--prefix', prefix)
    assert code == 1 and 'missing: build\\game-passes\\pass-a\\empty.bin' in report['problems'], report
    absent.write_bytes(b'')

    # An extra file means the extraction is not the tree the manifest describes.
    (restored / 'build' / 'game-passes' / 'pass-a' / 'stale.tmp').write_bytes(b'x')
    code, report, _ = run(manifest, restored, '--prefix', prefix)
    assert code == 1 and 'extra: build\\game-passes\\pass-a\\stale.tmp' in report['problems'], report
    (restored / 'build' / 'game-passes' / 'pass-a' / 'stale.tmp').unlink()

    # The prefix filters both sides: an unrelated declared file is neither
    # required nor treated as missing.
    code, report, _ = run(manifest, restored)
    assert code == 1, 'an unfiltered run must notice the absent docs file'
    assert any('docs\\unrelated.md' in problem for problem in report['problems']), report

    # Refusals rather than crashes: no manifest, no tree, nothing under the prefix.
    code, _, error = run(folder / 'absent.jsonl', restored)
    assert code == 2 and 'no manifest' in error, error
    code, _, error = run(manifest, folder / 'absent-dir')
    assert code == 2 and 'no restored tree' in error, error
    code, _, error = run(manifest, restored, '--prefix', 'nothing\\here\\')
    assert code == 2 and 'no files under that prefix' in error, error

    print(f'PASS: {report and 3} declared files, hash/missing/extra/prefix/refusal covered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
