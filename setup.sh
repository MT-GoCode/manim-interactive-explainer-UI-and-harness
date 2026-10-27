#!/usr/bin/env bash
# One-time setup, idempotent: repo-local TeX (Manim's MathTex), the Python env, Node deps, the explain-build /
# fetch-comments commands on PATH, and the pre-push hook that runs ./test.   ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
REPO=$PWD
TEX="$REPO/.tinytex/TinyTeX"
if ! ls "$TEX"/bin/*/tlmgr >/dev/null 2>&1; then
  mkdir -p .tinytex
  curl -sL https://yihui.org/tinytex/install-bin-unix.sh | TINYTEX_DIR="$REPO/.tinytex" sh -s - "" --no-path   # $1 = folder to keep the download in (none)
fi
BIN=$(dirname "$(ls "$TEX"/bin/*/tlmgr)")
"$BIN/tlmgr" update --self   # the daily TinyTeX bundle can lag the package repo; tlmgr refuses installs until it is current
# The packages Manim's default TeX template and MathTex rendering need (Manim docs' TinyTeX list, minus the CJK set).
"$BIN/tlmgr" install amsmath babel-english cbfonts-fd cm-super count1to doublestroke dvisvgm everysel fontspec \
  frcursive fundus-calligra gnu-freefont jknapltx latex-bin mathastext microtype multitoc physics preview prelim2e \
  ragged2e relsize rsfs setspace standalone tipa wasy wasysym xcolor xetex xkeyval
echo "$BIN" > .tinytex/bin-path
PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig PATH=/opt/homebrew/bin:$PATH uv sync
npm ci --no-audit --no-fund
# Commands on PATH are links to this repo's bin/ scripts (one venv, no copy).
mkdir -p "$HOME/.local/bin"
for cmd in bin/*; do ln -sf "$REPO/$cmd" "$HOME/.local/bin/$(basename "$cmd")"; done
cat > .git/hooks/pre-push <<'HOOK'
#!/bin/sh
[ "$(uname)" = Darwin ] || { echo "explainers: ./test needs macOS (Manim + Electron); push from a Mac." >&2; exit 1; }
exec "$(git rev-parse --show-toplevel)/test"
HOOK
chmod +x .git/hooks/pre-push
echo "setup OK: TeX at $BIN; commands in ~/.local/bin"
