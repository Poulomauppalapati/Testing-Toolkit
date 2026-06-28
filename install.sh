#!/usr/bin/env bash
# ===========================================================
# Testing Toolkit - Install, Build & Launch (macOS / Linux)
#
# Windows: double-click install.cmd instead (native, no bash)
# macOS/Linux: chmod +x install.sh && ./install.sh
#
# Installs packages, builds the app, and launches it.
# ===========================================================

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
EMBED_DIR="$ROOT/python-embed"
WHEELHOUSE="$ROOT/src/wheelhouse"
SRC_DIR="$ROOT/src"
REQUIREMENTS="$ROOT/src/requirements.txt"

echo ""
echo "============================================"
echo " Testing Toolkit - Install & Build"
echo "============================================"
echo ""

# === Phase 0: Clean old state (always) ===
echo "[INFO] Cleaning old build artifacts..."
rm -rf "$SRC_DIR/build" "$SRC_DIR/dist" 2>/dev/null || true
find "$SRC_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "[OK] Clean done."

# === Phase 1: Find a usable Python ===
PYTHON=""

# Prefer embedded Python (version-matched to the wheelhouse)
if [ -x "$EMBED_DIR/bin/python3" ]; then
    PYTHON="$EMBED_DIR/bin/python3"
    PYVER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
fi

# Fallback: system python3
if [ -z "$PYTHON" ] && command -v python3 &>/dev/null; then
    PYVER=$(python3 --version 2>&1 | awk '{print $2}')
    PYMAJ=$(echo "$PYVER" | cut -d. -f1)
    PYMIN=$(echo "$PYVER" | cut -d. -f2)
    if [ "$PYMAJ" -ge 3 ] && [ "$PYMIN" -ge 10 ]; then
        PYTHON="python3"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "[ERROR] No Python 3.10+ found."
    echo "        Install Python or run make_portable.py on a connected machine."
    exit 1
fi

echo "[INFO] Python: $PYTHON ($PYVER)"

# === Phase 2: Install packages (always) ===
echo "[INFO] Installing packages from wheelhouse..."
"$PYTHON" -m pip install --no-index --find-links "$WHEELHOUSE" \
    --no-warn-script-location -r "$REQUIREMENTS" --quiet || {
    echo "[ERROR] Package installation failed."
    echo "        Run: cd src && python make_wheelhouse.py"
    exit 1
}
echo "[INFO] Installing PyInstaller..."
"$PYTHON" -m pip install --no-index --find-links "$WHEELHOUSE" \
    --no-warn-script-location pyinstaller --quiet || {
    echo "[ERROR] PyInstaller installation failed."
    exit 1
}
echo "[OK] All packages installed."

# === Phase 3: Build the app ===
echo ""
"$PYTHON" "$SRC_DIR/build.py" --quiet || {
    echo ""
    echo "[ERROR] Build failed. See output above."
    exit 1
}

# === Phase 3.5: Create distributable zip ===
DIST="$SRC_DIR/dist/TestingToolkit"
if [ -d "$DIST" ]; then
    echo "[INFO] Creating TestingToolkit.zip..."
    (cd "$SRC_DIR/dist" && zip -qr "TestingToolkit.zip" "TestingToolkit")
    if [ $? -eq 0 ]; then
        echo "[OK] TestingToolkit.zip created in dist folder."
    else
        echo "[WARN] Zip creation failed. Continuing anyway."
    fi
fi

# === Phase 4: Launch the built app ===
if [ -f "$DIST/TestingToolkit" ]; then
    echo ""
    echo "[SUCCESS] Build complete. Launching..."
    exec "$DIST/TestingToolkit"
elif [ -f "$DIST/TestingToolkit.exe" ]; then
    echo ""
    echo "[SUCCESS] Build complete. Launching..."
    exec "$DIST/TestingToolkit.exe"
else
    echo "[ERROR] Built executable not found in: $DIST"
    echo "        Check build output above."
    exit 1
fi
