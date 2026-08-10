#!/usr/bin/env bash
#
# Installs scripts/pre-commit.sh as a git pre-commit hook.
# Run once after cloning:  ./scripts/install-hooks.sh
#
# The hook runs the full pre-commit script (lint + format + tests for
# backend, sdk, frontend). To bypass for a quick commit: git commit --no-verify

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$ROOT/.git/hooks"
HOOK_FILE="$HOOKS_DIR/pre-commit"

mkdir -p "$HOOKS_DIR"
cat > "$HOOK_FILE" <<EOF
#!/usr/bin/env bash
# Installed by scripts/install-hooks.sh — managed by scripts/pre-commit.sh
exec "$ROOT/scripts/pre-commit.sh"
EOF
chmod +x "$HOOK_FILE"

echo "✓ Pre-commit hook installed at $HOOK_FILE"
