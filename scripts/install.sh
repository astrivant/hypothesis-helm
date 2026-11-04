#!/bin/sh
set -eu
: "${HELM_PLUGIN_DIR:?Helm must set HELM_PLUGIN_DIR}"
case "${HH_EXECUTION_BACKEND:-reference}" in
    reference) extra= ;;
    cpu-vector) extra='[cpu]' ;;
    gpu) extra='[gpu]' ;;
    *)
        printf '%s\n' 'Unknown HH_EXECUTION_BACKEND' >&2
        exit 2
        ;;
esac
printf 'INFO Installing Hypothesis Helm backend=%s\n' "${HH_EXECUTION_BACKEND:-reference}" >&2
"${PYTHON:-python3}" -m venv "$HELM_PLUGIN_DIR/.plugin-venv"
"$HELM_PLUGIN_DIR/.plugin-venv/bin/pip" install "$HELM_PLUGIN_DIR$extra"
printf '%s\n' 'INFO Hypothesis Helm installation complete' >&2
