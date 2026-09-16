#!/usr/bin/env bash
# Configure or recover the exact applied worker fleet from an explicit local run definition.
set -euo pipefail
cd "$(dirname "$0")/.."
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
export ANSIBLE_LOCAL_TEMP="$PWD/.cache/ansible/tmp"
mkdir -p "$ANSIBLE_LOCAL_TEMP"
configuration=${1:?Pass an Ansible run vars file, such as ansible/run.yml}
shift
exec ansible-playbook -i localhost, ansible/site.yml --extra-vars "@$configuration" "$@"
