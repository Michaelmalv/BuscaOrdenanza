import os
import sys
import json
import time
import gzip
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from ingestion.workflow import get_s3_client

def download_and_parse_json(args):
    s3_client, bucket_name, key = args
    retries = 3
    for attempt in range(retries):
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            chunks = json.loads(content)
            
            # Strip content_markdown to keep search_index light
            clean_chunks = []
            for chunk in chunks:
                clean_chunk = {
                    'id': chunk.get('id'),
                    'document_id': chunk.get('document_id'),
                    'title': chunk.get('title'),
                    'section': chunk.get('section'),
                    'chunk_number': chunk.get('chunk_number'),
                    'source': chunk.get('source'),
                    'content_text': chunk.get('content_text', '')
                }
                clean_chunks.append(clean_chunk)
            return clean_chunks
        except Exception as e:
            if attempt == retries - 1:
                print(f"[ERROR] Fallo final procesando {key}: {e}")
                return []
            time.sleep(1)

def main():
    print("=" * 60)
    print("      GENERADOR DE INDICE DE BUSQUEDA SERVERLESS (GZIP)      ")
    print("=" * 60)
    sys.stdout.flush()

    # 1. Conectar con Cloudflare R2
    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] No se pudieron cargar las credenciales de R2 en el archivo .env.")
        return

    print("[OK] Conexion con Cloudflare R2 establecida.")
    sys.stdout.flush()

    # 2. Listar archivos JSON en R2
    print("\nListando archivos JSON en el bucket de R2...")
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
        print(f"[ERROR] Fallo el listado de R2: {e}")
        return

    if not json_keys:
        print("No hay fragmentos JSON en R2. Por favor sube archivos primero.")
        return

    # 3. Descargar y consolidar en paralelo
    print(f"\nDescargando y consolidando fragmentos (usando 30 hilos en paralelo)...")
    sys.stdout.flush()
    
    consolidated_index = []
    download_args = [(s3_client, settings.bucket_name, key) for key in json_keys]
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(download_and_parse_json, arg): arg for arg in download_args}
        for idx, future in enumerate(as_completed(futures), 1):
            chunks = future.result()
            consolidated_index.extend(chunks)
            if idx % 500 == 0 or idx == len(json_keys):
                print(f"  --> Descargados y limpiados {idx}/{len(json_keys)} archivos JSON...")
                sys.stdout.flush()

    duration = time.time() - start_time
    print(f"[OK] Consolidacion de {len(consolidated_index)} fragmentos completada en {duration:.2f} segundos.")
    sys.stdout.flush()

    # 4. Guardar archivo local comprimido con GZIP
    local_index_path = ROOT_DIR / "search_index.json.gz"
    print(f"\nComprimiendo y guardando indice local en {local_index_path}...")
    sys.stdout.flush()
    try:
        with gzip.open(local_index_path, "wt", encoding="utf-8") as f:
            json.dump(consolidated_index, f, ensure_ascii=False)
        
        file_size_mb = os.path.getsize(local_index_path) / (1024 * 1024)
        print(f"[OK] Indice local guardado y comprimido. Tamano: {file_size_mb:.2f} MB.")
        sys.stdout.flush()
    except Exception as e:
        print(f"[ERROR] No se pudo guardar el archivo comprimido local: {e}")
        return

    # 5. Subir a R2
    r2_key = "search_index.json.gz"
    print(f"\nSubiendo '{r2_key}' a Cloudflare R2...")
    sys.stdout.flush()
    try:
        s3_client.upload_file(
            Filename=str(local_index_path),
            Bucket=settings.bucket_name,
            Key=r2_key,
            ExtraArgs={"ContentType": "application/gzip"}
        )
        print("[OK] Indice de busqueda (GZIP) subido a R2 con exito.")
        print("-" * 60)
        print("   SISTEMA LISTO: El buscador serverless ya tiene su indice comprimido en la nube.")
        print("=" * 60)
        sys.stdout.flush()
    except Exception as e:
        print(f"[ERROR] Fallo la subida a R2: {e}")

if __name__ == '__main__':
    main()
