import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from src.catalog import CHANNELS, DEFAULT_CHANNEL_KEY, ChannelConfig, ThemeConfig
from src.generator import TextGenerator
from src.settings import Settings
from src.web import fetch_theme_samples


@dataclass
class SessionState:
    channel_key: Optional[str] = None
    theme_slug: Optional[str] = None
    examples: Optional[list[str]] = None


SESSIONS: Dict[int, SessionState] = {}
logger = logging.getLogger("ghostwriter.bot")


def split_topic(text: str) -> tuple[str, Optional[str]]:
    topic = None
    lines = []
    for line in text.splitlines():
        lower_line = line.lower()
        if lower_line.startswith("тема:"):
            topic = line.split(":", 1)[1].strip() or None
        else:
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    return cleaned, topic


def get_state(chat_id: int) -> SessionState:
    state = SESSIONS.get(chat_id)
    if state is None:
        state = SessionState()
        SESSIONS[chat_id] = state
    return state


def build_channels_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=channel.name,
                callback_data=f"channel:{channel.key}",
            )
        ]
        for channel in CHANNELS.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_themes_keyboard(channel: ChannelConfig) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=theme.title,
                callback_data=f"theme:{channel.key}:{theme.slug}",
            )
        ]
        for theme in channel.themes
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ensure_channel(state: SessionState) -> ChannelConfig:
    key = state.channel_key or DEFAULT_CHANNEL_KEY
    return CHANNELS[key]


def ensure_theme(channel: ChannelConfig, state: SessionState) -> Optional[ThemeConfig]:
    if state.theme_slug is None:
        return None
    try:
        return channel.theme_by_slug(state.theme_slug)
    except KeyError:
        return None


def build_router(generator: TextGenerator) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def handle_start(message: Message) -> None:
        greeting = (
            "Привет. Я помогаю готовить посты для телеграм-каналов."
            " Отправь текст."
            " Сначала выбери канал и рубрику, затем пришли материалы."
        )
        await message.answer(greeting, reply_markup=build_channels_keyboard())

    @router.callback_query(F.data.startswith("channel:"))
    async def handle_channel(callback: CallbackQuery) -> None:
        if not callback.data:
            await callback.answer()
            return
        _, channel_key = callback.data.split(":", 1)
        if channel_key not in CHANNELS:
            await callback.answer("Неизвестный канал", show_alert=True)
            return
        state = get_state(callback.message.chat.id)
        state.channel_key = channel_key
        state.theme_slug = None
        state.examples = None
        logger.info("Выбран канал %s для чата %s", channel_key, callback.message.chat.id)
        channel = CHANNELS[channel_key]
        await callback.message.answer(
            f"Канал «{channel.name}» выбран. Теперь выберите рубрику:",
            reply_markup=build_themes_keyboard(channel),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("theme:"))
    async def handle_theme(callback: CallbackQuery) -> None:
        if not callback.data:
            await callback.answer()
            return
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer()
            return
        _, channel_key, theme_slug = parts
        if channel_key not in CHANNELS:
            await callback.answer("Канал не найден", show_alert=True)
            return
        channel = CHANNELS[channel_key]
        try:
            theme = channel.theme_by_slug(theme_slug)
        except KeyError:
            await callback.answer("Рубрика не найдена", show_alert=True)
            return
        state = get_state(callback.message.chat.id)
        state.channel_key = channel.key
        state.theme_slug = theme.slug
        state.examples = None
        logger.info(
            "Выбрана рубрика %s для чата %s",
            theme.slug,
            callback.message.chat.id,
        )
        await callback.message.answer(
            f"Отлично! Рубрика {theme.title} активна.\nПришли текст.",
        )
        await callback.answer()

    @router.message()
    async def handle_text(message: Message) -> None:
        original_text = message.text or ""
        state = get_state(message.chat.id)
        if state.channel_key is None:
            await message.answer(
                "Выбери канал, чтобы продолжить:",
                reply_markup=build_channels_keyboard(),
            )
            return
        channel = ensure_channel(state)
        theme = ensure_theme(channel, state)
        if theme is None:
            await message.answer(
                "Сначала выбери рубрику:",
                reply_markup=build_themes_keyboard(channel),
            )
            return
        body, topic = split_topic(original_text)
        if not body:
            await message.answer("Нужен текст, чтобы собрать пост.")
            return
        examples = state.examples
        if examples is None:
            try:
                logger.info(
                    "Подгружаю примеры для %s/%s",
                    channel.web_slug,
                    theme.hashtag,
                )
                examples = await fetch_theme_samples(channel.web_slug, theme.hashtag)
            except Exception:
                logger.exception("Не удалось получить примеры для %s", theme.hashtag)
                examples = []
            state.examples = examples
        try:
            result = await generator.generate_post(
                theme,
                body,
                topic_hint=topic,
                extra_context=None,
                examples=examples,
            )
        except Exception:
            await message.answer("Не получилось подготовить пост. Попробуй еще раз позже.")
            return
        if not result:
            await message.answer("Ответ пустой. Попробуй переформулировать запрос.")
            return
        logger.info("Сообщение сгенерировано для чата %s", message.chat.id)
        await message.answer(result)
        await message.answer(
            "Хочешь попробовать в другой рубрике?",
            reply_markup=build_themes_keyboard(channel),
        )

    return router


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()
    settings = Settings.load()
    generator = TextGenerator(settings.openai_key)
    bot = Bot(token=settings.bot_token, parse_mode="HTML")
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(generator))
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
