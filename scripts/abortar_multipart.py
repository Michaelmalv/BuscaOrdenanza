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
    print(" ABORTAR CARGAS MULTIPARTES INCOMPLETAS EN R2 ")
    print("=" * 60)

    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] R2 no está configurado en el archivo .env.")
        return

    bucket = settings.bucket_name
    print(f"Buscando cargas incompletas en el bucket: {bucket}...")

    try:
        # Listar cargas multipartes activas
        response = s3_client.list_multipart_uploads(Bucket=bucket)
        uploads = response.get('Uploads', [])
        
        if not uploads:
            print("  --> No se encontraron cargas multipartes incompletas.")
            print("=" * 60)
            return

        print(f"Se encontraron {len(uploads)} cargas incompletas. Abortando...")
        
        aborted_count = 0
        for upload in uploads:
            key = upload['Key']
            upload_id = upload['UploadId']
            print(f"  Abortando: {key} (ID: {upload_id[:8]}...)")
            try:
                s3_client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
                aborted_count += 1
            except Exception as e:
                print(f"    [Error] No se pudo abortar: {e}")

        print(f"\n  --> Se abortaron con éxito {aborted_count} cargas incompletas.")
    except Exception as e:
        print(f"[ERROR] Ocurrió un fallo al comunicarse con R2: {e}")
    print("=" * 60)

if __name__ == "__main__":
    main()
