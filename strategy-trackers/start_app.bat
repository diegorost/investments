@echo off
cd /d "%~dp0"
start "strategy-trackers-api" cmd /k "cd worker && npx wrangler dev --config wrangler.toml"
start "strategy-trackers-site" cmd /k "python -m http.server 8788"
timeout /t 2 /nobreak >nul
start http://localhost:8788/index.html
