from pathlib import Path
import sys
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.workflow import process_uploaded_file
from app.main import sanitize_filename

UPLOAD_DIR = ROOT_DIR / 'data' / 'uploads'
MARKDOWN_DIR = ROOT_DIR / 'data' / 'markdown'
JSON_DIR = ROOT_DIR / 'data' / 'json'

def main():
    print("=" * 60)
    print(" PIPELINE DE PROCESAMIENTO MASIVO OFFLINE - BUSCA ORDENANZA ")
    print("=" * 60)
    
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
    
    # 2. Process missing ones
    pending_files = []
    for path in pdf_files:
        markdown_file = MARKDOWN_DIR / f'{path.stem}.md'
        json_file = JSON_DIR / f'{path.stem}.json'
        if not markdown_file.exists() or not json_file.exists():
            pending_files.append(path)
            
    total_pending = len(pending_files)
    print(f"Pendientes de procesamiento: {total_pending} / {total} documentos.")
    
    if total_pending == 0:
        print("\n¡Todos los documentos ya han sido procesados y convertidos con éxito!")
        print("Puedes iniciar el servidor web y verlos inmediatamente.")
        return
        
    print("\nIniciando conversión masiva en segundo plano...")
    print("Presiona Ctrl + C en cualquier momento para pausar de forma segura.")
    print("-" * 60)
    
    processed_count = 0
    error_count = 0
    
    for idx, path in enumerate(pending_files, 1):
        percent = (idx / total_pending) * 100
        print(f"\n[{idx}/{total_pending}] ({percent:.1f}%) Procesando: {path.name}")
        try:
            process_uploaded_file(
                input_path=str(path),
                markdown_dir=str(MARKDOWN_DIR),
                json_dir=str(JSON_DIR),
                index_to_meili=False # Do not index to Meili directly, local fallback is fast
            )
            processed_count += 1
            print(f"  --> Éxito: Markdown y JSON generados.")
        except KeyboardInterrupt:
            print("\nProcesamiento pausado por el usuario de forma segura.")
            break
        except Exception as e:
            error_count += 1
            print(f"  --> ERROR procesando {path.name}: {e}")
            
    print("\n" + "=" * 60)
    print(" PROCESAMIENTO COMPLETADO ")
    print("=" * 60)
    print(f"Procesados exitosamente: {processed_count}")
    print(f"Errores en conversión: {error_count}")
    print(f"Total en biblioteca actual: {total - total_pending + processed_count} / {total}")
    print("\n¡Ya puedes recargar la aplicación web en tu navegador!")
    print("=" * 60)

if __name__ == '__main__':
    main()
