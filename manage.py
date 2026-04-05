import argparse
from bot import init_session, run_bot

def command_run(_args: argparse.Namespace) -> None:
    run_bot()


def command_session_init(_args: argparse.Namespace) -> None:
    me = init_session()
    name = me.first_name or ''
    username = f'@{me.username}' if me.username else 'no username'
    print(
        'Telegram session is ready.\n'
        f'Account: {name} ({username})\n'
        'Session file: userbot.session\n'
        'You can now start the bot locally or with docker compose.'
    )
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='userbot',
        description='UserBot local CLI',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    run_parser = subparsers.add_parser(
        'run',
        help='run the userbot in the current shell',
    )
    run_parser.set_defaults(func=command_run)

    session_parser = subparsers.add_parser(
        'session-init',
        help='create or refresh the Telegram session',
    )
    session_parser.set_defaults(func=command_session_init)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
