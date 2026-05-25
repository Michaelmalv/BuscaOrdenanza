import os
import re
from pathlib import Path

import aspose.words as aw


EVALUATION_PATTERNS = [
    r'^\*\*  \(\)\*\*',
    r'^\s*\*\*  \(\)\*\*\s*',
    r'\*\*Evaluation Only\. Created with Aspose\.Words\. Copyright 2003-2025 Aspose Pty Ltd\.\*\*$',
    r'\*\*Evaluation Only\. Created with Aspose\.Words\. Copyright 2003-2025 Aspose Pty Ltd\.\*\*\s*$',
    r'\*\*Created with an evaluation copy of Aspose\.Words\. To remove all limitations, you can use Free Temporary License \[\*\*https://products\.aspose\.com/words/temporary-license/\*\*\]\(https://products\.aspose\.com/words/temporary-license/\)\*\*',
    r'Evaluation Only\. Created with Aspose\.Words\. Copyright 2003-2025 Aspose Pty Ltd\.$',
    r'Evaluation Only\. Created with Aspose\.Words\. Copyright 2003-2025 Aspose Pty Ltd\.\s*$',
    r'Created with an evaluation copy of Aspose\.Words\. To remove all limitations, you can use Free Temporary License',
    r'https?://products\.aspose\.com/words/temporary-license/',
]


def remove_specific_evaluation_text(md_file_path: str) -> None:
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        for pattern in EVALUATION_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)

        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()

        with open(md_file_path, 'w', encoding='utf-8') as file:
            file.write(content)
    except Exception as exc:
        raise RuntimeError(f'Error limpiando el Markdown: {exc}') from exc


def convert_to_md(input_path: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)

    file_name = Path(input_path).stem
    output_path = os.path.join(output_dir, f'{file_name}.md')

    document = aw.Document(input_path)
    document.save(output_path, aw.SaveFormat.MARKDOWN)
    remove_specific_evaluation_text(output_path)

    return output_path


def batch_convert_to_md(input_directory: str, output_dir: str) -> list[str]:
    if not os.path.exists(input_directory):
        raise FileNotFoundError(f"La carpeta '{input_directory}' no existe.")

    supported_extensions = ['.pdf', '.doc', '.docx']
    input_files = [
        f for f in os.listdir(input_directory)
        if any(f.lower().endswith(ext) for ext in supported_extensions)
    ]

    output_paths: list[str] = []
    for input_file in input_files:
        input_path = os.path.join(input_directory, input_file)
        output_paths.append(convert_to_md(input_path, output_dir))

    return output_paths
