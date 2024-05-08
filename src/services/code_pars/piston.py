from piston_rspy import (
    Client,
    File,
    Executor,
    ExecResult,
)
from .base import ParseCode


class PistonClient:
    def __init__(self):
        self.client = Client()

    async def execute(self, parse_code: ParseCode) -> ExecResult:
        data = await self.client.execute(
            Executor(
                language=parse_code.language,
                files=[File(content=parse_code.code)],
            )
        )
        return data.run
