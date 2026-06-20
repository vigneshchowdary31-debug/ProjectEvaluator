"""
GitHub Parser Service — validates URLs, fetches repo metadata,
recursive file trees, and package manifest files using the GitHub API.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Regex pattern to extract owner and repo name from GitHub URLs
GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://github\.com/|git@github\.com:)([^/]+)/([^/.]+)(?:\.git)?",
    re.IGNORECASE
)

# Manifest files we want to download to inspect dependencies
MANIFEST_FILENAMES = {
    "package.json",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "README.md",
    "setup.py",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile"
}

HTTP_TIMEOUT = 15.0


class ParserError(Exception):
    """Raised when GitHub API operations fail."""
    pass


class GithubParserService:
    """Service to interact with the public GitHub API and extract repository metadata."""

    MANIFEST_FILENAMES = MANIFEST_FILENAMES

    def __init__(self):
        settings = get_settings()
        self.github_token = settings.GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"

    @staticmethod
    def parse_repo_url(url: str) -> Tuple[str, str]:
        """
        Parse a GitHub repository URL to extract owner and repo name.

        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git

        Returns:
            Tuple of (owner, repo_name)

        Raises:
            ParserError: If the URL is not a valid GitHub repository URL.
        """
        url = url.strip()
        match = GITHUB_URL_PATTERN.search(url)
        if not match:
            raise ParserError(
                f"Invalid GitHub URL: {url}. "
                "Ensure it follows the format https://github.com/owner/repo"
            )
        owner, repo = match.group(1), match.group(2)
        logger.debug("Parsed owner: %s, repo: %s from URL: %s", owner, repo, url)
        return owner, repo

    def fetch_repo_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch general repository metadata from GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        logger.info("Fetching repository metadata: %s/%s", owner, repo)

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT, headers=self.headers) as client:
                response = client.get(url)
                if response.status_code == 404:
                    raise ParserError(f"Repository '{owner}/{repo}' not found. Ensure it is public.")
                elif response.status_code == 403:
                    # Check for rate limit
                    rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                    if rate_limit_remaining == "0":
                        raise ParserError("GitHub API rate limit exceeded. Provide a GITHUB_TOKEN in your env to bypass.")
                    raise ParserError("Access forbidden to GitHub repository.")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise ParserError(f"GitHub API error ({e.response.status_code}): {e.response.text}")
        except httpx.RequestError as e:
            raise ParserError(f"Network error while reaching GitHub: {str(e)}")

    def fetch_latest_commit(self, owner: str, repo: str, branch: str) -> str:
        """Fetch the latest commit SHA for a specific branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
        logger.info("Fetching latest commit SHA for %s/%s branch %s", owner, repo, branch)

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT, headers=self.headers) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("sha", "")
        except Exception as e:
            logger.warning("Failed to fetch latest commit SHA: %s. Proceeding with empty SHA.", str(e))
            return ""

    def fetch_git_tree(self, owner: str, repo: str, commit_sha: str) -> List[Dict[str, Any]]:
        """Fetch recursive file tree listing of the repository."""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1"
        logger.info("Fetching recursive file tree for %s/%s commit %s", owner, repo, commit_sha)

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT, headers=self.headers) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("tree", [])
        except Exception as e:
            logger.error("Failed to fetch repository tree: %s", str(e))
            raise ParserError(f"Could not retrieve repository tree listing: {str(e)}")

    def fetch_raw_file(self, owner: str, repo: str, commit_sha: str, path: str) -> Optional[str]:
        """Download raw file content from raw.githubusercontent.com."""
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{path}"
        logger.debug("Downloading raw file: %s", url)

        try:
            # We don't need GitHub API authentication headers for raw.githubusercontent.com
            with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                return None
        except Exception as e:
            logger.warning("Could not download raw file %s: %s", path, str(e))
            return None

    def get_repo_details(self, url: str) -> Tuple[Dict[str, Any], List[str], Dict[str, str], str]:
        """
        High-level orchestrator to extract repository owner, name, default branch,
        commit SHA, file tree paths, and contents of manifest files.
        """
        owner, repo = self.parse_repo_url(url)
        metadata = self.fetch_repo_metadata(owner, repo)
        
        default_branch = metadata.get("default_branch", "main")
        commit_sha = self.fetch_latest_commit(owner, repo, default_branch)
        
        if not commit_sha:
            commit_sha = default_branch  # Fallback to branch name if commits API fails
            
        tree_nodes = self.fetch_git_tree(owner, repo, commit_sha)
        
        # Filter files from tree
        file_paths: List[str] = []
        manifest_contents: Dict[str, str] = {}
        
        for node in tree_nodes:
            path = node.get("path", "")
            type_ = node.get("type", "")
            
            if not path or type_ != "blob":
                continue
                
            file_paths.append(path)
            
            # Check if this is a manifest file and download it
            filename = path.split("/")[-1]
            if filename in MANIFEST_FILENAMES:
                # Cap file size/download to first few levels to keep it lightweight
                if len(path.split("/")) <= 3:
                    content = self.fetch_raw_file(owner, repo, commit_sha, path)
                    if content:
                        manifest_contents[path] = content[:20000]  # Cap at 20KB per file

        return metadata, file_paths, manifest_contents, commit_sha

    @staticmethod
    def build_folder_tree(paths: List[str], max_depth: int = 4, max_files: int = 200) -> Dict[str, Any]:
        """
        Convert a flat list of file paths into a nested folder structure dictionary,
        capping depth and file count.
        """
        tree: Dict[str, Any] = {}
        file_count = 0

        for path in sorted(paths):
            parts = path.split("/")
            if len(parts) > max_depth:
                continue

            current = tree
            for part in parts[:-1]:
                if part not in current or current[part] is None:
                    current[part] = {}
                current = current[part]

            file_count += 1
            if file_count > max_files:
                break

            current[parts[-1]] = None

        return tree
