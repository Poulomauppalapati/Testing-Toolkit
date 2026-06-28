#!/usr/bin/env bash
#
# Testing Toolkit - offline installer launcher (macOS / Linux)
# Finds a Python interpreter, then hands off to install.py, which installs
# everything from THIS folder. No internet access required.
#
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect os-arch to look for a bundled portable Python.
uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$uname_s" in
  darwin*) os_name="macos" ;;
  linux*)  os_name="linux" ;;
  *)       os_name="$uname_s" ;;
esac
uname_m="$(uname -m)"
case "$uname_m" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) arch="$uname_m" ;;
esac

PYEXE=""

# 1) Prefer a portable Python bundled with this folder.
for cand in \
  "$BUNDLE_DIR/runtime/$os_name-$arch/bin/python3" \
  "$BUNDLE_DIR/runtime/$os_name-$arch/bin/python" \
  "$BUNDLE_DIR/runtime/$os_name/bin/python3"; do
  if [ -x "$cand" ]; then PYEXE="$cand"; break; fi
done

# 2) Fall back to a Python already on the machine.
if [ -z "$PYEXE" ]; then
  if command -v python3 >/dev/null 2>&1; then PYEXE="python3";
  elif command -v python >/dev/null 2>&1; then PYEXE="python";
  fi
fi

if [ -z "$PYEXE" ]; then
  echo "[ERROR] No Python found and no bundled runtime for $os_name-$arch."
  echo "[ERROR] Install Python 3.9+ and re-run, e.g.:"
  echo "[ERROR]   macOS:  brew install python   (or download from python.org)"
  echo "[ERROR]   Linux:  sudo apt install python3 python3-venv"
  exit 1
fi

echo "[INFO] Using Python: $PYEXE"
exec "$PYEXE" "$BUNDLE_DIR/install.py" "$@"
