from ingestion.meilisearch_payload import markdown_file_to_meilisearch_documents, save_documents_json


def markdown_to_json(markdown_path: str, output_path: str) -> list[dict]:
    documents = markdown_file_to_meilisearch_documents(markdown_path)
    save_documents_json(documents, output_path)
    return documents
