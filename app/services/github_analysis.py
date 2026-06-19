"""
GitHub Analysis Service — orchestrates parsing + Gemini analysis + database caching.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.github_analysis import GithubAnalysis
from app.repositories.github_analysis import GithubAnalysisRepository
from app.schemas.github import (
    GithubAnalysisRequest,
    GithubAnalysisResponse,
    GithubAnalysisResultSchema,
)
from app.services.gemini import GeminiError, GeminiService
from app.services.github_parser import GithubParserService, ParserError
from app.config import get_settings
from app.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)


class GithubAnalysisService:
    """
    Orchestrates the GitHub analysis pipeline with caching:
    URL → Check DB Cache → (Cache Hit? Return) → Fetch via API → Analyze via Gemini → Save Cache → Return
    """

    def __init__(self, db: Session):
        self.db = db
        self.parser = GithubParserService()
        self.gemini = GeminiService()
        self.repo = GithubAnalysisRepository(db)
        self.settings = get_settings()

    def analyze(self, request: GithubAnalysisRequest) -> GithubAnalysisResponse:
        repo_url = request.repo_url.strip()
        force_refresh = request.force_refresh

        logger.info("GitHub analysis requested for: %s (force_refresh=%s)", repo_url, force_refresh)

        # 1. Parse URL to get owner and repo
        try:
            owner, repo_name = self.parser.parse_repo_url(repo_url)
            normalized_url = f"https://github.com/{owner}/{repo_name}".lower()
        except ParserError as e:
            raise BadRequestException(detail=str(e))

        # 2. Get existing cache entry (if any)
        cached_record = self.repo.get_by_repo_url(normalized_url)
        
        # Fetch metadata to get default branch & latest commit SHA
        commit_sha = None
        default_branch = "main"
        try:
            metadata = self.parser.fetch_repo_metadata(owner, repo_name)
            default_branch = metadata.get("default_branch", "main")
            commit_sha = self.parser.fetch_latest_commit(owner, repo_name, default_branch)
        except Exception as e:
            logger.warning("Failed to check GitHub API for commit SHA: %s", str(e))
            # Fallback: if we have a cache, return it immediately because we can't check GitHub API
            if cached_record:
                logger.info("GitHub API check failed. Returning cached analysis as fallback.")
                return self._build_response(
                    repo_url=normalized_url, 
                    commit_sha=cached_record.commit_sha, 
                    result_data=cached_record.result, 
                    is_cached=True, 
                    analyzed_at=cached_record.updated_at
                )
            raise BadRequestException(detail=f"GitHub API is unreachable and no cache exists: {str(e)}")

        # 3. Check if cached record is still valid
        if cached_record and not force_refresh:
            # Check if commit SHA matches
            sha_matches = (cached_record.commit_sha == commit_sha)
            
            # Check TTL
            ttl_expired = False
            ttl_hours = self.settings.GITHUB_CACHE_TTL_HOURS
            age = datetime.now(timezone.utc) - cached_record.updated_at.replace(tzinfo=timezone.utc)
            if age > timedelta(hours=ttl_hours):
                ttl_expired = True

            if sha_matches and not ttl_expired:
                logger.info("Cache hit for %s (commit_sha=%s)", normalized_url, commit_sha)
                return self._build_response(
                    repo_url=normalized_url,
                    commit_sha=commit_sha,
                    result_data=cached_record.result,
                    is_cached=True,
                    analyzed_at=cached_record.updated_at
                )
            else:
                logger.info("Cache stale or SHA changed for %s (sha_matches=%s, ttl_expired=%s)", normalized_url, sha_matches, ttl_expired)

        # 4. Fetch full repo tree and manifest files (Cache Miss)
        logger.info("Cache miss. Fetching details and performing Gemini analysis for: %s", normalized_url)
        try:
            tree_nodes = self.parser.fetch_git_tree(owner, repo_name, commit_sha or default_branch)
            
            file_paths = []
            manifest_contents = {}
            for node in tree_nodes:
                path = node.get("path", "")
                type_ = node.get("type", "")
                if not path or type_ != "blob":
                    continue
                file_paths.append(path)
                
                # Check manifest files
                filename = path.split("/")[-1]
                if filename in self.parser.MANIFEST_FILENAMES:
                    if len(path.split("/")) <= 3:  # limit depth to keep it clean
                        content = self.parser.fetch_raw_file(owner, repo_name, commit_sha or default_branch, path)
                        if content:
                            manifest_contents[path] = content[:20000]
        except Exception as e:
            # Fallback to cache if anything fails during parsing
            if cached_record:
                logger.warning("Failed to fetch full repo details: %s. Falling back to cached analysis.", str(e))
                return self._build_response(
                    repo_url=normalized_url, 
                    commit_sha=cached_record.commit_sha, 
                    result_data=cached_record.result, 
                    is_cached=True, 
                    analyzed_at=cached_record.updated_at
                )
            raise BadRequestException(detail=f"Failed to fetch repository details: {str(e)}")

        # 5. Build nested folder tree structure (capping at depth 4 / 200 files)
        folder_tree = self.parser.build_folder_tree(file_paths, max_depth=4, max_files=200)

        # 6. Analyze with Gemini
        try:
            analysis_result = self.gemini.analyze_github(
                repo_name=f"{owner}/{repo_name}",
                folder_tree=folder_tree,
                manifest_contents=manifest_contents
            )
        except GeminiError as e:
            if cached_record:
                logger.warning("Gemini analysis failed: %s. Falling back to cached analysis.", str(e))
                return self._build_response(
                    repo_url=normalized_url, 
                    commit_sha=cached_record.commit_sha, 
                    result_data=cached_record.result, 
                    is_cached=True, 
                    analyzed_at=cached_record.updated_at
                )
            raise BadRequestException(detail=f"AI analysis failed: {str(e)}")

        # Convert Pydantic result to dict for saving to DB
        result_dict = analysis_result.model_dump()

        # 7. Write to cache in SQLite
        if cached_record:
            self.repo.update(cached_record, commit_sha, result_dict)
            analyzed_at = cached_record.updated_at
        else:
            new_analysis = GithubAnalysis(
                repo_url=normalized_url,
                commit_sha=commit_sha,
                result=result_dict
            )
            self.repo.create(new_analysis)
            analyzed_at = new_analysis.created_at

        return self._build_response(
            repo_url=normalized_url,
            commit_sha=commit_sha,
            result_data=result_dict,
            is_cached=False,
            analyzed_at=analyzed_at
        )

    def _build_response(
        self,
        repo_url: str,
        commit_sha: Optional[str],
        result_data: dict,
        is_cached: bool,
        analyzed_at: datetime
    ) -> GithubAnalysisResponse:
        return GithubAnalysisResponse(
            repo_url=repo_url,
            commit_sha=commit_sha,
            is_cached=is_cached,
            analyzed_at=analyzed_at.isoformat(),
            analysis=GithubAnalysisResultSchema.model_validate(result_data)
        )
