import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, ShieldAlert, CheckCircle, AlertTriangle, XCircle, 
  BookOpen, Building2, Code, GraduationCap, Percent, HelpCircle,
  Printer, Download
} from 'lucide-react';
import api from '../api';

export default function ReportViewer() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('student'); // student | company

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await api.get(`/api/v1/reports/${id}`);
        setReport(res.data);
      } catch (err) {
        console.error(err);
        setError('Failed to retrieve the generated report details.');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [id]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
        <span className="text-gray-400 text-sm font-semibold tracking-wider">Formatting audit report...</span>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold leading-relaxed">
        {error || 'Report not found.'}
      </div>
    );
  }

  // Get active report schema
  const data = activeTab === 'student' ? report.student_report : report.company_report;

  // Determine health indicators
  const completion = report.completion_percentage;
  const readiness = data.production_readiness_score || 50.0;
  const classification = data.production_readiness_classification || 'Prototype';
  
  let verdict = 'Needs Significant Improvements';
  let verdictColor = 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  if (completion >= 90 && readiness >= 90) {
    verdict = 'Production Ready';
    verdictColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
  } else if (completion >= 70 && readiness >= 70) {
    verdict = 'Ready With Minor Fixes';
    verdictColor = 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20';
  } else if (completion < 40) {
    verdict = 'Incomplete';
    verdictColor = 'text-rose-400 bg-rose-500/10 border-rose-500/20 animate-pulse';
  }

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `Audit_Report_${report.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="space-y-8">
      {/* Back button & tab selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div className="flex items-center gap-3">
          <Link to={`/project/${report.project_id}`} className="p-2 border border-white/5 bg-white/5 text-gray-400 hover:text-white rounded-xl transition-all back-btn">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-black text-white uppercase tracking-wide">Audit Report Summary</h1>
            <p className="text-xs text-indigo-400 font-bold uppercase tracking-widest mt-0.5">Report ID: {report.id}</p>
          </div>
        </div>

        {/* Actions & Audience tab toggle */}
        <div className="flex flex-wrap items-center gap-3 self-start md:self-auto tab-controls">
          {/* Download Options */}
          <div className="bg-[#0f0f13] border border-white/5 p-1 rounded-xl flex items-center gap-1">
            <button 
              onClick={handlePrint}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-all"
              title="Print to PDF"
            >
              <Printer className="w-4 h-4" />
              PDF
            </button>
            <button 
              onClick={handleDownloadJson}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-all"
              title="Download JSON"
            >
              <Download className="w-4 h-4" />
              JSON
            </button>
          </div>

          {/* Audience tab toggle */}
          <div className="bg-[#0f0f13] border border-white/5 p-1 rounded-xl flex items-center gap-1">
            <button 
              onClick={() => setActiveTab('student')}
              className={`flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg transition-all ${
                activeTab === 'student' 
                  ? 'bg-indigo-600 text-white shadow-lg' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <GraduationCap className="w-4 h-4" />
              Student View
            </button>
            <button 
              onClick={() => setActiveTab('company')}
              className={`flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg transition-all ${
                activeTab === 'company' 
                  ? 'bg-indigo-600 text-white shadow-lg' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Building2 className="w-4 h-4" />
              Company View
            </button>
          </div>
        </div>
      </div>

      {/* Hero Scores Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Completion percentage gauge */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 flex items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Implementation Score</span>
            <span className="text-3xl font-black text-white">{completion.toFixed(1)}%</span>
            <span className="text-xs text-emerald-400 font-semibold block">PRD Coverage</span>
          </div>
          <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
            <Percent className="w-8 h-8" />
          </div>
        </div>

        {/* Production readiness score */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 flex items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Production Readiness</span>
            <span className="text-3xl font-black text-white">{readiness.toFixed(1)}%</span>
            <span className="text-xs text-indigo-400 font-bold block uppercase tracking-widest">{classification}</span>
          </div>
          <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
            <Code className="w-8 h-8" />
          </div>
        </div>

        {/* Verdict Badge */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 flex flex-col justify-center gap-1.5">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Final Verdict</span>
          <span className={`px-4 py-2 rounded-xl text-center text-xs font-black uppercase tracking-wider border ${verdictColor}`}>
            {verdict}
          </span>
        </div>
      </div>

      {/* Summary Narrative Section */}
      <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
        <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
          <BookOpen className="w-4 h-4 text-indigo-400" />
          {activeTab === 'student' ? 'Tutoring Notes & Guidance' : 'Executive Overview'}
        </h3>
        <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
          {activeTab === 'student' ? data.educational_notes : data.executive_summary}
        </p>
      </div>

      {/* Findings Breakdown Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Implemented features list */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            Implemented Features ({data.features_implemented?.length || 0})
          </h3>
          <ul className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
            {data.features_implemented?.map((f, i) => (
              <li key={i} className="flex items-start gap-2.5 p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl text-gray-300 text-xs leading-relaxed">
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* Missing features list */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <XCircle className="w-4 h-4 text-rose-400" />
            Missing Features / Gaps ({data.missing_features?.length || 0})
          </h3>
          <ul className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
            {data.missing_features?.map((f, i) => (
              <li key={i} className="flex items-start gap-2.5 p-3 bg-rose-500/5 border border-rose-500/10 rounded-xl text-gray-300 text-xs leading-relaxed">
                <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Code quality & Security reviews */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Security findings */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4 lg:col-span-1">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Security Assessment
          </h3>
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {data.security_findings?.length === 0 ? (
              <span className="text-gray-500 text-xs font-semibold block text-center py-6">No security alerts discovered.</span>
            ) : (
              data.security_findings?.map((f, i) => (
                <div key={i} className="p-3.5 bg-rose-500/5 border border-rose-500/10 rounded-xl text-xs text-gray-300 leading-relaxed">
                  {f}
                </div>
              ))
            )}
          </div>
        </div>

        {/* UI findings */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4 lg:col-span-1">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <GraduationCap className="w-4 h-4 text-indigo-400" />
            UI/UX Assessment
          </h3>
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {data.ui_findings?.length === 0 ? (
              <span className="text-gray-500 text-xs font-semibold block text-center py-6">No UI layout issues found.</span>
            ) : (
              data.ui_findings?.map((f, i) => (
                <div key={i} className="p-3.5 bg-indigo-500/5 border border-indigo-500/10 rounded-xl text-xs text-gray-300 leading-relaxed">
                  {f}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Code quality findings */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4 lg:col-span-1">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <Code className="w-4 h-4 text-purple-400" />
            Architecture & Quality
          </h3>
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {data.code_quality_findings?.length === 0 ? (
              <span className="text-gray-500 text-xs font-semibold block text-center py-6">No code quality problems detected.</span>
            ) : (
              data.code_quality_findings?.map((f, i) => (
                <div key={i} className="p-3.5 bg-purple-500/5 border border-purple-500/10 rounded-xl text-xs text-gray-300 leading-relaxed">
                  {f}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Actionable Recommendations List */}
      <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
        <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Priority Recommendations & Next Steps
        </h3>
        <ol className="space-y-3 pl-1">
          {data.recommendations?.map((r, i) => (
            <li key={i} className="flex gap-3 text-sm text-gray-300 leading-relaxed">
              <span className="w-6 h-6 rounded-full bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                {i + 1}
              </span>
              <span className="pt-0.5">{r}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
