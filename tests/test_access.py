"""Invented local trees only; no network or real innovation fixtures."""
import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from access.cli import main, self_check
from access.engine import Store, ordinary_path, project_key, portable
from test_standard import sample, markdown
ROOT = Path(__file__).absolute().parents[1]


class AccessTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.local').mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='tests-', dir=str(ROOT / '.local'))
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.projects = self.base / 'projects'
        self.projects.mkdir()
        self.state = self.base / 'state'
        self.receiver = self.projects / 'new project'
        self.receiver.mkdir()
        self.source = self.projects / 'source/innovations/sample-pattern'
        self.write(self.source)

    def write(self, path):
        record = sample()
        record['id'] = path.name
        (path / 'kit').mkdir(parents=True, exist_ok=True)
        (path / 'PATTERN.md').write_text(markdown(record), encoding='utf-8')
        (path / 'kit/steps.txt').write_text('Fill <setup> before continuing.', encoding='utf-8')

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args, self.state)
        return code, out.getvalue(), err.getvalue()

    def test_empty_configuration_and_machine_check(self):
        with patch('sys.stdin.isatty', return_value=False):
            code, out, err = self.cli(['ask', '--task', 'setup', '--project', str(self.receiver)])
        self.assertEqual(code, 2)
        self.assertIn('no search', err)
        self.assertFalse((self.state / 'settings.json').exists())
        result = self_check(self.state)
        self.assertTrue(result['synthetic_gather_check_select'])
        self.assertFalse(result['configured'])
        empty = self.base / 'empty'
        empty.mkdir()
        with Store(self.state, empty) as store:
            stats, errors = store.gather()
            self.assertEqual(stats['distinct_contents'], 0)
            self.assertEqual(store.ask('setup', '.')['offers'], [])
            self.assertFalse(errors)

    def test_nested_identity_and_containment(self):
        parent = self.projects / 'outer'
        nested = parent / 'inner'
        work = nested / 'src'
        work.mkdir(parents=True)
        (parent / '.git').mkdir()
        (nested / '.git').write_text('gitdir: fictional', encoding='utf-8')
        self.assertEqual(project_key(self.projects, cwd=work), 'outer/inner')
        self.assertEqual(project_key(self.projects, self.receiver), 'new project')
        with self.assertRaisesRegex(ValueError, 'No project marker'):
            project_key(self.projects, cwd=self.receiver)
        with self.assertRaises(ValueError):
            project_key(self.projects, self.base)
        try:
            (self.projects / 'alias').symlink_to(parent, target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(ValueError):
            ordinary_path(self.projects / 'alias/inner')

    def test_copies_warm_changes_removal_and_readonly(self):
        duplicate = self.projects / 'copy/innovations/sample-pattern'
        duplicate.parent.mkdir(parents=True)
        shutil.copytree(self.source, duplicate)
        def snapshot():
            return {str(p): p.read_bytes() for p in self.projects.rglob('*') if p.is_file()}
        before = snapshot()
        with Store(self.state, self.projects) as store:
            cold, _ = store.gather()
            self.assertEqual(tuple(cold[k] for k in ('collections', 'contributions', 'distinct_contents', 'copies')), (2, 2, 1, 1))
            self.assertEqual(cold['checks'], 1)
            identity = store.db.execute('SELECT id FROM bundles').fetchone()[0]
            store.decide('admit', [identity], '*', 'Reviewer', 'Synthetic review')
            warm, _ = store.gather()
            self.assertEqual((warm['checks'], warm['new_contents']), (0, 0))
            self.assertEqual(before, snapshot())
            self.assertEqual(len(store.ask('setup', 'new project')['offers']), 1)
            (self.source / 'kit/steps.txt').write_text('Changed fictional steps', encoding='utf-8')
            changed, _ = store.gather()
            self.assertEqual((changed['retained_contents'], changed['checks']), (2, 1))
            own = store.ask('setup', 'source')['offers']
            self.assertEqual({o['status'] for o in own}, {'admitted', 'own-unadmitted'})
            self.assertEqual([o['id'] for o in store.ask('setup', 'new project')['offers']], [identity])
            shutil.rmtree(self.source.parent.parent)
            shutil.rmtree(duplicate.parent.parent)
            removed, _ = store.gather()
            self.assertEqual(removed['retained_contents'], 2)
            selected = store.select([identity], 'new project')['selected'][0]
            self.assertTrue(Path(selected['bundle']).is_dir())
            self.assertTrue(all(not loc['current'] for loc in selected['locations']))
            self.assertEqual(len(selected['locations']), 2)

    def test_own_incomplete_and_full_context(self):
        text = '# Invented incomplete\n\nFixture setup.'
        (self.source / 'PATTERN.md').write_text(text, encoding='utf-8')
        with Store(self.state, self.projects) as store:
            store.gather()
            self.assertEqual(store.ask('setup', 'new project')['offers'], [])
            own = store.ask('setup', 'source')['offers'][0]
            self.assertEqual(own['status'], 'own-unadmitted')
            self.assertGreater(own['check']['problem_count'], 0)
            self.assertFalse(own['check']['presence_complete'])
            self.assertEqual(store.select([own['id']], 'source')['selected'][0]['pattern'], text)
            with self.assertRaises(ValueError):
                store.select([own['id']], 'new project')
            with self.assertRaises(ValueError):
                store.decide('admit', [own['id']], '*', 'Reviewer', 'Incomplete')

    def test_decisions_and_recheck_selection(self):
        self.write(self.projects / 'source/innovations/another-pattern')
        with Store(self.state, self.projects) as store:
            store.gather()
            ids = [r['id'] for r in store.db.execute('SELECT id FROM bundles ORDER BY id')]
            for identity in ids:
                store.decide('admit', [identity], '*', 'Reviewer', 'Synthetic review')
            source, target = ids
            store.decide('decline', [source], 'new project', 'Executive', 'Does not fit')
            self.assertEqual(len(store.ask('setup', 'new project')['offers']), 1)
            with self.assertRaises(ValueError):
                store.select([source], 'new project')
            self.assertEqual(len(store.ask('setup', 'source')['offers']), 2)
            store.decide('decline', [source], 'new project', 'Executive', 'Reconsidered', undo=True)
            store.decide('merge', [source], '*', 'Reviewer', 'Equivalent', target)
            self.assertEqual(len(store.ask('setup', 'new project')['offers']), 1)
            store.decide('exclude', [source], '*', 'CEO', 'Do not bypass restriction')
            self.assertEqual(store.ask('setup', 'new project')['offers'], [])
            with self.assertRaises(ValueError):
                store.select([target], 'new project')
            store.decide('exclude', [source], '*', 'CEO', 'Restored', undo=True)
            store.decide('retire', [target], '*', 'Reviewer', 'Counter evidence')
            self.assertEqual(store.ask('setup', 'source')['offers'], [])
            store.decide('retire', [target], '*', 'Reviewer', 'Reinstated', undo=True)
            store.decide('exclude', [target], 'new project', 'CEO', 'Scoped restriction')
            self.assertEqual(store.ask('setup', 'new project')['offers'], [])
            self.assertEqual(len(store.ask('setup', 'source')['offers']), 1)
            self.assertGreater(len(store.events()), 8)
            self.assertEqual(store.db.execute('SELECT count(*) FROM bundles').fetchone()[0], 2)

    def test_secret_link_and_special_entries(self):
        for path in (self.source / '.env', self.source / 'kit/private.pem', self.source / 'kit/.aws/credentials'):
            path.parent.mkdir(exist_ok=True)
            path.write_text('DO_NOT_READ', encoding='utf-8')
        real_read = Path.read_bytes
        def guarded_read(path):
            self.assertNotIn(path.name, ('.env', 'private.pem', 'credentials'))
            return real_read(path)
        with patch.object(Path, 'read_bytes', guarded_read):
            with Store(self.state, self.projects) as store:
                store.gather()
                row = dict(store.db.execute('SELECT * FROM bundles').fetchone())
                self.assertTrue(json.loads(row['issues']))
                self.assertFalse((store.bundle_path(row) / '.env').exists())
                self.assertNotIn('DO_NOT_READ', json.dumps(store.select([row['id']], 'source')))
                with self.assertRaises(ValueError):
                    store.decide('admit', [row['id']], '*', 'Reviewer', 'Must fail')
        self.assertEqual(self.cli(['check', str(self.source)])[0], 2)
        (self.source / '.env').unlink()
        (self.source / 'kit/private.pem').unlink()
        shutil.rmtree(self.source / 'kit/.aws')
        try:
            (self.source / 'kit/alias').symlink_to(self.source / 'kit/steps.txt')
            if hasattr(os, 'mkfifo'):
                os.mkfifo(self.source / 'kit/fifo')
        except OSError:
            return
        with Store(self.state, self.projects) as store:
            store.gather()
            rows = list(store.db.execute('SELECT * FROM bundles'))
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(json.loads(row['issues']) for row in rows))

    def test_tenfold_growth_offer_bounds_and_reuse(self):
        measurements = []
        with Store(self.state, self.projects) as store:
            for count in (10, 100):
                for i in range(1 if count == 10 else 10, count):
                    self.write(self.projects / ('source/innovations/pattern-' + str(i)))
                stats, _ = store.gather()
                for row in store.db.execute('SELECT id FROM bundles'):
                    store.decide('admit', [row['id']], '*', 'Reviewer', 'Synthetic review')
                result = store.ask('fictional setup', 'new project')
                size = len(json.dumps(result, separators=(',', ':')).encode())
                self.assertEqual(len(result['offers']), 5)
                self.assertEqual(result['matching'], count)
                self.assertLess(size, 13000)
                warm, _ = store.gather()
                self.assertEqual(warm['checks'], 0)
                measurements.append(dict(contents=count, cold_seconds=stats['seconds'], warm_seconds=warm['seconds'], offer_bytes=size))
        print('Synthetic growth measurements: ' + json.dumps(measurements))

    def test_cli_compact_check_cost_log_and_namespaces(self):
        code, out, err = self.cli(['check', str(self.source), '--json'])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result['problems'], [])
        self.assertTrue(result['review_required'])
        self.assertFalse((self.state / 'settings.json').exists())
        log = json.loads((self.state / 'command-uses.jsonl').read_text().splitlines()[0])
        self.assertEqual(log['output_bytes'], len(out.encode()))
        self.assertEqual(self.cli(['configure', '--projects-folder', str(self.projects)])[0], 0)
        code, out, err = self.cli(['ask', '--task', 'setup', '--project', str(self.source.parents[1])])
        self.assertEqual(code, 0, err)
        identity = json.loads(out)['offers'][0]['id']
        with Store(self.state, self.projects) as store:
            log = json.loads(store.db.execute("SELECT details FROM uses WHERE operation='ask'").fetchone()[0])
            self.assertEqual(log['output_bytes'], len(out.encode()))
            self.assertEqual(store.events(), [])
        self.assertEqual(self.cli(['log-use', identity, '--project', str(self.receiver), '--outcome', 'Synthetic failure', '--saving-note', 'No saving'])[0], 0)
        other = self.base / 'other'
        other.mkdir()
        self.assertEqual(self.cli(['configure', '--projects-folder', str(other)])[0], 0)
        with Store(self.state, other) as store:
            self.assertEqual(store.db.execute('SELECT count(*) FROM bundles').fetchone()[0], 0)

    def test_bad_record_values_and_cli_decisions(self):
        record = sample()
        record['applicability'] = 'invalid shape'
        (self.source / 'PATTERN.md').write_text(markdown(record), encoding='utf-8')
        with Store(self.state, self.projects) as store:
            store.gather()
            offer = store.ask('setup', 'source')['offers'][0]
            self.assertFalse(offer['check']['presence_complete'])
        self.write(self.source)
        self.cli(['configure', '--projects-folder', str(self.projects)])
        code, out, err = self.cli(['ask', '--task', 'setup', '--project', str(self.source.parents[1])])
        self.assertEqual(code, 0, err)
        identity = next(o['id'] for o in json.loads(out)['offers'] if o['check']['presence_complete'])
        self.assertEqual(self.cli(['admit', identity, '--actor', 'Reviewer', '--reason', 'Invented review'])[0], 0)
        args = ['select', identity, '--project', str(self.receiver)]
        self.assertEqual(self.cli(args)[0], 0)
        self.assertEqual(self.cli(['exclude', identity, '--all', '--actor', 'CEO', '--reason', 'Invented exclusion'])[0], 0)
        self.assertEqual(self.cli(args)[0], 2)
        self.assertEqual(self.cli(['exclude', identity, '--all', '--project', str(self.receiver), '--actor', 'CEO', '--reason', 'Invalid scope'])[0], 2)
        events = json.loads(self.cli(['decisions', identity])[1])['events']
        self.assertEqual(len(events), 2)

    def test_merge_reversal_and_transaction_rollback(self):
        self.write(self.projects / 'source/innovations/another-pattern')
        self.write(self.projects / 'source/innovations/third-pattern')
        with Store(self.state, self.projects) as store:
            store.gather()
            ids = [r['id'] for r in store.db.execute('SELECT id FROM bundles ORDER BY id')]
            for identity in ids:
                store.decide('admit', [identity], '*', 'Reviewer', 'Invented review')
            source, target, third = ids
            store.decide('merge', [source], '*', 'Reviewer', 'Equivalent', target)
            with self.assertRaises(ValueError):
                store.decide('merge', [target], '*', 'Reviewer', 'Would chain', third)
            store.decide('merge', [source], '*', 'Reviewer', 'Undo equivalence', target, undo=True)
            store.decide('merge', [target], '*', 'Reviewer', 'New equivalence', third)
            events = len(store.events())
        with self.assertRaises(ValueError):
            with Store(self.state, self.projects) as store:
                store.decide('retire', [source, 'not-a-content-id'], '*', 'Reviewer', 'Must roll back')
        with Store(self.state, self.projects) as store:
            self.assertEqual(len(store.events()), events)
        with self.assertRaises(ValueError):
            ordinary_path(self.projects / '.ssh/unknown')

    def test_floor_and_detached_clone(self):
        for name in ('CON.txt', 'LPT1', 'trailing.', 'a:b', 'a\\b'):
            self.assertFalse(portable(name))
        for file in [ROOT / 'knowhow.py', *(ROOT / 'access').glob('*.py')]:
            ast.parse(file.read_text(encoding='utf-8'), feature_version=(3, 9))
        clone = self.base / 'standalone clone'
        clone.mkdir()
        for name in ('knowhow.py', 'access', 'standard'):
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, clone / name, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copyfile(source, clone / name)
        def run(*args):
            return subprocess.run([sys.executable, str(clone / 'knowhow.py'), *args], cwd=str(self.receiver), text=True, capture_output=True)
        result = run('self-check', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['synthetic_gather_check_select'])
        self.assertEqual(run('configure', '--projects-folder', str(self.projects)).returncode, 0)
        result = run('ask', '--task', 'setup', '--project', str(self.receiver))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['offers'], [])


if __name__ == '__main__':
    unittest.main()
