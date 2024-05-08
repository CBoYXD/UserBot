from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParseCommands:
    save_file: bool
    # will be more commands

    @classmethod
    @property
    def all_commands(self) -> list[str]:
        return ['!s']

    @classmethod
    def init(cls, commands_line: str):
        commands = [
            command
            for command in commands_line.split()
            if command.startswith('!')
        ]  # create list, remove filter command
        save_file = False
        for command in commands:
            if command not in cls.all_commands:
                return None
            else:
                if command == '!s':
                    save_file = True
        return ParseCommands(save_file=save_file)


@dataclass
class ParseCode:
    language: str
    code: str
    commands: Optional[ParseCommands]

    @classmethod
    def parse_tg_msg(
        cls, msg: str, language: str = None
    ) -> ParseCode:
        msg_lines = msg.split('\n')
        commands = ParseCommands.init(msg_lines[0])
        index = 1  # If language is None mus be another list index
        if language is None:
            language = msg_lines[index]
            index += 1
        code = '\n'.join(msg_lines[index:])
        return cls(language=language, code=code, commands=commands)
