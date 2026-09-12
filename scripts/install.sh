#!/bin/sh
set -eu
: "${HELM_PLUGIN_DIR:?Helm must set HELM_PLUGIN_DIR}"
"${PYTHON:-python3}" -m venv "$HELM_PLUGIN_DIR/.plugin-venv"
"$HELM_PLUGIN_DIR/.plugin-venv/bin/pip" install "$HELM_PLUGIN_DIR"
