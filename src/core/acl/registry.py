"""Known modules and commands available for grants.

`afk` and `codex*` settings/auth commands stay owner-only and are
deliberately omitted here.
"""


MODULES: dict[str, set[str]] = {
    'fun': {'type', 'тайп', 'spam', 'спам'},
    'info': {
        'weather', 'погода',
        'crypto', 'price', 'крипто', 'ціна',
    },
    'quote': {'q', 'quote', 'ц', 'цитата'},
    'notes': {'note', 'нотатка', 'notes', 'нотатки'},
    'interpreters': {'run', 'запуск', 'py', 'code', 'код'},
    'ai': {
        'ai', 'ші',
        'chat', 'чат',
        'chatclear',
        'tldr', 'коротко',
        'tr', 'translate', 'пер', 'переклад',
    },
}

ALL_COMMANDS: set[str] = {
    cmd for cmds in MODULES.values() for cmd in cmds
}

DANGEROUS_SCOPES: set[str] = {
    '*',
    'module:interpreters',
    'cmd:py',
    'cmd:run',
    'cmd:code',
}


def normalize_scope(token: str) -> str | None:
    """Convert user input into a canonical scope, or None if invalid."""
    token = token.strip().lower()
    if not token:
        return None
    if token == '*':
        return '*'
    if ':' in token:
        kind, _, name = token.partition(':')
        if kind == 'module' and name in MODULES:
            return token
        if kind == 'cmd' and name in ALL_COMMANDS:
            return token
        return None
    if token in MODULES:
        return f'module:{token}'
    if token in ALL_COMMANDS:
        return f'cmd:{token}'
    return None
