import os
import re
import sys
import shutil
import unicodedata
import time
import multiprocessing
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DEST_DIR = ROOT_DIR / 'data' / 'uploads'

SOURCES = {
    'RES': r"C:\Users\User\Desktop\RESOLUCIONES",
    'ORD': r"C:\Users\User\Desktop\Ordenanzas"
}

def sanitize_filename(filename: str) -> str:
    normalized = unicodedata.normalize('NFKD', filename)
    ascii_str = normalized.encode('ascii', 'ignore').decode('utf-8')
    sanitized = re.sub(r'[^a-zA-Z0-9-._]', '_', ascii_str)
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    return sanitized

def compress_worker(src_file_str, dest_file_str, temp_dest_str, result_dict):
    import fitz
    src_file = Path(src_file_str)
    dest_file = Path(dest_file_str)
    temp_dest = Path(temp_dest_str)
    
    try:
        doc = fitz.open(str(src_file))
        doc.rewrite_images(
            dpi_threshold=150,
            dpi_target=100,
            quality=50,
            lossy=True,
            lossless=True
        )
        
        doc.save(
            str(temp_dest),
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()
        
        comp_size = temp_dest.stat().st_size
        orig_size = src_file.stat().st_size
        
        if comp_size >= orig_size:
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except:
                    pass
            result_dict['status'] = 'copied_no_savings'
        else:
            result_dict['status'] = 'compressed'
            result_dict['comp_size'] = comp_size
    except Exception as e:
        if temp_dest.exists():
            try:
                temp_dest.unlink()
            except:
                pass
        result_dict['status'] = 'error'
        result_dict['error'] = str(e)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("=" * 60)
    print(" COMPRESIÓN Y COPIA PARALELA RESILIENTE (MODO REANUDACIÓN) ")
    print("=" * 60)
    sys.stdout.flush()
    
    # Ensure destination folder exists
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Clean any temp files left by previous runs
    for f in DEST_DIR.iterdir():
        if f.is_file() and (f.name.startswith('temp_') or f.name.startswith('temp_worker_')):
            try:
                f.unlink()
            except:
                pass
        
    # 2. Scan source folders
    tasks = []
    for prefix, src_path in SOURCES.items():
        src_dir = Path(src_path)
        if not src_dir.exists():
            print(f"[WARN] La ruta no existe: {src_path}")
            sys.stdout.flush()
            continue
            
        for item in src_dir.iterdir():
            if not item.is_file():
                continue
            suffix = item.suffix.lower()
            if suffix not in {'.pdf', '.doc', '.docx'}:
                continue
            tasks.append((prefix, item))
            
    total_files = len(tasks)
    print(f"Total de archivos en origen: {total_files}")
    sys.stdout.flush()
    
    # Check what's already completed in data/uploads
    existing_dest_files = set(os.listdir(DEST_DIR))
    
    pending_tasks = []
    skipped_count = 0
    total_comp_size = 0
    
    for prefix, src_file in tasks:
        sanitized_name = f"{prefix}_{sanitize_filename(src_file.name)}"
        dest_file = DEST_DIR / sanitized_name
        
        if sanitized_name in existing_dest_files:
            skipped_count += 1
            total_comp_size += dest_file.stat().st_size
        else:
            pending_tasks.append((prefix, src_file))
            
    print(f"Archivos ya completados (omitidos): {skipped_count}")
    print(f"Archivos pendientes por procesar: {len(pending_tasks)}")
    sys.stdout.flush()
    
    if not pending_tasks:
        print("¡Todos los archivos ya están copiados y comprimidos en data/uploads/!")
        sys.stdout.flush()
        return
        
    print(f"Procesando {len(pending_tasks)} pendientes (4 trabajadores paralelos con timeout de 90s)...")
    sys.stdout.flush()
    
    compressed_count = 0
    copied_count = 0
    error_count = 0
    timeout_count = 0
    
    start_time = time.time()
    
    # Manager for sharing result dict with worker processes
    manager = multiprocessing.Manager()
    
    max_workers = 4
    active_processes = []  # list of (prefix, src_file, p, temp_dest, result_dict, t0, orig_size, dest_file, task_idx)
    
    task_idx = 0
    
    while task_idx < len(pending_tasks) or active_processes:
        # 1. Fill the worker pool up to max_workers
        while len(active_processes) < max_workers and task_idx < len(pending_tasks):
            prefix, src_file = pending_tasks[task_idx]
            task_idx += 1
            
            orig_size = src_file.stat().st_size
            orig_mb = orig_size / (1024 * 1024)
            sanitized_name = f"{prefix}_{sanitize_filename(src_file.name)}"
            dest_file = DEST_DIR / sanitized_name
            temp_dest = DEST_DIR / f"temp_worker_{sanitized_name}"
            
            is_pdf = src_file.suffix.lower() == '.pdf'
            should_compress = is_pdf and (orig_mb > 2.0)
            
            t0 = time.time()
            
            if should_compress:
                result_dict = manager.dict()
                result_dict['status'] = 'unknown'
                p = multiprocessing.Process(
                    target=compress_worker,
                    args=(str(src_file), str(dest_file), str(temp_dest), result_dict)
                )
                p.start()
                active_processes.append((prefix, src_file, p, temp_dest, result_dict, t0, orig_size, dest_file, task_idx))
            else:
                # Fast copy (process immediately in main thread)
                try:
                    shutil.copy2(src_file, dest_file)
                    total_comp_size += orig_size
                    copied_count += 1
                    if task_idx % 100 == 0 or task_idx == 1 or task_idx == len(pending_tasks):
                        print(f"[{task_idx}/{len(pending_tasks)}] Copiado rápido: {src_file.name} en {time.time()-t0:.2f}s")
                    sys.stdout.flush()
                except Exception as e:
                    error_count += 1
                    print(f"[{task_idx}/{len(pending_tasks)}] ERROR COPIA RÁPIDA: {e}")
                    sys.stdout.flush()
        
        # 2. Check on active background workers
        if active_processes:
            time.sleep(0.2)
            still_active = []
            for item in active_processes:
                prefix, src_file, p, temp_dest, result_dict, t0, orig_size, dest_file, t_idx = item
                elapsed = time.time() - t0
                
                if p.is_alive():
                    if elapsed > 90.0:
                        # Timeout! Terminate process
                        p.terminate()
                        p.join()
                        if temp_dest.exists():
                            try:
                                temp_dest.unlink()
                            except:
                                pass
                        # Fallback copy
                        try:
                            shutil.copy2(src_file, dest_file)
                            total_comp_size += orig_size
                            copied_count += 1
                            timeout_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] TIMEOUT (excedió 90s): {src_file.name} -> Copiado original en {elapsed:.1f}s")
                        except Exception as ex:
                            error_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] TIMEOUT + ERROR COPIA en {src_file.name}: {ex}")
                        sys.stdout.flush()
                    else:
                        still_active.append(item)
                else:
                    # Worker finished
                    p.join()
                    status = result_dict.get('status')
                    if status == 'compressed':
                        comp_size = result_dict.get('comp_size', 0)
                        if temp_dest.exists():
                            try:
                                if dest_file.exists():
                                    dest_file.unlink()
                                temp_dest.rename(dest_file)
                                total_comp_size += comp_size
                                compressed_count += 1
                                reduction = (orig_size - comp_size) / orig_size * 100
                                print(f"[{t_idx}/{len(pending_tasks)}] Comprimido: {src_file.name} ({comp_size/(1024**2):.2f} MB, -{reduction:.1f}%) en {time.time()-t0:.1f}s")
                            except Exception as e:
                                try:
                                    shutil.copy2(src_file, dest_file)
                                    total_comp_size += orig_size
                                    copied_count += 1
                                    print(f"[{t_idx}/{len(pending_tasks)}] Copiado original (fallback rename falló: {e}) en {time.time()-t0:.1f}s")
                                except Exception as ex:
                                    error_count += 1
                                    print(f"[{t_idx}/{len(pending_tasks)}] ERROR RENAME en {src_file.name}: {e}. Fallback falló: {ex}")
                        else:
                            try:
                                shutil.copy2(src_file, dest_file)
                                total_comp_size += orig_size
                                copied_count += 1
                                print(f"[{t_idx}/{len(pending_tasks)}] Copiado original (temp no encontrado) en {time.time()-t0:.1f}s")
                            except Exception as ex:
                                error_count += 1
                                print(f"[{t_idx}/{len(pending_tasks)}] ERROR: Temp no encontrado. Fallback falló: {ex}")
                    elif status == 'copied_no_savings':
                        try:
                            shutil.copy2(src_file, dest_file)
                            total_comp_size += orig_size
                            copied_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] Copiado original (sin ahorro): {src_file.name} en {time.time()-t0:.1f}s")
                        except Exception as ex:
                            error_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] ERROR COPIA (sin ahorro): {ex}")
                    elif status == 'error':
                        err = result_dict.get('error')
                        try:
                            shutil.copy2(src_file, dest_file)
                            total_comp_size += orig_size
                            copied_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] Copiado original (error compresión: {err}): {src_file.name} en {time.time()-t0:.1f}s")
                        except Exception as ex:
                            error_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] ERROR COMPRESION en {src_file.name}: {err}. Fallback falló: {ex}")
                    else:
                        try:
                            shutil.copy2(src_file, dest_file)
                            total_comp_size += orig_size
                            copied_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] Copiado original (estado desconocido): {src_file.name} en {time.time()-t0:.1f}s")
                        except Exception as ex:
                            error_count += 1
                            print(f"[{t_idx}/{len(pending_tasks)}] ERROR: Estado desconocido. Fallback falló: {ex}")
                    sys.stdout.flush()
            active_processes = still_active
                
    elapsed = time.time() - start_time
    print("=" * 60)
    print(" RESUMEN DEL PROCESO PARALELO CON TIMEOUT ")
    print("=" * 60)
    print(f"Tiempo total de esta tanda: {elapsed/60:.2f} minutos")
    print(f"  - Comprimidos exitosamente: {compressed_count}")
    print(f"  - Copiados (original o fallback): {copied_count}")
    print(f"  - Timeouts (excedieron 90s): {timeout_count}")
    print(f"  - Errores en esta tanda: {error_count}")
    print(f"Tamaño total acumulado en uploads: {total_comp_size/(1024**3):.2f} GB")
    print("=" * 60)
    sys.stdout.flush()

if __name__ == '__main__':
    main()
