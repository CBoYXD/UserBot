from ..tools.router import Router
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from asyncio import sleep

intrp_router = Router('intrp')
