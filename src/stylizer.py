from typing import Optional, Sequence
import re

from src.catalog import ThemeConfig
from src.prompt import SYSTEM_PROMPT_TEMPLATE


def _detect_max_words(instruction: str, default: int = 140) -> int:
    match = re.search(r"до\\s+(\\d+)\\s+слов", instruction, flags=re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return default
    return default


def _is_emoji_base(ch: str) -> bool:
    code = ord(ch)
    return (0x2600 <= code <= 0x27BF) or (0x1F000 <= code <= 0x1FAFF)


def _extract_emoji_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    last_index = -1
    for ch in text:
        if _is_emoji_base(ch):
            tokens.append(ch)
            last_index = len(tokens) - 1
            continue
        if ord(ch) == 0xFE0F and last_index >= 0:
            tokens[last_index] = tokens[last_index] + ch
    seen = set()
    uniq: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _collect_emoji_whitelist(source_text: str, examples: Optional[Sequence[str]]) -> list[str]:
    whitelist: list[str] = []
    for token in _extract_emoji_tokens(source_text or ""):
        if token not in whitelist:
            whitelist.append(token)
    if examples:
        for ex in examples:
            for token in _extract_emoji_tokens(ex):
                if token not in whitelist:
                    whitelist.append(token)
    return whitelist[:20]


def _detect_list_marker(examples: Optional[Sequence[str]], whitelist: list[str], source_text: str) -> Optional[str]:
    if not whitelist:
        return None
    counts: dict[str, int] = {}
    def feed_line(line: str) -> None:
        stripped = line.lstrip()
        for token in whitelist:
            if stripped.startswith(token):
                counts[token] = counts.get(token, 0) + 1
                break
    if examples:
        for ex in examples:
            for line in ex.splitlines():
                feed_line(line)
    for line in (source_text or "").splitlines():
        feed_line(line)
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def theme_messages(
    theme: ThemeConfig,
    source_text: str,
    topic_hint: Optional[str] = None,
    extra_context: Optional[str] = None,
    examples: Optional[Sequence[str]] = None,
) -> list[dict[str, str]]:
    base_text = (source_text or "").strip() or "нет"
    examples_block = "нет"
    if examples:
        formatted = []
        for index, example in enumerate(examples[:5]):
            formatted.append(f"Пример {index + 1}:\n{example.strip()}")
        examples_block = "\n\n".join(formatted)
    emoji_whitelist = _collect_emoji_whitelist(base_text, examples)
    list_marker = _detect_list_marker(examples, emoji_whitelist, base_text)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        channel_name="Альфа Инвестиции",
        theme_title=theme.title,
        theme_hashtag=theme.hashtag,
        theme_instruction=theme.instruction.strip(),
        examples_block=examples_block,
        source_text=base_text,
        extra_context=(extra_context or "").strip() or "нет",
        topic_hint=(topic_hint or "").strip() or "нет",
        max_words=_detect_max_words(theme.instruction),
        emoji_whitelist=(" ".join(emoji_whitelist) if emoji_whitelist else "нет"),
        list_marker_hint=(list_marker or "нет"),
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Верни только текст поста без лишних пояснений."},
    ]
