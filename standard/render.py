"""Generate instructions and skeleton: python -m standard.render [--check]."""
import argparse
import json
from pathlib import Path
from .definition import (CONDITIONS, CONTEXT_HEADING, DISCOVERY_LIMITS, NOTICE,
                         PREDICATES, RECORD, REVIEW_ITEMS, SECTIONS, STANDARD_VERSION)


def skeleton(schema):
    if 'constant' in schema:
        return schema['constant']
    if schema['type'] == 'object':
        return {key: skeleton(value) for key, value in schema['fields'].items()}
    if schema['type'] == 'list':
        return [skeleton(schema['item'])] if schema['minimum'] else []
    return None


def _fields(schema, prefix=''):
    lines = []
    for key, spec in schema.get('fields', {}).items():
        path = prefix + key
        detail = spec['description']
        if 'constant' in spec:
            detail += ' Value: ' + str(spec['constant']) + '.'
        if 'choices' in spec:
            detail += ' Values: ' + ', '.join(spec['choices']) + '.'
        if spec['type'] == 'list':
            detail += ' Minimum items: ' + str(spec['minimum']) + '.'
        lines.append('| `' + path + '` | ' + spec['type'] + ' | ' + detail + ' |')
        if spec['type'] == 'object':
            lines.extend(_fields(spec, path + '.'))
        elif spec['type'] == 'list' and spec['item']['type'] == 'object':
            lines.extend(_fields(spec['item'], path + '[].'))
    return lines


def documents():
    lines = ['# Contribution standard ' + STANDARD_VERSION, '', NOTICE, '',
             'Use Python 3.9 or newer. Run `python /path/to/clone/check_contribution.py /path/to/contribution` from any directory; add `--json` for machine-readable output.', '',
             'The command reads the supplied bundle without executing kits, following symlinks, fetching evidence or writing into projects. Exit 0 means complete recorded presence, 1 means incomplete or invalid material, and 2 means usage or read failure. Human review remains required after exit 0.', '',
             '## Bundle and explanation', '',
             'Use one lowercase kebab directory containing PATTERN.md and a kit directory with at least one ordinary deployable file. Declare every kit file once. Asset paths use forward slashes below kit/, with no absolute paths, traversal, symlinks or Windows-reserved names.', '',
             'Give PATTERN.md a level-one title and these first six level-two sections in order, each with a nonempty explanation. Additional sections may follow. Finish with one Context record section containing exactly one fenced JSON object. Nulls in the generated skeleton are blanks to complete, never evidence.', '']
    lines += ['- `' + heading + '`: ' + instruction for heading, instruction in SECTIONS]
    lines += ['', '## Full context', '', RECORD['description'], '',
              'The JSON does not duplicate title, summary, problem, mechanism or instructions. Empty lists mean none identified and require review. Null means unknown and prevents completeness except for verification details explicitly inapplicable to an unchecked or unavailable account.', '',
              '| Field | Type | Meaning |', '|---|---|---|']
    lines.extend(_fields(RECORD))
    lines += ['', '## Conditional requirements', '']
    for rule in CONDITIONS:
        lines += ['- Within `' + rule['path'] + '`, when `' + rule['when'][0] + '` is `' + rule['when'][1] + '`, supply ' + ', '.join('`' + p + '`' for p in rule['require']) + '. ' + ('May be null: ' + ', '.join('`' + p + '`' for p in rule['nullable']) + '.' if rule['nullable'] else '')]
    lines += ['- ' + rule['message'] for rule in PREDICATES]
    lines += ['', '## Discovery and integration', '',
              '`standard.check_contribution(path)` returns standard_version, record, discovery, checks, presence_complete, review_required, limitations and read_error. Checks contain rule_id, field, state (present/missing/invalid/unknown) and a message. Malformed JSON leaves record and discovery null. Missing fields and unknown values are never invented.', '',
              '`standard.discovery_record(record, pattern_text)` derives a screening projection from full context and the single authored explanation: title from its level-one heading, summary from the first required section and problem from the second. The checker adds presence_complete and has_unknowns. Retain the full record and bundle; discovery is lossy and cannot establish selection. Its context_ref is relative to the contribution. Store code owns hashes, supplying locations, admission state and comparisons.', '',
              'Discovery bounds: `' + json.dumps(DISCOVERY_LIMITS, sort_keys=True) + '`. Identifier and version strings are capped at 64 characters; asset kinds at four values of 32 characters. Fit conditions are truncated; limits and unknowns are flags. Serialized byte size also depends on character escaping.', '',
              '## Review obligations', '']
    lines += ['- **' + key + '**: ' + message for key, message in REVIEW_ITEMS]
    lines += ['', '## Maintaining this standard', '',
              'Edit standard/definition.py, then run `python -m standard.render` from the clone root. The field walker and conditional-rule interpreter consume that definition directly. `python -m standard.render --check` verifies generated artifacts. Tests use invented bundles.', '']
    template = ['# <Contribution title>', '']
    for heading, instruction in SECTIONS:
        template += ['## ' + heading, '', '<' + instruction + '>', '']
    template += ['## ' + CONTEXT_HEADING, '', '```json', json.dumps(skeleton(RECORD), indent=2), '```', '']
    return {'STANDARD.md': '\n'.join(lines), 'PATTERN.template.md': '\n'.join(template)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    stale = []
    for name, content in documents().items():
        target = root / name
        if args.check:
            if not target.exists() or target.read_text(encoding='utf-8') != content:
                stale.append(name)
        else:
            target.write_text(content, encoding='utf-8')
    if stale:
        parser.exit(1, 'Regenerate stale files: ' + ', '.join(stale) + '\n')


if __name__ == '__main__':
    main()
