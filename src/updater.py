"""Self-update support. Standard library only - adds nothing to the bundle.

Flow: fetch a small JSON manifest, compare versions, download the installer,
verify its SHA-256, then hand off to Inno Setup in silent mode and quit so the
running files can be replaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

# The /releases/latest/download/ path is a permanent redirect to the asset on
# the most recently published release, so this URL never needs to change.
# Do not switch this to api.github.com: that endpoint allows only 60
# unauthenticated requests per hour per IP, and an office behind one NAT
# address would exhaust it and stop receiving updates.
MANIFEST_URL = 'https://github.com/fpcolin/fp-vc-converter/releases/latest/download/version.json'

NETWORK_TIMEOUT = 6      # seconds; keep short so a VPN-less laptop is not stalled
DOWNLOAD_TIMEOUT = 300


class UpdateError(Exception):
    """Raised when an update was found but could not be applied."""


def parse_version(value: str) -> tuple[int, ...]:
    """Turn '2.1.10' into (2, 1, 10) so comparison is numeric, not alphabetical.

    Without this, the string comparison '2.1.10' > '2.1.9' is False and the
    tenth patch release would never be offered.
    """
    parts = []
    for chunk in str(value).split('.'):
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _urlopen(url: str, timeout: int):
    context = ssl.create_default_context()
    request = urllib.request.Request(url, headers={'User-Agent': 'FPVendorCafeConverter-Updater'})
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def check(current_version: str) -> dict | None:
    """Return the manifest if a newer version is published, else None.

    Any network or parsing problem returns None: a missing update server must
    never stop someone converting a file.
    """
    try:
        with _urlopen(MANIFEST_URL, NETWORK_TIMEOUT) as response:
            manifest = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None

    if not isinstance(manifest, dict) or 'version' not in manifest or 'url' not in manifest:
        return None
    if parse_version(manifest['version']) <= parse_version(current_version):
        return None
    return manifest


def check_async(current_version: str, callback) -> None:
    """Run check() off the UI thread.

    callback receives the manifest dict. It is invoked from a worker thread, so
    the caller must marshal back to Tk via root.after() before touching widgets.
    """
    def worker():
        manifest = check(current_version)
        if manifest:
            callback(manifest)

    threading.Thread(target=worker, daemon=True).start()


def download(manifest: dict, progress=None) -> Path:
    """Download the installer to a temp file and verify its checksum."""
    url = manifest['url']
    expected = str(manifest.get('sha256', '')).lower().strip()

    target = Path(tempfile.gettempdir()) / f'fp_vendorcafe_converter_setup_{manifest["version"]}.exe'
    digest = hashlib.sha256()

    try:
        with _urlopen(url, DOWNLOAD_TIMEOUT) as response, open(target, 'wb') as out:
            total = int(response.headers.get('Content-Length') or 0)
            seen = 0
            while True:
                block = response.read(65536)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                seen += len(block)
                if progress and total:
                    progress(seen / total)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        target.unlink(missing_ok=True)
        raise UpdateError(f'Download failed: {exc}') from exc

    # Refuse to execute anything whose hash does not match the manifest. Without
    # this, anyone able to tamper with the download would get code execution.
    if not expected:
        target.unlink(missing_ok=True)
        raise UpdateError('Manifest has no sha256 entry; refusing to run the installer.')
    if digest.hexdigest().lower() != expected:
        target.unlink(missing_ok=True)
        raise UpdateError('Checksum mismatch; the download was corrupt or tampered with.')

    return target


def apply(installer: Path) -> None:
    """Launch the installer detached and return so the caller can exit.

    /SILENT shows only a progress bar. Inno's CloseApplications handles shutting
    down this process; we exit immediately anyway.
    """
    flags = ['/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART']
    creation = 0
    if sys.platform == 'win32':
        creation = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        # Explicit DEVNULL rather than inheriting: in a windowed build there is
        # no console, so sys.stdin/stdout/stderr are None and Windows raises
        # "WinError 6: The handle is invalid" when it tries to pass them on.
        subprocess.Popen(
            [str(installer), *flags],
            close_fds=True,
            creationflags=creation,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise UpdateError(f'Could not start the installer: {exc}') from exc