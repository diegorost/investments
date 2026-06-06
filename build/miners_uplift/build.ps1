$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
python -m PyInstaller `
    --workpath "$root\build\miners_uplift\work" `
    --distpath "$root\dist" `
    --noconfirm `
    "$root\build\miners_uplift\miners_uplift.spec"
