"""Read-only presence checks. Python 3.9+, no external dependencies."""
import datetime
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

from .definition import (CONDITIONS, CONTEXT_HEADING, DISCOVERY_LIMITS,
                         NOTICE, PREDICATES, RECORD, REVIEW_ITEMS, SECTIONS, STANDARD_VERSION)


def _lookup(value, path):
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _slug(title):
    return re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')


def _sections(source):
    """Ignore headings inside fenced code; retain real section order and bodies."""
    sections, title, active, body, fence = [], '', None, [], None
    for line in source.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            if active is not None:
                body.append(line)
            continue
        if fence is None:
            if line.startswith('# ') and not title:
                title = line[2:].strip()
            if line.startswith('## '):
                if active is not None:
                    sections.append((active, '\n'.join(body).strip()))
                active, body = line[3:].strip(), []
                continue
        if active is not None:
            body.append(line)
    if active is not None:
        sections.append((active, '\n'.join(body).strip()))
    return title, sections


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _parse(source):
    title, sections = _sections(source)
    bodies = [body for heading, body in sections if heading == CONTEXT_HEADING]
    if len(bodies) != 1:
        raise ValueError('Supply exactly one final Context record section.')
    if not sections or sections[-1][0] != CONTEXT_HEADING:
        raise ValueError('Put Context record after all explanatory sections.')
    blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', bodies[0], re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('Supply exactly one fenced JSON object in Context record.')
    record = json.loads(blocks[0], object_pairs_hook=_pairs,
                        parse_constant=lambda token: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + token)))
    return record


def _safe_path(base, raw):
    if not isinstance(raw, str) or not raw or '\\' in raw:
        raise ValueError('Use a forward-slash relative path.')
    posix, windows = PurePosixPath(raw), PureWindowsPath(raw)
    parts = raw.split('/')
    if posix.is_absolute() or windows.drive or any(p in ('', '.', '..') for p in parts):
        raise ValueError('Absolute, empty and traversing paths are not allowed.')
    for part in parts:
        stem = part.split('.')[0].upper()
        reserved = stem in ('CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$') or bool(re.fullmatch(r'(?:COM|LPT)[1-9¹²³]', stem))
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((' ', '.')) or reserved:
            raise ValueError('Use portable Linux/Windows path components.')
    current = base
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlinks are not inspected.')
    return current


def _base_path(path):
    path = Path(path).absolute()
    for parent in [path] + list(path.parents):
        if parent.is_symlink():
            raise ValueError('Symlinks are not inspected.')
    return path


def discovery_record(record, pattern_text=''):
    """Bounded screening projection; caller must retain the full record and bundle.

    pattern_text supplies the single authored title/summary/problem. No extra facts
    are inserted into the record. The context locator is contribution-relative.
    """
    title, sections = _sections(pattern_text)
    prose = dict(sections)
    clip = lambda value, size: str(value)[:size]
    app = record.get('applicability') if isinstance(record, dict) else None
    app = app if isinstance(app, dict) else {}
    limits = DISCOVERY_LIMITS
    def conditions(key):
        values = app.get(key, [])
        if not isinstance(values, list):
            return []
        return [clip(item, limits['condition_chars']) for item in values[:limits[key]] if isinstance(item, str)]
    evidence = record.get('evidence', []) if isinstance(record, dict) else []
    evidence = evidence if isinstance(evidence, list) else []
    outcomes, statuses = set(), set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if item.get('outcome') in ('success', 'failure', 'mixed'):
            outcomes.add(item['outcome'])
        verification = item.get('verification')
        if isinstance(verification, dict) and verification.get('status') in ('checked', 'unchecked', 'unavailable'):
            statuses.add(verification['status'])
    assets = record.get('assets', []) if isinstance(record, dict) else []
    kinds = sorted({str(a.get('kind', ''))[:32] for a in assets if isinstance(a, dict)})[:4] if isinstance(assets, list) else []
    def bounded(name):
        value = record.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else str(value)[:64]
    return {'id': bounded('id'), 'schema_version': bounded('schema_version'),
            'standard_version': bounded('standard_version'),
            'title': clip(title, limits['title']),
            'summary': clip(prose.get(SECTIONS[0][0], ''), limits['summary']),
            'problem': clip(prose.get(SECTIONS[1][0], ''), limits['problem']),
            'fits': conditions('fits'), 'does_not_fit': conditions('does_not_fit'),
            'has_limits': bool(record.get('limits')), 'evidence_outcomes': sorted(outcomes),
            'verification_statuses': sorted(statuses), 'asset_kinds': kinds,
            'context_ref': 'PATTERN.md#context-record',
            'screening_only': True}


def check_contribution(path):
    checks = []
    result = {'standard_version': STANDARD_VERSION, 'record': None, 'discovery': None,
              'checks': checks, 'presence_complete': False,
              'review_required': [{'rule_id': key, 'message': message} for key, message in REVIEW_ITEMS],
              'limitations': [NOTICE, 'Evidence locators and reported verification are not independently verified.'],
              'read_error': False}
    def report(rule, field, state, message):
        checks.append({'rule_id': rule, 'field': field, 'state': state, 'message': message})
    try:
        base = _base_path(path)
        if not base.is_dir():
            raise ValueError('Supply a contribution directory.')
        pattern = _safe_path(base, 'PATTERN.md')
        source = pattern.read_text(encoding='utf-8')
    except (OSError, ValueError, UnicodeError) as error:
        report('read', 'PATTERN.md', 'invalid', str(error))
        result['read_error'] = True
        return result
    title, sections = _sections(source)
    report('title', 'PATTERN.md', 'present' if title else 'missing', 'Supply a level-one contribution title.')
    names = [name for name, body in sections]
    previous = -1
    for heading, instruction in SECTIONS:
        positions = [i for i, name in enumerate(names) if name == heading]
        state = 'present'
        if not positions:
            state = 'missing'
        elif len(positions) != 1 or positions[0] <= previous:
            state = 'invalid'
        elif not sections[positions[0]][1].strip():
            state = 'missing'
        if positions:
            previous = positions[0]
        report('section', heading, state, instruction + ' Use the required order and one occurrence per section.')
    # Additional sections belong after the six required sections.
    expected = [heading for heading, _ in SECTIONS]
    if names[:len(expected)] != expected:
        report('section_order', 'PATTERN.md', 'invalid', 'Keep the six required sections first, in their defined order.')
    try:
        record = _parse(source)
    except (ValueError, TypeError) as error:
        report('json', 'Context record', 'invalid', str(error))
        return result
    if not isinstance(record, dict):
        report('json', 'Context record', 'invalid', 'Context must be a JSON object.')
        return result
    result['record'] = record
    nullable = set()
    required = []
    for rule in CONDITIONS:
        target = rule['path']
        if target.endswith('[]'):
            items = record.get(target[:-2], [])
            contexts = [(target[:-2] + '[' + str(i) + ']', v) for i, v in enumerate(items)] if isinstance(items, list) else []
        else:
            contexts = [(target, record.get(target))]
        for prefix, context in contexts:
            if _lookup(context, rule['when'][0]) == rule['when'][1]:
                nullable.update(prefix + '.' + item for item in rule['nullable'])
                required.extend((prefix + '.' + item, _lookup(context, item)) for item in rule['require'])
    def validate(value, schema, field):
        if value is None:
            report('field', field, 'present' if field in nullable else 'unknown', schema['description'])
            return
        kind = schema['type']
        valid = True
        if kind == 'object':
            valid = isinstance(value, dict)
        elif kind == 'list':
            valid = isinstance(value, list) and len(value) >= schema['minimum']
        elif kind == 'integer':
            valid = type(value) is int
        else:
            valid = isinstance(value, str) and bool(value.strip())
        if valid and 'constant' in schema:
            valid = value == schema['constant']
        if valid and 'choices' in schema:
            valid = value in schema['choices']
        if valid and kind == 'date':
            try:
                valid = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))
                datetime.date.fromisoformat(value)
            except ValueError:
                valid = False
        if valid and kind == 'id':
            valid = bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value)) and value == base.name
        if valid and kind == 'asset_path':
            try:
                file = _safe_path(base, value)
                valid = value.startswith('kit/') and file.is_file()
            except (ValueError, OSError):
                valid = False
        if valid and kind == 'context_ref':
            valid = False
            if value.startswith('PATTERN.md#/'):
                current = record
                try:
                    for part in value[len('PATTERN.md#/'):].split('/'):
                        part = part.replace('~1', '/').replace('~0', '~')
                        current = current[int(part)] if isinstance(current, list) else current[part]
                    valid = current is not None
                except (KeyError, IndexError, ValueError, TypeError):
                    pass
            elif value.startswith('PATTERN.md#'):
                valid = value[len('PATTERN.md#'):] in {_slug(name) for name in names}
        report('field', field or '$', 'present' if valid else 'invalid', schema['description'])
        if kind == 'object' and isinstance(value, dict):
            for key, child in schema['fields'].items():
                name = field + '.' + key if field else key
                if key not in value:
                    report('field', name, 'missing', child['description'])
                else:
                    validate(value[key], child, name)
            for key in value.keys() - schema['fields'].keys():
                report('field', field + '.' + key, 'invalid', 'Unknown field; use the supported record version.')
        if kind == 'list' and isinstance(value, list):
            for i, item in enumerate(value):
                validate(item, schema['item'], field + '[' + str(i) + ']')
    validate(record, RECORD, '')
    for field, value in required:
        if not value:
            report('conditional', field, 'missing', 'Supply the details required by the reported state.')
    for rule in PREDICATES:
        values = record.get(rule['path'])
        good = isinstance(values, list) and any(isinstance(item, dict) and item.get(rule['field']) == rule['equals'] for item in values)
        report('predicate', rule['path'], 'present' if good else 'missing', rule['message'])
    # The bundle contains only PATTERN.md and kit/. Never follow symlinks.
    actual_assets = set()
    try:
        for entry in base.iterdir():
            if entry.name not in ('PATTERN.md', 'kit') or entry.is_symlink():
                report('layout', entry.name, 'invalid', 'Keep only PATTERN.md and a regular kit directory in a contribution.')
        kit = _safe_path(base, 'kit')
        if not kit.is_dir():
            report('kit', 'kit/', 'missing', 'Supply a kit directory with at least one deployable file.')
        else:
            pending = [kit]
            while pending:
                for entry in pending.pop().iterdir():
                    rel = entry.relative_to(base).as_posix()
                    _safe_path(base, rel)
                    if entry.is_dir():
                        pending.append(entry)
                    elif entry.is_file():
                        actual_assets.add(rel)
                    else:
                        report('kit', rel, 'invalid', 'Use ordinary deployable files.')
            if not actual_assets:
                report('kit', 'kit/', 'missing', 'Supply at least one deployable file.')
        assets = record.get('assets', [])
        declared = [a.get('path') for a in assets if isinstance(a, dict) and isinstance(a.get('path'), str)] if isinstance(assets, list) else []
        for extra in actual_assets - set(declared):
            report('asset_inventory', extra, 'missing', 'Describe this supplied file in assets, including its context reference.')
        if len(declared) != len(set(declared)):
            report('asset_inventory', 'assets', 'invalid', 'List each asset once.')
    except (OSError, ValueError) as error:
        report('kit', 'kit/', 'invalid', str(error))
        if isinstance(error, OSError):
            result['read_error'] = True
    complete = all(item['state'] == 'present' for item in checks)
    result['presence_complete'] = complete
    result['discovery'] = discovery_record(record, source)
    result['discovery']['presence_complete'] = complete
    result['discovery']['has_unknowns'] = any(item['state'] == 'unknown' for item in checks)
    return result
