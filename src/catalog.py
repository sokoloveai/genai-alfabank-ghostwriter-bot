from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ThemeConfig:
    slug: str
    hashtag: str
    title: str
    instruction: str


@dataclass(frozen=True)
class ChannelConfig:
    key: str
    name: str
    web_slug: str
    themes: List[ThemeConfig]

    def theme_by_slug(self, slug: str) -> ThemeConfig:
        for theme in self.themes:
            if theme.slug == slug:
                return theme
        raise KeyError(f"unknown theme slug: {slug}")


ALFA_INVESTMENTS_THEMES = [
    ThemeConfig(
        slug="alfa_index",
        hashtag="#альфаиндекс",
        title="#АльфаИндекс",
        instruction=(
            "Ты редактор телеграм-канала Альфа Инвестиции."
            " Создавай сжатые и динамичные посты рубрики #АльфаИндекс."
            " Структура: яркая подводка, ключевые факты с цифрами, лаконичный вывод с призывом следить за рынком."
            " Пиши деловым, но дружелюбным тоном. Упоминай индекс и конкретные активы по необходимости."
            " Длина до 120 слов. Избегай клише."
        ),
    ),
    ThemeConfig(
        slug="fun_investing",
        hashtag="#занимательныеинвестиции",
        title="#ЗанимательныеИнвестиции",
        instruction=(
            "Ты ведешь рубрику #ЗанимательныеИнвестиции в канале Альфа Инвестиции."
            " Объясняй инвестиционные факты через любопытные сравнения, цифры и неожиданные аналогии."
            " Делай вовлекающий, легкий тон, но сохраняй достоверность."
            " Завершай вопросом или предложением обсудить в комментариях."
            " Длина до 140 слов."
        ),
    ),
    ThemeConfig(
        slug="what_to_buy",
        hashtag="#чтокупить",
        title="#ЧтоКупить",
        instruction=(
            "Ты автор подборки #ЧтоКупить в канале Альфа Инвестиции."
            " Давай четкие рекомендации по активам: тезис, причина, цифры или условия входа."
            " Предлагай варианты для разных профилей риска, отмечай риски."
            " Завершай призывом следить за новыми идеями."
            " Длина до 150 слов."
        ),
    ),
    ThemeConfig(
        slug="week_summary",
        hashtag="#главноезанеделю",
        title="#ГлавноеЗаНеделю",
        instruction=(
            "Ты собираешь дайджест #ГлавноеЗаНеделю для канала Альфа Инвестиции."
            " Суммируй 3–4 ключевых события недели, отмечай влияние на рынки и инвесторов."
            " Подчеркивай тренды, цифры, важные даты."
            " Завершай выводом и намеком на ожидания следующей недели."
            " Длина до 160 слов."
        ),
    ),
]


CHANNELS = {
    "alfa_investments": ChannelConfig(
        key="alfa_investments",
        name="Альфа Инвестиции",
        web_slug="alfa_investments",
        themes=ALFA_INVESTMENTS_THEMES,
    ),
}

DEFAULT_CHANNEL_KEY = "alfa_investments"
