import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
SNAPSHOT = ROOT / '.snapshot'

IGNORE = {
    '.git',
    '.snapshot',
    '__pycache__',
    '.venv',
    'venv'
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_tree(directory, prefix=''):
    lines = []

    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

    for entry in entries:

        if entry.name in IGNORE:
            continue

        rel = entry.relative_to(ROOT)

        if entry.is_dir():
            lines.append(prefix + rel.as_posix() + '/')
            lines.extend(build_tree(entry, prefix + '    '))
        else:
            lines.append(prefix + rel.as_posix())

    return lines


def build_index():

    result = []

    for path in sorted(ROOT.rglob('*')):

        rel = path.relative_to(ROOT)

        if any(part in IGNORE for part in rel.parts):
            continue

        if path.is_file():
            result.append({
                'path': rel.as_posix(),
                'sha256': sha256(path),
                'size': path.stat().st_size
            })

    return result


def main():

    SNAPSHOT.mkdir(exist_ok=True)

    tree = build_tree(ROOT)

    (SNAPSHOT / 'tree.md').write_text(
        '\n'.join(tree),
        encoding='utf-8'
    )

    index = build_index()

    with open(SNAPSHOT / 'files.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

    print('Snapshot created.')
    print(SNAPSHOT / 'tree.md')
    print(SNAPSHOT / 'files.json')


if __name__ == '__main__':
    main()
