from html import escape

from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot import utils
from src.bot.info.help import build_info_html, build_info_text
from src.core.acl import cmd
from src.core.router import Router
from src.services.crypto import CryptoService
from src.services.weather import WeatherService


info_router = Router('info')


def _extract_arg(msg: Message) -> str:
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ''


@info_router.message(
    cmd('info', 'info', 'help', 'команди', 'допомога')
)
async def info_cmd(msg: Message):
    await utils.edit_or_send_as_text_file(
        msg,
        build_info_html(),
        file_text=build_info_text(),
        filename=f'commands-{msg.id}.txt',
    )


@info_router.message(cmd('info', 'weather', 'погода'))
async def weather_cmd(msg: Message, weather: WeatherService):
    city = _extract_arg(msg)
    if not city:
        await msg.edit(
            '<b>Usage:</b> <code>.weather &lt;city&gt;</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.edit(
        f'<b>Weather:</b> <i>looking up {escape(city)}…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        report = await weather.fetch(city)
    except Exception as e:
        await msg.edit(
            f'<b>Weather error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    if report is None:
        await msg.edit(
            f'<b>Weather:</b> city '
            f'<code>{escape(city)}</code> not found.',
            parse_mode=ParseMode.HTML,
        )
        return

    text = (
        f'<b>{report.icon} {escape(report.location)}</b>\n'
        f'<b>{report.description}</b>\n'
        f'🌡 <b>{report.temperature}°C</b> '
        f'(feels {report.feels_like}°C)\n'
        f'💧 Humidity: {report.humidity}%\n'
        f'💨 Wind: {report.wind} km/h'
    )
    await msg.edit(text, parse_mode=ParseMode.HTML)


@info_router.message(
    cmd('info', 'crypto', 'price', 'крипто', 'ціна')
)
async def crypto_cmd(msg: Message, crypto: CryptoService):
    arg = _extract_arg(msg)
    if not arg:
        await msg.edit(
            '<b>Usage:</b> '
            '<code>.crypto &lt;symbol&gt;</code> '
            '(e.g. <code>btc</code>, <code>eth</code>).',
            parse_mode=ParseMode.HTML,
        )
        return

    symbols = [s.strip() for s in arg.split() if s.strip()]
    await msg.edit(
        '<b>Crypto:</b> <i>fetching…</i>',
        parse_mode=ParseMode.HTML,
    )

    try:
        prices = await crypto.fetch(symbols)
    except Exception as e:
        await msg.edit(
            f'<b>Crypto error:</b> '
            f'<code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
        return

    if not prices:
        await msg.edit(
            '<b>Crypto:</b> no coins found.',
            parse_mode=ParseMode.HTML,
        )
        return

    lines = []
    for coin in prices:
        if coin.usd is None:
            lines.append(
                f'<b>{escape(coin.symbol.upper())}:</b> n/a'
            )
            continue
        change_str = ''
        if coin.change_24h is not None:
            arrow = '🟢' if coin.change_24h >= 0 else '🔴'
            change_str = (
                f' {arrow} {coin.change_24h:+.2f}% (24h)'
            )
        lines.append(
            f'<b>{escape(coin.symbol.upper())}</b> '
            f'<code>{crypto.format_price(coin.usd)}</code>'
            f'{change_str}'
        )

    await msg.edit(
        '<b>💰 Crypto</b>\n' + '\n'.join(lines),
        parse_mode=ParseMode.HTML,
    )
