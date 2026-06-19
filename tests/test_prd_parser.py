import pytest
from unittest.mock import MagicMock, patch
import httpx
from app.services.prd_parser import PRDParserService, ParserError

def test_extract_doc_id_valid():
    parser = PRDParserService()
    
    # Test standard edit URL
    url1 = "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
    assert parser.extract_doc_id(url1) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
    
    # Test preview URL
    url2 = "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/preview"
    assert parser.extract_doc_id(url2) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
    
    # Test URL with user index
    url3 = "https://docs.google.com/document/u/0/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
    assert parser.extract_doc_id(url3) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"

def test_extract_doc_id_invalid():
    parser = PRDParserService()
    url = "https://google.com/some/other/link"
    with pytest.raises(ParserError) as exc_info:
        parser.extract_doc_id(url)
    assert "Could not extract Google Document ID" in str(exc_info.value)

def test_clean_text():
    parser = PRDParserService()
    dirty_text = "\ufeffTitle\n\n\n\nSection 1\n\n\u200bSubsection  \n\n\n"
    cleaned = parser._clean_text(dirty_text)
    # BOM and zero-width spaces removed
    # Consecutive newlines collapsed to max 2
    # Trailing line whitespaces stripped
    assert cleaned == "Title\n\nSection 1\n\nSubsection"

@patch("httpx.Client.get")
def test_download_document_success(mock_get):
    # Set up mock response
    mock_response = MagicMock()
    mock_response.content = b"My PRD Title\n\nThis is the content of the PRD."
    mock_response.text = "My PRD Title\n\nThis is the content of the PRD."
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    parser = PRDParserService()
    url = "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
    
    text, title = parser.download_document(url)
    
    assert title == "My PRD Title"
    assert "This is the content of the PRD." in text
    mock_get.assert_called_once()

@patch("httpx.Client.get")
def test_download_document_not_found(mock_get):
    # Set up mock HTTP 404 error
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.side_effect = httpx.HTTPStatusError(
        message="Not Found",
        request=MagicMock(),
        response=mock_response
    )

    parser = PRDParserService()
    url = "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"
    
    with pytest.raises(ParserError) as exc_info:
        parser.download_document(url)
    
    assert "Document not found" in str(exc_info.value)
