$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
python -m PyInstaller `
    --workpath "$root\build\pricedate\work" `
    --distpath "$root\dist" `
    --noconfirm `
    "$root\build\pricedate\pricedate.spec"
