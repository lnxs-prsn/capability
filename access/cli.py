"""Explicit project commands; executable editions never hold caller state."""
import argparse
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

from standard import check_contribution
from .engine import Catalogue, Store, compact_check, load_listing, offer
from .publication import (Project, below, dumps, envelope, identity, install, inventory,
                          ordinary_path, portable, read_bytes)

SOURCE = Path(__file__).absolute().parents[1]
CURATOR = {'ingest', 'admit', 'merge', 'retire', 'exclude', 'decisions', 'publish-catalogue'}


def parser():
    command = argparse.ArgumentParser(description='Draw on published know-how and offer your own, with context.')
    sub = command.add_subparsers(dest='command', required=True)
    for name in ('init', 'ask', 'select', 'decline', 'log-use', 'check', 'offer', 'ingest',
                 'admit', 'merge', 'retire', 'exclude', 'decisions', 'publish-catalogue',
                 'self-check', 'pack-capability'):
        p = sub.add_parser(name)
        p.add_argument('--project', required=True, help='Folder owned by the running agent; attribution, not authentication')
        p.add_argument('--json', action='store_true')
        if name in {'ask', 'select'}:
            p.add_argument('--catalogue', required=True, help="Curator's published INDEX.md")
        if name == 'ask':
            p.add_argument('--task', required=True)
            p.add_argument('--limit', type=int, default=5)
        if name == 'select':
            p.add_argument('ids', nargs='+')
        elif name in {'admit', 'merge', 'retire', 'exclude', 'decline', 'log-use'}:
            p.add_argument('id')
        elif name == 'decisions':
            p.add_argument('id', nargs='?')
        elif name in {'check', 'offer'}:
            p.add_argument('path')
        if name in {'admit', 'merge', 'retire', 'exclude', 'decline'}:
            p.add_argument('--actor', required=True)
            p.add_argument('--reason', required=True)
            p.add_argument('--undo', action='store_true')
        if name == 'merge':
            p.add_argument('--into', required=True)
        if name == 'exclude':
            scope = p.add_mutually_exclusive_group(required=True)
            scope.add_argument('--all', action='store_true')
            scope.add_argument('--project-id')
        if name == 'ingest':
            p.add_argument('--published-parts', help='Required list; absence performs no work')
        if name in {'publish-catalogue', 'pack-capability'}:
            p.add_argument('--edition', required=True)
        if name == 'log-use':
            p.add_argument('--outcome', required=True)
            p.add_argument('--saving-note', default='')
    return command


def pack_capability(source, edition):
    """Only the developing generic source can stage its own fixed publication."""
    source = ordinary_path(source)
    if source != SOURCE or (source / 'EDITION.json').exists():
        raise ValueError('pack-capability --project must name this developing capability source, not an edition')
    if not portable(edition):
        raise ValueError('Use a portable single-component edition name')
    names = ['knowhow.py', 'check_contribution.py', 'USE.md', 'OWNER.md', 'PUBLICATION.md',
             'UPDATE.md', 'EXISTING.md', '.gitignore', 'access/__init__.py', 'access/cli.py', 'access/engine.py',
             'access/publication.py', 'standard/__init__.py', 'standard/check.py',
             'standard/definition.py', 'standard/render.py', 'standard/STANDARD.md',
             'standard/PATTERN.template.md', 'tests/test_standard.py', 'tests/test_access.py']
    files = {name: read_bytes(below(source, name)) for name in names}
    # No recursive capture of state, publications, repositories or innovations.
    manifest = envelope('capability', files, {'edition': edition, 'python_floor': '3.9'})
    stage = below(source, '.staging/' + edition)
    mid = install(stage, 'EDITION.json', manifest, files)
    return {'edition': edition, 'manifest_sha256': mid, 'stage': str(stage),
            'files': len(files), 'notice': 'Staged only. Executive verifies, then publishes and indexes the manifest hash.'}


def self_check(project):
    """Real publication flow with explicitly invented evidence, wholly temporary."""
    from standard.definition import SECTIONS
    with tempfile.TemporaryDirectory(prefix='self-check-', dir=str(project.state)) as directory:
        base = Path(directory)
        for name in ('supplier', 'curator', 'taker'):
            (base / name).mkdir()
        supplier, curator, taker = [Project(base / name, initialize=True) for name in ('supplier', 'curator', 'taker')]
        bundle = supplier.root / 'invented-pattern'
        (bundle / 'kit').mkdir(parents=True)
        record = {
            'schema_version': 1, 'standard_version': '1.0', 'id': 'invented-pattern',
            'origin': {'project': 'Invented self-check', 'situation': 'Synthetic setup', 'environment': 'Offline',
                       'developed_on': '2026-01-01', 'development_kind': 'invented', 'development_account': 'Invented exercise only.'},
            'applicability': {'fits': ['Synthetic setup'], 'does_not_fit': [], 'prerequisites': [], 'adaptations': []},
            'evidence': [{'claim': 'Synthetic demonstration', 'outcome': 'success', 'project': 'Invented self-check',
                          'situation': 'Invented exercise', 'occurred_on': '2026-01-01', 'locators': ['invented:one'],
                          'verification': {'status': 'unchecked', 'checked_on': None, 'checked_by': None,
                                           'scope': None, 'result': None, 'reason': 'Invented, not real evidence.'}}],
            'limits': ['Synthetic only'],
            'evolution': {'origin_state': 'unknown', 'assessed_on': '2026-01-01', 'locators': [],
                          'deltas': [], 'reason': 'Invented exercise'},
            'assets': [{'path': 'kit/steps.txt', 'kind': 'checklist', 'purpose': 'Invented setup',
                        'adaptations': [], 'dependencies': [], 'context_ref': 'PATTERN.md#/applicability'}]}
        text = '# Invented setup\n\n' + ''.join('## ' + h + '\n\nInvented setup exercise.\n\n' for h, _ in SECTIONS)
        (bundle / 'PATTERN.md').write_text(text + '## Context record\n\n```json\n' + dumps(record) + '\n```\n', encoding='utf-8')
        (bundle / 'kit/steps.txt').write_text('Fill <setup>.\n', encoding='utf-8')
        published = offer(supplier, bundle)
        with Store(curator) as store:
            first = store.ingest({'published_parts': [str(supplier.root / 'published')], '_base': base})
            warm = store.ingest({'published_parts': [str(supplier.root / 'published')], '_base': base})
            store.decide('admit', published['id'], '*', 'Synthetic reviewer', 'Invented exercise only')
            store.publish('synthetic')
        catalogue = Catalogue(curator.index)
        asked = catalogue.ask('setup', taker.id)
        selected = catalogue.select([published['id']], taker.id)
        okay = (not first['errors'] and first['counts']['new_contents'] == 1 and warm['counts']['checks'] == 0
                and len(asked['offers']) == 1 and bool(selected['selected'][0]['pattern']))
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'python_floor_met': sys.version_info >= (3, 9), 'synthetic_publication_flow': okay,
            'notice': 'This machine only; synthetic evidence proves no real savings or operation on other platforms.'}


def execute(args, project, listing=None):
    name = args.command
    if name == 'init':
        return {'project_id': project.id, 'records': str(project.state), 'index': str(project.index)}, 0
    if name == 'check':
        path = project.input(args.path)
        inventory(path)
        result = compact_check(check_contribution(path))
        return result, 2 if result['read_error'] else (0 if result['presence_complete'] else 1)
    if name == 'offer':
        return offer(project, args.path), 0
    if name == 'self-check':
        result = self_check(project)
        return result, 0 if result['synthetic_publication_flow'] else 1
    if name in {'ask', 'select'}:
        catalogue = Catalogue(args.catalogue)  # Resolve current index anew, even for an old candidate ID.
        declines = project.records('declines.jsonl')
        result = (catalogue.ask(args.task, project.id, declines, args.limit) if name == 'ask'
                  else catalogue.select(args.ids, project.id, declines))
        project.append('catalogues.jsonl', {'at': time.time(), 'index': str(ordinary_path(args.catalogue)),
                                           'manifest_sha256': catalogue.hash})
        return result, 0
    if name in {'decline', 'log-use'}:
        identity(args.id)
        if name == 'decline':
            if not args.actor.strip() or not args.reason.strip():
                raise ValueError('Supply a nonempty actor and reason')
            result = {'at': time.time(), 'id': args.id, 'actor': args.actor, 'reason': args.reason,
                      'undo': args.undo, 'project_id': project.id}
            project.append('declines.jsonl', result)
        else:
            if not args.outcome.strip():
                raise ValueError('Supply a nonempty outcome')
            result = {'id': args.id, 'outcome': args.outcome, 'saving_note': args.saving_note,
                      'notice': 'Caller-reported use and estimate, not independently verified.'}
            project.append('uses.jsonl', {'at': time.time(), **result})
        return result, 0
    with Store(project) as store:
        if name == 'ingest':
            result = store.ingest(listing)
            return result, 1 if result['partial_failure'] else 0
        if name == 'decisions':
            return store.inspect(args.id), 0
        if name == 'publish-catalogue':
            return store.publish(args.edition), 0
        scope = getattr(args, 'project_id', None) or '*'
        return store.decide(name, args.id, scope, args.actor, args.reason,
                            getattr(args, 'into', None), args.undo), 0


def render(result, json_mode):
    if json_mode or 'problems' not in result:
        return dumps(result) + '\n'
    lines = list(result['limitations'])
    lines.extend('{state}: {field}: {message}'.format(**p) for p in result['problems'])
    lines.append('Human review required:')
    lines.extend('- ' + item['message'] for item in result['review_required'])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    start = time.perf_counter()
    args = parser().parse_args(argv)
    project = None
    try:
        # A missing input list must do nothing, including creating cost/state records.
        listing = load_listing(args.published_parts) if args.command == 'ingest' else None
        if args.command == 'pack-capability':
            result, code = pack_capability(args.project, args.edition), 0
            project = None
        else:
            project = Project(args.project, initialize=args.command == 'init')
            result, code = execute(args, project, listing)
        output = render(result, args.json)
        details = {'at': time.time(), 'operation': args.command, 'output_bytes': len(output.encode('utf-8')),
                   'seconds': round(time.perf_counter() - start, 6), 'status': code,
                   'ids': [o['id'] for o in result.get('offers', [])] or getattr(args, 'ids',
                           [args.id] if getattr(args, 'id', None) else []),
                   'catalogue_sha256': result.get('catalogue_sha256'), 'ingest': result.get('counts')}
        if project:
            if args.command in CURATOR:
                with Store(project) as store:
                    store.log(args.command, details)
            else:
                project.append('costs.jsonl', details)
        else:
            cost_path = ordinary_path(SOURCE / '.staging/costs.jsonl')
            # Packaging is maintenance in the developing source, never an edition operation.
            with cost_path.open('ab') as handle:
                handle.write((dumps(details) + '\n').encode())
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write(output.encode('utf-8'))
        else:
            sys.stdout.write(output)
        return code
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
        message = dumps({'error': str(error)}) + '\n'
        if project:
            details = {'at': time.time(), 'operation': args.command, 'status': 2,
                       'output_bytes': len(message.encode('utf-8')),
                       'seconds': round(time.perf_counter() - start, 6), 'failed': True}
            try:
                if args.command in CURATOR:
                    with Store(project) as store:
                        store.log(args.command, details)
                else:
                    project.append('costs.jsonl', details)
            except (OSError, ValueError, sqlite3.Error):
                pass  # Unwritable state cannot record its own failure; retain the original diagnostic.
        sys.stderr.write(message)
        return 2
