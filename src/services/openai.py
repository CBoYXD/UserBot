import asyncio

from openai import OpenAI


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = 'gpt-5-codex',
        reasoning_effort: str = 'medium',
    ):
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self._create_response,
            prompt,
            system_instruction,
        )

    async def chat(
        self,
        messages: list[dict],
        system_instruction: str | None = None,
    ) -> str:
        input_messages = [
            {
                'role': self._map_role(message['role']),
                'content': message['text'],
            }
            for message in messages
        ]
        return await asyncio.to_thread(
            self._create_response,
            input_messages,
            system_instruction,
        )

    def _create_response(
        self,
        input_data: str | list[dict[str, str]],
        system_instruction: str | None = None,
    ) -> str:
        request: dict = {
            'model': self._model,
            'input': input_data,
        }
        if system_instruction:
            request['instructions'] = system_instruction
        if self._reasoning_effort:
            request['reasoning'] = {
                'effort': self._reasoning_effort,
            }
        response = self._client.responses.create(**request)
        return response.output_text or ''

    @staticmethod
    def _map_role(role: str) -> str:
        if role == 'user':
            return 'user'
        return 'assistant'
