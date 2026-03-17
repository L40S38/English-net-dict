from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = (DATA_DIR / "db" / "data.db").resolve()


class Settings(BaseSettings):
    app_name: str = "English Etymology Dictionary API"
    app_env: str = "development"
    openai_api_key: str = ""
    openai_model_structured: str = "gpt-4o-mini"
    openai_model_chat: str = "gpt-4o-mini"
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1024x1536"
    data_dir: str = str(DATA_DIR.resolve())
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    image_dir: str = str((DATA_DIR / "images").resolve())
    cors_origins: list[str] = ["http://localhost:5173"]
    nltk_data_dir: str = str((DATA_DIR / "nltk_data").resolve())

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
