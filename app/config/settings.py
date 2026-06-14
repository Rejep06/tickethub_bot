from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    MANAGERS_CHAT_ID: int
    MANAGER_IDS: str = ""
    RUN_DB_CREATE_ALL: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def manager_ids(self) -> list[int]:
        if not self.MANAGER_IDS.strip():
            return []

        ids: list[int] = []
        for raw_id in self.MANAGER_IDS.split(","):
            raw_id = raw_id.strip()
            if raw_id:
                ids.append(int(raw_id))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
