import os
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import sanitize_filename

UPLOAD_DIR = ROOT_DIR / 'data' / 'uploads'
MARKDOWN_DIR = ROOT_DIR / 'data' / 'markdown'
JSON_DIR = ROOT_DIR / 'data' / 'json'

def worker_process_file(args):
    path_str, markdown_dir_str, json_dir_str = args
    from ingestion.workflow import process_uploaded_file
    
    t0 = time.time()
    try:
        res = process_uploaded_file(
            input_path=path_str,
            markdown_dir=markdown_dir_str,
            json_dir=json_dir_str,
            index_to_meili=False
        )
        return {
            'status': 'success',
            'filename': Path(path_str).name,
            'time': time.time() - t0,
            'docs_created': res.get('documents_created', 0)
        }
    except Exception as e:
        return {
            'status': 'error',
            'filename': Path(path_str).name,
            'time': time.time() - t0,
            'error': str(e)
        }

def main():
    # Force UTF-8 encoding for stdout
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 60)
    print(" PIPELINE DE PROCESAMIENTO MASIVO PARALELO - BUSCA ORDENANZA ")
    print("=" * 60)
    sys.stdout.flush()
    
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    
    all_files = sorted(list(UPLOAD_DIR.iterdir()))
    pdf_files = []
    
    # 1. First sanitize filenames
    for item in all_files:
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        if suffix not in {'.pdf', '.doc', '.docx'}:
            continue
            
        original_name = item.name
        sanitized_name = sanitize_filename(original_name)
        
        target_path = item
        if original_name != sanitized_name:
            target_path = UPLOAD_DIR / sanitized_name
            try:
                item.rename(target_path)
                print(f"Renombrado para sanitizar: {original_name} -> {sanitized_name}")
            except Exception as e:
                print(f"Error renombrando {original_name}: {e}")
                target_path = item
        
        pdf_files.append(target_path)
    
    total = len(pdf_files)
    print(f"\nSe encontraron {total} archivos de documentos en 'data/uploads/'.")
    sys.stdout.flush()
    
    # 2. Verificar cuáles archivos ya están en R2 para evitar doble trabajo y limpiar disco local
    already_uploaded = set()
    from ingestion.workflow import get_s3_client
    from app.config import settings
    s3_client = get_s3_client()
    if s3_client:
        try:
            print("\nConsultando Cloudflare R2 para identificar documentos ya subidos...")
            sys.stdout.flush()
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.bucket_name, Prefix="uploads/")
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        filename = key.split('/')[-1]
                        if filename:
                            already_uploaded.add(filename)
            print(f"Se encontraron {len(already_uploaded)} documentos ya subidos con éxito en Cloudflare R2.")
            sys.stdout.flush()
        except Exception as e:
            print(f"Advertencia al consultar R2: {e}. Se procesarán todos los archivos locales.")
            sys.stdout.flush()

    pending_files = []
    skipped_count = 0
    for path in pdf_files:
        if path.name in already_uploaded:
            try:
                path.unlink()
            except Exception:
                pass
            skipped_count += 1
        else:
            pending_files.append(path)

    if skipped_count > 0:
        print(f"Omitidos (ya están en Cloudflare R2 y se limpiaron localmente): {skipped_count} documentos.")
        sys.stdout.flush()

    total_pending = len(pending_files)
    print(f"Pendientes de procesamiento real: {total_pending} documentos.")
    sys.stdout.flush()
    
    if total_pending == 0:
        print("\n¡Todos los documentos ya han sido procesados y subidos con éxito!")
        sys.stdout.flush()
        return
        
    max_workers = 4
    print(f"\nIniciando conversión y subida a R2 con {max_workers} procesos en paralelo...")
    print("Presiona Ctrl + C en cualquier momento para pausar de forma segura.")
    print("-" * 60)
    sys.stdout.flush()
    
    processed_count = 0
    error_count = 0
    total_docs_created = 0
    
    start_time = time.time()
    
    # Prepare arguments for workers
    worker_args = [(str(path), str(MARKDOWN_DIR), str(JSON_DIR)) for path in pending_files]
    
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker_process_file, arg): arg for arg in worker_args}
            
            for idx, future in enumerate(as_completed(futures), 1):
                res = future.result()
                filename = res['filename']
                dur = res['time']
                percent = (idx / total_pending) * 100
                
                if res['status'] == 'success':
                    processed_count += 1
                    total_docs_created += res['docs_created']
                    print(f"[{idx}/{total_pending}] ({percent:.1f}%) Éxito: {filename} ({res['docs_created']} fragmentos) en {dur:.1f}s")
                else:
                    error_count += 1
                    print(f"[{idx}/{total_pending}] ({percent:.1f}%) [ERROR] {filename}: {res.get('error')}")
                
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\nProcesamiento pausado por el usuario de forma segura.")
        sys.stdout.flush()
        
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(" PROCESAMIENTO COMPLETADO ")
    print("=" * 60)
    print(f"Tiempo total: {elapsed/60:.2f} minutos")
    print(f"Procesados exitosamente: {processed_count}")
    print(f"Errores en conversión: {error_count}")
    print(f"Total fragmentos indexables creados: {total_docs_created}")
    print("\n¡Ya puedes recargar la aplicación web en tu navegador!")
    print("=" * 60)
    sys.stdout.flush()

if __name__ == '__main__':
    main()
