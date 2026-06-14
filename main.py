
import asyncio
import logging
import os
import re
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("netease-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

NETEASE_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Host": "music.163.com",
    "Origin": "https://music.163.com",
    "Referer": "https://music.163.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Cookie": "appver=2.0.2",
}

SEARCH_URL = "https://music.163.com/api/cloudsearch/pc"
LYRIC_URL  = "http://music.163.com/api/song/lyric"

RESULTS_PER_PAGE = 6

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔍 Search a song")]],
    resize_keyboard=True,
    input_field_placeholder="Or just type a song name…",
)


class SearchState(StatesGroup):
    waiting_for_query = State()


def clean_query(q: str) -> str:
    q = re.sub(r"[「」\"'()\[\]{}\-_/]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def log_debug(tag: str, data):
    try:
        logger.debug("%s: %s", tag, data)
    except Exception:
        logger.debug("%s: <unserializable>", tag)

def is_group(message: Message) -> bool:
    return message.chat.type in ("group", "supergroup")

async def search_songs(session: aiohttp.ClientSession, query: str, limit: int = RESULTS_PER_PAGE):
    query = clean_query(query)

    payload = {
        "s": query,
        "type": 1,
        "limit": limit,
        "offset": 0,
    }

    log_debug("SEARCH_QUERY", query)
    log_debug("SEARCH_PAYLOAD", payload)

    try:
        async with session.get(
                SEARCH_URL,
                params=payload,
                headers=NETEASE_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:

            text = await resp.text()
            log_debug("RAW_RESPONSE_TEXT", text[:1000])

            data = await resp.json(content_type=None)

        songs = data.get("result", {}).get("songs", [])

        log_debug("SONGS_COUNT", len(songs))

        if not songs:
            log_debug("EMPTY_RESPONSE", data)

        songs.sort(key=lambda x: x.get("score", 0), reverse=True)

        results = []
        for s in songs:
            artists = ", ".join(a["name"] for a in s.get("ar", []))
            duration = s.get("dt", 0)

            results.append({
                "id": s["id"],
                "name": s["name"],
                "artists": artists,
                "duration": duration,
            })

        return results

    except Exception:
        logger.exception("Search failed")
        return []


async def get_lyrics(session: aiohttp.ClientSession, song_id: int) -> Optional[str]:
    params = {"os": "pc", "id": song_id, "lv": -1, "kv": -1, "tv": -1}

    try:
        async with session.get(
            LYRIC_URL,
            params=params,
            headers=NETEASE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json(content_type=None)

        lrc = data.get("lrc", {}).get("lyric", "")
        if not lrc or lrc.strip() in ("", "//"):
            return None

        if re.fullmatch(r"\s*\[[\d:\.]+\]\s*", lrc.strip()):
            return None

        return lrc.strip()

    except Exception:
        logger.exception("Lyrics fetch failed")
        return None


def build_results_keyboard(songs: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, s in enumerate(songs):
        duration_s = s["duration"] // 1000
        label = f"{i+1}. {s['name']} — {s['artists']}  [{duration_s//60}:{duration_s%60:02d}]"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"song:{s['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


router_dp = Dispatcher(storage=MemoryStorage())


@router_dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎵 NetEase Song Lyrics Bot\n\nSend me a song name (or artist + song) and I'll search music.163.com for you.",
        reply_markup=MAIN_KEYBOARD,
    )


@router_dp.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext, session: aiohttp.ClientSession):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await _do_search(message, state, session, query_override=args[1].strip())
        return

    if is_group(message):
        await message.answer("❌ Use /search <song name>")
        return

    await state.set_state(SearchState.waiting_for_query)
    await message.answer("🔍 Enter song name:")

@router_dp.message(SearchState.waiting_for_query)
async def handle_query(message: Message, state: FSMContext, session: aiohttp.ClientSession):
    await _do_search(message, state, session)


@router_dp.message(F.text == "🔍 Search a song")
async def handle_button(message: Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await message.answer("🔍 Enter song name:")


@router_dp.message(F.text)
async def handle_text(message: Message, state: FSMContext, session: aiohttp.ClientSession):
    text = message.text or ""

    if is_group(message):
        if not text.startswith("/search"):
            return

        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /search <song name>")
            return

        query = parts[1].strip()
        await _do_search(message, state, session, query_override=query)
        return

    if text.startswith("/search"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            await _do_search(message, state, session, query_override=parts[1].strip())
        else:
            await _do_search(message, state, session)
        return

    await _do_search(message, state, session)


async def _do_search(message, state, session, query_override=""):
    query = clean_query(query_override or message.text)

    await state.clear()
    status = await message.answer(f"🔍 Searching: {query}")

    songs = await search_songs(session, query)

    if not songs:
        await status.edit_text("No results found.")
        return

    await state.update_data(songs={str(s["id"]): s for s in songs})

    text = "🎶 Results:\n\n"
    for i, s in enumerate(songs, 1):
        dur = s["duration"] // 1000
        text += f"{i}. {s['name']} — {s['artists']} ({dur//60}:{dur%60:02d})\n"

    await status.edit_text(
        text,
        reply_markup=build_results_keyboard(songs),
    )


@router_dp.callback_query(F.data.startswith("song:"))
async def handle_song(callback: CallbackQuery, state: FSMContext, session: aiohttp.ClientSession):
    await callback.answer()

    song_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    song = data.get("songs", {}).get(str(song_id))

    if not song:
        await callback.message.answer("Expired. Search again.")
        return

    status = await callback.message.answer("Fetching lyrics...")

    lrc = await get_lyrics(session, song_id)

    if not lrc:
        await status.edit_text("No lyrics found.")
        return

    header = f"🎵 {song['name']} — {song['artists']}\n\nSynced lyrics:"

    chunks = [lrc[i:i + 3900] for i in range(0, len(lrc), 3900)]

    first_chunk = chunks[0]

    await status.edit_text(
        f"{header}\n```\n{first_chunk}\n```",
        parse_mode=ParseMode.MARKDOWN
    )

    for chunk in chunks[1:]:
        await callback.message.answer(
            f"```\n{chunk}\n```",
            parse_mode=ParseMode.MARKDOWN
        )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    async with aiohttp.ClientSession() as session:
        router_dp["session"] = session

        logger.info("Bot started")
        await router_dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())