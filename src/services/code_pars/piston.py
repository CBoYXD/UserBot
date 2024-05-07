from __future__ import annotations
from piston_rspy import (
    Client,
    File,
    Executor,
    ExecResult,
)
from dataclasses import dataclass


@dataclass
class ParseCodeForPiston:
    language: str
    code: str

    @classmethod
    def parse_tg_msg(cls, msg: str) -> ParseCodeForPiston:
        msg_lines = msg.split('\n')
        msg_lines.pop(0)
        language = msg_lines[0]
        code = '\n'.join(msg_lines[1:])
        return cls(
            language=language,
            code=code,
        )


class PistonClient:
    def __init__(self):
        self.client = Client()

    async def execute(
        self, parse_code: ParseCodeForPiston
    ) -> ExecResult:
        data = await self.client.execute(
            Executor(
                language=parse_code.language,
                files=[File(content=parse_code.code)],
            )
        )
        return data.run
