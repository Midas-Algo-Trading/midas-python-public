from utils import cli_util
from color import color


commands = []


def add_command(command):
    commands.append(command)


def get_command_names() -> list[str]:
    return [command.name for command in commands]


def get_command(cmd_name: str, args: list[str]):
    if cmd_name in get_command_names():
        for command in commands:
            if command.name != cmd_name:
                continue

            command.func(*args)
    elif cmd_name == 'help' or cmd_name == 'commands':
        print_help()
    else:
        cli_util.output(color.WARNING + f'No commands matched the name {cmd_name!r}')
        cli_util.output(color.WARNING + f"Try typing 'help' for a list of available commands")


def print_help():
    cli_util.output(color.BOLD + 'Commands')
    for command in commands:
        print(f'{command.name} : {command.desc}')
        if command.usage is not None:
            print(f'   usage: {command.usage}')
