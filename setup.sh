#!/usr/bin/env bash
# One-time setup, idempotent: a repo-local TeX (for Manim's MathTex) and the Python env.  ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
TEX="$PWD/.tinytex/TinyTeX"
if [ ! -x "$TEX/bin/universal-darwin/tlmgr" ] && ! ls "$TEX"/bin/*/tlmgr >/dev/null 2>&1; then
  mkdir -p .tinytex
  curl -sL https://yihui.org/tinytex/install-bin-unix.sh | TINYTEX_DIR="$PWD/.tinytex" sh -s - "" --no-path   # $1 = folder to keep the download in (none)
fi
BIN=$(dirname "$(ls "$TEX"/bin/*/tlmgr)")
"$BIN/tlmgr" update --self   # the daily TinyTeX bundle can lag the package repo; tlmgr refuses installs until it is current
# The packages Manim's default TeX template and MathTex rendering need (Manim docs' TinyTeX list, minus the CJK set).
"$BIN/tlmgr" install amsmath babel-english cbfonts-fd cm-super count1to doublestroke dvisvgm everysel fontspec \
  frcursive fundus-calligra gnu-freefont jknapltx latex-bin mathastext microtype multitoc physics preview prelim2e \
  ragged2e relsize rsfs setspace standalone tipa wasy wasysym xcolor xetex xkeyval
echo "$BIN" > .tinytex/bin-path
PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig PATH=/opt/homebrew/bin:$PATH uv sync
echo "setup OK: TeX at $BIN"
