"""Content snapshots, local decisions and task screening. No project writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time

from standard import STANDARD_VERSION, check_contribution

PRUNE = {'.git', '.hg', '.svn', '.ssh', '.aws', '__pycache__',
         '.venv', 'venv', 'node_modules'}


def dumps(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), sort_keys=True)


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def ordinary_path(value):
    """Absolute lexical path; reject links/reparse points in every existing ancestor."""
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    for part in [*reversed(path.parents), path]:
        if secret(part.name):
            raise ValueError('Prohibited path component')
        if part.exists() or part.is_symlink():
            if linked(part):
                raise ValueError('Symlinks/reparse points are not supported')
    return path


def secret(name):
    lower = name.lower()
    return lower == '.env' or lower.startswith('.env.') or lower.endswith('.pem') or lower in {'.ssh', '.aws'}


def portable(name):
    stem = name.split('.')[0].upper()
    return (name not in {'.', '..'} and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            and not name.endswith((' ', '.')) and stem not in
            {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(1, 10)),
             *('LPT' + str(i) for i in range(1, 10))})


def within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError('Project must be inside the configured projects folder')


def project_key(root, value=None, cwd=None):
    path = ordinary_path(value if value is not None else (cwd or Path.cwd()))
    within(path, root)
    if not path.is_dir():
        raise ValueError('Project must be an existing directory')
    if value is None:
        while not ((path / '.git').exists() or (path / 'innovations').is_dir()):
            if path == root:
                raise ValueError('No project marker; supply --project PATH explicitly')
            path = path.parent
    return os.path.normcase(str(path.relative_to(root))).replace(os.sep, '/') or '.'


def compact_check(result):
    return {
        'presence_complete': result['presence_complete'],
        'problems': [c for c in result['checks'] if c['state'] != 'present'],
        'review_required': result['review_required'],
        'limitations': result['limitations'], 'read_error': result['read_error'],
    }


def tokens(text):
    return set(re.findall(r'[^\W_]+', text.casefold(), re.UNICODE))


class Store:
    def __init__(self, state, root):
        self.root = ordinary_path(root)
        self.state = ordinary_path(state)
        namespace = hashlib.sha256(os.path.normcase(str(self.root)).encode('utf-8')).hexdigest()
        self.home = ordinary_path(self.state / 'namespaces' / namespace)
        self.home.mkdir(parents=True, exist_ok=True)
        self.bundles = ordinary_path(self.home / 'bundles')
        self.bundles.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(ordinary_path(self.home / 'catalog.sqlite')), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS bundles (
                id TEXT PRIMARY KEY, name TEXT, result TEXT, issues TEXT, standard TEXT);
            CREATE TABLE IF NOT EXISTS locations (
                path TEXT, id TEXT, project TEXT, current INTEGER,
                PRIMARY KEY(path,id));
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY, at REAL, operation TEXT, id TEXT,
                scope TEXT, actor TEXT, reason TEXT, target TEXT, undo INTEGER);
            CREATE TABLE IF NOT EXISTS uses (
                seq INTEGER PRIMARY KEY, at REAL, operation TEXT, project TEXT, details TEXT);
        ''')
        self.db.execute('BEGIN IMMEDIATE')

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind:
            self.db.rollback()
        else:
            self.db.commit()
        self.db.close()

    def get(self, identity):
        row = self.db.execute('SELECT * FROM bundles WHERE id=?', (identity,)).fetchone()
        if row is None:
            raise ValueError('Unknown content ID; use the full ID from ask')
        return dict(row)

    def bundle_path(self, row):
        return self.bundles / row['id'] / row['name']

    def snapshot(self, source):
        """Stage one stable read, hash framed paths/bytes, then publish immutable content."""
        stage = None
        files = {}
        directories = []
        issues = []
        hashed_bytes = 0
        digest = hashlib.sha256()
        name = source.name
        if not portable(name):
            raise ValueError('Nonportable contribution directory name')

        def frame(kind, relative, data=b''):
            for part in (kind.encode(), relative.encode('utf-8'), data):
                digest.update(len(part).to_bytes(8, 'big'))
                digest.update(part)

        def walk(folder, relative=''):
            nonlocal hashed_bytes
            try:
                entries = sorted(folder.iterdir(), key=lambda p: p.name)
            except OSError:
                issues.append({'path': relative, 'problem': 'Directory unreadable; snapshot is partial'})
                return
            for entry in entries:
                rel = relative + entry.name
                try:
                    if secret(entry.name) or entry.name in PRUNE:
                        issues.append({'path': '[withheld]', 'problem': 'Prohibited entry omitted; snapshot is partial'})
                        frame('withheld', rel)
                        continue
                    if not portable(entry.name) or linked(entry):
                        issues.append({'path': '[unsafe entry]', 'problem': 'Link or nonportable name omitted; snapshot is partial'})
                        frame('unsafe', rel)
                        continue
                    mode = entry.lstat().st_mode
                    if stat.S_ISDIR(mode):
                        frame('directory', rel)
                        directories.append(rel)
                        walk(entry, rel + '/')
                    elif stat.S_ISREG(mode):
                        before = entry.stat()
                        data = entry.read_bytes()
                        after = entry.stat()
                        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                                after.st_size, after.st_mtime_ns, after.st_ino):
                            issues.append({'path': rel, 'problem': 'Source changed during read; ask again'})
                        frame('file', rel, data)
                        hashed_bytes += len(data)
                        files[rel] = data
                    else:
                        issues.append({'path': rel, 'problem': 'Special file omitted; snapshot is partial'})
                        frame('special', rel)
                except OSError:
                    issues.append({'path': rel, 'problem': 'Entry unreadable; snapshot is partial'})
                    frame('unreadable', rel)
        try:
            walk(source)
            # Problems affect identity so a partial snapshot cannot borrow a complete check.
            frame('issues', '', dumps(issues).encode())
            identity = digest.hexdigest()
            row = self.db.execute('SELECT * FROM bundles WHERE id=?', (identity,)).fetchone()
            checked = 0
            if row is None:
                stage = Path(tempfile.mkdtemp(prefix='stage-', dir=str(self.bundles)))
                target = stage / name
                target.mkdir()
                for relative in directories:
                    (target / relative).mkdir(parents=True, exist_ok=True)
                for relative, data in files.items():
                    (target / relative).write_bytes(data)
                destination = self.bundles / identity
                if destination.exists():
                    # A prior interrupted transaction may leave a complete, unindexed snapshot.
                    shutil.rmtree(destination)
                stage.rename(destination)
                result = check_contribution(destination / name)
                self.db.execute('INSERT INTO bundles VALUES(?,?,?,?,?)',
                                (identity, name, dumps(result), dumps(issues), STANDARD_VERSION))
                checked = 1
            elif row['standard'] != STANDARD_VERSION:
                result = check_contribution(self.bundle_path(dict(row)))
                self.db.execute('UPDATE bundles SET result=?, standard=? WHERE id=?',
                                (dumps(result), STANDARD_VERSION, identity))
                checked = 1
            return identity, hashed_bytes, checked
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)

    def gather(self):
        start = time.perf_counter()
        counts = dict(collections=0, contributions=0, distinct_contents=0, copies=0,
                      hashed_bytes=0, checks=0, new_contents=0)
        errors = []
        seen = set()
        self.db.execute('UPDATE locations SET current=0')

        def collection(folder):
            counts['collections'] += 1
            key = project_key(self.root, folder.parent)
            try:
                entries = sorted(folder.iterdir(), key=lambda p: p.name)
            except OSError:
                errors.append('An innovations collection could not be read')
                return
            for entry in entries:
                try:
                    if secret(entry.name) or entry.name in PRUNE or linked(entry) or not entry.is_dir():
                        continue
                    old_count = self.db.execute('SELECT count(*) FROM bundles').fetchone()[0]
                    identity, size, checked = self.snapshot(entry)
                    counts['contributions'] += 1
                    counts['new_contents'] += self.db.execute('SELECT count(*) FROM bundles').fetchone()[0] - old_count
                    counts['hashed_bytes'] += size
                    counts['checks'] += checked
                    seen.add(identity)
                    self.db.execute('INSERT OR REPLACE INTO locations VALUES(?,?,?,1)',
                                    (entry.relative_to(self.root).as_posix(), identity, key))
                except (OSError, ValueError):
                    errors.append('A contribution could not be gathered safely')

        def visit(folder):
            try:
                entries = sorted(folder.iterdir(), key=lambda p: p.name)
            except OSError:
                errors.append('A projects directory could not be read')
                return
            for entry in entries:
                try:
                    if (secret(entry.name) or entry.name in PRUNE or entry == self.state
                            or linked(entry) or not entry.is_dir()):
                        continue
                    if entry.name == 'innovations':
                        collection(entry)
                        # A contribution is a bundle, not a nested projects container.
                    else:
                        visit(entry)
                except OSError:
                    errors.append('A projects directory could not be inspected')
        visit(self.root)
        counts['distinct_contents'] = len(seen)
        counts['copies'] = counts['contributions'] - len(seen)
        counts['retained_contents'] = self.db.execute('SELECT count(*) FROM bundles').fetchone()[0]
        counts['errors'] = len(errors)
        counts['seconds'] = round(time.perf_counter() - start, 6)
        return counts, errors[:8]

    def events(self, identity=None):
        if identity is not None:
            self.get(identity)
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM events' + (' WHERE id=?' if identity else '') + ' ORDER BY seq',
            (identity,) if identity else ())]

    def effective(self, identity):
        state = {}
        for event in self.events(identity):
            state[(event['operation'], event['scope'])] = event
        return state

    def active(self, state, operation, scope='*'):
        event = state.get((operation, scope))
        return event is not None and not event['undo']

    def blocked(self, identity, project, visited=None):
        # Restrictions on any merged predecessor also protect its surviving target.
        visited = set() if visited is None else visited
        if identity in visited:
            return False
        visited.add(identity)
        state = self.effective(identity)
        if (self.active(state, 'retire') or self.active(state, 'exclude')
                or self.active(state, 'exclude', project) or self.active(state, 'decline', project)):
            return True
        for row in self.db.execute("SELECT DISTINCT id FROM events WHERE operation='merge'"):
            event = self.effective(row['id']).get(('merge', '*'))
            if event and not event['undo'] and event['target'] == identity:
                if self.blocked(row['id'], project, visited):
                    return True
        return False

    def eligibility(self, row, project):
        state = self.effective(row['id'])
        if self.blocked(row['id'], project) or self.active(state, 'merge'):
            return None
        check = json.loads(row['result'])
        admitted = (self.active(state, 'admit') and check['presence_complete']
                    and not json.loads(row['issues']))
        own = self.db.execute('SELECT 1 FROM locations WHERE id=? AND project=?',
                              (row['id'], project)).fetchone() is not None
        return 'admitted' if admitted else ('own-unadmitted' if own else None)

    def decide(self, operation, identities, scope, actor, reason, target=None, undo=False):
        if not actor.strip() or not reason.strip():
            raise ValueError('Supply nonempty --actor and --reason')
        for identity in identities:
            row = self.get(identity)
            check = json.loads(row['result'])
            if operation == 'admit' and not undo:
                if not check['presence_complete'] or json.loads(row['issues']):
                    raise ValueError('Admission requires complete presence and a complete safe snapshot; review remains required')
            if operation == 'merge' and not undo:
                other = self.get(target)
                if target == identity or self.active(self.effective(target), 'merge'):
                    raise ValueError('Merge target must be distinct and must not itself be merged')
                if self.eligibility(other, scope) != 'admitted':
                    raise ValueError('Merge target must be admitted and available')
                # A merged source cannot become a target, preventing cycles and ambiguous chains.
                if any(self.active(self.effective(r['id']), 'merge') and
                       self.effective(r['id'])[('merge', '*')]['target'] == identity
                       for r in self.db.execute("SELECT DISTINCT id FROM events WHERE operation='merge'")):
                    raise ValueError('Merge source is already a target; retire or undo its incoming merges first')
            self.db.execute('INSERT INTO events(at,operation,id,scope,actor,reason,target,undo) VALUES(?,?,?,?,?,?,?,?)',
                            (time.time(), operation, identity, scope, actor, reason, target, int(undo)))
        return {'operation': operation, 'ids': identities, 'scope': scope, 'undo': undo,
                'reason': reason, 'actor': actor, 'target': target}

    def ask(self, task, project, limit=5):
        if not task.strip():
            raise ValueError('Supply a nonempty task')
        if not 1 <= limit <= 20:
            raise ValueError('--limit must be between 1 and 20')
        query = tokens(task)
        ranked = []
        for raw in self.db.execute('SELECT * FROM bundles'):
            row = dict(raw)
            eligibility = self.eligibility(row, project)
            if eligibility is None:
                continue
            result = json.loads(row['result'])
            discovery = result['discovery'] or {}
            pattern = (self.bundle_path(row) / 'PATTERN.md')
            text = pattern.read_text(encoding='utf-8', errors='replace') if pattern.is_file() else ''
            matched = query & tokens(text)
            if not matched:
                continue
            score = len(matched)
            for field, weight in [('title', 5), ('problem', 3), ('fits', 3)]:
                score += weight * len(query & tokens(dumps(discovery.get(field, ''))))
            record = result['record'] or {}
            applicability = record.get('applicability')
            applicability = applicability if isinstance(applicability, dict) else {}
            negative = applicability.get('does_not_fit', [])
            item = {'id': row['id'], 'name': row['name'], 'status': eligibility, 'discovery': discovery,
                    'match_terms': sorted(matched)[:12], 'negative_condition_terms': sorted(query & tokens(dumps(negative)))[:12],
                    'screening_only': True, 'projection_is_lossy': True,
                    'check': compact_check(result) if eligibility == 'own-unadmitted' else None,
                    'snapshot_issues': json.loads(row['issues'])[:3],
                    'snapshot_issue_count': len(json.loads(row['issues']))}
            ranked.append((-score, row['id'], item))
        ranked.sort(key=lambda item: (item[0], item[1]))
        offered = []
        for _, _, item in ranked[:limit]:
            # Own diagnostics can be large; full check/select supplies all problems.
            if item['check']:
                problems = item['check']['problems']
                item['check'] = {'presence_complete': item['check']['presence_complete'],
                                 'problems': problems[:3], 'problem_count': len(problems)}
            if len(dumps(offered + [item]).encode('utf-8')) > 12000:
                break
            offered.append(item)
        return {'project': project, 'offers': offered, 'matching': len(ranked),
                'omitted': len(ranked) - len(offered), 'offer_budget_bytes': 12000,
                'notice': 'Screening only. Select candidates to read full context; lexical matches do not prove fit.'}

    def select(self, identities, project):
        selected = []
        for identity in identities:
            row = self.get(identity)
            eligibility = self.eligibility(row, project)
            if eligibility is None:
                raise ValueError('Content is not available to this project; ask again for current offers')
            path = self.bundle_path(row)
            pattern = path / 'PATTERN.md'
            selected.append({'id': identity, 'status': eligibility, 'bundle': str(path),
                             'pattern': pattern.read_text(encoding='utf-8', errors='replace') if pattern.is_file() else None,
                             'check': json.loads(row['result']), 'snapshot_issues': json.loads(row['issues']),
                             'locations': [dict(r) for r in self.db.execute(
                                 'SELECT path,project,current FROM locations WHERE id=? ORDER BY path', (identity,))],
                             'decisions': self.events(identity)})
        return {'project': project, 'selected': selected,
                'notice': 'Read full context and assets before applying. No kit was executed or copied to the project.'}

    def log(self, operation, project, details):
        self.db.execute('INSERT INTO uses(at,operation,project,details) VALUES(?,?,?,?)',
                        (time.time(), operation, project, dumps(details)))
