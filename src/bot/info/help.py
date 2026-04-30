from html import escape


COMMAND_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        'ℹ️ Info',
        [
            (
                '.info / .help / .команди / .допомога',
                'Show this help with all commands.',
            ),
            (
                '.weather / .погода <city>',
                'Current weather report for a city.',
            ),
            (
                '.crypto / .price / .крипто / .ціна <symbol…>',
                'USD price and 24h change (e.g. btc eth).',
            ),
        ],
    ),
    (
        'Agent',
        [
            ('.agent status', 'Show local agent and Ollama status.'),
            (
                '.agent on / .agent off',
                'Enable or disable message ingestion.',
            ),
            (
                '.agent model [name]',
                'Show or set local Ollama model.',
            ),
            (
                '.agent ask <prompt>',
                'Ask the local Ollama agent with chat context.',
            ),
            (
                '.agent memory <query>',
                'Ask using stored local chat memory.',
            ),
            (
                '.agent context [N]',
                'Show recent stored context for this chat.',
            ),
            (
                '.agent autoreply on|off',
                'Configure auto-reply flag for this chat.',
            ),
        ],
    ),
    (
        '🤖 AI',
        [
            (
                '.ai / .ші <prompt>',
                'One-shot question: Codex first, local Ollama fallback.',
            ),
            (
                '.chat / .чат <message>',
                'Chat memory: Codex first, local Ollama fallback.',
            ),
            ('.chatclear', 'Clear current chat history.'),
            (
                '.tldr / .коротко [N]',
                'Summarize last N messages (default 50).',
            ),
            (
                '.tr / .translate / .пер / .переклад [lang] <text|reply>',
                'Translate text; Ollama fallback prefers translategemma.',
            ),
            ('.aimodel', 'Show current AI model and effort.'),
            ('.codexmodel [name]', 'Show or set Codex model.'),
            (
                '.codexeffort [low|medium|high]',
                'Show or set reasoning effort.',
            ),
            ('.codexreset', 'Reset AI settings to defaults.'),
            ('.codexlogin', 'Start Codex OAuth flow.'),
            ('.codexauth <redirect_url>', 'Finish Codex OAuth.'),
            ('.codexstatus', 'Show Codex auth status.'),
            ('.codexlogout', 'Clear Codex auth state.'),
        ],
    ),
    (
        '📝 Notes',
        [
            (
                '.note / .нотатка <text|reply>',
                'Save a note (auto-tagged).',
            ),
            ('.note show <id>', 'Show a saved note.'),
            ('.note rm <id>', 'Delete a saved note.'),
            ('.note find <query>', 'Search notes by text.'),
            (
                '.notes / .нотатки [#tag]',
                'List all notes (optionally by tag).',
            ),
        ],
    ),
    (
        '💻 Code',
        [
            (
                '.run / .запуск <lang> <code>',
                'Execute code via Piston.',
            ),
            ('.py <code>', 'Run Python in-process.'),
            (
                '.code / .код save <name> <lang> <code>',
                'Save a code snippet.',
            ),
            ('.code run <name>', 'Run a saved snippet.'),
            ('.code show <name>', 'Show a saved snippet.'),
            ('.code ls', 'List saved snippets.'),
            ('.code rm <name>', 'Delete a saved snippet.'),
        ],
    ),
    (
        '💬 Quote',
        [
            (
                '.q / .quote / .ц / .цитата (reply)',
                'Render replied message as a quote sticker.',
            ),
        ],
    ),
    (
        '🎉 Fun',
        [
            (
                '.type / .тайп <text>',
                'Animated typing effect.',
            ),
            (
                '.spam / .спам <N> (reply)',
                'Reply N times mentioning the user.',
            ),
        ],
    ),
    (
        '🔐 Permissions',
        [
            (
                '.allow <user> <module|cmd|*>',
                'Grant a scope to another user.',
            ),
            (
                '.disallow <user> [scope]',
                'Revoke one scope or all grants.',
            ),
            (
                '.allowed [user]',
                'List grants for a user or everyone.',
            ),
        ],
    ),
]


def build_info_html() -> str:
    lines: list[str] = ['<b>📖 Commands</b>']
    for title, entries in COMMAND_SECTIONS:
        lines.append('')
        lines.append(f'<b>{escape(title)}</b>')
        for cmd, desc in entries:
            lines.append(
                f'<code>{escape(cmd)}</code> — {escape(desc)}'
            )
    return '\n'.join(lines)


def build_info_text() -> str:
    lines: list[str] = ['Commands']
    for title, entries in COMMAND_SECTIONS:
        lines.append('')
        lines.append(title)
        for cmd, desc in entries:
            lines.append(f'  {cmd} — {desc}')
    return '\n'.join(lines)
