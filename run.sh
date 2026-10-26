#!/usr/bin/env bash
# Run any command with the repo-local TeX on PATH:  ./run.sh manim -ql scene.py Scene
cd "$(dirname "$0")"
PATH="$(cat .tinytex/bin-path):$PATH" exec uv run -q "$@"
