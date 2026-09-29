import enum


class FileFormat(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    PPTX = "PPTX"