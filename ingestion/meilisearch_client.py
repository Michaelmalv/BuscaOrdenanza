from dataclasses import dataclass

from meilisearch import Client

from app.config import settings


@dataclass
class MeiliService:
    client: Client
    index_name: str

    @classmethod
    def from_settings(cls) -> "MeiliService":
        return cls(
            client=Client(settings.meili_url, settings.meili_master_key),
            index_name=settings.meili_index_name,
        )

    def index_documents(self, documents: list[dict]) -> dict:
        index = self.client.index(self.index_name)
        task = index.add_documents(documents, primary_key='id')
        return task

    def search(self, query: str, limit: int = 10) -> dict:
        index = self.client.index(self.index_name)
        return index.search(query, {"limit": limit})
