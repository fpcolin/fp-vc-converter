# Building and releasing the VendorCafe CSV Converter

## Layout

```
fp-vc-converter/
├─ src/
│  ├─ vc_converter.pyw    main application (.pyw = no console)
│  ├─ updater.py          update check (must stay .py - see below)
│  └─ fp.ico              app + installer icon
├─ build/
│  ├─ vc_converter.spec   PyInstaller config
│  ├─ version_info.txt    Windows file-properties metadata
│  ├─ installer.iss       Inno Setup config
│  └─ publish.py          generates version.json
└─ dist/                  build output (git-ignore this)
```

Assets sit in `src/` because `resource_path()` looks next to the script when
running from source and at the bundle root when frozen. The spec maps them to
`.` so both cases resolve identically.

## Why only the entry script is .pyw

`vc_converter.pyw` uses the `.pyw` extension so that double-clicking it on Windows
launches through `pythonw.exe` with no console window. This matters only when
running from source — for the built exe, `console=False` in the spec is what
suppresses the terminal, and that is already set.

**`updater.py` must keep its `.py` extension.** Python's import system only
recognises `.py` as a source suffix (`importlib.machinery.SOURCE_SUFFIXES` is
literally `['.py']`), so renaming it to `.pyw` makes `import updater` fail with
`ModuleNotFoundError`. The rule is: the entry script may be `.pyw`, every
imported module must be `.py`. PyInstaller handles the mixture fine.

`build/publish.py` also stays `.py` — it is a command-line tool that prints to
stdout and is never bundled.

Two consequences of running without a console, both already handled:

- Nothing in `src/` writes to `stdout` or `stderr`. Under `pythonw` those
  streams are `None`, so a stray `print()` raises `AttributeError`. Keep it
  that way; use a `messagebox` or a log file if you need output.
- `updater.apply()` passes explicit `DEVNULL` handles to `subprocess.Popen`.
  Inheriting absent handles is what produces the classic
  `OSError: [WinError 6] The handle is invalid` in windowed builds.

An unhandled exception in a windowed build goes nowhere visible — the app just
disappears. If you need to debug a frozen build, temporarily set
`console=True` in the spec and rebuild.

## One-time setup

Install the toolchain on the build machine:

```
pip install pyinstaller
```

Then install [Inno Setup](https://jrsoftware.org/isdl.php) (7.x is current) and
put its folder on `PATH` so `iscc` is callable. Find the folder rather than
assuming it — the version number is in the path, and the 7.x x64 build may land
in `Program Files` rather than `Program Files (x86)`:

```
where /r "C:\Program Files" ISCC.exe
where /r "C:\Program Files (x86)" ISCC.exe
```

Add that folder through System Properties → Environment Variables → User
variables → Path → New. Avoid `setx PATH "%PATH%;..."`: it truncates PATH at
1024 characters and can silently destroy existing entries. Restart Visual
Studio afterwards, since processes inherit the environment at launch, then
confirm with `iscc /?`.

The scripts here work with Inno Setup 6 and 7 alike; nothing in
`installer.iss` uses 7.x-only directives.

## Building a release

Set `MANIFEST_URL` in `src/updater.py` to wherever you will host the manifest,
then from the repo root:

```
pyinstaller build\vc_converter.spec --noconfirm --clean --workpath dist\work
iscc build\installer.iss
```

You get `dist\installer\FPVendorCafeConverter-<version>-setup.exe`.

## Cutting a new version

If you use the GitHub Actions workflow, skip this section — CI derives
everything from the tag. For manual builds, three values must move together, or
the updater will loop or go silent:

| File | Field |
|---|---|
| `src/vc_converter.pyw` | `VERSION` |
| `build/version_info.txt` | `filevers`, `prodvers`, `FileVersion`, `ProductVersion` |
| `build/installer.iss` | `AppVersion` |

Settings survive version bumps. `Config._load()` keys its reset on
`CONFIG_SCHEMA`, not `VERSION`, so an ordinary release leaves each user's saved
folder, filename, and toggles intact. Bump `CONFIG_SCHEMA` only when the shape
of the config file actually changes — renaming or removing a key, or changing
what a value means — and expect that release to reset everyone to defaults.

Then publish:

```
python build\publish.py dist\installer\FPVendorCafeConverter-2.1.0-setup.exe 2.1.0 ^
    --base-url https://github.com/fpcolin/fp-vc-converter/releases/download/v2.1.0 ^
    --notes "Adds batch export."
```

Upload the installer and the generated `version.json` to that URL. Installed
copies pick it up on next launch.

## How updates work

The app checks 1.2 seconds after the window appears, on a background thread. If
the manifest advertises a higher version it prompts; on accept it downloads to
`%TEMP%`, verifies SHA-256, launches the installer with `/SILENT`, and exits so
Inno can replace the files. Any network failure is swallowed — an unreachable
server never blocks someone from converting a file.

Two things make this work without an admin prompt:

- `PrivilegesRequired=lowest` installs to `%LOCALAPPDATA%\Programs`, which the
  user can write to. A Program Files install would trigger UAC on every update.
- `AppId` is a fixed GUID. Windows uses it to recognise an upgrade. Change it
  and every release installs alongside the last instead of replacing it.

The SHA-256 check is not optional. The updater downloads an executable and runs
it, so without hash verification anyone who could tamper with the download
would get code execution on every workstation.

## Distributing via GitHub Releases

GitHub works as the distribution point with no change to `updater.py` beyond
the URL. Set:

```python
MANIFEST_URL = 'https://github.com/fpcolin/fp-vc-converter/releases/latest/download/version.json'
```

This is already set in `src/updater.py`.

Until the first release is published, that URL returns HTTP 404. `check()`
treats any network error as "no update available" and returns `None`, so the
app runs normally — there is nothing to fix, and nothing for users to see.

One ordering consequence: the very first installer you hand out cannot update
itself *to* v2.0.1, because it already is v2.0.1. Self-updating starts working
from the second release onward. So tag `v2.0.1`, let the workflow publish it,
distribute that installer, and every later tag reaches users automatically.

`/releases/latest/download/<name>` is a permanent redirect to that asset on the
newest published release, so the URL never changes between versions. `urllib`
follows the redirect to `release-assets.githubusercontent.com` automatically.

**Use this path rather than `api.github.com`.** The REST API allows 60
unauthenticated requests per hour *per IP address*. Everyone in one office
shares a single NAT address, so a fleet of installed copies checking on launch
can exhaust that budget and start getting HTTP 403 — updates would silently
stop for everybody. The asset-download path has no such limit.

`publish.py` still records a *versioned* installer URL inside the manifest
(`/releases/download/v2.1.0/...`), so a client that downloads a manifest just
before a new release still fetches the exact file that manifest describes.

### Automated releases

`.github/workflows/release.yml` builds and publishes on a version tag:

```
git tag v2.1.0
git push origin v2.1.0
```

The workflow checks the tag against `VERSION` in `vc_converter.pyw` and fails if
they disagree, then rewrites `version_info.txt` and passes `/DAppVersion` to
Inno Setup. That makes `vc_converter.pyw` the single source of truth and removes
the three-places-to-edit problem described above — you now only bump `VERSION`
and tag.

### The private-repo problem

**Release assets on a private repo require an `Authorization` header.** There
is no way around this: an unauthenticated download returns 404. That leaves you
with a real trade-off, because the app must be able to fetch its own updates.

- **Public repo** — simplest and what the workflow assumes. Everything works
  unauthenticated. But your source is public.
- **Private source, public releases** — not possible in one repo; release
  visibility follows repo visibility. Some teams keep a private source repo and
  a second public repo that holds only releases, with CI pushing artifacts
  across. The installer is public, the code is not.
- **Embed a token** — a fine-grained PAT with read-only access to one repo will
  work, but anyone who has the exe can extract it with `strings`. Only consider
  this if the token grants nothing you would mind an ex-employee holding, and
  set an expiry.
- **GitHub for source, elsewhere for artifacts** — keep the repo private and
  host `version.json` plus the installer on an internal web server, a file
  share, or Azure Blob Storage with a long-lived SAS URL. This is usually the
  right answer for company-internal software.

Since this tool embeds company branding and is not obviously sensitive, a
public repo is defensible. Check with whoever owns your IP policy first, and
confirm nothing internal is in the git history before making a repo public —
history is published too, not just the current tree.

## Troubleshooting

### ModuleNotFoundError: No module named 'jaraco.text'

Raised from `pyi_rth_pkgres.py` the moment the exe starts. It means
`pkg_resources` was bundled but its dependencies were not.

Recent setuptools stopped vendoring `jaraco.text` inside `pkg_resources` and
now imports it as a real package from `setuptools/_vendor`. So excluding
`setuptools` while still collecting `pkg_resources` leaves a module whose
imports cannot resolve. The spec excludes both, which removes PyInstaller's
`pkg_resources` runtime hook altogether. Nothing in this app imports
`pkg_resources`, so this is safe. This program has no third-party dependencies
at all, so the exclude list can stay aggressive.

If a future dependency genuinely needs `pkg_resources`, drop it from `excludes`
and add its vendored imports instead:

```python
hiddenimports=['updater', 'jaraco.text', 'jaraco.functools',
               'jaraco.context', 'more_itertools', 'platformdirs'],
```

Always `--clean` after changing `excludes`; PyInstaller caches its analysis and
a stale cache will reproduce the old error and make the fix look ineffective.

### The exe starts and immediately vanishes

A windowed build has nowhere to print a traceback. Temporarily set
`console=True` in the spec, rebuild, and run from a terminal to see the error.

### Relaunching after an update

A silent install relaunches the app when it finishes, because a silent run is
almost always the self-updater and the user was mid-task a moment earlier. The
interactive Finished-page checkbox still applies to normal installs, and the two
`[Run]` entries are mutually exclusive — `skipifsilent` on one, a `Check:` on
the other — so the app never launches twice.

For unattended deployment where that is not wanted, pass `/NORELAUNCH`:

```
FPVendorCafeConverter-2.1.1-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NORELAUNCH
```

The decision lives in the installer rather than the updater, which matters:
users on an older build get the new behaviour as soon as they upgrade, because
it is the *new* installer that runs. Had the flag been sent by the updater
instead, it would not have taken effect until the upgrade after next.

## Code signing

Unsigned PyInstaller executables trigger SmartScreen ("Windows protected your
PC") and are a common source of antivirus false positives. For a company
rollout this matters more than it would for a personal tool — expect help-desk
tickets without it.

The workflow signs automatically when a certificate is configured, and skips
signing when it is not, so builds keep working either way.

### Order matters

Two constraints are baked into the step order, and both cause quiet breakage if
moved:

- The app exe is signed **before** Inno packages it. Signing only the installer
  leaves the installed program unsigned, so SmartScreen still fires on launch.
- The installer is signed **before** `publish.py` runs. Signing rewrites the
  file, so a checksum taken first would not match what users download and every
  update would abort with "Checksum mismatch".

Always timestamp (`/tr`), or signatures stop validating when the certificate
expires.

### Option 1: certificate file in a secret

Works with any OV certificate issued as a `.pfx`. Encode it:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cert.pfx")) | Set-Clipboard
```

Add it under Settings → Secrets and variables → Actions as
`SIGNING_PFX_BASE64`, plus `SIGNING_PFX_PASSWORD`.

Secrets are not exposed to pull requests from forks, so a public repo is not
automatically a leak. They *are* available to anyone with write access who can
push a tag or edit a workflow, so treat repository write access as equivalent
to holding the certificate.

Note that many CAs now issue OV certificates only on hardware tokens or in an
HSM, which cannot be exported to a `.pfx` and therefore cannot be used this
way. Check before buying if you intend to sign in CI.

### Option 2: Azure Artifact Signing

Microsoft's managed signing service, renamed from Trusted Signing in January
2026. Around $10/month, and there is no private key to store — authentication
uses OIDC, so no long-lived secret lives in the repo. Replace the two signing
steps with:

```yaml
      - uses: azure/artifact-signing-action@v1
        with:
          endpoint: https://eus.codesigning.azure.net/
          trusted-signing-account-name: <account>
          certificate-profile-name: <profile>
          files-folder: ${{ github.workspace }}\dist\FPVendorCafeConverter
          files-folder-filter: exe
          timestamp-rfc3161: http://timestamp.acs.microsoft.com
          timestamp-digest: SHA256
```

The account needs the Artifact Signing Certificate Profile Signer role, and the
certificate profile must be **Public Trust** — Private Trust profiles do not
suppress SmartScreen. Identity verification takes several days, so start early
if you have a deadline.

Either option builds SmartScreen reputation from zero. Warnings may persist for
the first few downloads until the signature accumulates trust.

## If IT manages the fleet

If workstations are under Intune, SCCM, or Group Policy, consider dropping the
self-updater and letting IT push versions instead. In that case switch
`installer.iss` to `PrivilegesRequired=admin` with
`DefaultDirName={autopf}\...`, and either wrap the Inno installer for Intune
(`IntuneWinAppUtil`) or repackage as MSI with WiX. Silent install for that path
is `FPVendorCafeConverter-2.1.0-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`.

Keeping the self-updater is the better fit if people install this themselves or
work off-domain.

## Antivirus notes

If the exe gets quarantined:

- The spec sets `upx=False`. Leave it — UPX compression is one of the strongest
  false-positive triggers for PyInstaller output.
- `onedir` (used here) is flagged less often than `onefile`, which unpacks to
  `%TEMP%` on every launch and looks like self-extracting malware.
- `version_info.txt` gives the binary real publisher metadata, which helps.
- Submit false positives to your vendor and, if you use Defender for Business,
  add a publisher-certificate allow rule once you are signing.
