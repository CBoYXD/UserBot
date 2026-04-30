from html import escape


def get_input_msg(language: str, code: str) -> str:
    return (
        '<b>Input:</b>\n'
        f'<pre language="{escape(language)}">'
        f'{escape(code)}</pre>'
    )


def get_input_text(language: str, code: str) -> str:
    return f'Input ({language}):\n{code}'


def get_output_msg(output: str) -> str:
    return (
        '<b>Output:</b>\n'
        f'<pre language="output">{escape(str(output))}</pre>'
    )


def get_output_text(output: str) -> str:
    return f'Output:\n{output}'


def get_process_time_msg(
    start_time: float, end_time: float
) -> str:
    elapsed = round(end_time - start_time, 4)
    return f'<b>Process time: {elapsed}s</b>'


def get_process_time_text(
    start_time: float, end_time: float
) -> str:
    elapsed = round(end_time - start_time, 4)
    return f'Process time: {elapsed}s'


def get_from_terminal_msg(output: str) -> str:
    if output:
        return (
            '<b>From terminal:</b>\n'
            f'<pre language="output">'
            f'{escape(output)}</pre>'
        )
    return ''


def get_from_terminal_text(output: str) -> str:
    if output:
        return f'From terminal:\n{output}'
    return ''


def get_ready_msg(*args: str) -> str:
    return '\n\n'.join(arg for arg in args if arg)


def get_ready_text(*args: str) -> str:
    return '\n\n'.join(arg for arg in args if arg)
