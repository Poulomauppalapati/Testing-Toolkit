# Testing Toolkit Agent - Offline Installer

This folder is **self-contained**. The installer uses only the files in here
(`wheelhouse/`, `models/`, `src/`, `runtime/`) and never contacts the public
internet during setup - safe for locked-down corporate networks.

## Install

### Windows
Double-click **`install.cmd`**, or run it from a terminal:

```bat
install.cmd
```

### macOS / Linux
Run **`install.sh`** from a terminal inside this folder:

```bash
./install.sh
```

You can also run the cross-platform core directly with any Python 3.9+:

```bash
python install.py
```

## What it does

1. Picks a Python interpreter (the bundled `runtime/<os>-<arch>` if present,
   otherwise a Python already installed on the machine).
2. Installs all Python packages **offline** from `wheelhouse/`
   (`pip --no-index --find-links wheelhouse`).
3. Copies the agent `src/` and ONNX `models/` into `~/TestingToolkit`.
4. Registers a login auto-start entry (Task Scheduler / launchd / systemd).
5. Starts the agent on `http://127.0.0.1:7842` and waits for it to be healthy.

Options: `--no-start` (install only), `--no-autostart` (skip login entry).

## Platform support

The committed `runtime/` and the native wheels (numpy, onnxruntime, lxml,
pyarrow, lancedb, PyMuPDF, ...) are currently **Windows x64** only, so the
fully-offline path works on Windows today.

To enable the same offline install on **macOS** or **Linux**, add to this
bundle:

- `runtime/macos-arm64/` (or `linux-amd64/`, etc.) - a portable Python 3.12, and
- platform wheels for that OS/arch built with:
  `pip download -r requirements.txt -d wheelhouse --platform <tag> --only-binary=:all:`

The installer auto-detects OS/arch and will use them with no further changes.
