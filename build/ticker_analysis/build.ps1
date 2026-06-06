$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
python -m PyInstaller `
    --workpath "$root\build\ticker_analysis\work" `
    --distpath "$root\dist" `
    --noconfirm `
    "$root\build\ticker_analysis\ticker_analysis.spec"
