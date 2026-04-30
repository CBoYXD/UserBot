"""Tools the AI assistant can invoke via function-calling."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from src.services.mermaid import MermaidService


MERMAID_TOOL: dict[str, Any] = {
    'type': 'function',
    'name': 'render_mermaid',
    'description': (
        'Render a Mermaid diagram and send it to the chat as a '
        'PNG image. Call this whenever a diagram, flowchart, '
        'sequence diagram, mindmap, gantt, ER, class diagram, '
        'or similar visual would explain the answer better than '
        'plain text. Provide valid Mermaid source. The image is '
        'sent to the user automatically; in your text reply just '
        'briefly note that the diagram was sent.'
    ),
    'parameters': {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'source': {
                'type': 'string',
                'description': (
                    'Full Mermaid diagram source, e.g. '
                    '"graph TD; A-->B". Do NOT wrap in '
                    'markdown code fences.'
                ),
            },
            'caption': {
                'type': 'string',
                'description': (
                    'Optional short caption for the image.'
                ),
            },
        },
        'required': ['source'],
    },
}


ToolDispatch = Callable[[str, dict[str, Any]], Awaitable[str]]


def build_ai_tools(
    mermaid: MermaidService,
    on_image: Callable[[bytes, str | None], Awaitable[None]],
) -> tuple[list[dict[str, Any]], ToolDispatch]:
    """Return ``(tool_specs, dispatch)`` for the AI loop.

    ``on_image`` is called with rendered image bytes and an optional
    caption whenever the model invokes ``render_mermaid``.
    """

    async def dispatch(name: str, args: dict[str, Any]) -> str:
        if name == 'render_mermaid':
            source = (args.get('source') or '').strip()
            if not source:
                return 'error: empty mermaid source'
            caption = args.get('caption') or None
            png = await mermaid.render(source)
            await on_image(png, caption)
            return 'ok: diagram sent to chat'
        return f'error: unknown tool {name!r}'

    return [MERMAID_TOOL], dispatch
