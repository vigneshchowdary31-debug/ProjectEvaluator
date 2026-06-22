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

  // Sheetsconnection, Imports, Approvals, Queue, Portfolio, and Notifications
  SHEETS: `${API_BASE}/sheets/`,
  SHEETS_CONNECT: `${API_BASE}/sheets/connect`,
  SHEETS_DISCONNECT: (id) => `${API_BASE}/sheets/${id}/disconnect`,
  SHEETS_TEST: (id) => `${API_BASE}/sheets/${id}/test`,
  SHEETS_SYNC: (id) => `${API_BASE}/sheets/${id}/sync`,
  SHEETS_LOGS: (id) => `${API_BASE}/sheets/${id}/logs`,

  IMPORTS: `${API_BASE}/imports/`,
  IMPORT_DETAIL: (id) => `${API_BASE}/imports/${id}`,
  IMPORT_HISTORY: (id) => `${API_BASE}/imports/${id}/history`,

  APPROVALS: `${API_BASE}/approvals/`,
  APPROVAL_APPROVE: (id) => `${API_BASE}/approvals/${id}/approve`,
  APPROVAL_REJECT: (id) => `${API_BASE}/approvals/${id}/reject`,
  APPROVAL_BULK_APPROVE: `${API_BASE}/approvals/bulk-approve`,

  QUEUE: `${API_BASE}/queue/`,
  QUEUE_STATUS: `${API_BASE}/queue/status`,
  QUEUE_CANCEL: (id) => `${API_BASE}/queue/${id}/cancel`,

  PORTFOLIO_COMPANIES: `${API_BASE}/portfolio/companies`,
  PORTFOLIO_COMPANY: (name) => `${API_BASE}/portfolio/company/${encodeURIComponent(name)}`,
  PORTFOLIO_GENERATE: `${API_BASE}/portfolio/generate`,

  NOTIFICATIONS: `${API_BASE}/notifications/`,
  NOTIFICATIONS_UNREAD: `${API_BASE}/notifications/unread-count`,
  NOTIFICATION_READ: (id) => `${API_BASE}/notifications/${id}/read`,
  NOTIFICATIONS_READ_ALL: `${API_BASE}/notifications/read-all`,
};
