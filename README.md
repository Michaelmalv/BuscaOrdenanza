# Busca Ordenanza

Repositorio base para una aplicacion tipo NotebookLM enfocada en PDFs convertidos a Markdown y buscados con Meilisearch.

## Objetivo

- Convertir PDFs, DOC y DOCX a Markdown.
- Partir Markdown en fragmentos indexables.
- Generar JSON listo para Meilisearch.
- Exponer una API para buscar y listar documentos.
- Dejar preparado un frontend para lectura y busqueda.

## Estructura

- `app/`: API principal.
- `ingestion/`: conversion, chunking e indexacion.
- `ui/`: interfaz web inicial.
- `scripts/`: utilidades de linea de comandos.
- `data/`: entrada, Markdown y JSON generados.

## Instalacion

1. Crear un entorno virtual.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Copiar `.env.example` a `.env` y ajustar credenciales.
4. Ejecutar la API con `uvicorn app.main:app --reload`.

## Flujo actual

1. Subes PDFs, DOC o DOCX desde `/` o llamando a `/api/subida-archivos`.
2. El backend guarda el archivo en `data/uploads`.
3. El pipeline convierte el archivo a Markdown.
4. El Markdown se fragmenta por encabezados.
5. Se genera JSON listo para Meilisearch.
6. Si hay credenciales, también se indexa en Meilisearch.

## Interfaz

- `/` y `/subida-archivos`: página de carga, búsqueda y visor de Markdown.
- La lista de documentos se obtiene desde `GET /api/documentos`.
- El Markdown de cada documento se obtiene con `GET /api/documentos/{document_id}/markdown`.
- Los fragmentos se consultan con `GET /api/documentos/{document_id}/fragmentos`, con filtro y paginación.
- La búsqueda real se realiza con `POST /api/buscar`.
- Al seleccionar un resultado de búsqueda, la interfaz salta al fragmento exacto.

## Rutas

- `GET /`: interfaz de subida.
- `POST /api/subida-archivos`: recibe archivos y ejecuta el pipeline.
- `GET /health`: verificación rápida.
- `POST /search`: consulta de búsqueda contra Meilisearch.
