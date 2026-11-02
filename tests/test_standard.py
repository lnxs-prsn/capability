"""Synthetic contributions only; no private project facts."""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from standard import check_contribution
from standard.definition import RECORD, SECTIONS
from standard.render import documents
ROOT = Path(__file__).absolute().parents[1]


def sample():
    return {
        'schema_version': 1, 'standard_version': '1.0', 'id': 'sample-pattern',
        'origin': {'project': 'Imaginary workshop', 'situation': 'Repeated fixture setup',
                   'environment': 'Offline exercise', 'developed_on': '2026-01-02',
                   'development_kind': 'invented', 'development_account': 'Created in a fictional exercise.'},
        'applicability': {'fits': ['Repeatable setup'], 'does_not_fit': ['Unique setups'], 'prerequisites': [], 'adaptations': []},
        'evidence': [{'claim': 'Reduced fictional omissions.', 'outcome': 'success', 'project': 'Imaginary workshop',
                      'situation': 'Three synthetic runs', 'occurred_on': '2026-01-03', 'locators': ['fictional-log@one'],
                      'verification': {'status': 'unchecked', 'checked_on': None, 'checked_by': None, 'scope': None,
                                       'result': None, 'reason': 'Synthetic example, not independently checked.'}}],
        'limits': ['No claim for unique setups.'],
        'evolution': {'origin_state': 'aligned', 'assessed_on': '2026-01-04', 'locators': ['fictional-source@one'],
                      'deltas': [], 'reason': 'Synthetic source matches.'},
        'assets': [{'path': 'kit/steps.txt', 'kind': 'checklist', 'purpose': 'Setup reminder', 'adaptations': [],
                    'dependencies': [], 'context_ref': 'PATTERN.md#/applicability'}]}


def markdown(record):
    lines = ['# Sample pattern', '']
    for i, (heading, _) in enumerate(SECTIONS):
        lines += ['## ' + heading, '', 'Fictional explanation ' + str(i) + '.', '']
    return '\n'.join(lines) + '\n## Context record\n\n```json\n' + json.dumps(record) + '\n```\n'


class StandardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'sample-pattern'
        (self.base / 'kit').mkdir(parents=True)
        (self.base / 'kit/steps.txt').write_text('Fill <setup> before continuing.', encoding='utf-8')
        self.record = sample()
        self.write()

    def write(self, record=None, source=None):
        (self.base / 'PATTERN.md').write_text(source if source is not None else markdown(record or self.record), encoding='utf-8')

    def test_complete_is_presence_only(self):
        result = check_contribution(self.base)
        self.assertTrue(result['presence_complete'], result['checks'])
        self.assertIn('not truth', result['limitations'][0])
        self.assertTrue(result['review_required'])
        self.assertEqual(result['discovery']['title'], 'Sample pattern')
        self.assertNotIn('title', result['record'])

    def test_each_required_key_missing(self):
        def paths(spec, prefix=()):
            if spec['type'] == 'object':
                for key, child in spec['fields'].items():
                    yield prefix + (key,)
                    yield from paths(child, prefix + (key,))
            elif spec['type'] == 'list' and spec['item']['type'] == 'object':
                yield from paths(spec['item'], prefix + (0,))
        for path in paths(RECORD):
            record = copy.deepcopy(self.record)
            node = record
            for part in path[:-1]:
                node = node[part]
            del node[path[-1]]
            with self.subTest(path=path):
                self.write(record)
                result = check_contribution(self.base)
                self.assertFalse(result['presence_complete'])
                self.assertTrue(any(c['state'] == 'missing' for c in result['checks']))

    def test_checked_unavailable_and_dates(self):
        v = self.record['evidence'][0]['verification']
        v['status'] = 'checked'
        self.write()
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        v.update(checked_on='2026-01-05', checked_by='Fictional reviewer', scope='Synthetic runs', result='Matched', reason=None)
        self.write()
        self.assertTrue(check_contribution(self.base)['presence_complete'])
        v['checked_on'] = '2026-02-30'
        self.write()
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        self.record = sample()
        self.record['evidence'][0]['verification']['status'] = 'unavailable'
        self.write()
        self.assertTrue(check_contribution(self.base)['presence_complete'])

    def test_failure_and_drift(self):
        self.record['evidence'][0]['outcome'] = 'failure'
        self.write()
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        self.record['evidence'].append(sample()['evidence'][0])
        self.record['evolution']['origin_state'] = 'diverged'
        self.write()
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        self.record['evolution']['deltas'] = ['Fictional source gained a step.']
        self.write()
        result = check_contribution(self.base)
        self.assertTrue(result['presence_complete'])
        self.assertEqual(result['discovery']['evidence_outcomes'], ['failure', 'success'])
        self.record['origin']['developed_on'] = None
        self.write()
        self.assertTrue(check_contribution(self.base)['discovery']['has_unknowns'])
        self.assertFalse(check_contribution(self.base)['presence_complete'])

    def test_paths_and_context_references(self):
        for path in ('../outside', '/tmp/elsewhere', 'C:/elsewhere', 'kit/../escape', 'kit/CON.txt', 'kit/a\\b', 'kit/missing.txt'):
            self.record['assets'][0]['path'] = path
            self.write()
            with self.subTest(path=path):
                self.assertFalse(check_contribution(self.base)['presence_complete'])
        self.record = sample()
        for ref in ('OTHER.md#/applicability', 'PATTERN.md#/missing', 'PATTERN.md#missing'):
            self.record['assets'][0]['context_ref'] = ref
            self.write()
            self.assertFalse(check_contribution(self.base)['presence_complete'])
        self.record['assets'][0]['context_ref'] = 'PATTERN.md#fits-projects-like'
        self.write()
        self.assertTrue(check_contribution(self.base)['presence_complete'])
        (self.base / 'kit/extra.txt').write_text('Invented asset', encoding='utf-8')
        self.assertFalse(check_contribution(self.base)['presence_complete'])

    def test_missing_kit_and_symlinks(self):
        (self.base / 'kit/steps.txt').unlink()
        (self.base / 'kit').rmdir()
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        target = Path(self.temp.name) / 'target'
        target.mkdir()
        try:
            (self.base / 'kit').symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Host does not permit symlinks')
        self.assertFalse(check_contribution(self.base)['presence_complete'])
        alias = Path(self.temp.name) / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        self.assertTrue(check_contribution(alias)['read_error'])

    def test_prose_and_malformed_json(self):
        original = markdown(self.record)
        for source in (original.replace('Fictional explanation 1.', ''),
                       original.replace('## Problem it solves', '## Different heading'),
                       original.replace('"id": "sample-pattern"', '"id": "sample-pattern", "id": "duplicate"'),
                       original.replace('"schema_version": 1', '"schema_version": NaN'),
                       original + '\n## Context record\n', original.replace('```json', '```text')):
            self.write(source=source)
            self.assertFalse(check_contribution(self.base)['presence_complete'])

    def test_bad_types_do_not_crash(self):
        for key in self.record:
            for value in (None, {}, [], False, 123, 'wrong'):
                with self.subTest(key=key, value=value):
                    if key == 'limits' and value == []:
                        continue  # An explicitly empty limits list is permitted, with review.
                    record = copy.deepcopy(self.record)
                    record[key] = value
                    self.write(record)
                    self.assertFalse(check_contribution(self.base)['presence_complete'])

    def test_bounded_discovery_retains_full_context(self):
        self.record['applicability']['fits'] = ['x' * 2000] * 100
        self.write()
        result = check_contribution(self.base)
        self.assertEqual(len(result['discovery']['fits']), 2)
        self.assertEqual(len(result['discovery']['fits'][0]), 96)
        self.assertEqual(len(result['record']['applicability']['fits']), 100)

    def test_generated_files_and_python_floor(self):
        for name, content in documents().items():
            self.assertEqual((ROOT / 'standard' / name).read_text(encoding='utf-8'), content)
        for file in list((ROOT / 'standard').glob('*.py')) + [ROOT / 'check_contribution.py']:
            ast.parse(file.read_text(encoding='utf-8'), feature_version=(3, 9))

    def test_cli_from_other_directory_read_only(self):
        def snapshot():
            return {p.relative_to(self.base).as_posix(): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        before = snapshot()
        command = [sys.executable, str(ROOT / 'check_contribution.py'), str(self.base), '--json']
        run = subprocess.run(command, cwd=self.temp.name, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)['presence_complete'])
        self.assertEqual(before, snapshot())
        self.record['limits'] = None
        self.write()
        self.assertEqual(subprocess.run(command, cwd=self.temp.name, capture_output=True).returncode, 1)
        command[2] = str(self.base / 'missing')
        self.assertEqual(subprocess.run(command, cwd=self.temp.name, capture_output=True).returncode, 2)


if __name__ == '__main__':
    unittest.main()
