from __future__ import annotations
from dataclasses import dataclass, field
from .utils import get_lang_by_file_ext


ALL_COMMANDS = ('!s', '!u', '!r')


@dataclass
class ParseCommands:
    save_file: bool = False
    use_file: bool = False
    use_reply: bool = False
    kwargs: dict = field(default_factory=dict)

    @staticmethod
    def _parse_file_command(command: str) -> dict:
        name_of_file = command[3:]
        if '.' not in name_of_file:
            return {'name_of_file': name_of_file}
        dot_idx = name_of_file.rindex('.')
        file_ext = name_of_file[dot_idx + 1:]
        return {
            'name_of_file': name_of_file,
            'language': get_lang_by_file_ext(file_ext),
        }

    @classmethod
    def parse_tg_msg(
        cls, commands_line: str
    ) -> ParseCommands:
        commands = [
            part
            for part in commands_line.split()
            if part.startswith('!')
        ]
        result = cls()
        for command in commands:
            prefix = command[:2]
            if prefix not in ALL_COMMANDS:
                continue
            if prefix == '!s':
                result.save_file = True
                result.kwargs.update(
                    cls._parse_file_command(command)
                )
            elif prefix == '!u':
                result.use_file = True
                result.kwargs.update(
                    cls._parse_file_command(command)
                )
            elif command.strip() == '!r':
                result.use_reply = True
        return result


@dataclass
class ParseCode:
    language: str
    code: str

    @classmethod
    def parse_tg_msg(
        cls,
        code_lines: list[str],
        language: str | None = None,
    ) -> ParseCode:
        idx = 0
        if language is None:
            if not code_lines:
                return cls(language='text', code='')
            language = code_lines[idx].strip()
            idx += 1
        code = '\n'.join(code_lines[idx:])
        return cls(language=language, code=code)
