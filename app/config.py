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
    r2_endpoint_url: str = os.getenv("R2_ENDPOINT_URL", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    bucket_name: str = os.getenv("BUCKET_NAME", "busca-ordenanza-bucket")


settings = Settings()
