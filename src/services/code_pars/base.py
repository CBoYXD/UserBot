from __future__ import annotations
from dataclasses import dataclass
from .utils import get_lang_by_file_ext
from typing import Optional


@dataclass
class ParseCommands:
    save_file: bool
    use_file: bool
    kwargs: dict
    # will be more commands

    @classmethod
    @property
    def all_commands(self) -> list[str]:
        return ['!s', '!u']

    @staticmethod
    def __use_file(command: str) -> dict:
        name_of_file = command[3:]
        dot_in_file = name_of_file.index('.')
        file_ext = name_of_file[dot_in_file + 1 :]
        return {
            'name_of_file': name_of_file,
            'language': get_lang_by_file_ext(file_ext),
        }

    @staticmethod
    def __save_file(command: str) -> dict:
        name_of_file = command[3:]
        dot_in_file = name_of_file.index('.')
        file_ext = name_of_file[dot_in_file + 1 :]
        return {
            'name_of_file': name_of_file,
            'language': get_lang_by_file_ext(file_ext),
        }

    @classmethod
    def parse_tg_msg(cls, commands_line: str):
        commands = [
            command
            for command in commands_line.split()
            if command.startswith('!')
        ]  # create list, remove filter command
        save_file = False
        use_file = False
        kwargs = {}
        if bool(commands):  # if command in list
            for command in commands:
                if command[:2] not in cls.all_commands:
                    return None
                else:
                    if command.startswith(
                        '!s'
                    ):  # use all separators like - or .
                        save_file = True
                        kwargs.update(
                            **ParseCommands.__save_file(command)
                        )
                    if command.startswith('!u'):
                        use_file = True
                        kwargs.update(
                            **ParseCommands.__use_file(command)
                        )

        return ParseCommands(
            save_file=save_file, use_file=use_file, kwargs=kwargs
        )


@dataclass
class ParseCode:
    language: str
    code: str

    @classmethod
    def parse_tg_msg(
        cls, code_lines: list[str], language: str = None
    ) -> ParseCode:
        index = 0  # If language is None mus be another list index
        if language is None:
            language = code_lines[index]
            index += 1
        code = '\n'.join(code_lines[index:])
        return cls(language=language, code=code)
