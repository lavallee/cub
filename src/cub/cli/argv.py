"""
Argv preprocessor for forgiving CLI flag and command handling.

Normalizes sys.argv before Typer parses it, handling common user patterns:
- ``cub --version`` → ``cub version``
- ``cub help run`` → ``cub run --help``
- ``cub run --debug`` → ``cub --debug run``
"""

_GLOBAL_FLAGS = {"--debug"}


def preprocess_argv(argv: list[str]) -> list[str]:
    """Normalize CLI arguments for Typer compatibility.

    Applied rules (in order):
    1. ``--version`` / ``-V`` as first arg → ``version`` subcommand
    2. ``help`` pseudo-command → ``--help`` appended to subcommands
    3. Global flags hoisted before the subcommand
    """
    if not argv:
        return argv

    # Rule 1: --version / -V at top level → version subcommand
    if argv[0] in ("--version", "-V"):
        return ["version"]

    # Rule 2: help pseudo-command → --help
    if argv[0] == "help":
        return _rewrite_help(argv[1:])

    # Rule 3: hoist global flags
    return _hoist_global_flags(argv)


def _rewrite_help(rest: list[str]) -> list[str]:
    """Rewrite ``help [subcmd...]`` into ``[subcmd...] --help``.

    Collects up to 2 non-flag, non-"help" tokens as subcommands.
    """
    subcmds: list[str] = []
    for token in rest:
        if token.startswith("-") or token == "help":
            continue
        subcmds.append(token)
        if len(subcmds) >= 2:
            break
    return [*subcmds, "--help"]


def _hoist_global_flags(argv: list[str]) -> list[str]:
    """Move global flags (e.g. ``--debug``) before the subcommand."""
    hoisted: list[str] = []
    rest: list[str] = []
    seen: set[str] = set()
    for token in argv:
        if token in _GLOBAL_FLAGS:
            if token not in seen:
                hoisted.append(token)
                seen.add(token)
            # Drop duplicates entirely
        else:
            rest.append(token)
    return [*hoisted, *rest]
