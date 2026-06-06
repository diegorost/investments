import os

src = os.path.normpath(os.path.join(SPECPATH, '..', '..', 'miners_uplift'))

a = Analysis(
    [os.path.join(src, 'main.py')],
    pathex=[src],
    binaries=[],
    datas=[
        (os.path.join(src, 'etf_gold_miners_uplift', 'gold_analysisETF.html'),   'etf_gold_miners_uplift'),
        (os.path.join(src, 'etf_silver_miners_uplift', 'silver_analysisETF.html'), 'etf_silver_miners_uplift'),
    ],
    hiddenimports=['yfinance', 'pandas', 'requests', 'lxml', 'beautifulsoup4'],
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
    name='miners_uplift',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
