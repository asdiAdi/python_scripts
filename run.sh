#!/usr/bin/env bash
# Thin runner for python_scripts only.
#
#   ./run.sh hello-world --name Bob
#   ./run.sh --list
#   ./run.sh --where hello-world
#
# No folder prefix: this file lives next to main.py and only ever
# runs python_scripts, so the origin is always obvious.
# This file is safe to copy elsewhere; it still only runs python.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"
if [[ "$(basename "${DEFAULT_ROOT}")" == "python_scripts" ]]; then
  DEFAULT_ROOT="$(cd "${DEFAULT_ROOT}/.." && pwd)"
fi
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${DEFAULT_ROOT}}"
PYTHON_PROJECT_DIR="${PYTHON_PROJECT_DIR:-}"

usage() {
  cat <<EOF
Thin runner for python_scripts.

Usage:
  $(basename "$0") [--root PATH] <command> [args...]
  $(basename "$0") [--root PATH] --list
  $(basename "$0") [--root PATH] --where <command>
  $(basename "$0") --help

Examples:
  $(basename "$0") hello-world --name Bob
  $(basename "$0") --list
  $(basename "$0") --where hello-world
EOF
}

resolve_python_dir() {
  if [[ -n "${PYTHON_PROJECT_DIR}" && -f "${PYTHON_PROJECT_DIR}/main.py" ]]; then
    echo "${PYTHON_PROJECT_DIR}"
  elif [[ -f "${WORKSPACE_ROOT}/python_scripts/main.py" ]]; then
    echo "${WORKSPACE_ROOT}/python_scripts"
  elif [[ -f "${SCRIPT_DIR}/main.py" ]]; then
    echo "${SCRIPT_DIR}"
  else
    echo ""
  fi
}

ROOT_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --root) ROOT_OVERRIDE="${2:-}"; shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done

if [[ -n "${ROOT_OVERRIDE}" ]]; then
  WORKSPACE_ROOT="${ROOT_OVERRIDE}"
fi

PY_DIR="$(resolve_python_dir)"
if [[ -z "${PY_DIR}" ]]; then
  echo "error: cannot find python_scripts/main.py (WORKSPACE_ROOT=${WORKSPACE_ROOT})" >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

cd "${PY_DIR}"
if command -v uv >/dev/null 2>&1; then
  exec uv run python main.py "$@"
else
  exec python3 main.py "$@"
fi
