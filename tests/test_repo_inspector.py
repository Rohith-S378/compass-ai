from unittest.mock import MagicMock
from compass.tools.repo_inspector import inspect_repository

def test_inspect_repository_success():
    client = MagicMock()
    client.get_repository.return_value = {
        "description": "test repo",
        "language": "Python",
        "stargazers_count": 42
    }
    # Mock get_file_text to return content for README only
    def mock_get_file_text(owner, repo, path):
        if path == "README.md":
            return "this is the readme"
        return None
    client.get_file_text.side_effect = mock_get_file_text

    result = inspect_repository(client, "owner", "repo")
    
    assert result["metadata"]["stargazers_count"] == 42
    assert "README.md" in result["files_found"]
    assert "CONTRIBUTING.md" not in result["files_found"]
    assert "Repository: owner/repo" in result["context_str"]
    assert "this is the readme" in result["context_str"]

def test_inspect_repository_no_files():
    client = MagicMock()
    client.get_repository.return_value = {}
    client.get_file_text.return_value = None

    result = inspect_repository(client, "owner", "repo")
    assert result["files_found"] == []
    assert "Primary Language: Unknown" in result["context_str"]
