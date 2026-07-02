import os
import sys
from pathlib import Path
import shutil

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from ingestion.workflow import get_s3_client
from ingestion.meilisearch_client import MeiliService

def main():
    print("=" * 60)
    print(" REINICIAR ALMACENAMIENTO Y BASE DE DATOS DESDE CERO ")
    print("=" * 60)
    
    # 1. Vaciar R2 Bucket
    s3_client = get_s3_client()
    if s3_client:
        bucket = settings.bucket_name
        print(f"\n1. Vaciando bucket de Cloudflare R2: {bucket}...")
        try:
            # Listar y eliminar todos los objetos
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket)
            
            delete_us = []
            for page in pages:
                for obj in page.get('Contents', []):
                    delete_us.append({'Key': obj['Key']})
            
            if delete_us:
                for i in range(0, len(delete_us), 1000):
                    chunk = delete_us[i:i+1000]
                    s3_client.delete_objects(Bucket=bucket, Delete={'Objects': chunk})
                print(f"  --> Se eliminaron {len(delete_us)} objetos de R2.")
            else:
                print("  --> El bucket R2 ya estaba vacío.")
        except Exception as e:
            print(f"  --> Error vaciando R2: {e}")
    else:
        print("\n1. R2 no configurado, saltando limpieza de R2.")

    # 2. Vaciar Meilisearch
    if settings.meili_url:
        print(f"\n2. Eliminando índice de Meilisearch: {settings.meili_index_name}...")
        try:
            service = MeiliService.from_settings()
            try:
                task = service.client.delete_index(settings.meili_index_name)
                print(f"  --> Solicitud de eliminación enviada a Meilisearch.")
            except Exception as e:
                print(f"  --> El índice ya no existía o error al borrar: {e}")
        except Exception as e:
            print(f"  --> Error conectando a Meilisearch: {e}")
            
    # 3. Vaciar directorios locales
    print("\n3. Vaciando directorios locales en data/...")
    data_dir = ROOT_DIR / 'data'
    for folder in ['markdown', 'json']:
        target_dir = data_dir / folder
        if target_dir.exists():
            print(f"  --> Vaciando {folder}...")
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        
    print("\n" + "=" * 60)
    print(" ¡LIMPIEZA COMPLETADA CON ÉXITO! ")
    print(" Ya puedes copiar las ordenanzas limpias a data/uploads/ y procesar.")
    print("=" * 60)

if __name__ == "__main__":
    main()
