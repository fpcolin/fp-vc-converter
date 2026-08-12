"""Generate version.json for a built installer.

    python build\\publish.py dist\\installer\\FPVendorCafeConverter-2.0.0-setup.exe 2.0.0 ^
        --base-url https://github.com/fpcolin/fp-vendorcafe-converter/releases/download/v2.0.0 ^
        --notes "Adds vCard export and auto-update."

Writes version.json beside the installer. Upload both to the distribution point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installer', type=Path)
    parser.add_argument('version')
    parser.add_argument('--base-url', required=True,
                        help='Folder URL the installer will be served from')
    parser.add_argument('--notes', default='', help='Short release notes shown to users')
    args = parser.parse_args()

    if not args.installer.is_file():
        raise SystemExit(f'Installer not found: {args.installer}')

    manifest = {
        'version': args.version,
        'url': f'{args.base_url.rstrip("/")}/{args.installer.name}',
        'sha256': sha256(args.installer),
        'notes': args.notes,
    }

    out = args.installer.parent / 'version.json'
    out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Wrote {out}')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
