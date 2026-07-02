import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from ingestion.workflow import get_s3_client

def main():
    print("=" * 60)
    print(" SUBIDA DE ARCHIVOS LOCALES EXISTENTES A CLOUDFLARE R2 ")
    print("=" * 60)

    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] R2 no está configurado en el archivo .env.")
        return

    bucket = settings.bucket_name
    
    # 1. Subir PDFs originales
    upload_dir = ROOT_DIR / 'data' / 'uploads'
    if upload_dir.exists():
        files = [f for f in upload_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.pdf', '.doc', '.docx']]
        print(f"\nSubiendo PDFs originales ({len(files)} archivos)...")
        for idx, f in enumerate(files, start=1):
            key = f"uploads/{f.name}"
            print(f"[{idx}/{len(files)}] Subiendo: {f.name} -> R2")
            try:
                s3_client.upload_file(str(f), bucket, key)
            except Exception as e:
                print(f"  --> Error subiendo {f.name}: {e}")
                
    # 2. Subir Markdowns (.md)
    markdown_dir = ROOT_DIR / 'data' / 'markdown'
    if markdown_dir.exists():
        files = [f for f in markdown_dir.iterdir() if f.is_file() and f.suffix.lower() == '.md']
        print(f"\nSubiendo archivos Markdown ({len(files)} archivos)...")
        for idx, f in enumerate(files, start=1):
            key = f"markdown/{f.name}"
            print(f"[{idx}/{len(files)}] Subiendo: {f.name} -> R2")
            try:
                s3_client.upload_file(str(f), bucket, key)
            except Exception as e:
                print(f"  --> Error subiendo {f.name}: {e}")
                
    # 3. Subir JSONs (.json)
    json_dir = ROOT_DIR / 'data' / 'json'
    if json_dir.exists():
        files = [f for f in json_dir.iterdir() if f.is_file() and f.suffix.lower() == '.json']
        print(f"\nSubiendo archivos JSON de fragmentos ({len(files)} archivos)...")
        for idx, f in enumerate(files, start=1):
            key = f"json/{f.name}"
            print(f"[{idx}/{len(files)}] Subiendo: {f.name} -> R2")
            try:
                s3_client.upload_file(str(f), bucket, key)
            except Exception as e:
                print(f"  --> Error subiendo {f.name}: {e}")
                
    print("\n" + "=" * 60)
    print(" ¡PROCESO DE SUBIDA COMPLETADO! ")
    print("=" * 60)

if __name__ == "__main__":
    main()
