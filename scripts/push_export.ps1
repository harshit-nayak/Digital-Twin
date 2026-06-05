param(
    [string]$ExportDir = "export_for_github",
    [string]$RemoteUrl = ""
)

Write-Host "Creating sanitized export (includes db)..."
$python = "python"
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) { $python = "python3" }

$exportScript = Join-Path $PSScriptRoot "create_export.py"
if (-not (Test-Path $exportScript)) { $exportScript = Join-Path (Get-Location) "scripts\create_export.py" }

if (-not (Test-Path $exportScript)) {
    Write-Error "Export script not found: $exportScript"
    exit 1
}

# Run export and auto-confirm with a 'y' sent to stdin
Write-Host "Running: $python $exportScript --zip --out $ExportDir"
"y" | & $python $exportScript --zip --out $ExportDir

if (-not (Test-Path $ExportDir)) {
    Write-Error "Export directory not found: $ExportDir"
    exit 1
}

Set-Location $ExportDir

if (-not (Test-Path ".git")) {
    git init
}

if (-not (Test-Path "README.md")) {
@"
Sanitized export of repository for public sharing.

Excluded: `app/api`, `.md` files (source docs), `logs`, `config`.
Included: source code and `db` directory.
"@ | Out-File -Encoding utf8 README.md
}

if (-not (Test-Path ".gitignore")) {
@"
# Ignore local environment and caches
.env
*.pyc
__pycache__/
venv/
*.sqlite3
"@ | Out-File -Encoding utf8 .gitignore
}

git add .
git commit -m "Sanitized export (prepared for public push)" -q

if ($RemoteUrl -ne "") {
    git remote remove origin -ErrorAction SilentlyContinue
    git remote add origin $RemoteUrl
}

Write-Host "Ready to push. To push, run:"
if ($RemoteUrl -ne "") {
    Write-Host "git push -u origin main"
} else {
    Write-Host "git remote add origin <REMOTE_URL>"
    Write-Host "git push -u origin main"
}

Write-Host "Done."
