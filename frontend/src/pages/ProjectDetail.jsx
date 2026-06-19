import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  FolderKanban, Play, Github, FileText, Globe, RefreshCw, 
  Terminal, History, ShieldAlert, Award, FileCode, CheckCircle, XCircle 
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
  
  // Audit Execution & WS console state
  const [auditing, setAuditing] = useState(false);
  const [activeRunId, setActiveRunId] = useState('');
  const [wsLogs, setWsLogs] = useState([]);
  const [wsProgress, setWsProgress] = useState(0);
  const [currentStepName, setCurrentStepName] = useState('');
  const consoleEndRef = useRef(null);

  const fetchData = async () => {
    try {
      const projRes = await api.get(API_PATHS.PROJECT_DETAIL(id));
      setProject(projRes.data);
      
      // We pass page_size as a query param still
      const runsRes = await api.get(`${API_PATHS.PROJECT_RUNS(id)}?page_size=20`);
      setRuns(runsRes.data.items);
      
      const evidenceRes = await api.get(API_PATHS.EVIDENCE_PROJECT(id));
      setEvidences(evidenceRes.data);

      const reportsRes = await api.get(API_PATHS.PROJECT_REPORTS(id));
      setReports(reportsRes.data);
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
                  <span className="text-2xl font-black text-indigo-400">{reports[0].completion_percentage.toFixed(1)}%</span>
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
                      <span className="text-sm font-black text-white">{r.completion_percentage.toFixed(0)}%</span>
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
                  <a 
                    href={e.screenshot_url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="w-full py-2 bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/10 text-indigo-400 font-extrabold text-[10px] uppercase rounded-lg tracking-wider text-center transition-all"
                  >
                    View Screenshot
                  </a>
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
    </div>
  );
}
