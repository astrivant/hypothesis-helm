"""
Validate Action inputs against the CLI without constructing executable command strings.
"""

import argparse

from hypothesis_helm.cli import argument_parser

__all__ = ("COMMANDS", "input_name", "normalize_options", "options")

COMMANDS = ("test", "scan", "audit", "generate", "run")
INPUT_NAMES = {"validate-schemas": "schema-validation", "no-cache": "cache", "output": "suite-output"}
# These inputs also configure installation, exports or the Action's execution wrapper.
SHARED = {
    "shard",
    "artifact-dir",
    "schema-validation",
    "schema-version",
    "schema-cache-dir",
    "schema-offline",
    "export-minimal-values",
    "minimal-values-timeout",
}
ACTION_DEFAULTS = {"shard": "auto", "jobs": "auto", "rerun": "auto", "cache": "true", "disable-schema-caching": "false"}


def input_name(action: argparse.Action) -> str:
    """
    Map a CLI option to its public Action input, preserving existing installation controls.

    Args:
        action (argparse.Action): An optional CLI argument.

    Returns:
        str: Hyphenated with-input name.
    """
    flag = action.option_strings[0].removeprefix("--")
    return INPUT_NAMES.get(flag, flag)


def options() -> dict[str, dict[str, argparse.Action]]:
    """
    Read argument kinds from the actual parser so validation follows CLI changes.

    Returns:
        dict[str, dict[str, argparse.Action]]: Command to named optional arguments.
    """
    commands = next(action.choices for action in argument_parser()._actions if isinstance(action, argparse._SubParsersAction))
    return {
        command: {input_name(action): action for action in commands[command]._actions if action.option_strings and action.dest != "help"}
        for command in COMMANDS
    }


def normalize_options(settings: dict[str, str], command: str) -> dict[str, str]:
    """
    Normalize switches and reject inputs that the selected command cannot consume.

    Args:
        settings (dict[str, str]): Literal environment values from composite inputs.
        command (str): Selected CLI command.

    Returns:
        dict[str, str]: Environment for the explicit Bash invocation.
    """
    catalog = options()
    if command not in catalog:
        raise ValueError(f"command must be one of {', '.join(COMMANDS)}")
    known = {name: action for arguments in catalog.values() for name, action in arguments.items()}
    result = dict(settings)
    for name, action in known.items():
        key = "HH_" + name.upper().replace("-", "_")
        if name == "schema-validation":
            key = "HH_VALIDATE_SCHEMAS"
        value = settings.get(key, "")
        if name not in catalog[command] and name not in SHARED and value not in ("", "false", ACTION_DEFAULTS.get(name)):
            raise ValueError(f"Action input '{name}' is not supported by command '{command}'")
        if name == "export-minimal-values":
            continue  # Export/commit-back has its own post-test step for local charts.
        if isinstance(action, argparse.BooleanOptionalAction) or action.nargs == 0:
            if value.lower() not in ("", "true", "false"):
                raise ValueError(f"Action input '{name}' must be true, false, or empty")
            enabled = value.lower() == "true"
            result[key] = "1" if enabled else ""
            if isinstance(action, argparse.BooleanOptionalAction):
                result["HH_NO_" + name.upper().replace("-", "_")] = "1" if value.lower() == "false" else ""
            if name == "cache":
                result["HH_NO_CACHE"] = "1" if value.lower() == "false" else ""
        elif name == "fail":
            result[key] = "info" if value.lower() == "true" else "" if value.lower() == "false" else value
        elif name == "log-color":
            result[key] = "always" if value.lower() == "true" else "never" if value.lower() == "false" else value
        elif name in {"report", "export-topological-graph"} and value.lower() == "false":
            result[key] = ""
    # Treat each line as data, never shell syntax. Comma-delimited codes remain valid.
    codes = ",".join(
        line.strip() for key in ("HH_IGNORE", "HH_DISABLE_CODES") for line in settings.get(key, "").splitlines() if line.strip()
    )
    result["HH_DISABLE_CODES"] = codes
    if settings.get("HH_KUBESEC", "false").lower() == "true":
        result["HH_VALIDATE_SCHEMAS"] = ""  # Kubesec routing validates the remaining resource types too.
    return result
