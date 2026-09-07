#!/usr/bin/env bash
# Thin runner for python_scripts only.
#   ai hello-world --name Bob
#   ai --list
#   ai --where hello-world
set -euo pipefail

#NOTE: Move this file to your scripts folder and add the python_scripts directory below
# Directory where python_scripts live
PY_DIR=

usage() {
  cat <<EOF
Thin runner for python_scripts.

Usage:
  $(basename "$0") <command> [args...]
  $(basename "$0") --list
  $(basename "$0") --where <command>
  $(basename "$0") --help

Examples:
  $(basename "$0") hello-world --name Bob
  $(basename "$0") --list
  $(basename "$0") --where hello-world
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  *) break ;;
  esac
done

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "${PY_DIR}/main.py" ]]; then
  echo "error: cannot find ${PY_DIR}/main.py" >&2
  exit 1
fi

cd "${PY_DIR}"
if command -v uv >/dev/null 2>&1; then
  exec uv run python main.py "$@"
else
  exec python3 main.py "$@"
fi
