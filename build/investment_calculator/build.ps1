$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
python -m PyInstaller `
    --workpath "$root\build\investment_calculator\work" `
    --distpath "$root\dist" `
    --noconfirm `
    "$root\build\investment_calculator\investment_calculator.spec"
