import json
import uuid
from pathlib import Path

from ingestion.markdown_chunker import markdown_to_plain_text, split_markdown_by_headers


def markdown_file_to_meilisearch_documents(
    markdown_path: str,
    document_id: str | None = None,
    source_name: str | None = None,
    title: str | None = None,
) -> list[dict]:
    path = Path(markdown_path)
    markdown = path.read_text(encoding='utf-8')

    if document_id is None:
        document_id = path.stem
    if source_name is None:
        source_name = path.name
    if title is None:
        title = path.stem.replace('_', ' ').replace('-', ' ').title()

    documents = []
    chunks = split_markdown_by_headers(markdown)

    for index, chunk in enumerate(chunks, start=1):
        content_markdown = chunk['content_markdown'].strip()
        if not content_markdown:
            continue

        documents.append({
            'id': f'{document_id}-{index}-{uuid.uuid4().hex[:8]}',
            'document_id': document_id,
            'title': title,
            'section': chunk['section'],
            'chunk_number': index,
            'source': source_name,
            'content_markdown': content_markdown,
            'content_text': markdown_to_plain_text(content_markdown),
        })

    return documents


def save_documents_json(documents: list[dict], output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
