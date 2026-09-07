import pytest
from pathlib import Path
from src.document_loader import load_document, load_text_file, DocumentIngestionError

@pytest.fixture
def temp_sample_txt(tmp_path):
    file = tmp_path / "sample.txt"
    file.write_text("Customer: John Doe\nIssue: Billing failure.", encoding="utf-8")
    return file

def test_load_text_file(temp_sample_txt):
    content = load_text_file(temp_sample_txt)
    assert "John Doe" in content
    assert "Billing failure" in content

def test_load_document_unsupported_format(tmp_path):
    bad_file = tmp_path / "document.xyz"
    bad_file.write_text("Random binary content")
    
    with pytest.raises(DocumentIngestionError):
        load_document(bad_file)

def test_load_document_missing_file():
    with pytest.raises(FileNotFoundError):
        load_document(Path("non_existent_folder/missing.pdf"))