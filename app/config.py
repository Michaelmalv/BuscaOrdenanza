import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Busca Ordenanza")
    meili_url: str = os.getenv("MEILI_URL", "http://127.0.0.1:7700")
    meili_master_key: str = os.getenv("MEILI_MASTER_KEY", "")
    meili_index_name: str = os.getenv("MEILI_INDEX_NAME", "documents")


settings = Settings()
