import os

src = os.path.normpath(os.path.join(SPECPATH, '..', '..', 'investment_calculator'))

a = Analysis(
    [os.path.join(src, 'app.py')],
    pathex=[src],
    binaries=[],
    datas=[(os.path.join(src, 'index.html'), '.')],
    hiddenimports=['flask', 'werkzeug', 'jinja2', 'click', 'itsdangerous'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='investment_calculator',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
