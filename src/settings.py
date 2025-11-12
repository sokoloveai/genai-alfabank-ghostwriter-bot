from dataclasses import dataclass
import os


@dataclass
class Settings:
    bot_token: str
    openai_key: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            openai_key=os.environ["OPENAI_API_KEY"],
        )
