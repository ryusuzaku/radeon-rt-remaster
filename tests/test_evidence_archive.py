"""Pure-function unit tests for the evidence-ledger and manifest parsers.

The full CLI contract is exercised separately by verify_evidence_archive.py.
This file covers the two pure helper groups in tools/evidence_archive.py that
decide what counts as a valid ledger and what counts as a valid archive:

  * read_ledger / append_ledger: the tracked EVIDENCE_LEDGER.jsonl parser.
    Blank and `policy` lines are part of the format, everything else must be
    an `archive` record, and the ledger is append-only.
  * read_manifest / walk_archive: the self-describing member list an archive
    carries. Every malformation must be refused and named, because a parser
    that silently drops an entry is the same defect as a flipped byte.

The tests build their own archives and ledger lines in a temp directory, so
they are deterministic and need no GPU, game, or network.
"""
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from evidence_archive import MANIFEST, Refused, append_ledger, read_ledger, read_manifest, verify, walk_archive

SCHEMA = 'rrt-evidence-archive'
VERSION = 1


def fixture_files():
    return {
        'bin/d3d9.dll': b'MZ' + bytes(range(256)) * 2,
        'ledger.jsonl': b'{"kind":"header"}\n{"kind":"end"}\n',
    }


def manifest_for(files):
    return {'schema': SCHEMA, 'version': VERSION, 'created': '2026-01-01T00:00:00+00:00',
            'source': 'unit', 'note': '', 'file_count': len(files),
            'total_bytes': sum(len(data) for data in files.values()),
            'files': [{'path': name, 'size': len(data),
                       'sha256': hashlib.sha256(data).hexdigest()}
                      for name, data in files.items()]}


def build_archive(path, files, manifest=None, extra=()):
    """Write a gz tar in the tool's layout: manifest member first, then members."""
    if manifest is None:
        manifest = manifest_for(files)
    with tarfile.open(path, 'w:gz', format=tarfile.PAX_FORMAT) as tar:
        payload = json.dumps(manifest, indent=1, sort_keys=True).encode('utf-8')
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra:
            if data is None:
                tar.addfile(info)
            else:
                tar.addfile(info, io.BytesIO(data))


def write_ledger(path, lines):
    path.write_text(''.join(line + '\n' for line in lines), encoding='utf-8')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_missing_ledger_is_empty(self):
        self.assertEqual(read_ledger(self.folder/'absent.jsonl'), [])

    def test_skips_blank_and_policy_lines(self):
        ledger = self.folder/'ledger.jsonl'
        record = {'kind': 'archive', 'pass': 'pass', 'archive': 'pass-1.tar.gz'}
        write_ledger(ledger, ['   ',
                              json.dumps({'kind': 'policy', 'note': 'archives are append-only'}),
                              json.dumps(record)])
        self.assertEqual(read_ledger(ledger), [record])

    def test_bad_json_is_named_by_line(self):
        ledger = self.folder/'ledger.jsonl'
        write_ledger(ledger, [json.dumps({'kind': 'archive', 'archive': 'a.tar.gz'}),
                              '{broken}'])
        with self.assertRaises(Refused) as caught:
            read_ledger(ledger)
        self.assertIn('ledger line 2', str(caught.exception))
        self.assertIn('not JSON', str(caught.exception))

    def test_unknown_kind_is_named_by_line(self):
        ledger = self.folder/'ledger.jsonl'
        write_ledger(ledger, [json.dumps({'kind': 'archive', 'archive': 'a.tar.gz'}),
                              json.dumps({'kind': 'other'})])
        with self.assertRaises(Refused) as caught:
            read_ledger(ledger)
        self.assertIn('ledger line 2', str(caught.exception))
        self.assertIn('unknown kind', str(caught.exception))

    def test_append_creates_and_counts(self):
        ledger = self.folder/'nested/ledger.jsonl'
        record = {'kind': 'archive', 'pass': 'pass', 'archive': 'pass-1.tar.gz'}
        self.assertEqual(append_ledger(ledger, record), 1)
        lines = ledger.read_text(encoding='utf-8').splitlines()
        self.assertEqual([json.loads(line) for line in lines], [record])

    def test_append_is_append_only(self):
        ledger = self.folder/'ledger.jsonl'
        append_ledger(ledger, {'kind': 'archive', 'archive': 'pass-1.tar.gz'})
        self.assertEqual(append_ledger(ledger, {'kind': 'archive', 'archive': 'pass-2.tar.gz'}), 2)
        with self.assertRaises(Refused) as caught:
            append_ledger(ledger, {'kind': 'archive', 'archive': 'pass-1.tar.gz'})
        self.assertIn('pass-1.tar.gz', str(caught.exception))

    def test_append_after_policy_line(self):
        ledger = self.folder/'ledger.jsonl'
        write_ledger(ledger, [json.dumps({'kind': 'policy', 'note': 'retention policy'})])
        self.assertEqual(append_ledger(ledger, {'kind': 'archive', 'archive': 'pass-1.tar.gz'}), 1)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def build(self, name, mutate=None, extra=()):
        files = fixture_files()
        manifest = manifest_for(files)
        if mutate is not None:
            mutate(manifest)
        archive = self.folder/name
        build_archive(archive, files, manifest=manifest, extra=extra)
        return archive

    def test_round_trip(self):
        files = fixture_files()
        archive = self.folder/'pass.tar.gz'
        build_archive(archive, files)
        manifest, declared = read_manifest(archive)
        self.assertEqual(manifest['schema'], SCHEMA)
        self.assertEqual(sorted(declared), sorted(files))
        for name, data in files.items():
            entry = declared[name]
            self.assertEqual(entry['size'], len(data))
            self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
        walked = sorted(walk_archive(archive, declared), key=lambda item: item[0])
        expected = sorted((name, len(data), hashlib.sha256(data).hexdigest())
                          for name, data in files.items())
        self.assertEqual(walked, expected)

    def test_missing_manifest_member(self):
        archive = self.folder/'nomanifest.tar.gz'
        with tarfile.open(archive, 'w:gz', format=tarfile.PAX_FORMAT) as tar:
            info = tarfile.TarInfo('ledger.jsonl')
            info.size = 1
            tar.addfile(info, io.BytesIO(b'x'))
        with self.assertRaises(Refused) as caught:
            read_manifest(archive)
        self.assertIn(MANIFEST, str(caught.exception))

    def test_wrong_schema_and_version(self):
        archive = self.build('schema.tar.gz', lambda m: m.update(schema='other', version=2))
        with self.assertRaises(Refused) as caught:
            read_manifest(archive)
        self.assertIn('unknown archive schema', str(caught.exception))
        archive = self.build('version.tar.gz', lambda m: m.update(version=2))
        with self.assertRaises(Refused) as caught:
            read_manifest(archive)
        self.assertIn('unsupported archive version 2', str(caught.exception))

    def test_declares_no_files(self):
        for bad in ([], None, 'nope'):
            with self.subTest(bad=bad):
                archive = self.build('nofiles.tar.gz', lambda m, bad=bad: m.update(files=bad))
                with self.assertRaises(Refused) as caught:
                    read_manifest(archive)
                self.assertIn('declares no files', str(caught.exception))

    def test_malformed_entries(self):
        cases = [
            (lambda files: files.__setitem__(0, 'nope'), 'malformed manifest entry'),
            (lambda files: files[0].pop('path'), 'manifest entry has no path'),
            (lambda files: files[0].update(path='../escape'), 'unsafe manifest path'),
            (lambda files: files[0].update(path='/etc/passwd'), 'unsafe manifest path'),
            (lambda files: files.append(dict(files[0])), 'duplicate manifest path'),
            (lambda files: files[0].update(size=-1), 'bad size'),
            (lambda files: files[0].update(size=1.5), 'bad size'),
            (lambda files: files[0].update(sha256='abc'), 'bad digest'),
            (lambda files: files[0].update(sha256=None), 'bad digest'),
        ]
        for mutate, needle in cases:
            with self.subTest(needle=needle):
                archive = self.folder/'entry.tar.gz'
                manifest = manifest_for(fixture_files())
                mutate(manifest['files'])
                build_archive(archive, fixture_files(), manifest=manifest)
                with self.assertRaises(Refused) as caught:
                    read_manifest(archive)
                self.assertIn(needle, str(caught.exception))

    def consume_walk(self, archive):
        _, declared = read_manifest(archive)
        with self.assertRaises(Refused) as caught:
            list(walk_archive(archive, declared))
        return str(caught.exception)

    def test_undeclared_member(self):
        archive = self.folder/'undeclared.tar.gz'
        build_archive(archive, fixture_files(),
                      extra=[(tarfile.TarInfo('injected.txt'), b'MZ injected')])
        error = self.consume_walk(archive)
        self.assertIn('undeclared archive member: injected.txt', error)

    def test_duplicate_member(self):
        archive = self.folder/'duplicate.tar.gz'
        build_archive(archive, fixture_files(),
                      extra=[(tarfile.TarInfo('ledger.jsonl'), b'forged')])
        error = self.consume_walk(archive)
        self.assertIn('duplicate archive member: ledger.jsonl', error)

    def test_non_regular_member(self):
        manifest = manifest_for(fixture_files())
        manifest['files'].append({'path': 'bin', 'size': 0, 'sha256': '0' * 64})
        directory = tarfile.TarInfo('bin')
        directory.type = tarfile.DIRTYPE
        archive = self.folder/'directory.tar.gz'
        build_archive(archive, fixture_files(), manifest=manifest,
                      extra=[(directory, None)])
        error = self.consume_walk(archive)
        self.assertIn('non-regular archive member: bin', error)

    def test_missing_member(self):
        manifest = manifest_for(fixture_files())
        archive = self.folder/'missing.tar.gz'
        build_archive(archive, {'bin/d3d9.dll': fixture_files()['bin/d3d9.dll']},
                      manifest=manifest)
        error = self.consume_walk(archive)
        self.assertIn('missing archive members: ledger.jsonl', error)


class TruncationTests(unittest.TestCase):
    def test_truncated_archive_is_a_failed_verification_not_a_crash(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            # Incompressible payload so cutting the file really cuts the stream.
            files = {'blob.bin': bytes((index * 167 + (index >> 8) * 31) % 251 for index in range(300000))}
            archive = folder/'whole.tar.gz'
            build_archive(archive, files)
            self.assertEqual(verify(archive)['result'], 'verified')
            cut = folder/'cut.tar.gz'
            cut.write_bytes(archive.read_bytes()[:len(archive.read_bytes())//2])
            report = verify(cut)
            self.assertEqual(report['result'], 'failed')
            self.assertTrue(report['problems'])


if __name__ == '__main__':
    unittest.main()
