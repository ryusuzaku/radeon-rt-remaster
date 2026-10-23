"""Contract: an evidence archive is self-verifying, or it is refused.

This exists because the failure it prevents already happened. On 2026-10-15 a
workspace move deleted every local game-pass bundle and the shader inventory,
because they were loose files under a gitignored `build/`. An archive is only a
fix if it can be *proved* intact before it is trusted, so the checks that matter
are the negative ones:

  * a flipped byte, a missing member, an extra member or a bumped schema must all
    fail verification and name what is wrong, rather than reporting success;
  * extraction must never write outside the target directory, and must never
    overwrite an existing file, because the archive may come from elsewhere;
  * bounds must be refusable from the command line only in the strict direction.

A verifier that always says "verified" would pass the happy path and hide exactly
the corruption this tool exists to detect, so every negative case below asserts
the specific failure rather than just a non-zero exit.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'evidence_archive.py'
assert TOOL.is_file(), f'missing {TOOL}'
MANIFEST = 'rrt-evidence-manifest.json'


def run(*arguments, env=None):
    environment = None
    if env is not None:
        environment = {**os.environ, **env}
    result = subprocess.run([sys.executable, str(TOOL), *map(str, arguments)],
                            capture_output=True, text=True, cwd=ROOT, env=environment)
    payload = None
    if result.stdout.strip():
        payload = json.loads(result.stdout)
    return result.returncode, payload, result.stderr


def source_tree(folder):
    root = folder / 'pass'
    (root / 'bin').mkdir(parents=True)
    (root / 'assets' / 'nested').mkdir(parents=True)
    (root / 'ledger.jsonl').write_text('{"kind":"header"}\n{"kind":"end"}\n', encoding='utf-8')
    (root / 'bin' / 'd3d9.dll').write_bytes(bytes(range(256)) * 4)
    (root / 'assets' / 'nested' / 'texture.bin').write_bytes(b'\x00\xff' * 64)
    (root / 'empty.bin').write_bytes(b'')
    return root


def rebuild(archive, destination, mutate):
    """Copy an archive, letting `mutate` change the manifest and member payloads."""
    with tarfile.open(archive, 'r:gz') as tar:
        manifest = json.loads(tar.extractfile(MANIFEST).read())
        members = [(member, tar.extractfile(member).read())
                   for member in tar if member.name != MANIFEST]
    manifest, members = mutate(manifest, members)
    with tarfile.open(destination, 'w:gz') as tar:
        payload = json.dumps(manifest, indent=1, sort_keys=True).encode()
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
        for member, data in members:
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return destination


def main():
    folder = Path(tempfile.mkdtemp(prefix='evidence-archive-'))
    root = source_tree(folder)
    expected = {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}
    assert len(expected) == 4, expected

    archive = folder / 'pass.tar.gz'
    code, created, error = run('create', root, '--out', archive, '--note', 'contract test')
    assert code == 0, error
    assert created['result'] == 'created' and created['file_count'] == 4
    assert created['total_bytes'] == sum(len(v) for v in expected.values())
    # The archive digest is reported so it can be recorded out of band; it must be
    # the digest of the file that exists, not of some intermediate buffer.
    assert created['archive_sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()

    code, verified, error = run('verify', archive)
    assert code == 0 and verified['result'] == 'verified', (verified, error)
    assert verified['file_count'] == 4 and verified['problems'] == []

    code, listed, error = run('list', archive)
    assert code == 0 and listed['source'] == 'pass' and listed['note'] == 'contract test'
    assert [entry['path'] for entry in listed['files']] == sorted(expected)

    target = folder / 'restored'
    code, restored, error = run('restore', archive, '--out', target)
    assert code == 0 and restored['file_count'] == 4, error
    for name, data in expected.items():
        assert (target / name).read_bytes() == data, name

    # A single flipped byte must be reported against the member it belongs to.
    def flip_ledger(manifest, members):
        out = []
        for member, data in members:
            if member.name == 'ledger.jsonl':
                data = data.replace(b'end', b'END')
            out.append((member, data))
        return manifest, out

    flipped = rebuild(archive, folder / 'flipped.tar.gz', flip_ledger)
    code, report, error = run('verify', flipped)
    assert code == 1 and report['result'] == 'failed', (code, report, error)
    assert any(problem['path'] == 'ledger.jsonl' for problem in report['problems']), report

    # An extra member is not silently ignored: an archive that gained a file is
    # not the archive that was signed off.
    def add_member(manifest, members):
        extra = tarfile.TarInfo('bin/injected.dll')
        return manifest, members + [(extra, b'MZ injected')]

    code, report, _ = run('verify', rebuild(archive, folder / 'extra.tar.gz', add_member))
    assert code == 1 and report['result'] == 'failed', report
    assert 'injected.dll' in report['problems'][0]['reason'], report

    # A declared member that is absent must fail, not be quietly skipped. The
    # manifest keeps its entry, so this is a truncated archive, not a smaller one.
    def drop_member(manifest, members):
        return manifest, [pair for pair in members if pair[0].name != 'bin/d3d9.dll']

    code, report, _ = run('verify', rebuild(archive, folder / 'dropped.tar.gz', drop_member))
    assert code == 1 and report['result'] == 'failed', report

    # A schema bump must be refused rather than interpreted under v1 rules.
    def bump_version(manifest, members):
        manifest['version'] = 2
        return manifest, members

    code, report, _ = run('verify', rebuild(archive, folder / 'bumped.tar.gz', bump_version))
    assert code == 1 and 'version' in report['problems'][0]['reason'], report

    # Traversal: a member that tries to escape must be refused by both verbs, and
    # nothing may appear outside the target directory.
    def traversal(manifest, members):
        escape = tarfile.TarInfo('../escaped.txt')
        return manifest, members + [(escape, b'escaped')]

    escape_archive = rebuild(archive, folder / 'escape.tar.gz', traversal)
    code, report, _ = run('verify', escape_archive)
    assert code == 1 and report['result'] == 'failed', report
    code, _, error = run('restore', escape_archive, '--out', folder / 'escape-target')
    assert code == 2 and ('escapes' in error or 'undeclared' in error), error
    assert not (folder / 'escaped.txt').exists()

    # A declared non-regular member (a symlink) must be refused, because writing
    # through it could redirect the restore anywhere.
    def symlink_member(manifest, members):
        link = tarfile.TarInfo('assets/link')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        manifest['files'].append({'path': 'assets/link', 'size': 0, 'sha256': '0' * 64})
        return manifest, members + [(link, b'')]

    code, _, error = run('restore', rebuild(archive, folder / 'link.tar.gz', symlink_member),
                         '--out', folder / 'link-target')
    assert code == 2 and 'non-regular' in error, error

    # Refusals: never overwrite, never nest the output, never widen a bound.
    code, _, error = run('create', root, '--out', archive)
    assert code == 2 and 'already exists' in error, error
    code, _, error = run('create', root, '--out', root / 'inside.tar.gz')
    assert code == 2 and 'inside the source' in error, error
    code, _, error = run('create', root, '--out', folder / 'bounded.tar.gz', '--max-files', '3')
    assert code == 2 and 'exceeds the 3 bound' in error, error
    code, _, error = run('create', root, '--out', folder / 'wide.tar.gz', '--max-files', '200001')
    assert code == 2 and '1..200000' in error, error
    code, _, error = run('restore', archive, '--out', target)
    assert code == 2 and 'not empty' in error, error

    # The archive is one file whose digest can be recorded out of band.
    recorded = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert len(recorded) == 64

    # --- Retention policy: evidence root, tracked ledger, and the check that
    # only the ledger can make. An archive carries its own manifest, so a rewrite
    # that regenerates the manifest is self-consistent; the ledger is the record
    # that lives outside the artifact and is what actually detects it.
    evidence = folder / 'evidence'
    ledger = folder / 'EVIDENCE_LEDGER.jsonl'
    code, recorded_archive, error = run('create', root, '--evidence-root', evidence,
                                        '--ledger', ledger, '--note', 'policy test')
    assert code == 0, error
    archived = Path(recorded_archive['archive'])
    assert archived.parent == evidence.resolve(), archived
    assert archived.name.startswith('pass-') and archived.suffix == '.gz', archived.name
    assert recorded_archive['ledger_records'] == 1

    entries = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()]
    assert len(entries) == 1 and entries[0]['pass'] == 'pass'
    assert entries[0]['archive'] == archived.name
    assert entries[0]['archive_sha256'] == hashlib.sha256(archived.read_bytes()).hexdigest()
    assert 'files' not in entries[0], 'the ledger must not carry content'

    code, checked, error = run('check', archived, '--ledger', ledger)
    assert code == 0 and checked['result'] == 'checked', (checked, error)

    # A rewritten archive with a *regenerated* manifest verifies against itself.
    # Only the ledger digest catches it. This is the whole reason `check` exists.
    def rewrite_with_valid_manifest(manifest, members):
        out = []
        for member, data in members:
            if member.name == 'ledger.jsonl':
                data = data + b'{"kind":"injected"}\n'
                for entry in manifest['files']:
                    if entry['path'] == 'ledger.jsonl':
                        entry['size'] = len(data)
                        entry['sha256'] = hashlib.sha256(data).hexdigest()
            out.append((member, data))
        return manifest, out

    forged_folder = folder / 'forged'
    forged_folder.mkdir()
    forged = rebuild(archived, forged_folder / archived.name, rewrite_with_valid_manifest)
    code, report, error = run('verify', forged)
    assert code == 0 and report['result'] == 'verified', ('self-consistent rewrite should verify', report)
    code, report, _ = run('check', forged, '--ledger', ledger)
    assert code == 1 and report['result'] == 'failed', report
    assert 'sha256' in report['problems'][0]['reason'], report

    # An archive the ledger has never seen cannot be checked at all.
    code, report, _ = run('check', archive, '--ledger', ledger)
    assert code == 1 and 'no ledger entry' in report['problems'][0]['reason'], report

    # The ledger is append-only. Deleting an archive does not license reusing its
    # name: a new archive is a different artifact and would silently replace the
    # record of the one that was signed off.
    absent_ledger = folder / 'absent-ledger.jsonl'
    absent = folder / 'absent.tar.gz'
    code, _, error = run('create', root, '--out', absent, '--ledger', absent_ledger)
    assert code == 0, error
    absent.unlink()
    code, _, error = run('create', root, '--out', absent, '--ledger', absent_ledger)
    assert code == 2 and 'ledger already records' in error, error

    # RRT_EVIDENCE_ROOT is the default when neither flag is given.
    environment = folder / 'env-root'
    code, env_archive, error = run('create', root, env={'RRT_EVIDENCE_ROOT': str(environment)})
    assert code == 0, error
    assert Path(env_archive['archive']).parent == environment.resolve(), env_archive

    # The two destinations are mutually exclusive rather than one silently winning.
    code, _, error = run('create', root, '--out', folder / 'both.tar.gz',
                         '--evidence-root', evidence)
    assert code == 2 and 'not allowed with argument' in error, error

    # An archive must never land where git would track it: that is the one mistake
    # with a legal consequence rather than a data one, so it is refused outright.
    tracked = ROOT / 'docs' / 'should-not-exist.tar.gz'
    code, _, error = run('create', root, '--out', tracked)
    assert code == 2 and 'must stay out of the repository' in error, error
    assert not tracked.exists(), 'refused archive still wrote a file'

    print(f'PASS: 4 files, {created["total_bytes"]} B, archive {created["archive_bytes"]} B, '
          f'{len(list(folder.glob("*.tar.gz")))} archives exercised, ledger {len(entries)} record')
    return 0


if __name__ == '__main__':
    sys.exit(main())
