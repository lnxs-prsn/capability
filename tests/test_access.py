"""Invented publications only; every running project is temporary."""
import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from access.cli import main, pack_capability
from access.engine import Catalogue, Store, offer
from access.publication import (Project, below, capture, content_id, dumps, envelope, install, loads,
                                ordinary_path, parse_manifest, read_bytes, read_index, sha, verified_file, write_index)
from test_standard import sample, markdown

ROOT = Path(__file__).absolute().parents[1]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='knowhow-tests-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.supplier = self.new_project('supplier')
        self.curator = self.new_project('curator')
        self.taker = self.new_project('new taker')
        self.bundle = self.write(self.supplier)
        self.listing = self.base / 'parts.json'
        self.list_parts(self.supplier, self.taker)

    def new_project(self, name):
        root = self.base / name
        root.mkdir()
        return Project(root, initialize=True)

    def write(self, project, name='sample-pattern', suffix=''):
        path = project.root / 'innovations' / name
        (path / 'kit').mkdir(parents=True, exist_ok=True)
        record = sample()
        record['id'] = name
        (path / 'PATTERN.md').write_text(markdown(record) + suffix, encoding='utf-8')
        (path / 'kit/steps.txt').write_text('Fill <setup> before continuing.', encoding='utf-8')
        return path

    def list_parts(self, *projects):
        self.listing.write_text(dumps({'format': 1, 'published_parts': [
            os.path.relpath(p.root / 'published', self.listing.parent) for p in projects]}), encoding='utf-8')

    def cli(self, name, *args, project=None, expected=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([name, '--project', str((project or self.curator).root), '--json', *map(str, args)])
        self.assertEqual(code, expected, err.getvalue() or out.getvalue())
        return json.loads(out.getvalue()) if out.getvalue() else json.loads(err.getvalue())

    def intake(self):
        return self.cli('ingest', '--published-parts', self.listing)

    def decide(self, op, cid, *args):
        return self.cli(op, cid, '--actor', 'Synthetic authority', '--reason', 'Invented test only', *args)

    def ready(self, edition='one'):
        publication = self.cli('offer', self.bundle, project=self.supplier)
        self.intake()
        self.decide('admit', publication['id'])
        self.cli('publish-catalogue', '--edition', edition)
        return publication['id']

    def ask(self, project=None):
        return self.cli('ask', '--catalogue', self.curator.index, '--task', 'setup', project=project or self.taker)

    def select(self, cid, expected=0, project=None):
        return self.cli('select', cid, '--catalogue', self.curator.index, project=project or self.taker, expected=expected)

    @staticmethod
    def snapshot(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_missing_list_does_nothing_and_empty_works(self):
        before = self.snapshot(self.base)
        result = self.cli('ingest', expected=2)
        self.assertIn('Missing list', result['error'])
        self.assertEqual(before, self.snapshot(self.base))
        self.list_parts()
        self.assertEqual(self.intake()['counts']['offers'], 0)
        self.cli('publish-catalogue', '--edition', 'empty')
        self.assertEqual(self.ask()['offers'], [])

    def test_missing_catalogue_explains_next_step_without_fallback(self):
        cid = self.ready()
        self.ask()
        block = read_index(self.curator.index)
        del block['catalogue']
        write_index(self.curator.index, block)
        for command, args in [('ask', ['--task', 'setup']), ('select', [cid])]:
            result = self.cli(command, *args, '--catalogue', self.curator.index, expected=2)
            self.assertIn('names no catalogue', result['error'])
            self.assertIn('--catalogue', result['error'])
            self.assertIn('OWNER.md', result['error'])
        self.curator.index.write_text('# Published material\n', encoding='utf-8')
        for command, args in [('ask', ['--task', 'setup']), ('select', [cid])]:
            result = self.cli(command, *args, '--catalogue', self.curator.index, expected=2)
            self.assertIn('names no catalogue', result['error'])

    def test_direct_generic_copy_works_without_catalogue(self):
        code = self.temporary_source()
        before = self.snapshot(code)
        project = self.base / 'fresh project'
        project.mkdir()
        result = self.run_code(code, 'init', '--project', project)
        self.assertEqual(result.returncode, 0, result.stderr)
        project = Project(project)
        result = self.run_code(code, 'self-check', '--project', project.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = self.write(project)
        for command in ('check', 'offer'):
            result = self.run_code(code, command, bundle, '--project', project.root)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_code(code, 'ask', '--task', 'setup', '--catalogue', project.index,
                               '--project', project.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('names no catalogue', result.stderr)
        self.assertEqual(before, self.snapshot(code))

    def test_init_index_preservation_and_identity_restoration(self):
        root = self.base / 'fresh'
        (root / 'published').mkdir(parents=True)
        prose = '# Published\n\nEdition applied: example 1\n\nOther review material.\n'
        (root / 'published/INDEX.md').write_text(prose, encoding='utf-8')
        p = Project(root, initialize=True)
        self.assertTrue(p.index.read_text().startswith(prose.rstrip()))
        self.assertEqual(Project(root, initialize=True).id, p.id)
        (p.state / 'project.json').unlink()
        with self.assertRaisesRegex(ValueError, 'restore'):
            Project(root, initialize=True)

    def test_offer_complete_fixed_idempotent_and_standard_unchanged(self):
        before = self.snapshot(self.bundle)
        first = self.cli('offer', self.bundle, project=self.supplier)
        second = self.cli('offer', self.bundle, project=self.supplier)
        self.assertEqual(first, second)
        self.assertEqual(len(read_index(self.supplier.index)['offers']), 1)
        self.assertEqual(before, self.snapshot(self.bundle))
        (self.bundle / 'kit/steps.txt').write_text('Changed invented instructions.', encoding='utf-8')
        changed = self.cli('offer', self.bundle, project=self.supplier)
        self.assertNotEqual(changed['id'], first['id'])
        self.assertTrue(Path(first['offer']).is_dir())
        self.intake()
        self.decide('admit', first['id'])
        self.cli('publish-catalogue', '--edition', 'one')
        self.assertEqual([o['id'] for o in self.ask()['offers']], [first['id']])

    def test_invalid_offer_never_published(self):
        (self.bundle / 'PATTERN.md').write_text('# Incomplete setup\n', encoding='utf-8')
        before = self.snapshot(self.supplier.root / 'published')
        self.cli('offer', self.bundle, project=self.supplier, expected=2)
        self.assertEqual(before, self.snapshot(self.supplier.root / 'published'))

    def test_copies_context_origins_and_supplier_disappearance(self):
        duplicate = self.new_project('copy')
        self.write(duplicate)
        cid = self.cli('offer', self.bundle, project=self.supplier)['id']
        self.assertEqual(self.cli('offer', duplicate.root / 'innovations/sample-pattern', project=duplicate)['id'], cid)
        self.list_parts(self.supplier, duplicate, self.taker)
        first = self.intake()
        self.assertEqual(first['counts']['new_contents'], 1)
        self.assertEqual(first['counts']['offers'], 2)
        self.assertEqual(self.intake()['counts']['checks'], 0)
        inspection = self.cli('decisions', cid)
        self.assertEqual(len(inspection['origins']), 2)
        self.decide('admit', cid)
        shutil.rmtree(self.supplier.root)
        shutil.rmtree(duplicate.root)
        self.cli('ingest', '--published-parts', self.listing, expected=1)
        self.cli('publish-catalogue', '--edition', 'retained')
        selected = self.select(cid)['selected'][0]
        self.assertEqual(selected['check']['record'], sample())
        self.assertIn('Fictional explanation', selected['pattern'])
        self.assertTrue((Path(selected['bundle']) / 'kit/steps.txt').is_file())
        self.assertTrue(all(not o['current'] for o in selected['origins']))
        self.assertEqual(len(self.ask()['offers']), 1)

    def test_decline_reversal_exclusions_and_current_policy(self):
        cid = self.ready()
        self.cli('decline', cid, '--actor', 'Executive', '--reason', 'Synthetic mismatch', project=self.taker)
        self.assertEqual(self.ask()['offers'], [])
        self.select(cid, expected=2)
        other = self.new_project('independent')
        self.assertEqual(len(self.ask(other)['offers']), 1)
        self.cli('decline', cid, '--actor', 'Executive', '--reason', 'Reconsidered', '--undo', project=self.taker)
        self.assertEqual(len(self.ask()['offers']), 1)
        self.decide('exclude', cid, '--project-id', self.taker.id)
        # Unpublished decisions do not pretend to have reached takers.
        self.assertEqual(len(self.ask()['offers']), 1)
        self.cli('publish-catalogue', '--edition', 'two')
        self.assertEqual(self.ask()['offers'], [])
        self.select(cid, expected=2)
        self.assertEqual(len(self.ask(other)['offers']), 1)
        self.decide('exclude', cid, '--all')
        self.cli('publish-catalogue', '--edition', 'three')
        self.assertEqual(self.ask(other)['offers'], [])
        self.decide('exclude', cid, '--all', '--undo')
        self.cli('publish-catalogue', '--edition', 'four')
        self.assertEqual(self.ask()['offers'], [])
        self.decide('exclude', cid, '--project-id', self.taker.id, '--undo')
        self.cli('publish-catalogue', '--edition', 'five')
        self.select(cid)

    def test_exclusion_uuid_must_be_published_and_known(self):
        cid = self.ready()
        unknown = self.new_project('unknown')
        self.cli('exclude', cid, '--project-id', unknown.id, '--actor', 'CEO', '--reason', 'Test', expected=2)
        self.list_parts(unknown)
        self.intake()
        self.decide('exclude', cid, '--project-id', unknown.id)

    def test_merge_propagates_restrictions_and_retains_reasons(self):
        first = self.ready()
        second_path = self.write(self.supplier, 'second-pattern')
        second = self.cli('offer', second_path, project=self.supplier)['id']
        third_path = self.write(self.supplier, 'third-pattern')
        third = self.cli('offer', third_path, project=self.supplier)['id']
        self.intake()
        self.decide('admit', second)
        self.decide('admit', third)
        self.decide('merge', first, '--into', second)
        self.cli('merge', second, '--into', third, '--actor', 'Executive', '--reason', 'Would chain', expected=2)
        self.cli('publish-catalogue', '--edition', 'merged')
        self.assertEqual(len(self.ask()['offers']), 2)
        self.cli('decline', first, '--actor', 'Executive', '--reason', 'Bad source', project=self.taker)
        self.select(second, expected=2)
        self.decide('exclude', first, '--all')
        self.cli('publish-catalogue', '--edition', 'excluded-source')
        self.assertEqual([o['id'] for o in self.ask()['offers']], [third])
        self.decide('merge', first, '--into', second, '--undo')
        self.decide('retire', second)
        self.decide('retire', second, '--undo')
        self.decide('admit', second, '--undo')
        self.cli('publish-catalogue', '--edition', 'history')
        self.select(second, expected=2)
        self.assertIn('Bad source', (self.taker.state / 'declines.jsonl').read_text())
        self.assertGreater(len(self.cli('decisions', first)['events']), 2)

    def test_tampering_and_no_current_policy_fallback(self):
        cid = self.ready()
        catalogue = Catalogue(self.curator.index)
        pattern = catalogue.path.parent / catalogue.get(cid)['prefix'] / 'PATTERN.md'
        original = pattern.read_bytes()
        pattern.write_bytes(original + b'changed')
        self.select(cid, expected=2)
        pattern.write_bytes(original)
        data_path = catalogue.path.parent / 'CATALOGUE.json'
        data_path.write_bytes(data_path.read_bytes() + b' ')
        self.cli('ask', '--catalogue', self.curator.index, '--task', 'setup', project=self.taker, expected=2)
        self.curator.index.unlink()
        self.select(cid, expected=2)

    def test_pending_incomplete_external_offer_does_not_gain_admission(self):
        (self.bundle / 'PATTERN.md').write_text('# Incomplete setup\n', encoding='utf-8')
        data = capture(self.bundle)
        cid = content_id(data)
        files = {'bundle/sample-pattern/' + n: body for n, body in data.items()}
        manifest = envelope('offer', files, {'content_id': cid, 'name': 'sample-pattern', 'standard_version': '1.0'})
        mid = sha((dumps(manifest) + '\n').encode())
        target = self.supplier.root / 'published' / 'knowhow/offers' / mid
        install(target, 'OFFER.json', manifest, files)
        block = read_index(self.supplier.index)
        block['offers'].append({'path': 'knowhow/offers/' + mid + '/OFFER.json', 'sha256': mid})
        write_index(self.supplier.index, block)
        self.intake()
        self.assertFalse(self.cli('decisions', cid)['check']['presence_complete'])
        self.cli('admit', cid, '--actor', 'Executive', '--reason', 'Must fail', expected=2)
        self.cli('publish-catalogue', '--edition', 'empty')
        self.assertEqual(self.ask()['offers'], [])
        self.select(cid, expected=2)

    def test_intake_only_reads_published_supplier_files(self):
        offer(self.supplier, self.bundle)
        private = self.supplier.root / 'private.md'
        private.write_text('PRIVATE', encoding='utf-8')
        real_read = Path.read_bytes
        def guarded(path):
            if path == self.supplier.root or self.supplier.root in path.parents:
                self.assertIn(self.supplier.root / 'published', path.parents)
            return real_read(path)
        with patch.object(Path, 'read_bytes', guarded):
            self.intake()

    def test_nonparticipating_published_index_is_not_an_intake_error(self):
        public = self.base / 'unadopted/published'
        public.mkdir(parents=True)
        (public / 'INDEX.md').write_text('# Published other material\n', encoding='utf-8')
        self.listing.write_text(dumps({'format': 1, 'published_parts': [str(public)]}), encoding='utf-8')
        result = self.intake()
        self.assertEqual(result['counts']['unadvertised_parts'], 1)
        self.assertFalse(result['errors'])

    def test_unlisted_selected_or_retained_files_fail_closed(self):
        cid = self.ready()
        catalogue = Catalogue(self.curator.index)
        unexpected = catalogue.path.parent / catalogue.get(cid)['prefix'] / 'kit/unlisted.txt'
        unexpected.write_text('Not published', encoding='utf-8')
        self.select(cid, expected=2)
        with Store(self.curator) as store:
            retained = store.bundles / cid / 'bundle/sample-pattern/kit/unlisted.txt'
            retained.write_text('Not retained by manifest', encoding='utf-8')
        self.cli('admit', cid, '--actor', 'Executive', '--reason', 'Must fail', expected=2)
        self.cli('publish-catalogue', '--edition', 'bad', expected=2)

    def test_duplicate_json_portable_paths_reparse_and_transaction_rollback(self):
        for name in ('../escape', '/absolute', 'C:/other', 'kit/CON.txt', 'kit/a\\b', 'kit/LPT¹', 'kit/trailing.'):
            with self.assertRaises(ValueError):
                below(self.base, name)
        with self.assertRaises(ValueError):
            loads('{"format":1,"format":1}')
        from types import SimpleNamespace
        real_lstat = Path.lstat
        def fake_lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if path == self.bundle:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=1024)
            return info
        with patch.object(Path, 'lstat', fake_lstat):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                ordinary_path(self.bundle)
        cid = self.ready()
        before = self.cli('decisions', cid)['events']
        with self.assertRaises(ValueError):
            with Store(self.curator) as store:
                store.decide('retire', cid, '*', 'Executive', 'Rollback exercise')
                store.decide('admit', 'f' * 64, '*', 'Executive', 'Unknown ID')
        self.assertEqual(before, self.cli('decisions', cid)['events'])

    def test_ingest_rejects_corrupt_offer_but_accepts_independent_valid_one(self):
        first = self.cli('offer', self.bundle, project=self.supplier)
        second_path = self.write(self.supplier, 'second-pattern')
        second = self.cli('offer', second_path, project=self.supplier)
        target = Path(first['offer']) / 'bundle/sample-pattern/kit/steps.txt'
        target.write_text('Tampered', encoding='utf-8')
        result = self.cli('ingest', '--published-parts', self.listing, expected=1)
        self.assertTrue(result['partial_failure'])
        self.assertEqual([r['id'] for r in self.cli('decisions')['contents']], [second['id']])

    def test_manifest_traversal_rejected_before_any_inventory_content_read(self):
        published = self.cli('offer', self.bundle, project=self.supplier)
        path = Path(published['offer']) / 'OFFER.json'
        manifest = json.loads(path.read_text())
        manifest['files']['../private.txt'] = {'sha256': '0' * 64, 'size': 1}
        raw = (dumps(manifest) + '\n').encode()
        path.write_bytes(raw)
        block = read_index(self.supplier.index)
        block['offers'][0]['sha256'] = sha(raw)
        write_index(self.supplier.index, block)
        real_read = Path.read_bytes
        reads = []
        def guarded(p):
            reads.append(p.name)
            return real_read(p)
        with patch.object(Path, 'read_bytes', guarded):
            self.cli('ingest', '--published-parts', self.listing, expected=1)
        self.assertNotIn('steps.txt', reads)
        self.assertNotIn('private.txt', reads)

    def test_prohibited_names_links_specials_and_containment(self):
        for name in ('.env', 'private.pem', '.aws/credentials'):
            unsafe = self.bundle / 'kit' / name
            unsafe.parent.mkdir(parents=True, exist_ok=True)
            unsafe.write_text('DO_NOT_READ', encoding='utf-8')
            real_read = Path.read_bytes
            def guarded(p):
                self.assertNotEqual(p, unsafe)
                return real_read(p)
            with patch.object(Path, 'read_bytes', guarded):
                self.cli('check', self.bundle, project=self.supplier, expected=2)
                self.cli('offer', self.bundle, project=self.supplier, expected=2)
            unsafe.unlink()
            if name.startswith('.aws'):
                unsafe.parent.rmdir()
        self.cli('offer', self.bundle, project=self.taker, expected=2)
        try:
            (self.bundle / 'kit/alias').symlink_to(self.bundle / 'kit/steps.txt')
        except OSError:
            return
        self.cli('offer', self.bundle, project=self.supplier, expected=2)
        (self.bundle / 'kit/alias').unlink()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(self.bundle / 'kit/fifo')
            self.cli('check', self.bundle, project=self.supplier, expected=2)

    def test_uuid_conflicts_and_moves_preserve_decisions(self):
        cid = self.ready()
        duplicate = self.base / 'duplicate'
        shutil.copytree(self.supplier.root, duplicate)
        self.listing.write_text(dumps({'format': 1, 'published_parts': [
            str(self.supplier.root / 'published'), str(duplicate / 'published')]}), encoding='utf-8')
        result = self.cli('ingest', '--published-parts', self.listing, expected=1)
        self.assertEqual(result['counts']['offers'], 0)
        shutil.rmtree(duplicate)
        old_id = self.supplier.id
        moved = self.base / 'moved supplier'
        self.supplier.root.rename(moved)
        self.supplier = Project(moved)
        self.assertEqual(self.supplier.id, old_id)
        self.list_parts(self.supplier, self.taker)
        self.intake()
        self.assertEqual(len(self.cli('decisions', cid)['origins']), 2)
        self.cli('decline', cid, '--actor', 'Executive', '--reason', 'Persistent', project=self.taker)
        moved_taker = self.base / 'moved taker'
        tid = self.taker.id
        self.taker.root.rename(moved_taker)
        self.taker = Project(moved_taker)
        self.assertEqual(tid, self.taker.id)
        self.assertEqual(self.ask()['offers'], [])
        moved_curator = self.base / 'moved curator'
        mid = Catalogue(self.curator.index).hash
        self.curator.root.rename(moved_curator)
        self.curator = Project(moved_curator)
        self.assertEqual(Catalogue(self.curator.index).hash, mid)

    def test_atomic_publication_and_no_overwrite(self):
        cid = self.ready()
        before = self.curator.index.read_bytes()
        self.decide('retire', cid)
        self.cli('publish-catalogue', '--edition', 'one', expected=2)
        self.assertEqual(before, self.curator.index.read_bytes())
        with patch('access.engine.write_index', side_effect=OSError('Synthetic interruption')):
            self.cli('publish-catalogue', '--edition', 'orphan', expected=2)
        self.assertEqual(before, self.curator.index.read_bytes())
        self.assertTrue((self.curator.root / 'published/knowhow/catalogues/orphan/EDITION.json').is_file())
        self.cli('publish-catalogue', '--edition', 'orphan')
        self.assertEqual(self.ask()['offers'], [])
        self.assertFalse(list((self.curator.root / 'published/knowhow/catalogues').glob('.stage-*')))

    def test_write_sets_costs_and_use_accounts(self):
        cid = self.ready()
        source_before = self.snapshot(self.supplier.root)
        curator_before = self.snapshot(self.curator.root)
        self.ask()
        self.select(cid)
        self.cli('log-use', cid, '--outcome', 'Invented failure', '--saving-note', 'No saving', project=self.taker)
        self.assertEqual(source_before, self.snapshot(self.supplier.root))
        self.assertEqual(curator_before, self.snapshot(self.curator.root))
        records = self.taker.records('costs.jsonl')
        self.assertEqual([r['operation'] for r in records], ['ask', 'select', 'log-use'])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(['ask', '--project', str(self.taker.root), '--catalogue', str(self.curator.index),
                                   '--task', 'setup', '--json']), 0)
        self.assertEqual(self.taker.records('costs.jsonl')[-1]['output_bytes'], len(out.getvalue().encode()))
        self.assertEqual(self.taker.records('uses.jsonl')[0]['outcome'], 'Invented failure')
        with Store(self.curator) as store:
            self.assertGreater(store.db.execute('SELECT count(*) FROM costs').fetchone()[0], 0)

    def test_ask_reads_no_full_bundle_and_tenfold_growth(self):
        measures = []
        for count in (10, 100):
            start = time.perf_counter()
            for n in range(0 if count == 10 else 10, count):
                path = self.write(self.supplier, 'pattern-' + str(n))
                offer(self.supplier, path)
            self.intake()
            with Store(self.curator) as store:
                for cid in store.ids():
                    if not store.active(store.effective(cid), 'admit'):
                        store.decide('admit', cid, '*', 'Synthetic reviewer', 'Invented exercise')
                store.publish('growth-' + str(count))
            real_read = Path.read_bytes
            def guarded(p):
                self.assertNotEqual(p.name, 'PATTERN.md')
                self.assertNotEqual(p.name, 'steps.txt')
                return real_read(p)
            with patch.object(Path, 'read_bytes', guarded):
                asked = self.ask()
            self.assertEqual(asked['matching'], count)
            self.assertEqual(len(asked['offers']), 5)
            self.assertLessEqual(len(dumps(asked['offers']).encode()), 12000)
            self.assertEqual(self.intake()['counts']['checks'], 0)
            measures.append({'contents': count, 'candidate_bytes': len(dumps(asked['offers']).encode()),
                             'exercise_seconds': round(time.perf_counter() - start, 3)})
        print('Synthetic growth: ' + dumps(measures))

    def run_code(self, code, *args):
        return subprocess.run([sys.executable, '-B', str(code / 'knowhow.py'), *map(str, args)],
                              cwd=str(self.taker.root), text=True, capture_output=True)

    def temporary_source(self):
        source = self.base / 'generic source'
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(
            '.git', '.local', '.knowhow', '.staging', '__pycache__'))
        return source

    @unittest.skipIf((ROOT / 'EDITION.json').exists(), 'Packing requires developing source')
    def test_source_packing_is_deterministic(self):
        source = self.temporary_source()
        first = self.run_code(source, 'pack-capability', '--project', source, '--edition', 'one')
        self.assertEqual(first.returncode, 0, first.stderr)
        packed = json.loads(first.stdout)
        edition = Path(packed['stage'])
        manifest = parse_manifest(edition / 'EDITION.json', packed['manifest_sha256'], 'capability')
        for name in manifest['files']:
            verified_file(edition, manifest, name)
        self.assertIn('EXISTING.md', manifest['files'])
        second = self.run_code(source, 'pack-capability', '--project', source, '--edition', 'one')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)['manifest_sha256'], packed['manifest_sha256'])

    def test_fixed_capability_detached_empty_and_readonly(self):
        cid = self.ready()
        run = self.run_code
        if (ROOT / 'EDITION.json').exists():
            edition = self.base / 'detached edition'
            shutil.copytree(ROOT, edition, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            source = self.temporary_source()
            packed = run(source, 'pack-capability', '--project', source, '--edition', 'one')
            self.assertEqual(packed.returncode, 0, packed.stderr)
            edition = self.base / 'detached edition'
            shutil.copytree(json.loads(packed.stdout)['stage'], edition)
        before = self.snapshot(edition)
        for path in edition.rglob('*'):
            path.chmod(0o555 if path.is_dir() else 0o444)
        edition.chmod(0o555)
        try:
            result = run(edition, 'self-check', '--project', self.taker.root, '--json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['synthetic_publication_flow'])
            result = run(edition, 'ask', '--project', self.taker.root, '--catalogue', self.curator.index, '--task', 'setup')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['offers'][0]['id'], cid)
            result = run(edition, 'select', cid, '--project', self.taker.root, '--catalogue', self.curator.index)
            self.assertEqual(result.returncode, 0, result.stderr)
            check = subprocess.run([sys.executable, str(edition / 'check_contribution.py'), str(self.bundle), '--json'],
                                   cwd=str(self.taker.root), text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(run(edition, 'init', '--project', edition).returncode, 2)
            rejected = run(edition, 'pack-capability', '--project', edition, '--edition', 'two')
            self.assertEqual(rejected.returncode, 2)
            self.assertIn('not an edition', rejected.stderr)
            self.assertEqual(before, self.snapshot(edition))
            self.assertFalse(list(edition.rglob('__pycache__')))
        finally:
            edition.chmod(0o755)
            for path in edition.rglob('*'):
                path.chmod(0o755 if path.is_dir() else 0o644)
        for path in [ROOT / 'knowhow.py', ROOT / 'check_contribution.py', *(ROOT / 'access').glob('*.py')]:
            ast.parse(path.read_text(), feature_version=(3, 9))


if __name__ == '__main__':
    unittest.main()
