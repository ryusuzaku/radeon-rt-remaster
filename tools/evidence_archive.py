"""Archive a local evidence bundle as one self-verifying file.

`build/game-passes/` is gitignored, and on 2026-10-15 a workspace move deleted 583
files of game evidence along with the shader inventory. Nothing was wrong with the
individual files: they were simply loose inside a directory that cleanup removes.
This tool makes "keep this pass" a single artifact with a manifest, so losing the
working tree does not lose the evidence, and so an archive can be proved intact
before it is trusted.

It decides nothing about *where* an archive lives. That is Q6 in the codebase map
and it is a policy question, not a tool question. Local archives contain captured
game content and must never be committed.

Usage:
    python tools/evidence_archive.py create PASS_DIR [--out FILE | --evidence-root DIR]
                                                    [--ledger docs/EVIDENCE_LEDGER.jsonl] [--note TEXT]
    python tools/evidence_archive.py verify  PASS.tar.gz
    python tools/evidence_archive.py check   PASS.tar.gz --ledger docs/EVIDENCE_LEDGER.jsonl
    python tools/evidence_archive.py list    PASS.tar.gz
    python tools/evidence_archive.py restore PASS.tar.gz --out DIR

Retention policy (closes Q6 in the codebase map):

  * Archives live outside the working tree, one file per pass. The default root is
    `<repo parent>/radeon-rt-remaster-evidence`, overridable with
    `--evidence-root` or `RRT_EVIDENCE_ROOT`.
  * `docs/EVIDENCE_LEDGER.jsonl` is the only tracked artifact. It records the pass
    name, size, file count and archive digest, never content, so it can live in
    git without redistributing anything captured from a game.
  * `verify` proves an archive is self-consistent. `check` additionally proves the
    archive is the one the ledger recorded, which is the only check a corrupted
    archive cannot pass by rewriting its own manifest.
  * Re-capture remains the fallback for content. The ledger exists so that losing
    an archive is a visible mismatch in git rather than a silent absence.

Exit codes: 0 success, 1 verification failure, 2 usage or refusal.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

SCHEMA = 'rrt-evidence-archive'
VERSION = 1
MANIFEST = 'rrt-evidence-manifest.json'
LEDGER_KIND = 'archive'
DEFAULT_ROOT_NAME = 'radeon-rt-remaster-evidence'
# Bounds keep one archive openable in memory-constrained tooling and stop a
# misdirected invocation from archiving a whole drive. Lowering them is allowed;
# raising them is not, so a bound cannot be argued away on the command line.
MAX_FILES = 200_000
MAX_FILE_BYTES = 2 << 30
MAX_TOTAL_BYTES = 8 << 30


class Refused(ValueError):
    """A refusal, not a crash: the caller asked for something unsafe or invalid."""


def need(value, message):
    if not value:
        raise Refused(message)


def digest_stream(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def digest_file(path):
    with Path(path).open('rb') as stream:
        return digest_stream(stream)


def relative_name(path, root):
    """POSIX relative name, refusing anything that could escape an extract root."""
    rel = PurePosixPath(path.relative_to(root).as_posix())
    need(rel.parts and '..' not in rel.parts and not rel.is_absolute(),
         f'unsafe relative path: {rel}')
    return rel


def scan(root, max_files):
    """Every regular file under root, sorted, with symlinks and specials refused."""
    need(root.is_dir(), f'not a directory: {root}')
    entries = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        for name in directories + files:
            full = Path(current) / name
            info = full.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise Refused(f'symlink not archived: {full}')
            if stat.S_ISREG(info.st_mode):
                entries.append((relative_name(full, root), full, info.st_size))
            elif not stat.S_ISDIR(info.st_mode):
                raise Refused(f'not a regular file: {full}')
    entries.sort(key=lambda item: item[0].as_posix())
    need(entries, f'nothing to archive under {root}')
    need(len(entries) <= max_files, f'{len(entries)} files exceeds the {max_files} bound')
    for name, path, size in entries:
        need(size <= MAX_FILE_BYTES, f'{name} exceeds the per-file bound')
    return entries


def default_root():
    """Evidence root outside the working tree, so a build wipe cannot reach it."""
    return Path(__file__).resolve().parents[1].parent / DEFAULT_ROOT_NAME


def evidence_root(argument=None):
    if argument:
        return Path(argument).resolve()
    configured = os.environ.get('RRT_EVIDENCE_ROOT')
    return Path(configured).resolve() if configured else default_root().resolve()


def read_ledger(path):
    """Archive records from the ledger; `policy` lines document it and are skipped."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise Refused(f'ledger line {number} is not JSON: {error}')
        kind = record.get('kind')
        need(kind in (LEDGER_KIND, 'policy'), f'ledger line {number} has an unknown kind')
        if kind == LEDGER_KIND:
            records.append(record)
    return records


def append_ledger(path, record):
    """Record an archive in the tracked ledger, refusing to rewrite history."""
    path = Path(path)
    existing = read_ledger(path)
    for entry in existing:
        if entry.get('archive') == record['archive']:
            raise Refused(f'ledger already records {record["archive"]}; '
                          'archives are append-only')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(record, sort_keys=True) + '\n')
    return len(existing) + 1


def destination_for(source, out=None, root=None):
    """Resolve the archive path from an explicit file, an explicit root, or the policy."""
    if out is not None:
        return Path(out)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    return evidence_root(root) / f'{Path(source).resolve().name}-{stamp}.tar.gz'


def nearest_existing(path):
    current = Path(path)
    while not current.exists():
        if current.parent == current:
            return current
        current = current.parent
    return current


def guard_tracked(path):
    """Refuse a destination git would track: captured content must not ship.

    This is the one mistake with a legal consequence rather than a data one, so it
    is a gate rather than a warning. Without a usable git it degrades to the
    convention documented above instead of blocking the archive.
    """
    anchor = nearest_existing(Path(path).parent)
    try:
        top = subprocess.run(['git', '-C', str(anchor), 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True)
        if top.returncode != 0:
            return
        ignored = subprocess.run(['git', '-C', str(anchor), 'check-ignore', '--quiet', str(path)],
                                 capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return
    need(ignored.returncode == 0,
         f'{path} is inside {top.stdout.strip()} and is not gitignored; '
         'archives contain captured content and must stay out of the repository')


def create(source, out, note, max_files, ledger=None):
    source = Path(source).resolve()
    out = Path(out).resolve()
    need(not out.exists(), f'output already exists: {out}')
    need(not out.is_relative_to(source), 'output must not be inside the source tree')
    guard_tracked(out)
    if ledger is not None:
        # Checked before any work: a duplicate must not cost a full archive pass.
        names = {entry.get('archive') for entry in read_ledger(ledger)}
        need(out.name not in names, f'ledger already records {out.name}')
    entries = scan(source, max_files)
    total = sum(size for _, _, size in entries)
    need(total <= MAX_TOTAL_BYTES, f'{total} bytes exceeds the archive bound')
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    # Hash before writing, so an unreadable or changing file fails before an
    # archive exists rather than producing a half-trustworthy artifact.
    manifest = {
        'schema': SCHEMA, 'version': VERSION, 'created': created,
        'source': source.name, 'note': note, 'file_count': len(entries), 'total_bytes': total,
        'files': [{'path': name.as_posix(), 'size': size, 'sha256': digest_file(path)}
                  for name, path, size in entries],
    }
    payload = json.dumps(manifest, indent=1, sort_keys=True).encode('utf-8')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(payload)
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))
        # Second pass: copy and re-hash. A file edited between passes is caught
        # here instead of being archived with a digest that no longer matches.
        for entry, (name, path, size) in zip(manifest['files'], entries):
            actual = digest_file(path)
            need(actual == entry['sha256'], f'source changed during archive: {name}')
            info = tarfile.TarInfo(name.as_posix())
            info.size = size
            info.mtime = 0
            info.mode = 0o644
            with path.open('rb') as stream:
                archive.addfile(info, stream)
    archive_digest = digest_file(out)
    result = {'result': 'created', 'archive': str(out), 'file_count': len(entries),
              'total_bytes': total, 'archive_bytes': out.stat().st_size,
              'archive_sha256': archive_digest}
    if ledger is not None:
        record = {'kind': LEDGER_KIND, 'recorded': created, 'pass': source.name, 'note': note,
                  'file_count': len(entries), 'total_bytes': total,
                  'archive': out.name, 'archive_bytes': result['archive_bytes'],
                  'archive_sha256': archive_digest}
        result['ledger_records'] = append_ledger(ledger, record)
        result['ledger'] = str(Path(ledger).resolve())
    return result


def check(archive, ledger):
    """Verify content *and* that this is the archive the ledger recorded.

    `verify` alone cannot detect a rewritten archive: the manifest travels inside
    it, so a tampered member with a regenerated manifest is self-consistent. The
    ledger lives in git, outside the artifact, which is what closes that gap.
    """
    archive = Path(archive).resolve()
    records = [entry for entry in read_ledger(ledger) if entry.get('archive') == archive.name]
    if not records:
        return {'result': 'failed', 'file_count': 0, 'total_bytes': 0,
                'problems': [{'path': '', 'reason': f'no ledger entry for {archive.name}'}]}
    if len(records) > 1:
        return {'result': 'failed', 'file_count': 0, 'total_bytes': 0,
                'problems': [{'path': '', 'reason': f'{len(records)} ledger entries for {archive.name}'}]}
    record = records[0]
    actual = digest_file(archive)
    problems = []
    if actual != record.get('archive_sha256'):
        problems.append({'path': '', 'reason': f'archive sha256 {actual} != ledger {record.get("archive_sha256")}'})
    if archive.stat().st_size != record.get('archive_bytes'):
        problems.append({'path': '', 'reason': f'archive size {archive.stat().st_size} != ledger {record.get("archive_bytes")}'})
    if problems:
        return {'result': 'failed', 'file_count': 0, 'total_bytes': 0, 'problems': problems}
    verified = verify(archive)
    if verified['result'] != 'verified':
        return verified
    if verified['file_count'] != record.get('file_count'):
        return {'result': 'failed', 'file_count': verified['file_count'],
                'total_bytes': verified['total_bytes'],
                'problems': [{'path': '', 'reason': f'{verified["file_count"]} files != ledger {record.get("file_count")}'}]}
    verified['result'] = 'checked'
    verified['ledger'] = str(Path(ledger).resolve())
    return verified


def read_manifest(archive):
    with tarfile.open(archive, 'r:gz') as tar:
        try:
            member = tar.getmember(MANIFEST)
        except KeyError:
            raise Refused(f'archive has no {MANIFEST}')
        need(member.isfile(), f'{MANIFEST} is not a regular file')
        stream = tar.extractfile(member)
        need(stream is not None, f'{MANIFEST} is unreadable')
        try:
            manifest = json.loads(stream.read().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise Refused(f'{MANIFEST} is not valid JSON: {error}')
    need(manifest.get('schema') == SCHEMA, 'unknown archive schema')
    need(manifest.get('version') == VERSION, f'unsupported archive version {manifest.get("version")}')
    files = manifest.get('files')
    need(isinstance(files, list) and files, 'archive manifest declares no files')
    declared = {}
    for entry in files:
        need(isinstance(entry, dict), 'malformed manifest entry')
        name = entry.get('path')
        need(isinstance(name, str) and name, 'manifest entry has no path')
        rel = PurePosixPath(name)
        need(not rel.is_absolute() and '..' not in rel.parts, f'unsafe manifest path: {name}')
        need(name not in declared, f'duplicate manifest path: {name}')
        need(isinstance(entry.get('size'), int) and entry['size'] >= 0, f'bad size for {name}')
        need(isinstance(entry.get('sha256'), str) and len(entry['sha256']) == 64, f'bad digest for {name}')
        declared[name] = entry
    return manifest, declared


def walk_archive(archive, declared):
    """Yield (name, size, sha256) for each member, refusing anything undeclared."""
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if member.name == MANIFEST:
                continue
            need(member.isfile(), f'non-regular archive member: {member.name}')
            need(member.name in declared, f'undeclared archive member: {member.name}')
            need(member.name not in seen, f'duplicate archive member: {member.name}')
            stream = tar.extractfile(member)
            need(stream is not None, f'unreadable archive member: {member.name}')
            digest = digest_stream(stream)
            seen.add(member.name)
            yield member.name, member.size, digest
    missing = sorted(set(declared) - seen)
    need(not missing, f'missing archive members: {", ".join(missing[:4])}')


def verify(archive):
    """Content problems are a failed verification (exit 1), not a usage error."""
    try:
        manifest, declared = read_manifest(archive)
        problems = []
        count = 0
        for name, size, digest in walk_archive(archive, declared):
            count += 1
            entry = declared[name]
            if size != entry['size']:
                problems.append({'path': name, 'reason': f'size {size} != {entry["size"]}'})
            elif digest != entry['sha256']:
                problems.append({'path': name, 'reason': 'sha256 mismatch'})
    except Refused as error:
        return {'result': 'failed', 'file_count': 0, 'total_bytes': 0,
                'problems': [{'path': '', 'reason': str(error)}]}
    return {'result': 'verified' if not problems else 'failed', 'file_count': count,
            'total_bytes': manifest['total_bytes'], 'created': manifest['created'],
            'problems': problems}


def list_archive(archive):
    manifest, declared = read_manifest(archive)
    names = sorted(declared)
    return {'result': 'listed', 'created': manifest['created'], 'source': manifest['source'],
            'note': manifest.get('note', ''), 'file_count': len(names),
            'total_bytes': manifest['total_bytes'], 'truncated': len(names) > 50,
            'files': [{'path': name, 'size': declared[name]['size']} for name in names[:50]]}


def restore(archive, out):
    out = Path(out).resolve()
    manifest, declared = read_manifest(archive)
    need(not (out.exists() and any(out.iterdir())), f'restore target is not empty: {out}')
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if member.name == MANIFEST:
                continue
            need(member.isfile(), f'non-regular archive member: {member.name}')
            need(member.name in declared, f'undeclared archive member: {member.name}')
            entry = declared[member.name]
            target = (out / PurePosixPath(member.name)).resolve()
            need(target.is_relative_to(out), f'archive member escapes the target: {member.name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            need(not target.exists(), f'restore would overwrite: {member.name}')
            stream = tar.extractfile(member)
            need(stream is not None, f'unreadable archive member: {member.name}')
            with target.open('wb') as handle:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    handle.write(block)
            need(target.stat().st_size == entry['size'], f'restored size mismatch: {member.name}')
            need(digest_file(target) == entry['sha256'], f'restored digest mismatch: {member.name}')
            written += 1
    need(written == len(declared), f'restored {written} of {len(declared)} declared files')
    return {'result': 'restored', 'target': str(out), 'file_count': written,
            'total_bytes': manifest['total_bytes']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    create_parser = sub.add_parser('create', help='archive a pass directory')
    create_parser.add_argument('source', type=Path)
    destination = create_parser.add_mutually_exclusive_group(required=False)
    destination.add_argument('--out', type=Path, help='exact archive path')
    destination.add_argument('--evidence-root', type=Path,
                             help=f'archive root (default $RRT_EVIDENCE_ROOT or <repo parent>/{DEFAULT_ROOT_NAME})')
    create_parser.add_argument('--ledger', type=Path, help='append a record to this JSONL ledger')
    create_parser.add_argument('--note', default='')
    create_parser.add_argument('--max-files', type=int, default=MAX_FILES)
    for name in ('verify', 'list'):
        sub.add_parser(name).add_argument('archive', type=Path)
    check_parser = sub.add_parser('check', help='verify content and the ledger record')
    check_parser.add_argument('archive', type=Path)
    check_parser.add_argument('--ledger', type=Path, required=True)
    restore_parser = sub.add_parser('restore', help='extract into an empty directory')
    restore_parser.add_argument('archive', type=Path)
    restore_parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            need(1 <= args.max_files <= MAX_FILES, f'--max-files must be 1..{MAX_FILES}')
            source = Path(args.source).resolve()
            destination_path = destination_for(source, args.out, args.evidence_root)
            result = create(source, destination_path, args.note, args.max_files, args.ledger)
        elif args.command == 'verify':
            result = verify(args.archive)
        elif args.command == 'check':
            result = check(args.archive, args.ledger)
        elif args.command == 'list':
            result = list_archive(args.archive)
        else:
            result = restore(args.archive, args.out)
    except Refused as error:
        print(f'refused: {error}', file=sys.stderr)
        return 2
    except (OSError, tarfile.TarError) as error:
        print(f'failed: {error}', file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0 if result['result'] in ('created', 'verified', 'checked', 'listed', 'restored') else 1


if __name__ == '__main__':
    sys.exit(main())
