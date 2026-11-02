"""The one command, callable from any working directory."""
import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

from standard import check_contribution
from .engine import Store, compact_check, dumps, ordinary_path, project_key

CLONE = Path(__file__).absolute().parents[1]


def parser():
    command = argparse.ArgumentParser(description='Find project know-how with its context, using local files only.')
    sub = command.add_subparsers(dest='command', required=True)
    for name in ('ask', 'select', 'check', 'decline', 'exclude', 'admit', 'merge', 'retire',
                 'self-check', 'configure', 'decisions', 'log-use'):
        p = sub.add_parser(name)
        p.add_argument('--json', action='store_true', help='Machine-readable response')
        if name in ('ask', 'select', 'decline', 'exclude', 'log-use'):
            p.add_argument('--project', help='Explicit calling/project scope directory')
        if name == 'ask':
            p.add_argument('--task', required=True)
            p.add_argument('--limit', type=int, default=5, help='1–20 candidates, within 12000 response-item bytes')
        if name in ('select', 'merge'):
            p.add_argument('ids', nargs='+', help='Full content SHA-256 IDs')
        elif name in ('decline', 'exclude', 'admit', 'retire', 'log-use'):
            p.add_argument('id', help='Full content SHA-256 ID')
        elif name == 'decisions':
            p.add_argument('id', nargs='?')
        elif name == 'check':
            p.add_argument('path')
        if name in ('decline', 'exclude', 'admit', 'merge', 'retire'):
            p.add_argument('--reason', required=True)
            p.add_argument('--actor', required=True, help='Attribution; not authentication')
            p.add_argument('--undo', action='store_true', help='Append a reasoned reversal')
        if name == 'merge':
            p.add_argument('--into', required=True)
        if name == 'exclude':
            p.add_argument('--all', action='store_true')
        if name == 'configure':
            p.add_argument('--projects-folder', required=True)
        if name == 'log-use':
            p.add_argument('--outcome', required=True)
            p.add_argument('--saving-note', default='')
    return command


def configure(state, value):
    root = ordinary_path(value)
    if not root.is_dir():
        raise ValueError('Projects folder must be an existing directory')
    state.mkdir(parents=True, exist_ok=True)
    setting = ordinary_path(state / 'settings.json')
    # Atomic replacement; each root has an independent namespace.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(state), delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(dumps({'projects_folder': str(root)}))
    try:
        temporary.replace(setting)
    finally:
        if temporary.exists():
            temporary.unlink()
    return root


def load_root(state):
    setting = ordinary_path(state / 'settings.json')
    if not setting.exists():
        if not sys.stdin.isatty():
            raise ValueError('Where is the projects folder? Run configure --projects-folder PATH; no search was performed')
        return configure(state, input('Projects folder (explicit directory; no search): ').strip())
    root = ordinary_path(json.loads(setting.read_text(encoding='utf-8'))['projects_folder'])
    if not root.is_dir():
        raise ValueError('Configured projects folder is unavailable; configure it explicitly')
    return root


def self_check(state):
    """Exercise the machine with isolated invented files, leaving real decisions alone."""
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='self-check-', dir=str(state)) as directory:
        base = Path(directory)
        root = base / 'projects'
        project = root / 'new-project'
        project.mkdir(parents=True)
        source = root / 'source/innovations/example'
        (source / 'kit').mkdir(parents=True)
        (source / 'PATTERN.md').write_text('# Invented self-check\n\nSynthetic machine exercise.\n', encoding='utf-8')
        (source / 'kit/example.txt').write_text('Replace <example>.\n', encoding='utf-8')
        with Store(base / 'state', root) as store:
            cold, errors = store.gather()
            warm, _ = store.gather()
            identity = store.db.execute('SELECT id FROM bundles').fetchone()[0]
            own = project_key(root, source.parents[1])
            selection = store.select([identity], own)
            isolated = store.ask('invented', project_key(root, project))
            okay = (not errors and cold['new_contents'] == 1 and warm['checks'] == 0
                    and bool(selection['selected'][0]['pattern']) and not isolated['offers'])
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'python_floor_met': sys.version_info >= (3, 9), 'local_write_and_sqlite': True,
            'synthetic_gather_check_select': okay,
            'configured': (state / 'settings.json').is_file(),
            'notice': 'Tests this machine only; does not establish operation on another OS or Python version.'}


def execute(args, state):
    name = args.command
    code = 0
    if name == 'configure':
        root = configure(state, args.projects_folder)
        store = Store(state, root)
        result = {'projects_folder': str(root), 'state': str(store.home),
                  'notice': 'A changed root is a new local namespace; prior decisions are not inherited.'}
        return result, code, store, None
    if name == 'self-check':
        result = self_check(state)
        return result, 0 if result['synthetic_gather_check_select'] else 1, None, None
    if name == 'check':
        # Preflight independently: the standard itself may read otherwise prohibited names.
        path = ordinary_path(args.path)
        from .engine import secret, linked
        for folder in [path, *path.parents]:
            if secret(folder.name):
                raise ValueError('Prohibited input path')
        def inspect(folder):
            for entry in folder.iterdir():
                if secret(entry.name):
                    raise ValueError('Bundle contains a prohibited entry; no check was run')
                if linked(entry):
                    raise ValueError('Bundle contains a link; no check was run')
                if entry.is_dir():
                    inspect(entry)
        if path.is_dir():
            inspect(path)
        result = compact_check(check_contribution(path))
        code = 2 if result['read_error'] else (0 if result['presence_complete'] else 1)
        return result, code, None, None
    root = load_root(state)
    store = Store(state, root)
    try:
        project = None
        if name in ('ask', 'select', 'decline', 'log-use'):
            project = project_key(root, args.project)
        if name in ('ask', 'select'):
            scan, warnings = store.gather()
            result = (store.ask(args.task, project, args.limit) if name == 'ask'
                      else store.select(args.ids, project))
            result['gather'] = scan
            result['warnings'] = warnings
        elif name == 'decisions':
            result = {'events': store.events(args.id)}
        elif name == 'log-use':
            store.get(args.id)
            if not args.outcome.strip():
                raise ValueError('Supply a nonempty outcome')
            result = {'id': args.id, 'project': project, 'outcome': args.outcome,
                      'saving_note': args.saving_note,
                      'notice': 'Caller-reported use and saving; not independently verified.'}
        else:
            scope = '*'
            if name == 'exclude':
                if args.all == bool(args.project):
                    raise ValueError('Exclude requires exactly one of --all or --project PATH')
                if args.project:
                    scope = project_key(root, args.project)
            if name == 'decline':
                scope = project
            result = store.decide(name, args.ids if name == 'merge' else [args.id], scope,
                                  args.actor, args.reason, getattr(args, 'into', None), args.undo)
        return result, code, store, project
    except BaseException:
        store.__exit__(*sys.exc_info())
        raise


def render(result, json_mode):
    # Check always contains only absent/invalid/unknown items, plus the review duties.
    # All other responses share a compact, parseable representation in either mode.
    if json_mode or 'problems' not in result:
        return dumps(result) + '\n'
    lines = list(result['limitations'])
    for item in result['problems']:
        lines.append('{state}: {field}: {message}'.format(**item))
    lines.append('Human review required:')
    lines.extend('- ' + item['message'] for item in result['review_required'])
    return '\n'.join(lines) + '\n'


def main(argv=None, state=None):
    start = time.perf_counter()
    args = parser().parse_args(argv)
    store = None
    try:
        state = ordinary_path(state or CLONE / '.local')
        result, code, store, project = execute(args, state)
        output = render(result, args.json)
        details = {'output_bytes': len(output.encode('utf-8')),
                   'seconds': round(time.perf_counter() - start, 6),
                   'ids': ([item['id'] for item in result['offers']] if args.command == 'ask' else
                           getattr(args, 'ids', [args.id] if hasattr(args, 'id') else [])),
                   'gather': result.get('gather')}
        if args.command == 'log-use':
            details.update(outcome=args.outcome, saving_note=args.saving_note)
        if store:
            store.log(args.command, project, details)
            store.__exit__(None, None, None)
            store = None
        else:
            state.mkdir(parents=True, exist_ok=True)
            # Checks/self-checks do not demand projects-folder configuration.
            with ordinary_path(state / 'command-uses.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(dumps({'at': time.time(), 'operation': args.command, **details}) + '\n')
        # Write encoded UTF-8 without platform newline conversion so byte accounting is exact.
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write(output.encode('utf-8'))
        else:
            sys.stdout.write(output)
        return code
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        if store:
            store.__exit__(*sys.exc_info())
        print(dumps({'error': str(error)}), file=sys.stderr)
        return 2
