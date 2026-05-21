import shlex


def cmd_to_string(cmd: list[str]):
    """Format a bash command as a string."""
    cmd_string = shlex.join(cmd)
    return cmd_string
