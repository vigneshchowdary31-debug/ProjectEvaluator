import pytest
from unittest.mock import MagicMock, patch
from app.services.gemini import GeminiService, GeminiError
from app.schemas.prd import PRDAnalysisResult, Page, Feature, Form, UserFlow

# A sample valid PRDAnalysisResult dictionary
SAMPLE_RESULT_DICT = {
    "pages": [
        {
            "name": "Dashboard",
            "route": "/dashboard",
            "description": "User dashboard page",
            "components": [
                {"name": "Header", "type": "navigation", "description": "Global navigation header"}
            ],
            "connected_pages": ["Settings"]
        }
    ],
    "features": [
        {
            "name": "User Registration",
            "description": "Allow new users to sign up",
            "priority": "must_have",
            "acceptance_criteria": ["Must validate email"],
            "related_pages": ["Register"]
        }
    ],
    "forms": [
        {
            "name": "Register Form",
            "description": "User registration fields",
            "page": "Register",
            "fields": [
                {"name": "Email", "field_type": "email", "required": True, "validation_rules": [], "options": []}
            ],
            "submit_action": "Submits user details"
        }
    ],
    "user_flows": [
        {
            "name": "Registration flow",
            "description": "Full sign up flow",
            "actor": "User",
            "preconditions": ["Not logged in"],
            "steps": [
                {"step_number": 1, "action": "Submit registration form", "page": "Register", "expected_result": "Redirect to login"}
            ],
            "postconditions": ["User account created"]
        }
    ]
}

@pytest.fixture
def mock_settings():
    with patch("app.services.gemini.get_settings") as mock:
        mock_settings_inst = MagicMock()
        mock_settings_inst.GEMINI_API_KEY = "test_api_key_123"
        mock_settings_inst.GEMINI_MODEL = "gemini-2.5-flash"
        mock.return_value = mock_settings_inst
        yield mock_settings_inst

@patch("google.genai.Client")
def test_gemini_init(mock_client_class, mock_settings):
    service = GeminiService()
    assert service.api_key == "test_api_key_123"
    assert service.model_name == "gemini-2.5-flash"
    mock_client_class.assert_called_once_with(api_key="test_api_key_123")

@patch("google.genai.Client")
def test_gemini_init_missing_key(mock_client_class, mock_settings):
    mock_settings.GEMINI_API_KEY = ""
    with pytest.raises(GeminiError) as exc_info:
        GeminiService()
    assert "GEMINI_API_KEY is not configured" in str(exc_info.value)

@patch("google.genai.Client")
def test_analyze_prd_via_parsed_attribute(mock_client_class, mock_settings):
    # Setup mock response with 'parsed' attribute
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    # Instantiate Pydantic model
    expected_result = PRDAnalysisResult.model_validate(SAMPLE_RESULT_DICT)
    mock_response.parsed = expected_result
    mock_response.text = '{"pages":[],"features":[],"forms":[],"user_flows":[]}'
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiService()
    result = service.analyze_prd("Document text example")

    assert result == expected_result
    mock_client.models.generate_content.assert_called_once()

@patch("google.genai.Client")
def test_analyze_prd_fallback_to_text(mock_client_class, mock_settings):
    # Setup mock response without 'parsed' (or parsed is None), only 'text'
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    import json
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = json.dumps(SAMPLE_RESULT_DICT)
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiService()
    result = service.analyze_prd("Document text example")

    assert len(result.pages) == 1
    assert result.pages[0].name == "Dashboard"
    assert result.features[0].priority == "must_have"
    mock_client.models.generate_content.assert_called_once()

@patch("google.genai.Client")
def test_analyze_prd_empty_document(mock_client_class, mock_settings):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    service = GeminiService()
    with pytest.raises(GeminiError) as exc_info:
        service.analyze_prd("   ")
    assert "Document text is empty" in str(exc_info.value)

def test_clean_json_response():
    # Test stripping markdown fences
    raw_json = '```json\n{"key": "value"}\n```'
    cleaned = GeminiService._clean_json_response(raw_json)
    assert cleaned == '{"key": "value"}'
    
    raw_json2 = '```\n{"key": "value"}\n```'
    cleaned2 = GeminiService._clean_json_response(raw_json2)
    assert cleaned2 == '{"key": "value"}'
    
    raw_json3 = '{"key": "value"}'
    cleaned3 = GeminiService._clean_json_response(raw_json3)
    assert cleaned3 == '{"key": "value"}'
