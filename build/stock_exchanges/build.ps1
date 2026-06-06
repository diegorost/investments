$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
python -m PyInstaller `
    --workpath "$root\build\stock_exchanges\work" `
    --distpath "$root\dist" `
    --noconfirm `
    "$root\build\stock_exchanges\stock_exchanges.spec"
