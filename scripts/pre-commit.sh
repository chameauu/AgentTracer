#!/usr/bin/env bash
#
# AgentTracer pre-commit script
# Runs the same checks as CI (.github/workflows/ci.yml) locally:
#   backend  -> ruff check, ruff format --check, pytest
#   sdk      -> ruff check, ruff format --check, pytest
#   frontend -> tsc --noEmit, vite build
#
# Usage:
#   ./scripts/pre-commit.sh            # run all checks
#   ./scripts/pre-commit.sh backend    # run only the backend checks
#
# Exit code 0 = all checks passed, 1 = at least one failed.
# Install as a git hook with:  ./scripts/install-hooks.sh

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

run() {
    local project="$1"
    shift
    local name="$1"
    shift

    echo "── [$project] $name"
    if ! (cd "$ROOT/$project" && "$@"); then
        echo "✗ [$project] $name FAILED"
        FAILED=1
    fi
}

only="${1:-all}"

if [[ "$only" == "all" || "$only" == "backend" ]]; then
    run backend "ruff check" uv run ruff check .
    run backend "ruff format --check" uv run ruff format --check .
    run backend "pytest" uv run pytest tests/
fi

if [[ "$only" == "all" || "$only" == "sdk" ]]; then
    run sdk "ruff check" uv run ruff check .
    run sdk "ruff format --check" uv run ruff format --check .
    run sdk "pytest" uv run pytest tests/
fi

if [[ "$only" == "all" || "$only" == "frontend" ]]; then
    run frontend "tsc --noEmit" npx tsc --noEmit
    run frontend "vite build" npm run build
fi

echo ""
if [[ $FAILED -eq 0 ]]; then
    echo "✓ All checks passed"
    exit 0
else
    echo "✗ Some checks failed — fix the issues above before committing"
    exit 1
fi
