"""
Парсинг загруженных файлов: txt, pdf, docx, csv.
"""
import io
import base64


def parse_file(filename: str, content: bytes) -> str:
    """Извлекает текст из файла по его расширению."""
    ext = filename.lower().split(".")[-1]
    
    try:
        if ext == "txt":
            return content.decode("utf-8", errors="ignore")
        
        elif ext == "pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text[:5000] if text else "PDF не содержит извлекаемого текста."
            except ImportError:
                return "PDF поддержка недоступна (установите pypdf)."
        
        elif ext == "docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(content))
                return "\n".join(p.text for p in doc.paragraphs)[:5000]
            except ImportError:
                return "DOCX поддержка недоступна (установите python-docx)."
        
        elif ext == "csv":
            text = content.decode("utf-8", errors="ignore")
            lines = text.split("\n")[:50]  # первые 50 строк
            return "\n".join(lines)
        
        elif ext in ("json",):
            return content.decode("utf-8", errors="ignore")[:3000]
        
        else:
            return f"Файл '{filename}' загружен, но формат '{ext}' не поддерживается для извлечения текста."
    
    except Exception as e:
        return f"Ошибка при обработке файла '{filename}': {str(e)}"
