import pytest
from unittest.mock import MagicMock, patch
import httpx
from app.services.github_parser import GithubParserService, ParserError

def test_parse_repo_url_valid():
    parser = GithubParserService()
    
    # Test standard HTTPS URL
    owner, repo = parser.parse_repo_url("https://github.com/owner/repo-name")
    assert owner == "owner"
    assert repo == "repo-name"

    # Test URL with .git extension
    owner, repo = parser.parse_repo_url("https://github.com/owner/repo-name.git")
    assert owner == "owner"
    assert repo == "repo-name"

    # Test SSH URL
    owner, repo = parser.parse_repo_url("git@github.com:owner/repo-name.git")
    assert owner == "owner"
    assert repo == "repo-name"

def test_parse_repo_url_invalid():
    parser = GithubParserService()
    with pytest.raises(ParserError) as exc_info:
        parser.parse_repo_url("https://gitlab.com/owner/repo")
    assert "Invalid GitHub URL" in str(exc_info.value)

def test_build_folder_tree():
    parser = GithubParserService()
    paths = [
        "app/main.py",
        "app/models/user.py",
        "app/models/project.py",
        "tests/test_parser.py",
        "requirements.txt"
    ]
    
    # Test nesting behavior
    tree = parser.build_folder_tree(paths, max_depth=4, max_files=200)
    assert tree["requirements.txt"] is None
    assert tree["app"]["main.py"] is None
    assert tree["app"]["models"]["user.py"] is None
    assert tree["app"]["models"]["project.py"] is None
    assert tree["tests"]["test_parser.py"] is None

    # Test depth cap
    shallow_tree = parser.build_folder_tree(paths, max_depth=1, max_files=200)
    assert "requirements.txt" in shallow_tree
    assert "app" not in shallow_tree  # app/main.py is at depth 2 (length 2 parts)

@patch("httpx.Client.get")
def test_fetch_repo_metadata_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"default_branch": "main", "description": "Project"}
    mock_get.return_value = mock_response

    parser = GithubParserService()
    metadata = parser.fetch_repo_metadata("owner", "repo")
    assert metadata["default_branch"] == "main"
    mock_get.assert_called_once()

@patch("httpx.Client.get")
def test_fetch_repo_metadata_404(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response

    parser = GithubParserService()
    with pytest.raises(ParserError) as exc_info:
        parser.fetch_repo_metadata("owner", "repo")
    assert "not found" in str(exc_info.value)

