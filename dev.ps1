param (
    [string]$Task = "help"
)

$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    . $venv
} else {
    Write-Error "Virtual environment not found. Run: python -m venv .venv"
    exit 1
}

switch ($Task) {
    "install" {
        pip install -r requirements.txt
        pip install -r dev-requirements.txt
    }
    "test" { pytest }
    "lint" { flake8 . }
    "format" { black .; isort . }
    "typecheck" { mypy . }
    "help" { Write-Host "Usage: .\dev.ps1 [install|test|lint|format|typecheck|help]" }
    default { Write-Host "Unknown task: $Task" }
}
