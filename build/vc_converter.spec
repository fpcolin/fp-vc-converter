# PyInstaller spec. Build from the repo root with:
#     pyinstaller build\vc_converter.spec --noconfirm --clean --workpath dist\work

block_cipher = None

a = Analysis(
    # .pyw suppresses the console when double-clicking the source on Windows.
    # It has no bearing on the built exe - console=False below does that job.
    # Note updater.py must keep its .py extension: Python's import system only
    # recognises .py as a source suffix, so a .pyw module is not importable.
    ['..\\src\\vc_converter.pyw'],
    pathex=['..\\src'],
    binaries=[],
    datas=[('..\\src\\fp.ico', '.')],
    hiddenimports=['updater'],
    hookspath=[],
    runtime_hooks=[],
    # This app is pure standard library, so almost everything can go. Do NOT
    # add http, email, ssl, urllib, csv, json or encodings here - the converter
    # and the updater need them.
    #
    # pkg_resources must be excluded alongside setuptools, not left behind.
    # Modern setuptools no longer vendors jaraco.text inside pkg_resources; it
    # imports it as a real package from setuptools/_vendor. Excluding setuptools
    # while collecting pkg_resources produces "ModuleNotFoundError: No module
    # named 'jaraco.text'" at startup, raised from PyInstaller's pkg_resources
    # runtime hook. Excluding pkg_resources removes that hook entirely.
    excludes=[
        'numpy', 'scipy', 'pandas', 'matplotlib', 'pytz', 'dateutil',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'sphinx', 'setuptools', 'pkg_resources', 'pip',
        'tkinter.test', 'test', 'lib2to3', 'pydoc_data',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: faster startup, fewer AV flags
    name='FPVendorCafeConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX packing is a major AV false-positive trigger
    console=False,                  # GUI app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='..\\src\\fp.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FPVendorCafeConverter',
)
