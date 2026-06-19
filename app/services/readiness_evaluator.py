"""
Production Readiness Evaluator — scores 8 development categories and
determines the final maturity classification (Prototype -> Enterprise Ready).
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ProductionReadinessEvaluator:
    """Evaluates readiness checklist scores and returns a consolidated report."""

    def __init__(self):
        pass

    def evaluate(
        self,
        file_paths: List[str],
        manifest_contents: Dict[str, str],
        security_findings_count: int,
        github_rating: str
    ) -> Dict[str, Any]:
        """
        Evaluate 8 readiness dimensions and output scores/percentages.
        """
        # Find if Dockerfile exists
        has_dockerfile = any("dockerfile" in p.lower() for p in file_paths)
        # Find if README exists
        has_readme = any("readme.md" in p.lower() for p in file_paths)
        # Find if monitoring exists (sentry, prometheus)
        has_monitoring = any(
            any(k in content.lower() for k in ("sentry", "prometheus", "opentelemetry"))
            for content in manifest_contents.values()
        )
        # Find if testing exists
        has_testing = any("test" in p.lower() for p in file_paths)
        # Find if logging exists
        has_logging = any(
            "logging.config" in content or "basicConfig" in content or "logger" in content for content in manifest_contents.values()
        ) or any("logger.py" in p or "logging.py" in p for p in file_paths)

        # 1. Deployment Readiness (Dockerfile, scripts, configs)
        deploy_score = 60.0
        if has_dockerfile:
            deploy_score += 25.0
        if has_readme:
            deploy_score += 15.0

        # 2. Security Score
        sec_score = max(0.0, 100.0 - (security_findings_count * 15.0))

        # 3. Monitoring
        monitor_score = 100.0 if has_monitoring else 50.0

        # 4. Logging
        logging_score = 100.0 if has_logging else 40.0

        # 5. Scalability
        scalability_score = 50.0
        if has_dockerfile:
            scalability_score += 30.0
        # If requirements/manifest indicates db or async drivers
        has_postgres = any("postgres" in content or "psycopg" in content for content in manifest_contents.values())
        if has_postgres:
            scalability_score += 20.0
        else:
            scalability_score += 10.0  # SQLite or other default

        # 6. Maintainability
        rating_map = {
            "excellent": 95.0,
            "good": 85.0,
            "fair": 70.0,
            "poor": 50.0
        }
        maintain_score = rating_map.get(github_rating.lower(), 70.0)

        # 7. Testing
        testing_score = 100.0 if has_testing else 30.0

        # 8. Documentation
        doc_score = 100.0 if has_readme else 40.0

        # Overall average calculation
        scores_list = [
            deploy_score,
            sec_score,
            monitor_score,
            logging_score,
            scalability_score,
            maintain_score,
            testing_score,
            doc_score
        ]
        overall_percentage = sum(scores_list) / len(scores_list)

        # Classifications
        if overall_percentage < 30.0:
            classification = "Prototype"
        elif overall_percentage < 50.0:
            classification = "Development Ready"
        elif overall_percentage < 70.0:
            classification = "Staging Ready"
        elif overall_percentage < 90.0:
            classification = "Production Ready"
        else:
            classification = "Enterprise Ready"

        return {
            "overall_readiness_percentage": round(overall_percentage, 1),
            "classification": classification,
            "categories": {
                "deployment_readiness": deploy_score,
                "security": sec_score,
                "monitoring": monitor_score,
                "logging": logging_score,
                "scalability": scalability_score,
                "maintainability": maintain_score,
                "testing": testing_score,
                "documentation": doc_score
            }
        }
