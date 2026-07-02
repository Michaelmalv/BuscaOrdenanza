import os
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from ingestion.workflow import get_s3_client
from ingestion.meilisearch_client import MeiliService

def index_batch(meili_service, batch):
    try:
        meili_service.index_documents(batch)
        return len(batch)
    except Exception as e:
        print(f"Error indexando lote en Meilisearch: {e}")
        return 0

def process_json_file(args):
    s3_client, bucket_name, key = args
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response['Body'].read().decode('utf-8')
        documents = json.loads(content)
        return documents
    except Exception as e:
        print(f"Error descargando {key}: {e}")
        return []

def main():
    print("=" * 60)
    print("   SINCRONIZACIÓN E INDEXACIÓN MASIVA A MEILISEARCH   ")
    print("=" * 60)
    sys.stdout.flush()

    # 1. Conectar con Meilisearch
    try:
        meili_service = MeiliService.from_settings()
        # Verificar conexión haciendo una llamada simple
        meili_service.client.health()
        print("✔ Conexión con Meilisearch establecida correctamente.")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar con Meilisearch en {settings.meili_url}.")
        print("Asegúrate de que Docker Desktop esté encendido y hayas ejecutado 'docker-compose up -d'.")
        print(f"Detalle del error: {e}")
        return

    # 2. Conectar con Cloudflare R2
    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] No se pudieron cargar las credenciales de R2 en el archivo .env.")
        return

    print("✔ Conexión con Cloudflare R2 establecida.")
    sys.stdout.flush()

    # 3. Listar archivos JSON en R2
    print("\nListando fragmentos JSON en el bucket de R2...")
    sys.stdout.flush()
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=settings.bucket_name, Prefix="json/")
        json_keys = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith('.json'):
                        json_keys.append(key)
        print(f"Se encontraron {len(json_keys)} documentos JSON en Cloudflare R2.")
        sys.stdout.flush()
    except Exception as e:
        print(f"[ERROR] Falló el listado de R2: {e}")
        return

    if not json_keys:
        print("No hay fragmentos JSON que indexar en R2. Por favor sube archivos primero.")
        return

    # 4. Descargar y preparar los documentos en paralelo
    print(f"\nDescargando y preparando documentos para indexar (usando 20 hilos en paralelo)...")
    sys.stdout.flush()
    
    all_documents = []
    download_args = [(s3_client, settings.bucket_name, key) for key in json_keys]
    
    start_download = time.time()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_json_file, arg): arg for arg in download_args}
        for idx, future in enumerate(as_completed(futures), 1):
            docs = future.result()
            all_documents.extend(docs)
            if idx % 500 == 0 or idx == len(json_keys):
                print(f"  --> Descargados {idx}/{len(json_keys)} archivos JSON...")
                sys.stdout.flush()

    download_duration = time.time() - start_download
    print(f"✔ Descarga completada en {download_duration:.2f} segundos.")
    print(f"Total de fragmentos individuales a indexar: {len(all_documents)}")
    sys.stdout.flush()

    # 5. Purgar índice existente para evitar duplicaciones viejas
    try:
        print("\nPurgando índice existente en Meilisearch para iniciar limpio...")
        index = meili_service.client.index(settings.meili_index_name)
        index.delete()
        print("✔ Índice purgado con éxito.")
    except Exception:
        # El índice podría no existir aún, lo cual es normal
        pass

    # Configurar filtros y búsquedas en Meilisearch
    try:
        # Volver a crear y configurar el índice
        index = meili_service.client.index(settings.meili_index_name)
        index.update_settings({
            'searchableAttributes': ['title', 'section', 'content_text'],
            'filterableAttributes': ['document_id', 'source'],
            'rankingRules': [
                'words',
                'typo',
                'proximity',
                'attribute',
                'sort',
                'exactness'
            ]
        })
        print("✔ Configuraciones del índice de Meilisearch actualizadas.")
    except Exception as e:
        print(f"Advertencia al configurar índice: {e}")

    # 6. Indexar en lotes de 200 documentos en Meilisearch
    print(f"\nIndexando {len(all_documents)} fragmentos en Meilisearch...")
    sys.stdout.flush()

    batch_size = 200
    batches = [all_documents[i:i + batch_size] for i in range(0, len(all_documents), batch_size)]
    
    indexed_count = 0
    start_indexing = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(index_batch, meili_service, batch): batch for batch in batches}
        for idx, future in enumerate(as_completed(futures), 1):
            count = future.result()
            indexed_count += count
            if idx % 50 == 0 or idx == len(batches):
                print(f"  --> Indexados {indexed_count}/{len(all_documents)} fragmentos...")
                sys.stdout.flush()

    indexing_duration = time.time() - start_indexing
    print(f"✔ Indexación completada en {indexing_duration:.2f} segundos.")
    print("-" * 60)
    print(f"   SINCRONIZACIÓN EXITOSA: {indexed_count} fragmentos listos para buscar.")
    print("=" * 60)
    sys.stdout.flush()

if __name__ == '__main__':
    main()
