"""Portable publication envelopes and project-owned records. No discovery scans."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import tempfile
import uuid

BEGIN = '<!-- knowhow:v1 -->'
END = '<!-- /knowhow:v1 -->'


def dumps(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def loads(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Expected a full lowercase SHA-256 identity')
    return value


def project_id(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Expected a canonical project UUID')
    return value


def secret(name):
    name = name.lower()
    return name == '.env' or name.startswith('.env.') or name.endswith('.pem') or name in {
        '.ssh', '.aws', '.git', '.hg', '.svn', '__pycache__', '.venv', 'node_modules'}


def portable(name):
    stem = name.split('.')[0].upper()
    return (bool(name) and name not in {'.', '..'} and not secret(name)
            and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name) and not name.endswith((' ', '.'))
            and stem not in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                             *('COM' + n for n in '123456789¹²³'), *('LPT' + n for n in '123456789¹²³')})


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def ordinary_path(value):
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    for item in [*reversed(path.parents), path]:
        if secret(item.name):
            raise ValueError('Prohibited path component')
        if (item.exists() or item.is_symlink()) and linked(item):
            raise ValueError('Links/reparse points are not supported')
    return path


def relative_parts(relative):
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('Expected a portable relative publication path')
    parts = relative.split('/')
    if (PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive
            or not all(portable(p) for p in parts)):
        raise ValueError('Unsafe publication path')
    return parts


def below(root, relative):
    return ordinary_path(root.joinpath(*relative_parts(relative)))


def within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError('Path must stay inside the running project')
    return path


def read_bytes(path):
    path = ordinary_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Only ordinary files can be read')
    data = path.read_bytes()
    after = path.lstat()
    if (before.st_size, before.st_mtime_ns, before.st_ino, before.st_mode) != (
            after.st_size, after.st_mtime_ns, after.st_ino, after.st_mode):
        raise ValueError('File changed during read')
    return data


def inventory(root):
    """Inspect every name/type before reading any file contents."""
    root = ordinary_path(root)
    pending, paths, folded = [root], [], set()
    while pending:
        for entry in pending.pop().iterdir():
            rel = entry.relative_to(root).as_posix()
            below(root, rel)
            key = rel.casefold()
            if key in folded:
                raise ValueError('Case-colliding publication names')
            folded.add(key)
            mode = entry.lstat().st_mode
            if stat.S_ISDIR(mode):
                pending.append(entry)
            elif stat.S_ISREG(mode):
                paths.append(rel)
            else:
                raise ValueError('Special files are not supported')
    return sorted(paths)


def capture(root):
    return {name: read_bytes(below(root, name)) for name in inventory(root)}


def content_id(files):
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        for part in (name.encode('utf-8'), data):
            digest.update(len(part).to_bytes(8, 'big'))
            digest.update(part)
    return digest.hexdigest()


def atomic(path, data):
    path = ordinary_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def envelope(kind, files, metadata):
    # Validate the whole inventory before any destination is created.
    for name in files:
        relative_parts(name)
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError('Case-colliding publication paths')
    return {'format': 1, 'kind': kind, 'metadata': metadata,
            'files': {name: {'sha256': sha(data), 'size': len(data)} for name, data in sorted(files.items())}}


def parse_manifest(path, expected, kind):
    data = read_bytes(path)
    if sha(data) != identity(expected):
        raise ValueError('Manifest identity mismatch')
    manifest = loads(data)
    if manifest.get('format') != 1 or manifest.get('kind') != kind or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported publication manifest')
    keys = set()
    for name, entry in manifest['files'].items():
        below(path.parent, name)
        if name.casefold() in keys or name.casefold() == path.name.casefold():
            raise ValueError('Duplicate or self-referencing inventory path')
        keys.add(name.casefold())
        if not isinstance(entry, dict) or type(entry.get('size')) is not int or entry['size'] < 0:
            raise ValueError('Invalid file inventory')
        identity(entry.get('sha256'))
    if not isinstance(manifest.get('metadata'), dict):
        raise ValueError('Missing manifest metadata')
    return manifest


def verified_file(root, manifest, name):
    entry = manifest['files'].get(name)
    if entry is None:
        raise ValueError('File absent from publication inventory')
    data = read_bytes(below(root, name))
    if len(data) != entry['size'] or sha(data) != entry['sha256']:
        raise ValueError('Published file hash/size mismatch')
    return data


def install(destination, manifest_name, manifest, files):
    """Publish complete directories; never overwrite a different edition."""
    destination = ordinary_path(destination)
    data = (dumps(manifest) + '\n').encode()
    if destination.exists():
        existing = parse_manifest(destination / manifest_name, sha(data), manifest['kind'])
        for name in files:
            verified_file(destination, existing, name)
        return sha(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=str(destination.parent)))
    try:
        for name, body in files.items():
            target = below(stage, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        (stage / manifest_name).write_bytes(data)
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return sha(data)


def read_index(path, optional=False):
    text = read_bytes(path).decode('utf-8')
    if optional and BEGIN not in text and END not in text:
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Index needs exactly one knowhow:v1 block')
    raw = text.split(BEGIN)[1].split(END)[0].strip()
    if not raw.startswith('```json\n') or not raw.endswith('\n```'):
        raise ValueError('Invalid knowhow index block')
    block = loads(raw[8:-4])
    if block.get('format') != 1 or not isinstance(block.get('offers'), list):
        raise ValueError('Unsupported index format')
    project_id(block.get('project_id'))
    return block


def write_index(path, block):
    path = ordinary_path(path)
    text = read_bytes(path).decode('utf-8') if path.exists() else '# Published material\n'
    new = BEGIN + '\n```json\n' + dumps(block) + '\n```\n' + END
    if BEGIN in text or END in text:
        read_index(path)  # Reject ambiguous/malformed blocks instead of destroying prose.
        start, stop = text.index(BEGIN), text.index(END) + len(END)
        text = text[:start] + new + text[stop:]
    else:
        text = text.rstrip() + '\n\n' + new + '\n'
    atomic(path, text.encode('utf-8'))


class Project:
    def __init__(self, root, initialize=False):
        self.root = ordinary_path(root)
        if not self.root.is_dir():
            raise ValueError('Running project must be an existing directory')
        code = Path(__file__).absolute().parents[1]
        if self.root == code or code in self.root.parents or self.root == code.parent:
            raise ValueError('Running project cannot be the loaded capability or its publishing root')
        # A supplied copy of a fixed edition is not a writable project either.
        if (self.root / 'EDITION.json').exists():
            raise ValueError('A fixed edition is not a writable project')
        self.state = ordinary_path(self.root / '.knowhow')
        self.index = ordinary_path(self.root / 'published/INDEX.md')
        marker = ordinary_path(self.state / 'project.json')
        if not marker.exists():
            if not initialize:
                raise ValueError('Run init --project PROJECT_ROOT first')
            if self.index.exists() and BEGIN in read_bytes(self.index).decode('utf-8'):
                raise ValueError('Published identity exists but local identity is missing; restore it, do not replace it')
            atomic(marker, (dumps({'format': 1, 'project_id': str(uuid.uuid4())}) + '\n').encode())
        record = loads(read_bytes(marker))
        self.id = project_id(record['project_id'])
        if initialize:
            block = read_index(self.index) if self.index.exists() and BEGIN in read_bytes(self.index).decode('utf-8') else {
                'format': 1, 'project_id': self.id, 'offers': []}
            if block['project_id'] != self.id:
                raise ValueError('Local and published project identities conflict')
            write_index(self.index, block)

    def input(self, value):
        return within(ordinary_path(value), self.root)

    def append(self, name, record):
        path = below(self.state, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab') as handle:
            handle.write((dumps(record) + '\n').encode())

    def records(self, name):
        path = below(self.state, name)
        return [loads(line) for line in read_bytes(path).splitlines() if line] if path.exists() else []
