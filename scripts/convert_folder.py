from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.pdf_to_markdown import batch_convert_to_md


if __name__ == '__main__':
    input_folder = ROOT_DIR / 'data' / 'input'
    output_folder = ROOT_DIR / 'data' / 'markdown'

    converted = batch_convert_to_md(str(input_folder), str(output_folder))
    print(f'Convertidos {len(converted)} archivos')
