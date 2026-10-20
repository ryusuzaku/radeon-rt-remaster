"""Verify an extracted subtree against the manifest that shipped with its archive.

Preservation images (the 2026-10-15 WIM, for example) come with a JSONL manifest
of `path`, `bytes` and `sha256` per file. Extracting a subtree is easy; knowing
whether the extraction is faithful is the part that matters, and it is not
something to eyeball. This compares every declared file and refuses to call an
extraction good if anything is missing, resized, changed or extra.

    python tools/verify_restored_tree.py MANIFEST.jsonl RESTORED_DIR
    python tools/verify_restored_tree.py MANIFEST.jsonl RESTORED_DIR --prefix "build\\game-passes\\"

Exit codes: 0 all declared files verified and nothing extra, 1 mismatch, 2 refusal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

# One manifest is a working tree, not a disk image; a bound keeps a wrong path
# from turning into an unbounded walk.
MAX_ENTRIES = 500_000


class Refused(ValueError):
    pass


def need(value, message):
    if not value:
        raise Refused(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('manifest', type=Path)
    parser.add_argument('restored', type=Path)
    parser.add_argument('--prefix', default='', help='only entries whose path starts with this')
    args = parser.parse_args(argv)
    try:
        need(args.manifest.is_file(), f'no manifest at {args.manifest}')
        need(args.restored.is_dir(), f'no restored tree at {args.restored}')
        declared = {}
        with args.manifest.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                need(number <= MAX_ENTRIES, f'manifest exceeds {MAX_ENTRIES} entries')
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as error:
                    raise Refused(f'manifest line {number} is not JSON: {error}')
                path = entry.get('path')
                need(isinstance(path, str) and path, f'manifest line {number} has no path')
                if not path.startswith(args.prefix):
                    continue
                need(isinstance(entry.get('bytes'), int) and isinstance(entry.get('sha256'), str),
                     f'manifest line {number} is missing bytes/sha256')
                need(path not in declared, f'duplicate manifest path: {path}')
                declared[path] = entry
        need(declared, 'manifest declares no files under that prefix')

        problems = []
        for name, entry in declared.items():
            target = args.restored / Path(name.replace('\\', '/'))
            if not target.is_file():
                problems.append(f'missing: {name}')
            elif target.stat().st_size != entry['bytes']:
                problems.append(f'size {target.stat().st_size} != {entry["bytes"]}: {name}')
            elif digest(target) != entry['sha256']:
                problems.append(f'sha256 mismatch: {name}')

        root = args.restored / Path(args.prefix.replace('\\', '/')) if args.prefix else args.restored
        present = {str(path.relative_to(args.restored)).replace('/', '\\')
                   for path in root.rglob('*') if path.is_file()} if root.exists() else set()
        for name in sorted(present - set(declared)):
            problems.append(f'extra: {name}')
    except Refused as error:
        print(f'refused: {error}', file=sys.stderr)
        return 2
    except OSError as error:
        print(f'failed: {error}', file=sys.stderr)
        return 2
    result = {'declared': len(declared), 'verified': len(declared) - len(problems),
              'problems': problems[:20], 'problem_count': len(problems)}
    print(json.dumps(result))
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
