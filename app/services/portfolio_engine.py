"""
Portfolio Engine Service — aggregates project statistics per company,
analyzes risk categories, generates HTML portfolio reports, and uploads them to Google Drive.
"""

import os
import logging
import tempfile
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.project import Project
from app.models.company_portfolio import CompanyPortfolio
from app.models.project_report import ProjectReport
from app.models.report import Report
from app.models.audit_run import AuditRun
from app.services.google_drive import GoogleDriveService

logger = logging.getLogger(__name__)


class PortfolioEngine:
    """Aggregates multi-project data into client-facing company portfolios."""

    def __init__(self, db: Session):
        self.db = db
        self.drive_service = GoogleDriveService()

    def generate_all_portfolios(self) -> List[CompanyPortfolio]:
        """Aggregate portfolios for all unique companies in the database."""
        # Find all distinct company names from projects (excluding nulls)
        companies_query = self.db.query(Project.company_name).filter(
            Project.company_name != None,
            Project.company_name != ""
        ).distinct().all()
        
        company_names = [r[0] for r in companies_query]
        portfolios = []
        for name in company_names:
            try:
                portfolio = self.generate_portfolio(name)
                portfolios.append(portfolio)
            except Exception as e:
                logger.error("Failed to generate portfolio for %s: %s", name, str(e))
                
        return portfolios

    def generate_portfolio(self, company_name: str) -> CompanyPortfolio:
        """Collect metrics, compile report, upload it, and save the CompanyPortfolio."""
        projects = self.db.query(Project).filter(Project.company_name == company_name).all()
        if not projects:
            raise ValueError(f"No projects found for company: {company_name}")

        total_projects = len(projects)
        total_completion = 0.0
        total_readiness = 0.0
        total_security = 0.0
        projects_at_risk = 0
        all_findings = []

        for p in projects:
            latest_report = self.db.query(ProjectReport).filter(
                ProjectReport.project_id == p.id
            ).order_by(ProjectReport.generated_at.desc()).first()

            latest_run = self.db.query(AuditRun).filter(
                AuditRun.project_id == p.id
            ).order_by(AuditRun.created_at.desc()).first()

            comp = 0.0
            read = 0.0
            sec = 100.0
            findings_count = 0

            if latest_report:
                comp = latest_report.completion_score
                rep_data = latest_report.report_data
                read = rep_data.get("production_readiness_score", 0.0) if isinstance(rep_data, dict) else 0.0

            if latest_run:
                reports = self.db.query(Report).filter(Report.audit_run_id == latest_run.id).all()
                findings_count = len(reports)
                for r in reports:
                    all_findings.append(r.title)
                    sev = r.severity.lower()
                    if sev == "critical":
                        sec -= 25.0
                    elif sev == "high":
                        sec -= 15.0
                    elif sev == "medium":
                        sec -= 10.0
                    elif sev == "low":
                        sec -= 5.0
                sec = max(0.0, sec)

            total_completion += comp
            total_readiness += read
            total_security += sec

            health = (comp * 0.5) + (read * 0.5) - (findings_count * 5)
            health = max(0.0, min(100.0, health))
            if health < 50.0:
                projects_at_risk += 1

        avg_completion = total_completion / total_projects
        avg_readiness = total_readiness / total_projects
        avg_security = total_security / total_projects
        
        # Calculate overall company health score
        avg_health = (avg_completion * 0.4) + (avg_readiness * 0.3) + (avg_security * 0.3)

        if avg_health >= 85.0:
            health_rating = "excellent"
        elif avg_health >= 70.0:
            health_rating = "good"
        elif avg_health >= 50.0:
            health_rating = "average"
        else:
            health_rating = "poor"

        # Determine top 5 risks
        risk_counter = Counter(all_findings)
        top_risks = [
            {"finding": item, "frequency": count}
            for item, count in risk_counter.most_common(5)
        ]

        # Check for existing portfolio record
        portfolio = self.db.query(CompanyPortfolio).filter(CompanyPortfolio.company_name == company_name).first()
        if not portfolio:
            portfolio = CompanyPortfolio(company_name=company_name)
            self.db.add(portfolio)

        portfolio.projects_count = total_projects
        portfolio.avg_completion = round(avg_completion, 1)
        portfolio.avg_security = round(avg_security, 1)
        portfolio.avg_readiness = round(avg_readiness, 1)
        portfolio.projects_at_risk = projects_at_risk
        portfolio.top_risks = top_risks
        portfolio.health_rating = health_rating
        portfolio.last_generated_at = datetime.now(timezone.utc)
        self.db.commit()

        # Generate HTML report and upload to Google Drive
        if self.drive_service.enabled:
            try:
                report_link = self._generate_and_upload_report(company_name, projects, portfolio)
                if report_link:
                    portfolio.report_url = report_link
                    self.db.commit()
            except Exception as drive_err:
                logger.error("Failed to upload portfolio report to Google Drive: %s", str(drive_err))

        return portfolio

    def _generate_and_upload_report(self, company_name: str, projects: List[Project], portfolio: CompanyPortfolio) -> Optional[str]:
        """Generates a beautiful HTML report summarizing the company portfolio and uploads it."""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Company Portfolio: {company_name}</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 40px; line-height: 1.6; background-color: #fcfcfc; }}
    h1 {{ color: #1a73e8; border-bottom: 2px solid #e8f0fe; padding-bottom: 10px; }}
    h2 {{ color: #202124; margin-top: 30px; }}
    .stats-container {{ display: flex; flex-wrap: wrap; margin-bottom: 30px; }}
    .stat-box {{ flex: 1; min-width: 150px; padding: 20px; border: 1px solid #dadce0; border-radius: 8px; margin-right: 15px; margin-bottom: 15px; background-color: #fff; box-shadow: 0 1px 2px 0 rgba(60,64,67,.3); }}
    .stat-label {{ font-size: 12px; color: #5f6368; font-weight: bold; text-transform: uppercase; }}
    .stat-number {{ font-size: 28px; font-weight: bold; color: #1a73e8; margin-top: 5px; }}
    .health-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 14px; font-weight: bold; text-transform: uppercase; }}
    .health-excellent {{ background-color: #e6f4ea; color: #137333; }}
    .health-good {{ background-color: #e6f4ea; color: #137333; }}
    .health-average {{ background-color: #fef7e0; color: #b06000; }}
    .health-poor {{ background-color: #fce8e6; color: #c5221f; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #fff; }}
    th, td {{ border: 1px solid #dadce0; padding: 12px; text-align: left; }}
    th {{ background-color: #f8f9fa; font-weight: bold; }}
    tr:nth-child(even) {{ background-color: #f8f9fa; }}
    .risk-list {{ list-style-type: none; padding-left: 0; }}
    .risk-item {{ background-color: #fce8e6; color: #c5221f; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; border-left: 4px solid #d93025; }}
  </style>
</head>
<body>
  <h1>Company Portfolio Report: {company_name}</h1>
  <p>Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
  
  <div class="stats-container">
    <div class="stat-box">
      <div class="stat-label">Total Projects</div>
      <div class="stat-number">{portfolio.projects_count}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Health Rating</div>
      <div class="stat-number">
        <span class="health-badge health-{portfolio.health_rating}">{portfolio.health_rating}</span>
      </div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Avg Completion</div>
      <div class="stat-number">{portfolio.avg_completion}%</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Avg Security Score</div>
      <div class="stat-number">{portfolio.avg_security}%</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">At-Risk Projects</div>
      <div class="stat-number" style="color: {'#d93025' if portfolio.projects_at_risk > 0 else '#137333'}">{portfolio.projects_at_risk}</div>
    </div>
  </div>

  <h2>Top Portfolio Risks</h2>
  {f'<p>No security/readiness risks identified across projects.</p>' if not portfolio.top_risks else 
   '<ul class="risk-list">' + ''.join(f'<li class="risk-item"><strong>{item["finding"]}</strong> (Affects {item["frequency"]} project(s))</li>' for item in portfolio.top_risks) + '</ul>'}

  <h2>Project Inventory</h2>
  <table>
    <thead>
      <tr>
        <th>Project Name</th>
        <th>Student Name</th>
        <th>Repository URL</th>
        <th>Source</th>
        <th>Created At</th>
      </tr>
    </thead>
    <tbody>
  """
        for p in projects:
            html_content += f"""
      <tr>
        <td><strong>{p.name}</strong></td>
        <td>{p.student_name or 'N/A'}</td>
        <td><a href="{p.repository_url or '#'}" target="_blank">{p.repository_url or 'N/A'}</a></td>
        <td>{p.source}</td>
        <td>{p.created_at.strftime('%Y-%m-%d')}</td>
      </tr>
"""
        html_content += """
    </tbody>
  </table>
</body>
</html>
"""

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"portfolio_{company_name.lower().replace(' ', '_')}.html")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Upload to Drive
        drive_folder_id = self.drive_service.parent_folder_id
        file_name = f"{company_name} Portfolio Report.html"
        view_link = self.drive_service.upload_file(
            file_path=temp_path,
            file_name=file_name,
            mime_type="text/html",
            folder_id=drive_folder_id
        )

        # Cleanup
        try:
            os.remove(temp_path)
        except Exception:
            pass

        return view_link
