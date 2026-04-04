from google import genai
from google.genai import types


class GeminiClient:
    def __init__(self, api_key: str, model: str = 'gemini-2.5-flash'):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text or ''

    async def chat(
        self,
        messages: list[dict],
        system_instruction: str | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
        )
        contents = []
        for m in messages:
            role = 'user' if m['role'] == 'user' else 'model'
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=m['text'])],
                )
            )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        return response.text or ''
