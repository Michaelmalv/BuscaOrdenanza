from pathlib import Path

from app.config import settings
from ingestion.meilisearch_client import MeiliService
from ingestion.meilisearch_payload import markdown_file_to_meilisearch_documents, save_documents_json
from ingestion.pdf_to_markdown import convert_to_md

SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx'}


def process_uploaded_file(input_path: str, markdown_dir: str, json_dir: str, index_to_meili: bool = True) -> dict:
    source_path = Path(input_path)
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f'Formato no soportado: {source_path.suffix}')

    markdown_dir_path = Path(markdown_dir)
    json_dir_path = Path(json_dir)
    markdown_dir_path.mkdir(parents=True, exist_ok=True)
    json_dir_path.mkdir(parents=True, exist_ok=True)

    markdown_path = convert_to_md(str(source_path), str(markdown_dir_path))
    documents = markdown_file_to_meilisearch_documents(markdown_path)

    json_path = json_dir_path / f'{source_path.stem}.json'
    save_documents_json(documents, str(json_path))

    meili_task = None
    meili_error = None
    if index_to_meili and settings.meili_url:
        try:
            service = MeiliService.from_settings()
            raw_task = service.index_documents(documents)
            
            # Ensure it is JSON serializable for FastAPI responses
            if hasattr(raw_task, 'task_uid'):
                meili_task = {
                    'taskUid': raw_task.task_uid,
                    'status': getattr(raw_task, 'status', 'enqueued'),
                    'type': getattr(raw_task, 'type', 'documentAdditionOrUpdate')
                }
            elif isinstance(raw_task, dict):
                meili_task = raw_task
            else:
                meili_task = str(raw_task)
        except Exception as exc:
            meili_error = str(exc)

    return {
        'source_file': source_path.name,
        'markdown_path': markdown_path,
        'json_path': str(json_path),
        'documents_created': len(documents),
        'meili_task': meili_task,
        'meili_error': meili_error,
    }
