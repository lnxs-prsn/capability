"""Curator-owned retention and decisions; read-only published catalogue access."""
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from standard import check_contribution, STANDARD_VERSION
from .publication import (below, capture, content_id, dumps, envelope, identity,
                          install, inventory, loads, ordinary_path, parse_manifest, portable,
                          project_id, read_bytes, read_index, sha, verified_file, write_index)


def compact_check(result):
    return {'presence_complete': result['presence_complete'],
            'problems': [c for c in result['checks'] if c['state'] != 'present'],
            'review_required': result['review_required'], 'limitations': result['limitations'],
            'read_error': result['read_error']}


def tokens(text):
    return set(re.findall(r'[^\W_]+', text.casefold(), re.UNICODE))


def offer(project, source):
    source = project.input(source)
    files = capture(source)
    result = check_contribution(source)
    if not result['presence_complete']:
        raise ValueError('Offer requires complete recorded presence; run check and review first')
    cid = content_id(files)
    published = {'bundle/' + source.name + '/' + name: data for name, data in files.items()}
    manifest = envelope('offer', published, {'content_id': cid, 'name': source.name,
                                           'standard_version': STANDARD_VERSION})
    mid = sha((dumps(manifest) + '\n').encode())
    destination = below(project.root / 'published', 'knowhow/offers/' + mid)
    with tempfile.TemporaryDirectory(dir=str(project.state), prefix='offer-check-') as stage:
        bundle = Path(stage) / source.name
        for name, data in files.items():
            target = below(bundle, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not check_contribution(bundle)['presence_complete']:
            raise ValueError('Staged offer does not meet the standard')
    block = read_index(project.index)
    if block['project_id'] != project.id:
        raise ValueError('Local and published identity conflict')
    install(destination, 'OFFER.json', manifest, published)
    ref = {'path': 'knowhow/offers/' + mid + '/OFFER.json', 'sha256': mid}
    if ref not in block['offers']:
        block['offers'].append(ref)
    write_index(project.index, block)
    return {'id': cid, 'manifest_sha256': mid, 'offer': str(destination),
            'notice': 'Presence is complete; truth, fitness and admission require review.'}


class Policy:
    def effective(self, cid):
        if getattr(self, '_states', None) is None:
            self._states, self._incoming = {}, {}
            for event in self.events():
                self._states.setdefault(event['id'], {})[(event['operation'], event['scope'])] = event
            for source, state in self._states.items():
                merge = state.get(('merge', '*'))
                if merge and not merge['undo']:
                    self._incoming.setdefault(merge['target'], []).append(source)
        return self._states.get(cid, {})

    @staticmethod
    def active(state, operation, scope='*'):
        event = state.get((operation, scope))
        return event is not None and not event['undo']

    def blocked(self, cid, project, declines=(), visited=None):
        visited = set() if visited is None else visited
        if cid in visited:
            return False
        visited.add(cid)
        state = self.effective(cid)
        if (self.active(state, 'retire') or self.active(state, 'exclude')
                or self.active(state, 'exclude', project)):
            return True
        local = [e for e in declines if e['id'] == cid]
        if local and not local[-1]['undo']:
            return True
        for source in self._incoming.get(cid, []):
            if self.blocked(source, project, declines, visited):
                return True
        return False

    def eligible(self, cid, project, declines=()):
        state = self.effective(cid)
        return (self.active(state, 'admit') and not self.active(state, 'merge')
                and not self.blocked(cid, project, declines))


class Store(Policy):
    def __init__(self, project):
        self.project = project
        self.home = ordinary_path(project.state / 'curator')
        self.home.mkdir(parents=True, exist_ok=True)
        self.bundles = ordinary_path(self.home / 'offers')
        self.db = sqlite3.connect(str(ordinary_path(self.home / 'catalog.sqlite')), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS bundles(id TEXT PRIMARY KEY, name TEXT, result TEXT, manifest TEXT);
            CREATE TABLE IF NOT EXISTS origins(project TEXT, path TEXT, offer TEXT, id TEXT, current INTEGER,
                PRIMARY KEY(project,path,offer));
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, path TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at REAL, operation TEXT,
                id TEXT, scope TEXT, actor TEXT, reason TEXT, target TEXT, undo INTEGER);
            CREATE TABLE IF NOT EXISTS costs(seq INTEGER PRIMARY KEY, at REAL, operation TEXT, details TEXT);
        ''')
        self.db.execute('BEGIN IMMEDIATE')

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.db.rollback() if kind else self.db.commit()
        finally:
            self.db.close()

    def ids(self):
        return [r[0] for r in self.db.execute('SELECT id FROM bundles ORDER BY id')]

    def get(self, cid):
        identity(cid)
        row = self.db.execute('SELECT * FROM bundles WHERE id=?', (cid,)).fetchone()
        if row is None:
            raise ValueError('Unknown content ID')
        return dict(row)

    def events(self, cid=None):
        if cid is not None:
            self.get(cid)
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM events' + (' WHERE id=?' if cid else '') + ' ORDER BY seq', (cid,) if cid else ())]

    def origins(self, cid):
        return [dict(r) for r in self.db.execute('SELECT * FROM origins WHERE id=? ORDER BY project,path,offer', (cid,))]

    def retained_files(self, row):
        root = below(self.bundles, row['id'])
        expected = loads(row['manifest'])
        manifest = parse_manifest(root / 'OFFER.json', sha((dumps(expected) + '\n').encode()), 'offer')
        if set(inventory(root)) != set(manifest['files']) | {'OFFER.json'}:
            raise ValueError('Retained offer contains unlisted files')
        files = {n: verified_file(root, manifest, n) for n in manifest['files']}
        prefix = 'bundle/' + row['name'] + '/'
        if content_id({n[len(prefix):]: body for n, body in files.items()}) != row['id']:
            raise ValueError('Retained content identity mismatch')
        return files

    def inspect(self, cid=None):
        if cid is None:
            return {'contents': [{'id': i, 'name': self.get(i)['name'],
                                   'presence_complete': loads(self.get(i)['result'])['presence_complete']}
                                  for i in self.ids()], 'events': self.events(),
                    'known_projects': [dict(r) for r in self.db.execute('SELECT * FROM projects ORDER BY id')]}
        row = self.get(cid)
        root = below(self.bundles, cid)
        pattern = 'bundle/' + row['name'] + '/PATTERN.md'
        return {'id': cid, 'pattern': self.retained_files(row)[pattern].decode('utf-8'),
                'bundle': str(root / 'bundle' / row['name']), 'check': loads(row['result']),
                'origins': self.origins(cid), 'events': self.events(cid)}

    def ingest(self, listing):
        counts = {'publications': 0, 'unadvertised_parts': 0, 'offers': 0,
                  'new_contents': 0, 'checks': 0, 'read_bytes': 0}
        errors, roots, claims, blocks = [], set(), {}, {}
        for value in listing['published_parts']:
            try:
                root = ordinary_path(listing['_base'] / value)
                roots.add(str(root))
                block = read_index(root / 'INDEX.md', optional=True)
                if block is None:
                    counts['unadvertised_parts'] += 1
                    continue
                pid = block['project_id']
                if pid in claims and claims[pid] != root:
                    raise ValueError('Conflicting published roots claim one project UUID')
                claims[pid] = root
                blocks[str(root)] = block
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({'published_part': value, 'error': str(exc)})
        if any('Conflicting published roots' in e['error'] for e in errors):
            return {'counts': counts, 'errors': errors, 'partial_failure': True}
        self.db.execute('UPDATE origins SET current=0')
        for root_name in sorted(roots):
            root = Path(root_name)
            if root_name not in blocks:
                continue
            try:
                block = blocks[root_name]
                pid = block['project_id']
                self.db.execute('INSERT OR REPLACE INTO projects VALUES(?,?)', (pid, root_name))
                self.db.execute('UPDATE origins SET current=0 WHERE project=?', (pid,))
                counts['publications'] += 1
                for ref in block['offers']:
                    try:
                        path = below(root, ref['path'])
                        manifest = parse_manifest(path, ref['sha256'], 'offer')
                        meta = manifest['metadata']
                        if (set(meta) != {'content_id', 'name', 'standard_version'}
                                or meta['standard_version'] != STANDARD_VERSION):
                            raise ValueError('Unsupported offer metadata/standard version')
                        cid, name = identity(meta['content_id']), meta['name']
                        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
                            raise ValueError('Invalid contribution slug')
                        prefix = 'bundle/' + name + '/'
                        if not manifest['files'] or any(not n.startswith(prefix) for n in manifest['files']):
                            raise ValueError('Offer inventory must contain only its bundle')
                        if set(inventory(path.parent)) != set(manifest['files']) | {path.name}:
                            raise ValueError('Offer has unlisted files')
                        data = {n: verified_file(path.parent, manifest, n) for n in manifest['files']}
                        if content_id({n[len(prefix):]: b for n, b in data.items()}) != cid:
                            raise ValueError('Content identity mismatch')
                        counts['read_bytes'] += sum(map(len, data.values()))
                        exists = self.db.execute('SELECT 1 FROM bundles WHERE id=?', (cid,)).fetchone()
                        retained = below(self.bundles, cid)
                        install(retained, 'OFFER.json', manifest, data)
                        if not exists:
                            result = check_contribution(retained / 'bundle' / name)
                            self.db.execute('INSERT INTO bundles VALUES(?,?,?,?)',
                                            (cid, name, dumps(result), dumps(manifest)))
                            counts['new_contents'] += 1
                            counts['checks'] += 1
                        self.db.execute('INSERT OR REPLACE INTO origins VALUES(?,?,?,?,1)',
                                        (pid, root_name, ref['sha256'], cid))
                        counts['offers'] += 1
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        errors.append({'published_part': root_name, 'error': str(exc)})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({'published_part': root_name, 'error': str(exc)})
        return {'counts': counts, 'errors': errors, 'partial_failure': bool(errors)}

    def decide(self, operation, cid, scope, actor, reason, target=None, undo=False):
        if not actor.strip() or not reason.strip():
            raise ValueError('Supply a nonempty actor and reason')
        row = self.get(cid)
        if operation == 'exclude' and scope != '*':
            project_id(scope)
            if self.db.execute('SELECT 1 FROM projects WHERE id=?', (scope,)).fetchone() is None:
                raise ValueError('Unknown project UUID; ingest its published index first')
        if operation == 'admit' and not undo:
            self.retained_files(row)
            if not loads(row['result'])['presence_complete']:
                raise ValueError('Admission requires complete recorded presence; semantic review remains required')
        if operation == 'merge' and not undo:
            self.get(target)
            if cid == target or not self.eligible(target, '*'):
                raise ValueError('Merge target must be distinct, admitted and available')
            if any(self.active(self.effective(i), 'merge') and
                   self.effective(i)[('merge', '*')]['target'] == cid for i in self.ids()):
                raise ValueError('Merge source already has incoming merges; undo them first')
        self.db.execute('INSERT INTO events(at,operation,id,scope,actor,reason,target,undo) VALUES(?,?,?,?,?,?,?,?)',
                        (time.time(), operation, cid, scope, actor, reason, target, int(undo)))
        self._states = None
        return {'operation': operation, 'id': cid, 'scope': scope, 'actor': actor,
                'reason': reason, 'target': target, 'undo': undo}

    def publish(self, edition):
        if not portable(edition):
            raise ValueError('Use a portable single-component edition name')
        files, items = {}, []
        included = {e['id'] for e in self.events() if e['operation'] == 'admit' and not e['undo']}
        included.update(e['id'] for e in self.events() if e['operation'] == 'merge')
        for cid in sorted(included):
            row = self.get(cid)
            result = loads(row['result'])
            for name, body in self.retained_files(row).items():
                files['contents/' + cid + '/' + name] = body
            check_path = 'contents/' + cid + '/CHECK.json'
            files[check_path] = (dumps(result) + '\n').encode()
            items.append({'id': cid, 'name': row['name'], 'discovery': result['discovery'],
                          'prefix': 'contents/' + cid + '/bundle/' + row['name'] + '/',
                          'check': check_path, 'origins': self.origins(cid)})
        files['CATALOGUE.json'] = (dumps({'format': 1, 'items': items, 'events': self.events(),
                                         'notice': 'Only published decisions apply; published bytes remain readable.'}) + '\n').encode()
        manifest = envelope('catalogue', files, {'edition': edition, 'curator_id': self.project.id})
        destination = below(self.project.root / 'published', 'knowhow/catalogues/' + edition)
        block = read_index(self.project.index)
        if block['project_id'] != self.project.id:
            raise ValueError('Local and published identity conflict')
        mid = install(destination, 'EDITION.json', manifest, files)
        block['catalogue'] = {'path': 'knowhow/catalogues/' + edition + '/EDITION.json', 'sha256': mid}
        write_index(self.project.index, block)
        return {'edition': edition, 'manifest_sha256': mid, 'catalogue': str(destination), 'contents': len(items)}

    def log(self, operation, details):
        self.db.execute('INSERT INTO costs(at,operation,details) VALUES(?,?,?)', (time.time(), operation, dumps(details)))


def load_listing(path):
    if path is None:
        raise ValueError('Missing list of published parts; supply --published-parts LIST.json; nothing was read or changed')
    path = ordinary_path(path)
    listing = loads(read_bytes(path))
    if (not isinstance(listing, dict) or listing.get('format') != 1
            or not isinstance(listing.get('published_parts'), list)
            or not all(isinstance(p, str) and p for p in listing['published_parts'])):
        raise ValueError('Expected format 1 and a published_parts list of directory locators')
    listing['_base'] = path.parent
    return listing


class Catalogue(Policy):
    def __init__(self, index):
        index = ordinary_path(index)
        block = read_index(index, optional=True)
        if block is None or 'catalogue' not in block:
            raise ValueError("This index names no catalogue; obtain a curator's published INDEX.md "
                             "naming a current catalogue and supply it with --catalogue. "
                             "To curate for yourself, follow OWNER.md. No fallback was used.")
        ref = block['catalogue']
        self.path = below(index.parent, ref['path'])
        self.hash = identity(ref['sha256'])
        self.manifest = parse_manifest(self.path, self.hash, 'catalogue')
        if self.manifest['metadata'].get('curator_id') != block['project_id']:
            raise ValueError('Catalogue curator identity conflicts with index')
        self.data = loads(verified_file(self.path.parent, self.manifest, 'CATALOGUE.json'))
        if self.data.get('format') != 1:
            raise ValueError('Unsupported catalogue index')
        self.items = {identity(item['id']): item for item in self.data['items']}
        if len(self.items) != len(self.data['items']):
            raise ValueError('Duplicate catalogue content identities')
        for cid, item in self.items.items():
            if (not isinstance(item['name'], str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', item['name'])
                    or item['prefix'] != 'contents/' + cid + '/bundle/' + item['name'] + '/'
                    or item['check'] != 'contents/' + cid + '/CHECK.json'):
                raise ValueError('Invalid catalogue content paths')

    def ids(self):
        return sorted(self.items)

    def get(self, cid):
        identity(cid)
        if cid not in self.items:
            raise ValueError('Content is absent from the current catalogue')
        return self.items[cid]

    def events(self, cid=None):
        return [e for e in self.data['events'] if cid is None or e['id'] == cid]

    def ask(self, task, project, declines=(), limit=5):
        if not task.strip() or not 1 <= limit <= 20:
            raise ValueError('Supply a nonempty task and a limit from 1 to 20')
        query, ranked = tokens(task), []
        for cid, row in self.items.items():
            if not self.eligible(cid, project, declines):
                continue
            discovery = row['discovery'] or {}
            searchable = [discovery.get(key, '') for key in
                          ('title', 'summary', 'problem', 'fits', 'does_not_fit', 'asset_kinds')]
            matched = query & tokens(dumps(searchable))
            if not matched:
                continue
            score = len(matched) + sum(weight * len(query & tokens(dumps(discovery.get(field, ''))))
                                       for field, weight in [('title', 5), ('problem', 3), ('fits', 3)])
            item = {'id': cid, 'status': 'admitted', 'discovery': discovery,
                    'match_terms': sorted(matched)[:12],
                    'negative_condition_terms': sorted(query & tokens(dumps(discovery.get('does_not_fit', []))))[:12],
                    'screening_only': True, 'projection_is_lossy': True}
            ranked.append((-score, cid, item))
        ranked.sort(key=lambda entry: (entry[0], entry[1]))
        offers = []
        for _, _, item in ranked[:limit]:
            if len(dumps(offers + [item]).encode()) > 12000:
                break
            offers.append(item)
        return {'project': project, 'catalogue_sha256': self.hash, 'offers': offers,
                'matching': len(ranked), 'omitted': len(ranked) - len(offers), 'offer_budget_bytes': 12000,
                'notice': 'Screening only; select full context before deciding fitness. Lexical matching can miss synonyms.'}

    def select(self, ids, project, declines=()):
        selected = []
        for cid in ids:
            row = self.get(cid)
            if not self.eligible(cid, project, declines):
                raise ValueError('Content is not available to this project under current policy')
            prefix = row['prefix']
            bundle = below(self.path.parent, prefix.rstrip('/'))
            expected = {n[len(prefix):] for n in self.manifest['files'] if n.startswith(prefix)}
            if set(inventory(bundle)) != expected:
                raise ValueError('Selected bundle contains unlisted files')
            files = {n[len(prefix):]: verified_file(self.path.parent, self.manifest, n)
                     for n in self.manifest['files'] if n.startswith(prefix)}
            if content_id(files) != cid:
                raise ValueError('Selected content identity mismatch')
            check = loads(verified_file(self.path.parent, self.manifest, row['check']))
            selected.append({'id': cid, 'pattern': files['PATTERN.md'].decode('utf-8'),
                             'check': check, 'bundle': str(bundle),
                             'origins': row['origins'], 'decisions': self.events(cid)})
        return {'project': project, 'catalogue_sha256': self.hash, 'selected': selected,
                'notice': 'Inspection is not successful reuse. Read context, evidence, limits and adaptations; kits are never executed.'}
