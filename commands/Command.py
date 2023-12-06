from __future__ import annotations

from typing import Callable


# Command class to create a new Command
class Command:
    def __init__(self, name: str, desc: str, func: Callable, usage: str | None = None):
        self.name = name
        self.desc = desc
        self.func = func
        self.usage = usage
