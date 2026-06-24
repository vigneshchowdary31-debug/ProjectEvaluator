import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  FolderKanban, Play, Github, FileText, Globe, RefreshCw, 
  Terminal, History, ShieldAlert, Award, FileCode, CheckCircle, XCircle, Lock, Loader2
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [runs, setRuns] = useState([]);
  const [evidences, setEvidences] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Tabs & RBAC state
  const [activeTab, setActiveTab] = useState('overview');
  const [rbacStatus, setRbacStatus] = useState(null);
  const [rbacScores, setRbacScores] = useState(null);
  const [rbacCoverage, setRbacCoverage] = useState([]);
  const [rbacViolations, setRbacViolations] = useState([]);
  const [selectedLockerRole, setSelectedLockerRole] = useState('Guest');

  // Auth audit state
  const [authStatus, setAuthStatus] = useState(null);
  const [authScores, setAuthScores] = useState(null);
  const [authFindings, setAuthFindings] = useState([]);
  const [authRoutes, setAuthRoutes] = useState([]);

  // Audit Execution & WS console state
  const [auditing, setAuditing] = useState(false);
  const [activeRunId, setActiveRunId] = useState('');
  const [wsLogs, setWsLogs] = useState([]);
  const [wsProgress, setWsProgress] = useState(0);
  const [currentStepName, setCurrentStepName] = useState('');
  const consoleEndRef = useRef(null);

  // Failure Diagnostics state
  const [selectedDiagnosticsRun, setSelectedDiagnosticsRun] = useState(null);
  const [diagnosticsData, setDiagnosticsData] = useState(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);

  // Lightbox Image State
  const [activeLightboxImage, setActiveLightboxImage] = useState(null);

  // Handle ESC key to close failure diagnostics and lightbox modals
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setSelectedDiagnosticsRun(null);
        setDiagnosticsData(null);
        setActiveLightboxImage(null);
      }
    };
    if (selectedDiagnosticsRun || activeLightboxImage) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedDiagnosticsRun, activeLightboxImage]);

  const handleOpenDiagnostics = async (runId) => {
    setSelectedDiagnosticsRun(runId);
    setLoadingDiagnostics(true);
    setDiagnosticsData(null);
    try {
      const res = await api.get(`/api/v1/audit-runs/${runId}/diagnostics`);
      setDiagnosticsData(res.data);
    } catch (err) {
      console.error("Failed to load audit diagnostics", err);
    } finally {
      setLoadingDiagnostics(false);
    }
  };

  const fetchData = async () => {
    try {
      const projRes = await api.get(API_PATHS.PROJECT_DETAIL(id));
      setProject(projRes.data);
      
      const runsRes = await api.get(`${API_PATHS.PROJECT_RUNS(id)}?page_size=20`);
      setRuns(runsRes.data.items);
      
      const evidenceRes = await api.get(API_PATHS.EVIDENCE_PROJECT(id));
      setEvidences(evidenceRes.data);

      const reportsRes = await api.get(API_PATHS.PROJECT_REPORTS(id));
      setReports(reportsRes.data);

      // Fetch RBAC data
      try {
        const rbacStatusRes = await api.get(`/api/v1/projects/${id}/rbac/status`);
        setRbacStatus(rbacStatusRes.data);
        if (rbacStatusRes.data && rbacStatusRes.data.rbac_enabled) {
          const [scoresRes, coverageRes, violationsRes] = await Promise.all([
            api.get(`/api/v1/projects/${id}/rbac/scores`),
            api.get(`/api/v1/projects/${id}/rbac/coverage`),
            api.get(`/api/v1/projects/${id}/rbac/violations`),
          ]);
          setRbacScores(scoresRes.data);
          setRbacCoverage(coverageRes.data.coverage || []);
          setRbacViolations(violationsRes.data.violations || []);
        }
      } catch (rbacErr) {
        console.error('Failed to load RBAC results', rbacErr);
      }

      // Fetch Auth audit data
      try {
        const authStatusRes = await api.get(API_PATHS.AUTH_STATUS(id));
        setAuthStatus(authStatusRes.data);
        if (authStatusRes.data && authStatusRes.data.auth_required) {
          const [authScoresRes, authFindingsRes, authRoutesRes] = await Promise.all([
            api.get(API_PATHS.AUTH_SCORES(id)),
            api.get(API_PATHS.AUTH_FINDINGS(id)),
            api.get(API_PATHS.AUTH_ROUTES(id)),
          ]);
          setAuthScores(authScoresRes.data);
          setAuthFindings(authFindingsRes.data.findings || []);
          setAuthRoutes(authRoutesRes.data.protected_routes || []);
        }
      } catch (authErr) {
        console.error('Failed to load Auth results', authErr);
      }
    } catch (err) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(`Failed to load project details: ${err.response.data.detail}`);
      } else {
        setError('Failed to load project details.');
      }
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchData();
  }, [id]);

  // Scroll WS console to bottom when logs update
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [wsLogs]);

  const handleRunAudit = async () => {
    setAuditing(true);
    setWsLogs([]);
    setWsProgress(0);
    setCurrentStepName('Initializing');

    try {
      const runRes = await api.post(API_PATHS.PROJECT_AUDIT(id));
      const runId = runRes.data.id;
      setActiveRunId(runId);
      
      // Setup WebSocket connection
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || '127.0.0.1:8000';
      const wsUrl = `${protocol}//${host}/api/v1/audit-runs/${runId}/ws`;
      
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        setWsLogs(prev => [...prev, { text: '>> Connected to real-time audit event broadcast channel.', type: 'info' }]);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const elapsed = data.elapsed_seconds ? `[+${data.elapsed_seconds.toFixed(1)}s]` : '';
        const logText = `${elapsed} ${data.message}`;
        
        setWsLogs(prev => [...prev, { 
          text: logText, 
          type: data.is_error ? 'error' : data.step === 'complete' ? 'success' : 'log' 
        }]);
        setWsProgress(data.progress || 0);
        setCurrentStepName(data.step || '');
        
        if (data.step === 'complete') {
          setAuditing(false);
          fetchData();
          ws.close();
        } else if (data.step === 'failed') {
          setAuditing(false);
          fetchData();
          ws.close();
        }
      };

      ws.onerror = (err) => {
        setWsLogs(prev => [...prev, { text: '>> WebSocket connection error.', type: 'error' }]);
        setAuditing(false);
        ws.close();
      };

      ws.onclose = () => {
        setWsLogs(prev => [...prev, { text: '>> WebSocket session disconnected.', type: 'info' }]);
      };

    } catch (err) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(`Audit Run Failed: ${err.response.data.detail}`);
      } else {
        setError('Failed to trigger audit run. Please check the server logs.');
      }
      setAuditing(false);
    }
  };

  const getGroupedCoverage = () => {
    const pages = {};
    rbacCoverage.forEach(row => {
      if (!pages[row.page]) {
        pages[row.page] = { page: row.page, url: row.url, Guest: '-', User: '-', Admin: '-', Guest_img: null, User_img: null, Admin_img: null };
      }
      pages[row.page][row.role] = row.status;
      pages[row.page][`${row.role}_img`] = row.screenshot_url;
    });
    return Object.values(pages);
  };

  const getRoleScreenshots = () => {
    const screenshots = [];
    rbacCoverage.forEach(row => {
      if (row.role === selectedLockerRole && row.screenshot_url) {
        screenshots.push({ url: row.screenshot_url, page: row.page });
      }
    });
    return screenshots;
  };


  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <RefreshCw className="w-10 h-10 text-indigo-500 animate-spin" />
        <span className="text-gray-400 text-sm font-semibold tracking-wider">Loading project profile...</span>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold leading-relaxed">
        {error || 'Project not found.'}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Back button & title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link to="/projects" className="p-2 border border-white/5 bg-white/5 text-gray-400 hover:text-white rounded-xl transition-all">
            <FolderKanban className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-black text-white uppercase tracking-wide">{project.name}</h1>
            <p className="text-xs text-indigo-400 font-bold uppercase tracking-widest mt-0.5">Project ID: {project.id}</p>
          </div>
        </div>

        <button 
          onClick={handleRunAudit}
          disabled={auditing}
          className="flex items-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-500 active:scale-95 disabled:opacity-50 disabled:pointer-events-none text-white font-bold tracking-wider text-xs uppercase rounded-xl shadow-lg shadow-indigo-500/10 transition-all"
        >
          <Play className="w-4 h-4" />
          {auditing ? 'Audit Executing...' : 'Run Audit'}
        </button>
      </div>

      {/* Grid: Details & Live Console */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: URLs & Metadata */}
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-6">
            <h3 className="text-sm font-black text-white uppercase tracking-wider border-b border-white/5 pb-3">URLs Configuration</h3>
            
            <div className="space-y-4">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">GitHub Codebase</span>
                {project.repository_url ? (
                  <a href={project.repository_url} target="_blank" rel="noreferrer" className="text-sm text-indigo-400 hover:underline flex items-center gap-1.5 break-all">
                    <Github className="w-4 h-4 shrink-0" />
                    Repository URL
                  </a>
                ) : <span className="text-sm text-gray-500 font-medium">Not configured</span>}
              </div>

              <div className="space-y-1">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">PRD Google Doc</span>
                {project.prd_url ? (
                  <a href={project.prd_url} target="_blank" rel="noreferrer" className="text-sm text-indigo-400 hover:underline flex items-center gap-1.5 break-all">
                    <FileText className="w-4 h-4 shrink-0" />
                    PRD Doc URL
                  </a>
                ) : <span className="text-sm text-gray-500 font-medium">Not configured</span>}
              </div>

              <div className="space-y-1">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Production Deployment</span>
                {project.deployment_url ? (
                  <a href={project.deployment_url} target="_blank" rel="noreferrer" className="text-sm text-indigo-400 hover:underline flex items-center gap-1.5 break-all">
                    <Globe className="w-4 h-4 shrink-0" />
                    Live Site Link
                  </a>
                ) : <span className="text-sm text-gray-500 font-medium">Not configured</span>}
              </div>
            </div>
          </div>

          {/* Quick Metrics */}
          {reports.length > 0 && (
            <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
              <h3 className="text-sm font-black text-white uppercase tracking-wider border-b border-white/5 pb-3">Latest Audit</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 rounded-xl p-4 border border-white/5 text-center">
                  <span className="text-xs font-bold text-gray-400 block uppercase tracking-wider mb-1">Completion</span>
                  <span className="text-2xl font-black text-indigo-400">
                    {reports[0].completion_percentage < 0 ? 'N/A' : `${reports[0].completion_percentage.toFixed(1)}%`}
                  </span>
                </div>
                <div className="bg-white/5 rounded-xl p-4 border border-white/5 text-center">
                  <span className="text-xs font-bold text-gray-400 block uppercase tracking-wider mb-1">Readiness</span>
                  <span className="text-2xl font-black text-indigo-400">{reports[0].student_report.production_readiness_score.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Console / Execution Terminal */}
        <div className="lg:col-span-2 space-y-6">
          {(auditing || wsLogs.length > 0) ? (
            <div className="glass-card rounded-2xl p-6 border border-white/10 shadow-2xl bg-black relative flex flex-col h-96">
              <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
                <div className="flex items-center gap-2 text-indigo-400 font-bold text-xs uppercase tracking-widest">
                  <Terminal className="w-4 h-4 animate-spin-slow" />
                  Live Audit Execution Console
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{currentStepName.toUpperCase()}</span>
                  <span className="text-xs font-black text-indigo-400">{wsProgress}%</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden mb-4">
                <div 
                  className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                  style={{ width: `${wsProgress}%` }}
                ></div>
              </div>

              {/* Console log outputs */}
              <div className="flex-1 overflow-y-auto font-mono text-xs text-gray-300 space-y-2 p-3 bg-neutral-950/80 border border-white/5 rounded-xl">
                {wsLogs.map((log, idx) => (
                  <div 
                    key={idx} 
                    className={`${
                      log.type === 'error' 
                        ? 'text-rose-400 font-semibold' 
                        : log.type === 'info' 
                          ? 'text-indigo-400' 
                          : log.type === 'success'
                            ? 'text-emerald-400 font-bold'
                            : 'text-gray-300'
                    }`}
                  >
                    {log.text}
                  </div>
                ))}
                <div ref={consoleEndRef} />
              </div>
            </div>
          ) : (
            <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center justify-center gap-3">
              <Terminal className="w-12 h-12 text-gray-600" />
              <h3 className="text-lg font-bold text-gray-300">Live Console Idle</h3>
              <p className="text-gray-500 text-sm max-w-sm">
                Initiate an audit run to watch Playwright crawling viewports, dependency audits, and Gemini report synthesis logs in real-time.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-white/5 pb-px gap-6">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-4 text-xs font-bold uppercase tracking-wider transition-all border-b-2 ${
            activeTab === 'overview' 
              ? 'border-indigo-500 text-white' 
              : 'border-transparent text-gray-500 hover:text-white'
          }`}
        >
          Overview & Reports
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`pb-4 text-xs font-bold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 ${
            activeTab === 'security' 
              ? 'border-indigo-500 text-white' 
              : 'border-transparent text-gray-500 hover:text-white'
          }`}
        >
          <ShieldAlert className="w-4 h-4 text-indigo-500" />
          Security & RBAC Matrix
        </button>
        <button
          onClick={() => setActiveTab('auth')}
          className={`pb-4 text-xs font-bold uppercase tracking-wider transition-all border-b-2 flex items-center gap-2 ${
            activeTab === 'auth' 
              ? 'border-indigo-500 text-white' 
              : 'border-transparent text-gray-500 hover:text-white'
          }`}
        >
          <Lock className="w-4 h-4 text-indigo-500" />
          Authentication
        </button>
      </div>

      {activeTab === 'overview' && (
        <>
          {/* Reports, Audit Runs & Evidence Tabs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Reports History */}
            <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
              <div className="flex items-center justify-between border-b border-white/5 pb-3">
                <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
                  <Award className="w-4 h-4 text-indigo-400" />
                  Audit Reports History
                </h3>
              </div>
              
              {reports.length === 0 ? (
                <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider block py-6 text-center">No reports compiled yet.</span>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {reports.map((r, i) => (
                    <Link 
                      key={r.id} 
                      to={`/report/${r.id}`}
                      className="flex items-center justify-between p-4 bg-white/5 border border-white/5 rounded-xl hover:border-indigo-500/20 hover:bg-indigo-500/5 transition-all group"
                    >
                      <div className="space-y-1">
                        <span className="text-sm font-extrabold text-white group-hover:text-indigo-400 transition-all">
                          Audit #{reports.length - i}
                        </span>
                        <span className="text-[10px] text-gray-500 block uppercase font-bold tracking-wider">
                          {new Date(r.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-wider">Completion</span>
                          <span className="text-sm font-black text-white">
                            {r.completion_percentage < 0 ? 'N/A' : `${r.completion_percentage.toFixed(0)}%`}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-wider">Readiness</span>
                          <span className="text-sm font-black text-white">
                            {r.student_report.production_readiness_score.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Audit Run Jobs */}
            <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
              <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
                <History className="w-4 h-4 text-indigo-400" />
                Audit Runs
              </h3>

              {runs.length === 0 ? (
                <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider block py-6 text-center">No runs logged yet.</span>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {runs.map((run) => (
                    <div key={run.id} className="p-4 bg-white/5 border border-white/5 rounded-xl flex items-center justify-between">
                      <div className="space-y-1">
                        <span className="text-xs text-gray-400 font-bold block truncate max-w-xs uppercase tracking-wider">ID: {run.id}</span>
                        <span className="text-[10px] text-gray-500 block font-bold uppercase tracking-wider">
                          Triggered: {new Date(run.created_at).toLocaleString()}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider flex items-center gap-1 ${
                          run.status === 'completed' 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                            : run.status === 'failed'
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse'
                        }`}>
                          {run.status === 'completed' && <CheckCircle className="w-3.5 h-3.5" />}
                          {run.status === 'failed' && <XCircle className="w-3.5 h-3.5" />}
                          {run.status}
                        </span>
                        {run.status === 'failed' && (
                          <button
                            onClick={() => handleOpenDiagnostics(run.id)}
                            className="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md flex items-center gap-1 transition-all"
                            title="Diagnose Failure"
                          >
                            <ShieldAlert className="w-3 h-3" />
                            Diagnose
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Evidences Section */}
          <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
            <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
              <FileCode className="w-4 h-4 text-indigo-400" />
              Evidence Locker ({evidences.length})
            </h3>
            
            {evidences.length === 0 ? (
              <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider block py-6 text-center">No evidences collected.</span>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {evidences.map((e) => (
                  <div key={e.id} className="p-4 bg-white/5 border border-white/5 rounded-xl flex flex-col justify-between gap-3 text-xs">
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="px-2 py-0.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-extrabold uppercase rounded tracking-widest text-[9px]">
                          {e.evidence_type}
                        </span>
                        <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">
                          {new Date(e.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      
                      {e.file_path && (
                        <div className="text-gray-400 font-mono truncate mb-1.5" title={e.file_path}>
                          File: {e.file_path.split('/').pop()}
                        </div>
                      )}
                      {e.line_range && <span className="text-gray-500 font-mono block mb-1">Lines: {e.line_range}</span>}
                    </div>

                    {e.screenshot_url ? (
                      <div className="space-y-2">
                        <div 
                          className="aspect-video w-full rounded-lg overflow-hidden border border-white/5 bg-neutral-950 cursor-pointer"
                          onClick={() => setActiveLightboxImage(e.screenshot_url)}
                        >
                          <img 
                            src={e.screenshot_url} 
                            alt="Evidence Screenshot" 
                            className="w-full h-full object-cover hover:scale-105 transition-all duration-300"
                            onError={(el) => { el.target.style.display = 'none'; }}
                          />
                        </div>
                        <button 
                          onClick={() => setActiveLightboxImage(e.screenshot_url)}
                          className="w-full block py-2 bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/10 text-indigo-400 font-extrabold text-[10px] uppercase rounded-lg tracking-wider text-center transition-all"
                        >
                          View Fullsize
                        </button>
                      </div>
                    ) : e.details ? (
                      <div className="bg-[#0c0c0e] p-2 border border-white/5 rounded-lg text-[10px] text-gray-500 max-h-24 overflow-y-auto font-mono whitespace-pre-wrap">
                        {e.details}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {activeTab === 'security' && (
        /* RBAC Security Tab Content */
        <div className="space-y-8 animate-shimmer-off">
          {(!rbacStatus || !rbacStatus.rbac_enabled) ? (
            <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center justify-center gap-3">
              <ShieldAlert className="w-12 h-12 text-gray-600" />
              <h3 className="text-lg font-bold text-gray-300">RBAC Testing Not Enabled</h3>
              <p className="text-gray-500 text-sm max-w-sm">
                Enable RBAC multi-role crawling and input test credentials in the project configuration to analyze role boundaries and access levels.
              </p>
            </div>
          ) : rbacStatus.status === 'UNTESTED' ? (
            <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-12 h-12 text-indigo-500 animate-pulse" />
              <h3 className="text-lg font-bold text-gray-300">RBAC Audit Pending</h3>
              <p className="text-gray-500 text-sm max-w-sm">
                Run a new project audit to execute multi-role crawling and compile security scores.
              </p>
            </div>
          ) : (
            <>
              {/* Scores Grid */}
              {rbacScores && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className="glass-card rounded-2xl p-6 border border-emerald-500/20 text-center relative overflow-hidden">
                    <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-widest mb-2">Overall Score</span>
                    <span className="text-3xl font-black text-emerald-400">{rbacScores.overall_score.toFixed(1)}%</span>
                  </div>
                  <div className="glass-card rounded-2xl p-6 border border-white/5 text-center">
                    <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-widest mb-2">Authentication</span>
                    <span className="text-3xl font-black text-indigo-400">{rbacScores.auth_score.toFixed(1)}%</span>
                  </div>
                  <div className="glass-card rounded-2xl p-6 border border-white/5 text-center">
                    <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-widest mb-2">Authorization</span>
                    <span className="text-3xl font-black text-indigo-400">{rbacScores.authz_score.toFixed(1)}%</span>
                  </div>
                  <div className="glass-card rounded-2xl p-6 border border-white/5 text-center">
                    <span className="text-[10px] font-bold text-gray-400 block uppercase tracking-widest mb-2">Session Security</span>
                    <span className="text-3xl font-black text-indigo-400">{rbacScores.session_score.toFixed(1)}%</span>
                  </div>
                </div>
              )}

              {/* Coverage Matrix Table */}
              <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
                <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
                  Role Coverage Matrix
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-white/5 text-gray-500 font-bold uppercase tracking-widest text-[9px]">
                        <th className="py-3 px-4">Page Path</th>
                        <th className="py-3 px-4 text-center">Guest Access</th>
                        <th className="py-3 px-4 text-center">User Access</th>
                        <th className="py-3 px-4 text-center">Admin Access</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getGroupedCoverage().map((row, idx) => (
                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-all">
                          <td className="py-3 px-4 font-mono text-gray-300 truncate max-w-xs">{row.page}</td>
                          <td className="py-3 px-4 text-center">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              row.Guest === 'ALLOWED' ? 'bg-emerald-500/10 text-emerald-400' :
                              row.Guest === 'BLOCKED' ? 'bg-neutral-500/10 text-gray-400' :
                              row.Guest === 'PRIVILEGE_ESCALATION' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'text-gray-600'
                            }`}>
                              {row.Guest}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              row.User === 'ALLOWED' ? 'bg-emerald-500/10 text-emerald-400' :
                              row.User === 'BLOCKED' ? 'bg-neutral-500/10 text-gray-400' :
                              row.User === 'PRIVILEGE_ESCALATION' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'text-gray-600'
                            }`}>
                              {row.User}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              row.Admin === 'ALLOWED' ? 'bg-emerald-500/10 text-emerald-400' :
                              row.Admin === 'BLOCKED' ? 'bg-neutral-500/10 text-gray-400' :
                              row.Admin === 'PRIVILEGE_ESCALATION' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'text-gray-600'
                            }`}>
                              {row.Admin}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Privilege Escalations & Violations */}
              <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
                <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
                  Authorization Violations
                </h3>
                {rbacViolations.length === 0 ? (
                  <span className="text-emerald-400 text-xs font-semibold uppercase tracking-wider block py-4 text-center">
                    ✓ No administrative privilege isolation boundary breaches detected.
                  </span>
                ) : (
                  <div className="space-y-3">
                    {rbacViolations.map((v, i) => (
                      <div key={i} className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex flex-col gap-1.5 text-xs text-rose-400 font-semibold leading-relaxed">
                        <div className="flex items-center justify-between">
                          <span className="font-black uppercase tracking-wider text-[10px] bg-rose-500/20 px-2 py-0.5 rounded">
                            {v.severity.toUpperCase()} VIOLATION
                          </span>
                          <span className="font-mono text-gray-400">{v.target_route}</span>
                        </div>
                        <p className="text-gray-300 font-medium text-xs mt-1">{v.description}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Role Evidence Screenshots */}
              <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-6">
                <div className="flex items-center justify-between border-b border-white/5 pb-3">
                  <h3 className="text-sm font-black text-white uppercase tracking-wider">
                    Role Evidence Locker
                  </h3>
                  {/* Selector Buttons */}
                  <div className="flex bg-neutral-900 rounded-lg p-0.5 gap-1">
                    {['Guest', 'User', 'Admin'].map(role => (
                      <button
                        key={role}
                        onClick={() => setSelectedLockerRole(role)}
                        className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all ${
                          selectedLockerRole === role
                            ? 'bg-indigo-600 text-white shadow-md'
                            : 'text-gray-500 hover:text-white'
                        }`}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Screenshots Carousel/Grid */}
                {getRoleScreenshots().length === 0 ? (
                  <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider block py-6 text-center">
                    No screenshots compiled under {selectedLockerRole} context.
                  </span>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {getRoleScreenshots().map((scr, idx) => (
                      <div key={idx} className="p-3 bg-white/5 border border-white/5 rounded-xl space-y-2 text-xs">
                        <div 
                          className="aspect-video w-full rounded-lg overflow-hidden border border-white/5 bg-neutral-950 cursor-pointer"
                          onClick={() => setActiveLightboxImage(scr.url)}
                        >
                          <img
                            src={scr.url}
                            alt="Role Evidence"
                            className="w-full h-full object-cover hover:scale-105 transition-all duration-300"
                            onError={(el) => { el.target.style.display = 'none'; }}
                          />
                        </div>
                        <div className="text-[10px] text-gray-400 font-mono truncate" title={scr.page}>
                          Path: {scr.page}
                        </div>
                        <button
                          onClick={() => setActiveLightboxImage(scr.url)}
                          className="w-full block py-1.5 bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/10 text-indigo-400 font-extrabold text-[9px] uppercase rounded-lg tracking-wider text-center transition-all"
                        >
                          View Screenshot
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Authentication Tab */}
      {activeTab === 'auth' && (
        <div className="space-y-6">
          {/* Auth Status Overview */}
          <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-500" />
              Authentication Audit Status
            </h3>
            {authStatus ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-white/5 rounded-xl text-center">
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Status</span>
                  <span className={`text-sm font-extrabold ${
                    authStatus.status === 'SUCCESS' ? 'text-emerald-400' :
                    authStatus.status === 'PARTIAL' ? 'text-amber-400' :
                    authStatus.status === 'FAILED' ? 'text-rose-400' : 'text-gray-400'
                  }`}>{authStatus.status}</span>
                </div>
                <div className="p-4 bg-white/5 rounded-xl text-center">
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Auth Required</span>
                  <span className="text-sm font-extrabold text-white">{authStatus.auth_required ? 'Yes' : 'No'}</span>
                </div>
                <div className="p-4 bg-white/5 rounded-xl text-center">
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Credentials</span>
                  <span className={`text-sm font-extrabold ${authStatus.has_credentials ? 'text-emerald-400' : 'text-gray-400'}`}>
                    {authStatus.has_credentials ? 'Configured' : 'Not Set'}
                  </span>
                </div>
                <div className="p-4 bg-white/5 rounded-xl text-center">
                  <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Auth Score</span>
                  <span className="text-sm font-extrabold text-white">{authScores ? `${authScores.auth_score.toFixed(1)}%` : 'N/A'}</span>
                </div>
              </div>
            ) : (
              <p className="text-gray-500 text-xs">Authentication audit has not been configured for this project.</p>
            )}
          </div>

          {/* Protected Routes */}
          {authRoutes.length > 0 && (
            <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">Discovered Protected Routes</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="text-left py-2 px-3 text-gray-500 uppercase tracking-widest font-bold">Route</th>
                      <th className="text-left py-2 px-3 text-gray-500 uppercase tracking-widest font-bold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {authRoutes.map((r, i) => (
                      <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-all">
                        <td className="py-2 px-3 text-white font-mono">{r.route}</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            r.status === 'ACCESSED' ? 'bg-emerald-500/10 text-emerald-400' :
                            r.status === 'REDIRECTED' ? 'bg-amber-500/10 text-amber-400' :
                            'bg-rose-500/10 text-rose-400'
                          }`}>{r.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Auth Findings */}
          {authFindings.length > 0 && (
            <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">Authentication Quality Findings</h3>
              <div className="space-y-3">
                {authFindings.map((f, i) => (
                  <div key={i} className="p-4 bg-white/5 rounded-xl border border-white/5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{f.title}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        f.severity === 'critical' ? 'bg-rose-500/10 text-rose-400' :
                        f.severity === 'high' ? 'bg-orange-500/10 text-orange-400' :
                        f.severity === 'medium' ? 'bg-amber-500/10 text-amber-400' :
                        'bg-gray-500/10 text-gray-400'
                      }`}>{f.severity}</span>
                    </div>
                    <p className="text-gray-400 text-[11px] leading-relaxed">{f.description}</p>
                    <p className="text-indigo-400 text-[10px]"><strong>Recommendation:</strong> {f.recommendation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {(!authStatus || !authStatus.auth_required) && (
            <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center gap-3">
              <Lock className="w-10 h-10 text-gray-600" />
              <h3 className="text-base font-bold text-gray-300">Authentication Audit Not Enabled</h3>
              <p className="text-gray-500 text-xs max-w-md">
                Enable "Authentication Required" in the project settings and provide login credentials to audit pages behind authentication.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Failure Diagnostics Modal */}
      {selectedDiagnosticsRun && (
        <div 
          onClick={(e) => { if (e.target === e.currentTarget) { setSelectedDiagnosticsRun(null); setDiagnosticsData(null); } }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
        >
          <div className="bg-[#0b0c10] border border-white/10 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
            {/* Header */}
            <div className="p-6 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-rose-950/20 to-neutral-900">
              <div className="space-y-1">
                <h3 className="text-lg font-black text-rose-400 flex items-center gap-2 uppercase tracking-wider">
                  <ShieldAlert className="w-5 h-5 text-rose-500" />
                  Audit Failure Diagnostics
                </h3>
                <p className="text-xs text-gray-400 font-mono">Run ID: {selectedDiagnosticsRun}</p>
              </div>
              <button
                onClick={() => { setSelectedDiagnosticsRun(null); setDiagnosticsData(null); }}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-all text-xs font-bold uppercase tracking-wider"
              >
                Close
              </button>
            </div>

            {/* Content */}
            <div className="p-6 overflow-y-auto space-y-6">
              {loadingDiagnostics ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <Loader2 className="w-8 h-8 text-rose-500 animate-spin" />
                  <span className="text-xs text-gray-400 font-extrabold uppercase tracking-widest">Running dependency diagnostics...</span>
                </div>
              ) : diagnosticsData ? (
                <>
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-white/5 border border-white/5 rounded-xl space-y-1">
                      <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-wider block">Failed Stage</span>
                      <span className="text-sm font-black text-rose-400 uppercase tracking-widest">{diagnosticsData.failed_stage || 'Unknown'}</span>
                    </div>
                    <div className="p-4 bg-white/5 border border-white/5 rounded-xl space-y-1">
                      <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-wider block">Last Successful Step</span>
                      <span className="text-sm font-black text-emerald-400 uppercase tracking-widest">{diagnosticsData.last_successful_step || 'None'}</span>
                    </div>
                  </div>

                  {/* Failure Reason */}
                  <div className="p-4 bg-rose-950/20 border border-rose-500/20 rounded-xl space-y-2">
                    <span className="text-[10px] text-rose-400 font-extrabold uppercase tracking-wider block">Error Message</span>
                    <p className="text-xs font-bold text-rose-200 leading-relaxed">{diagnosticsData.failure_reason || 'No error message captured.'}</p>
                  </div>

                  {/* Stack Trace */}
                  {diagnosticsData.failure_stack_trace && (
                    <div className="space-y-2">
                      <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-wider block">Python Exception Stack Trace</span>
                      <pre className="p-4 bg-black/60 border border-white/5 rounded-xl text-[10px] font-mono text-gray-300 overflow-x-auto max-h-48 overflow-y-auto leading-relaxed whitespace-pre">
                        {diagnosticsData.failure_stack_trace}
                      </pre>
                    </div>
                  )}

                  {/* Dependencies Health */}
                  <div className="space-y-3">
                    <span className="text-[10px] text-gray-400 font-extrabold uppercase tracking-wider block">Environment Dependency Health Check</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {Object.entries(diagnosticsData.dependency_status || {}).map(([dep, status]) => {
                        const isHealthy = status === 'healthy';
                        const isDisabled = status === 'disabled';
                        return (
                          <div key={dep} className="p-3.5 bg-[#070709] border border-white/5 rounded-xl flex items-center justify-between">
                            <span className="text-xs font-bold text-gray-300 capitalize">{dep.replace('_', ' ')}</span>
                            <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider border ${
                              isHealthy 
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                                : isDisabled 
                                  ? 'bg-gray-500/10 text-gray-400 border-white/5' 
                                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}>
                              {status}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-6 text-xs text-gray-500 font-bold uppercase">Failed to retrieve diagnostics data.</div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-white/5 bg-[#070709] flex justify-end">
              <button
                onClick={() => { setSelectedDiagnosticsRun(null); setDiagnosticsData(null); }}
                className="bg-white/5 hover:bg-white/10 text-white font-bold text-xs uppercase tracking-widest px-5 py-2.5 rounded-xl border border-white/10 transition-all"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lightbox Modal */}
      {activeLightboxImage && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-fade-in"
          onClick={() => setActiveLightboxImage(null)}
        >
          <div className="relative max-w-5xl w-full max-h-[90vh] flex flex-col items-center">
            <button 
              onClick={() => setActiveLightboxImage(null)}
              className="absolute -top-10 right-0 text-white hover:text-indigo-400 text-3xl font-bold transition-all"
            >
              &times;
            </button>
            <img 
              src={activeLightboxImage} 
              alt="Evidence Fullsize" 
              className="max-w-full max-h-[80vh] object-contain rounded-lg border border-white/10 shadow-2xl" 
            />
          </div>
        </div>
      )}

    </div>
  );
}
