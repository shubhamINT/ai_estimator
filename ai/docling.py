from docling.document_converter import DocumentConverter

async def exract_markdown(file_path: str) -> str:
    converter = DocumentConverter()
    doc = converter.convert(file_path).document
    return doc.export_to_markdown()