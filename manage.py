import argparse
import subprocess
from pathlib import Path

from bot import init_session, run_bot


ROOT_DIR = Path(__file__).resolve().parent


def _run_command(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT_DIR, check=True)


def command_run(_args: argparse.Namespace) -> None:
    run_bot()


def command_session_init(_args: argparse.Namespace) -> None:
    me = init_session()
    name = me.first_name or ''
    username = f'@{me.username}' if me.username else 'no username'
    print(
        'Telegram session is ready.\n'
        f'Account: {name} ({username})\n'
        'Session file: userbot.session'
    )


def command_redis_up(_args: argparse.Namespace) -> None:
    _run_command(['docker', 'compose', 'up', '-d', 'redis_db'])


def command_redis_down(_args: argparse.Namespace) -> None:
    _run_command(['docker', 'compose', 'stop', 'redis_db'])


def command_up(_args: argparse.Namespace) -> None:
    _run_command(['docker', 'compose', 'up', '--build'])


def command_down(_args: argparse.Namespace) -> None:
    _run_command(['docker', 'compose', 'down'])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='manage.py',
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

    redis_up_parser = subparsers.add_parser(
        'redis-up',
        help='start only Redis via docker compose',
    )
    redis_up_parser.set_defaults(func=command_redis_up)

    redis_down_parser = subparsers.add_parser(
        'redis-down',
        help='stop only Redis',
    )
    redis_down_parser.set_defaults(func=command_redis_down)

    up_parser = subparsers.add_parser(
        'up',
        help='build and start the full docker compose stack',
    )
    up_parser.set_defaults(func=command_up)

    down_parser = subparsers.add_parser(
        'down',
        help='stop and remove the docker compose stack',
    )
    down_parser.set_defaults(func=command_down)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
