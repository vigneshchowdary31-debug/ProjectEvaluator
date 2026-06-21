export const API_BASE = '/api/v1';

export const API_PATHS = {
  // Auth
  LOGIN: `${API_BASE}/auth/login`,
  REGISTER: `${API_BASE}/auth/register`,
  REFRESH: `${API_BASE}/auth/refresh`,
  LOGOUT: `${API_BASE}/auth/logout`,
  LOGOUT_ALL: `${API_BASE}/auth/logout-all`,
  ME: `${API_BASE}/auth/me`,

  // Projects CRUD & Nested
  PROJECTS: `${API_BASE}/projects/`,
  PROJECT_DETAIL: (id) => `${API_BASE}/projects/${id}`,
  PROJECT_AUDIT: (id) => `${API_BASE}/projects/${id}/audit`,
  PROJECT_RUNS: (id) => `${API_BASE}/projects/${id}/audit-runs`,
  PROJECT_REPORTS: (id) => `${API_BASE}/reports/project/${id}`,

  // Reports
  REPORTS: `${API_BASE}/reports/`,
  REPORT_DETAIL: (id) => `${API_BASE}/reports/${id}`,

  // Evidence
  EVIDENCE_PROJECT: (id) => `${API_BASE}/evidence/project/${id}`,
  EVIDENCE_RUN: (id) => `${API_BASE}/evidence/run/${id}`,

  // Analytics & Leaderboards
  ANALYTICS_SUMMARY: `${API_BASE}/analytics/summary`,
  ANALYTICS_RANKINGS: `${API_BASE}/analytics/rankings/students`,
  ANALYTICS_COMPANY: `${API_BASE}/analytics/company`,

  // Settings
  SETTINGS_STATUS: `${API_BASE}/settings/status`,

  // Authenticated Audit
  AUTH_CREDENTIALS: (id) => `${API_BASE}/projects/${id}/auth/credentials`,
  AUTH_STATUS: (id) => `${API_BASE}/projects/${id}/auth/status`,
  AUTH_FINDINGS: (id) => `${API_BASE}/projects/${id}/auth/findings`,
  AUTH_ROUTES: (id) => `${API_BASE}/projects/${id}/auth/routes`,
  AUTH_SCORES: (id) => `${API_BASE}/projects/${id}/auth/scores`,
};
