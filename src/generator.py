import asyncio
import logging
import re
from typing import Optional, Sequence

from openai import OpenAI

from config import MODEL_NAME, TEMPERATURE, TOP_P
from src.catalog import ThemeConfig
from src.stylizer import theme_messages


class TextGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = MODEL_NAME,
        temperature: float = TEMPERATURE,
        top_p: float = TOP_P,
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _sanitize_output(text: str) -> str:
        if not text:
            return text
        sanitized = text.replace("—", "-").replace("–", "-")
        sanitized = sanitized.replace("ё", "е").replace("Ё", "Е")
        sanitized = sanitized.replace("\r\n", "\n").replace("\r", "\n")
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
        sanitized = "\n".join(line.rstrip() for line in sanitized.split("\n"))
        sanitized = re.sub(r" {3,}", "  ", sanitized)
        lines = sanitized.split("\n")
        merged: list[str] = []
        for line in lines:
            stripped = line.strip()
            is_symbolic = len(stripped) <= 2 and not any(ch.isalnum() for ch in stripped)
            if is_symbolic and merged:
                merged[-1] = (merged[-1].rstrip() + " " + stripped).strip()
            else:
                if stripped == "":
                    if merged and merged[-1].strip() == "":
                        continue
                merged.append(line)
        sanitized = "\n".join(merged).strip()
        return sanitized

    @staticmethod
    def _looks_like_refusal(text: str) -> bool:
        if not text:
            return True
        lowered = text.strip().lower()
        bad_markers = [
            "я не могу", "не могу выполнить", "к сожалению", "жду", "ожидаю",
            "пришлите текст", "как ии", "не имею возможности", "cannot", "sorry",
        ]
        return any(marker in lowered for marker in bad_markers)

    async def generate_post(
        self,
        theme: ThemeConfig,
        source_text: str,
        topic_hint: Optional[str] = None,
        extra_context: Optional[str] = None,
        examples: Optional[Sequence[str]] = None,
    ) -> str:
        messages = theme_messages(theme, source_text, topic_hint, extra_context, examples)
        num_examples = len(examples) if examples else 0
        self.logger.info("Few-shot примеров: %d", num_examples)
        if examples:
            for index, example in enumerate(examples, start=1):
                self.logger.info("FEW-SHOT #%d:\n%s", index, example)
        system_prompt_text = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt_text = msg.get("content", "")
                break
        if system_prompt_text:
            self.logger.info("SYSTEM PROMPT (полный):\n%s", system_prompt_text)
        self.logger.info(
            "Запрос к модели: канал=%s тема=%s topic_hint=%s examples=%d model=%s T=%.2f top_p=%.2f",
            theme.hashtag,
            theme.slug,
            topic_hint,
            len(examples) if examples else 0,
            self.model,
            self.temperature,
            self.top_p,
        )
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        content = self._sanitize_output(content)
        if self._looks_like_refusal(content):
            self.logger.warning("Обнаружен отказ/служебный ответ, выполняю повторную генерацию")
            reinforce = {
                "role": "system",
                "content": (
                    "Пересобери без служебных фраз и отказов. "
                    "Верни только текст поста в требуемом стиле."
                ),
            }
            second = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[*messages, reinforce],
                temperature=max(0.3, self.temperature - 0.2),
                top_p=self.top_p,
            )
            content = (second.choices[0].message.content or "").strip()
            content = self._sanitize_output(content)
        self.logger.info("Ответ модели получен, длина=%d", len(content))
        return content
