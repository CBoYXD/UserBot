import json
from typing import Any

import httpx

from src.services.codex.constants import RESPONSES_URL


def clamp_reasoning_effort(reasoning_effort: str) -> str:
    if reasoning_effort == 'minimal':
        return 'low'
    return reasoning_effort


def build_body(
    messages: list[dict[str, str]],
    system_instruction: str | None,
    session_id: str | None,
    model: str,
    reasoning_effort: str,
    tools: list[dict[str, Any]] | None = None,
    extra_input: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    input_messages: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        role = message.get('role')
        text = message.get('text', '')
        if role == 'user':
            input_messages.append(
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': text,
                        }
                    ],
                }
            )
            continue

        input_messages.append(
            {
                'type': 'message',
                'role': 'assistant',
                'content': [
                    {
                        'type': 'output_text',
                        'text': text,
                        'annotations': [],
                    }
                ],
                'status': 'completed',
                'id': f'msg_{index}',
            }
        )

    if extra_input:
        input_messages.extend(extra_input)

    body: dict[str, Any] = {
        'model': model,
        'store': False,
        'stream': True,
        'input': input_messages,
        'text': {'verbosity': 'medium'},
        'include': ['reasoning.encrypted_content'],
        'tool_choice': 'auto',
        'parallel_tool_calls': True,
    }
    if tools:
        body['tools'] = tools
    if system_instruction:
        body['instructions'] = system_instruction
    if session_id:
        body['prompt_cache_key'] = session_id
    if reasoning_effort:
        body['reasoning'] = {
            'effort': clamp_reasoning_effort(reasoning_effort),
            'summary': 'auto',
        }
    return body


def build_headers(
    credentials: dict[str, Any],
    session_id: str | None,
) -> dict[str, str]:
    headers = {
        'Authorization': f"Bearer {credentials['access']}",
        'chatgpt-account-id': str(credentials['account_id']),
        'originator': 'pi',
        'User-Agent': 'UserBot Codex OAuth',
        'OpenAI-Beta': 'responses=experimental',
        'accept': 'text/event-stream',
        'content-type': 'application/json',
    }
    if session_id:
        headers['session_id'] = session_id
    return headers


def extract_response_text(response: dict[str, Any]) -> str:
    output = response.get('output')
    if not isinstance(output, list):
        return ''

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get('type') != 'message':
            continue
        content = item.get('content')
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') in {
                'output_text',
                'refusal',
            }:
                text = block.get('text')
                if isinstance(text, str) and text:
                    parts.append(text)
    return ''.join(parts)


def process_sse_event(
    event_lines: list[str],
    text_parts: list[str],
    final_response: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not event_lines:
        return final_response

    payload = '\n'.join(event_lines).strip()
    if not payload or payload == '[DONE]':
        return final_response

    event = json.loads(payload)
    event_type = event.get('type')
    if event_type == 'error':
        message = event.get('message') or 'Codex error'
        raise RuntimeError(str(message))
    if event_type == 'response.failed':
        error = event.get('response', {}).get('error', {})
        message = (
            error.get('message') or 'Codex response failed'
        )
        raise RuntimeError(str(message))
    if event_type in {
        'response.output_text.delta',
        'response.refusal.delta',
    }:
        delta = event.get('delta')
        if isinstance(delta, str):
            text_parts.append(delta)
        return final_response
    if event_type in {
        'response.completed',
        'response.done',
        'response.incomplete',
    }:
        response = event.get('response')
        if isinstance(response, dict):
            return response
    return final_response


async def stream_response(
    http: httpx.AsyncClient,
    credentials: dict[str, Any],
    body: dict[str, Any],
    session_id: str | None,
) -> tuple[str, dict[str, Any] | None]:
    headers = build_headers(credentials, session_id)
    text_parts: list[str] = []
    final_response: dict[str, Any] | None = None
    async with http.stream(
        'POST',
        RESPONSES_URL,
        headers=headers,
        json=body,
    ) as response:
        if response.status_code >= 400:
            detail = await response.aread()
            message = detail.decode(
                'utf-8', errors='replace'
            )
            raise httpx.HTTPStatusError(
                message,
                request=response.request,
                response=response,
            )

        event_lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                final_response = process_sse_event(
                    event_lines,
                    text_parts,
                    final_response,
                )
                event_lines = []
                continue
            if line.startswith('data:'):
                event_lines.append(line[5:].strip())

        if event_lines:
            final_response = process_sse_event(
                event_lines,
                text_parts,
                final_response,
            )

    text = ''.join(text_parts).strip()
    if not text and final_response:
        text = extract_response_text(final_response).strip()
    return text, final_response
