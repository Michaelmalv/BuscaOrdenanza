from pathlib import Path

from app.config import settings
from ingestion.meilisearch_client import MeiliService
from ingestion.meilisearch_payload import markdown_file_to_meilisearch_documents, save_documents_json
from ingestion.pdf_to_markdown import convert_to_md

import boto3
from botocore.config import Config

SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx'}


_s3_client_cache = None

def get_s3_client():
    global _s3_client_cache
    if _s3_client_cache is not None:
        return _s3_client_cache

    if not settings.r2_endpoint_url or not settings.r2_access_key_id or not settings.r2_secret_access_key:
        return None

    _s3_client_cache = boto3.client(
        's3',
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version='s3v4', max_pool_connections=20)
    )
    return _s3_client_cache


def process_uploaded_file(input_path: str, markdown_dir: str, json_dir: str, index_to_meili: bool = True) -> dict:
    source_path = Path(input_path)
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f'Formato no soportado: {source_path.suffix}')

    document_id = source_path.stem
    s3_client = get_s3_client()
    r2_enabled = s3_client is not None

    markdown_dir_path = Path(markdown_dir)
    json_dir_path = Path(json_dir)
    markdown_dir_path.mkdir(parents=True, exist_ok=True)
    json_dir_path.mkdir(parents=True, exist_ok=True)

    # 1. Subir PDF original a R2
    if r2_enabled:
        pdf_key = f"uploads/{source_path.name}"
        s3_client.upload_file(str(source_path), settings.bucket_name, pdf_key)

    # 2. Generar Markdown localmente
    markdown_path = convert_to_md(str(source_path), str(markdown_dir_path))
    markdown_file_path = Path(markdown_path)
    
    # 3. Subir Markdown a R2
    if r2_enabled:
        md_key = f"markdown/{markdown_file_path.name}"
        s3_client.upload_file(str(markdown_file_path), settings.bucket_name, md_key)

    # 4. Segmentar Markdown a fragmentos y guardar JSON localmente
    documents = markdown_file_to_meilisearch_documents(markdown_path)
    json_path = json_dir_path / f'{document_id}.json'
    save_documents_json(documents, str(json_path))

    # 5. Subir JSON a R2
    if r2_enabled:
        json_key = f"json/{json_path.name}"
        s3_client.upload_file(str(json_path), settings.bucket_name, json_key)

    # 6. Indexar en Meilisearch
    meili_task = None
    meili_error = None
    if index_to_meili and settings.meili_url:
        try:
            service = MeiliService.from_settings()
            raw_task = service.index_documents(documents)
            
            # Asegurar serialización JSON
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

    # 7. Eliminar archivos locales temporales si R2 está activo y todo se subió
    if r2_enabled:
        try:
            if source_path.exists():
                source_path.unlink()
            if markdown_file_path.exists():
                markdown_file_path.unlink()
            if json_path.exists():
                json_path.unlink()
        except Exception as e:
            print(f"Error limpiando archivos locales temporales: {e}")

    return {
        'source_file': source_path.name,
        'markdown_path': markdown_path if not r2_enabled else f"markdown/{markdown_file_path.name}",
        'json_path': str(json_path) if not r2_enabled else f"json/{json_path.name}",
        'documents_created': len(documents),
        'meili_task': meili_task,
        'meili_error': meili_error,
    }
