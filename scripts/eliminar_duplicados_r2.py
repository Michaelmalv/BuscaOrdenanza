import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from ingestion.workflow import get_s3_client
from ingestion.meilisearch_client import MeiliService

def normalize_name(name: str) -> str:
    # Convertir a minúsculas
    stem = name.lower()
    # Eliminar extensiones repetidas
    while any(stem.endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.md', '.json']):
        stem = stem.rsplit('.', 1)[0]
    # Reemplazar guiones y espacios por guiones bajos
    stem = stem.replace('-', '_').replace(' ', '_').replace('__', '_').strip('_')
    return stem

def get_penalty(name: str) -> int:
    penalty = 0
    lower_name = name.lower()
    if '.pdf.pdf' in lower_name:
        penalty += 20
    if '.pdf' in lower_name[:-4]: # doble extensión interna
        penalty += 10
    if name.endswith('.PDF'): # extensión en mayúsculas
        penalty += 2
    return penalty

def main():
    print("=" * 60)
    print(" SCRIPT DE DEPURACIÓN DE DUPLICADOS EN R2 Y MEILISEARCH ")
    print("=" * 60)

    s3_client = get_s3_client()
    if not s3_client:
        print("[ERROR] R2 no está configurado en el archivo .env.")
        return

    bucket = settings.bucket_name
    print(f"Conectando al bucket: {bucket}...")
    
    # 1. Listar todos los archivos en uploads/
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="uploads/")
    except Exception as e:
        print(f"[ERROR] No se pudo listar el bucket: {e}")
        return

    contents = response.get('Contents', [])
    if not contents:
        print("El bucket está vacío. No hay nada que depurar.")
        return

    print(f"Se encontraron {len(contents)} archivos en la carpeta uploads/ de R2.")

    # 2. Agrupar por nombre normalizado
    groups = {}
    for obj in contents:
        key = obj['Key']
        filename = Path(key).name
        normalized = normalize_name(filename)
        if normalized not in groups:
            groups[normalized] = []
        groups[normalized].append(key)

    # 3. Identificar duplicados
    to_delete_keys = []
    meili_docs_to_delete = []
    
    print("\nAnalizando duplicados...")
    duplicate_groups_count = 0
    
    for norm_name, keys in groups.items():
        if len(keys) > 1:
            duplicate_groups_count += 1
            # Ordenar por penalización (menor a mayor) y luego por longitud de nombre (menor a mayor)
            # El primero de la lista será el que CONSERVAMOS.
            sorted_keys = sorted(keys, key=lambda k: (get_penalty(Path(k).name), len(Path(k).name)))
            keep_key = sorted_keys[0]
            delete_keys = sorted_keys[1:]
            
            print(f"\nGrupo Duplicado #{duplicate_groups_count} ({norm_name}):")
            print(f"  [CONSERVAR] -> {keep_key}")
            for dk in delete_keys:
                print(f"  [ELIMINAR ] -> {dk}")
                to_delete_keys.append(dk)
                meili_docs_to_delete.append(Path(dk).stem)

    if not to_delete_keys:
        print("\n¡Excelente! No se encontraron archivos duplicados en el bucket.")
        print("=" * 60)
        return

    print(f"\nTotal de archivos duplicados a eliminar en R2: {len(to_delete_keys)}")
    
    # Confirmar y proceder a borrar de R2
    print("\nIniciando eliminación en Cloudflare R2...")
    deleted_count = 0
    for key in to_delete_keys:
        stem = Path(key).stem
        # Definir las llaves asociadas a eliminar
        keys_to_remove = [
            key,                              # PDF original (uploads/...)
            f"markdown/{stem}.md",            # Markdown (markdown/...)
            f"json/{stem}.json"               # JSON (json/...)
        ]
        
        for k in keys_to_remove:
            try:
                # Comprobar si existe antes de borrar
                s3_client.delete_object(Bucket=bucket, Key=k)
                deleted_count += 1
            except Exception as e:
                # Silencioso si no existe (por si no se había procesado su md/json)
                pass

    print(f"  --> Se eliminaron {deleted_count} objetos asociados en R2.")

    # 4. Eliminar de Meilisearch
    if settings.meili_url and meili_docs_to_delete:
        print("\nConectando a Meilisearch para limpiar índices...")
        try:
            service = MeiliService.from_settings()
            index = service.client.index(service.index_name)
            
            print(f"Eliminando {len(meili_docs_to_delete)} documentos duplicados...")
            for doc_id in meili_docs_to_delete:
                try:
                    # En Meilisearch eliminamos por filtro document_id
                    task = index.delete_documents(filter=f"document_id = '{doc_id}'")
                    print(f"  --> Solicitud enviada para eliminar doc_id: {doc_id}")
                except Exception as ex:
                    print(f"  --> Error eliminando {doc_id} de Meili: {ex}")
        except Exception as e:
            print(f"[ERROR] No se pudo conectar a Meilisearch: {e}")

    print("\n" + "=" * 60)
    print(" ¡PROCESO DE DEPURACIÓN COMPLETADO! ")
    print("=" * 60)

if __name__ == "__main__":
    main()
