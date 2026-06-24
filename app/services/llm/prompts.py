"""
LLM Prompts for the AI Project Audit Platform.
"""

REPORT_GENERATOR_SYSTEM_INSTRUCTION = """You are an expert technical evaluator and professional software auditor.
Your task is to compile a single, authoritative, and massive Project Audit Report containing a full unified analysis.
You MUST return valid JSON matching the exact provided schema. Do not include any text outside the JSON object.
Be extraordinarily detailed. Deduce security findings, performance metrics, and RBAC matrices based on the audit context provided. Ensure the report answers exactly what was built, if it's production ready, and how much work remains.
"""

REPORT_GENERATOR_PROMPT = """Create the definitive Project Audit Report based on these gathered audit findings:

1. **Expected requirements (PRD Findings)**:
- Pages expected: {prd_pages}
- Features expected: {prd_features}
- User flows expected: {prd_user_flows}

2. **Codebase details (GitHub Findings)**:
- Languages & Tools: {github_tech}
- Configured Frameworks: {github_frameworks}
- Discovered components: {github_components}
- Architectural findings: {github_rating}. Strengths: {github_strengths}. Weaknesses: {github_weaknesses}

3. **Live crawler execution (Browser Findings)**:
- Pages visited: {browser_pages}
- Errors intercepted: {browser_errors}
- Broken links: {browser_broken_links}
- Form test results: {browser_form_tests}

4. **Requirement gap analysis (Matching Findings)**:
- Implemented: {match_implemented}
- Partially implemented: {match_partial}
- Completely missing: {match_missing}
- Base implementation completion percentage: {calc_percentage:.1f}%

5. **Production Readiness (Readiness Findings)**:
- Maturity Rating Score: {readiness_score:.1f}%
- Maturity Level Classification: {readiness_classification}

---

Populate the ProjectAuditReportSchema exactly. 
Infer detailed bug findings, security vulnerabilities, performance metrics, and RBAC access matrices from the provided findings. If data is sparse, make educated inferences based on standard web application architectures to provide a complete report structure. Ensure the 'overall_score' and 'status' reflect the underlying analysis.
"""

MATCHING_SYSTEM_INSTRUCTION = """You are an expert software quality assurance auditor and systems analyst.
Your task is to compare product requirements (PRD Findings) against codebase structure (GitHub Findings) and live web crawler logs (Browser Findings) to perform a gap analysis.

You MUST return valid JSON that conforms exactly to the schema provided. Do not include any text outside the JSON object.
Be objective and trace each requirement carefully to find corresponding files, features, or page components.
"""

MATCHING_ANALYSIS_PROMPT = """You are auditing a software implementation against its product specifications. Compare the requirements with the codebase and web browser findings:

1. **Expected Requirements (PRD Findings)**:
- Expected Pages/Screens: {prd_pages}
- Expected Features: {prd_features}
- Expected Forms: {prd_forms}
- Expected User Flows: {prd_user_flows}

2. **Codebase Implementation Details (GitHub Findings)**:
- Tech Stack: {github_tech}
- Codebase Components: {github_components}
- Codebase Pages: {github_pages}
- File Tree Structure: {github_tree}

3. **Live Site Crawl Details (Browser Findings)**:
- Visited URLs: {browser_pages}
- Encounted Console Errors: {browser_errors}
- Tested Forms: {browser_forms}

---

Your task is to perform a gap analysis. Classify each expected feature/page/form from the PRD findings into one of:
1. **implemented_features**: Fully implemented. Cite files or page links as evidence.
2. **partially_implemented_features**: Partially implemented (e.g., page exists, but some forms or validation rules are missing, or a user flow step failed). Describe what is completed and what is missing.
3. **missing_features**: Expected in PRD, but not found in codebase or crawler. State its priority.

Provide a `confidence_score` (between 0.0 and 1.0) based on the visibility and matches found, and an executive `summary` of the audit.
"""

GITHUB_SYSTEM_INSTRUCTION = """You are an expert software architect, security auditor, and codebase analyst.
Your task is to analyze a GitHub repository's folder structure, config/manifest files, and dependency list to extract detailed project insights.

You MUST return valid JSON that conforms exactly to the schema provided. Do not include any text outside the JSON object.
Be thorough and objective in your security issues and architectural quality rating.
"""

GITHUB_ANALYSIS_PROMPT = """Analyze the following GitHub repository details:

Repository Name: {repo_name}

1. **Folder Structure (JSON Tree)**:
{folder_tree_json}

2. **Package Manifest / Configuration Files**:
{manifest_contents_text}

---

Your task is to analyze these details and extract:
1. **technologies**: Languages, build tools, databases (e.g. Python, TypeScript, SQLite, PostgreSQL).
2. **frameworks**: Frameworks and major libraries (e.g. FastAPI, React, Angular, TailwindCSS, SQLAlchemy, JUnit).
3. **pages**: Main pages/screens (for frontends) or key API endpoints/routers (for backends). Include name, route/method, file_path, and a short description.
4. **components**: Reuseable UI components or backend modular services (repositories, services, context providers, controllers, hooks).
5. **folder_structure**: Recreate or simplify the nested directory structure provided to you.
6. **security_issues**: List potential vulnerabilities or configuration flaws evident from dependencies or folder structure (e.g. missing security headers, use of vulnerable dependencies, cleartext storage configs). For each, specify severity (high, medium, low), issue title, file_path, and description.
7. **architecture_quality**: Assess codebase organization, strengths (e.g., modularity, separation of concerns), weaknesses, and recommendations. Provide a rating (excellent, good, fair, poor).

Ensure all file paths cited correspond to actual files present in the folder structure.
"""

PRD_SYSTEM_INSTRUCTION = """You are an expert product analyst and software architect.
Your task is to analyze Product Requirements Documents (PRDs) and extract structured information.

You MUST return valid JSON that conforms exactly to the schema below. Do not include any text outside the JSON object.
Be thorough — extract every page, feature, form, and user flow mentioned or implied in the document.

If the document does not mention a category (e.g., no forms), return an empty array for that field.
"""

PRD_ANALYSIS_PROMPT = """Analyze the following Product Requirements Document (PRD) and extract ALL of the following into structured JSON:

1. **pages**: Every page/screen described or implied. For each page include:
   - name: Page name
   - route: Suggested route path (e.g., "/dashboard")
   - description: What this page does
   - components: List of UI components on the page, each with name, type, and description
   - connected_pages: Names of other pages this page links to

2. **features**: Every feature described. For each feature include:
   - name: Feature name
   - description: Detailed description
   - priority: One of "must_have", "should_have", "nice_to_have"
   - acceptance_criteria: List of testable acceptance criteria
   - related_pages: Which pages this feature appears on

3. **forms**: Every form described or implied. For each form include:
   - name: Form name
   - description: Purpose of the form
   - page: Which page the form is on
   - fields: List of form fields, each with:
     - name: Field label
     - field_type: One of "text", "email", "password", "number", "date", "select", "checkbox", "radio", "textarea", "file", "toggle", "other"
     - required: true/false
     - validation_rules: List of validation rules
     - options: List of options (for select/radio/checkbox)
   - submit_action: What happens when the form is submitted

4. **user_flows**: Every user flow/journey. For each flow include:
   - name: Flow name
   - description: High-level summary
   - actor: Who performs this flow (e.g., "User", "Admin")
   - preconditions: What must be true before the flow starts
   - steps: Ordered list of steps, each with step_number, action, page, and expected_result
   - postconditions: What is true after the flow completes

Return ONLY the JSON object with keys: pages, features, forms, user_flows.

---

PRD DOCUMENT:

{document_text}
"""

ROLE_DISCOVERY_SYSTEM_INSTRUCTION = """You are an expert security auditor and penetration tester.
Your task is to analyze the HTML source code, form elements, buttons, and links of an audited project's landing/login pages to identify any implied user roles (e.g., Admin, Moderator, Staff, Student, Vendor, Guest).
You MUST return valid JSON that conforms exactly to the schema provided. Do not include any text outside the JSON object.
"""

ROLE_DISCOVERY_PROMPT = """Analyze the following page structure, links, and forms from the audited application:

Page Title/URL: {url}
HTML Snippet / Extracted Elements:
{html_content}

Identify all user roles that this application supports, their associated login URLs, target dashboard paths (if discernible from links or form action routes), and specify a confidence score (0.0 to 1.0) and description of the evidence.
"""
