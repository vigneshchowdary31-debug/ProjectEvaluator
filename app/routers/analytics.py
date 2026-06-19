"""
Analytics Router — endpoints for analytics summaries, student rankings, and company dashboards.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.project import Project
from app.models.audit_run import AuditRun
from app.models.generated_report import GeneratedReport
from app.models.report import Report
from app.repositories.user import UserRepository

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics Dashboard"])


@router.get("/summary")
def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve global statistics summary for all projects."""
    # Enforce basic auth
    total_projects = db.query(func.count(Project.id)).scalar() or 0
    total_runs = db.query(func.count(AuditRun.id)).scalar() or 0
    
    # Calculate average completion
    avg_completion = db.query(func.avg(GeneratedReport.completion_percentage)).scalar() or 0.0
    
    # Count security reports by severity
    vuln_counts = {
        "critical": db.query(func.count(Report.id)).filter(Report.severity == "critical").scalar() or 0,
        "high": db.query(func.count(Report.id)).filter(Report.severity == "high").scalar() or 0,
        "medium": db.query(func.count(Report.id)).filter(Report.severity == "medium").scalar() or 0,
        "low": db.query(func.count(Report.id)).filter(Report.severity == "low").scalar() or 0,
    }

    # Projects list with completion scores for trend chart
    projects_list = []
    projects = db.query(Project).all()
    for p in projects:
        # Get latest generated report
        latest_report = db.query(GeneratedReport).filter(
            GeneratedReport.project_id == p.id
        ).order_by(GeneratedReport.created_at.desc()).first()
        
        projects_list.append({
            "id": p.id,
            "name": p.name,
            "completion_percentage": latest_report.completion_percentage if latest_report else 0.0,
            "created_at": p.created_at.isoformat()
        })

    return {
        "total_projects": total_projects,
        "total_audit_runs": total_runs,
        "average_completion_percentage": round(avg_completion, 1),
        "security_findings_breakdown": vuln_counts,
        "projects_trend": projects_list
    }


@router.get("/rankings/students")
def get_student_rankings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve students leaderboard ranked by project completion percentage, code quality, and security."""
    user_repo = UserRepository(db)
    all_users, _ = user_repo.get_all(page=1, page_size=200) # Retrieve up to 200 users
    
    rankings = []
    for u in all_users:
        if u.is_admin:
            continue
            
        user_projects = db.query(Project).filter(Project.owner_id == u.id).all()
        if not user_projects:
            continue
            
        proj_count = len(user_projects)
        total_completion = 0.0
        total_readiness = 0.0
        total_bugs = 0
        has_reports = False
        
        for p in user_projects:
            latest_report = db.query(GeneratedReport).filter(
                GeneratedReport.project_id == p.id
            ).order_by(GeneratedReport.created_at.desc()).first()
            
            if latest_report:
                has_reports = True
                total_completion += latest_report.completion_percentage
                # Extract readiness score from student report JSON
                std_rep = latest_report.student_report
                total_readiness += std_rep.get("production_readiness_score", 50.0)
                
            # Count findings
            bugs_count = db.query(func.count(Report.id)).filter(
                Report.project_id == p.id
            ).scalar() or 0
            total_bugs += bugs_count

        avg_completion = total_completion / proj_count if has_reports else 0.0
        avg_readiness = total_readiness / proj_count if has_reports else 0.0
        
        rankings.append({
            "student_id": u.id,
            "student_name": u.full_name,
            "company_name": u.company_name or "Independent",
            "projects_count": proj_count,
            "average_completion_percentage": round(avg_completion, 1),
            "average_production_readiness": round(avg_readiness, 1),
            "total_vulnerabilities": total_bugs,
            # Composite score calculation (completion weighted 60%, readiness 30%, clean-code safety bonus 10%)
            "score": round((avg_completion * 0.6) + (avg_readiness * 0.3) + (max(0, 10 - total_bugs) * 1.0), 1)
        })
        
    # Sort rankings by composite score descending
    rankings.sort(key=lambda x: x["score"], reverse=True)
    return rankings


@router.get("/company")
def get_company_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve aggregated stats for all company projects (Admins & Corporate stakeholders)."""
    # Group by company name
    companies_query = db.query(User.company_name).filter(User.company_name != None).distinct().all()
    companies = [c[0] for c in companies_query]
    
    company_stats = []
    
    for c_name in (companies or ["Independent"]):
        # Find all users belonging to this company
        user_ids = [u.id for u in db.query(User).filter(User.company_name == c_name).all()]
        if not user_ids:
            continue
            
        company_projects = db.query(Project).filter(Project.owner_id.in_(user_ids)).all()
        if not company_projects:
            continue
            
        proj_count = len(company_projects)
        total_completion = 0.0
        total_readiness = 0.0
        total_bugs = 0
        project_healths = []
        
        for p in company_projects:
            latest_report = db.query(GeneratedReport).filter(
                GeneratedReport.project_id == p.id
            ).order_by(GeneratedReport.created_at.desc()).first()
            
            completion = 0.0
            readiness = 50.0
            if latest_report:
                completion = latest_report.completion_percentage
                std_rep = latest_report.student_report
                readiness = std_rep.get("production_readiness_score", 50.0)
                
            total_completion += completion
            total_readiness += readiness
            
            bugs_count = db.query(func.count(Report.id)).filter(
                Report.project_id == p.id
            ).scalar() or 0
            total_bugs += bugs_count
            
            # Health classification for this project
            health_score = (completion * 0.5) + (readiness * 0.5) - (bugs_count * 5)
            health_score = max(0.0, min(100.0, health_score))
            project_healths.append(health_score)

        avg_completion = total_completion / proj_count
        avg_readiness = total_readiness / proj_count
        avg_health = sum(project_healths) / len(project_healths) if project_healths else 0.0
        
        # Risk level determination based on average health
        if avg_health >= 80:
            risk_level = "Low"
        elif avg_health >= 50:
            risk_level = "Medium"
        else:
            risk_level = "High"

        company_stats.append({
            "company_name": c_name,
            "projects_count": proj_count,
            "average_completion": round(avg_completion, 1),
            "average_readiness": round(avg_readiness, 1),
            "total_vulnerabilities": total_bugs,
            "average_health_score": round(avg_health, 1),
            "risk_level": risk_level
        })
        
    return company_stats
