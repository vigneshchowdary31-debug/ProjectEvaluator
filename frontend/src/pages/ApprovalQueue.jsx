import React, { useState, useEffect } from 'react';
import { 
  CheckSquare, Square, ThumbsUp, ThumbsDown, AlertTriangle, 
  RefreshCw, Check, X, ClipboardList, Send, ExternalLink 
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';

export default function ApprovalQueue() {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  
  // Rejection dialog
  const [rejectingProject, setRejectingProject] = useState(null);
  const [rejectNotes, setRejectNotes] = useState('');
  const [submittingRejection, setSubmittingRejection] = useState(false);

  // Bulk action loading
  const [bulkLoading, setBulkLoading] = useState(false);
  const [itemLoading, setItemLoading] = useState({});

  useEffect(() => {
    fetchApprovals();
  }, []);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const res = await api.get(API_PATHS.APPROVALS);
      setApprovals(res.data);
      setSelectedIds(new Set());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (projectId) => {
    setItemLoading(prev => ({ ...prev, [projectId]: 'approve' }));
    try {
      await api.post(API_PATHS.APPROVAL_APPROVE(projectId));
      setApprovals(prev => prev.filter(a => a.project_id !== projectId));
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to approve project.');
    } finally {
      setItemLoading(prev => ({ ...prev, [projectId]: null }));
    }
  };

  const handleReject = async (e) => {
    e.preventDefault();
    if (!rejectingProject) return;
    setSubmittingRejection(true);
    try {
      const projectId = rejectingProject.project_id;
      await api.post(API_PATHS.APPROVAL_REJECT(projectId), { notes: rejectNotes });
      setApprovals(prev => prev.filter(a => a.project_id !== projectId));
      setRejectingProject(null);
      setRejectNotes('');
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reject project.');
    } finally {
      setSubmittingRejection(false);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Are you sure you want to bulk-approve ${selectedIds.size} selected projects?`)) return;
    
    setBulkLoading(true);
    try {
      const idsArray = Array.from(selectedIds);
      const res = await api.post(API_PATHS.APPROVAL_BULK_APPROVE, { project_ids: idsArray });
      alert(`Successfully approved ${res.data?.approved_count || 0} projects!`);
      fetchApprovals();
    } catch (err) {
      alert(err.response?.data?.detail || 'Bulk approval failed.');
    } finally {
      setBulkLoading(false);
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === approvals.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(approvals.map(a => a.project_id)));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Admin Approval Queue</h1>
          <p className="text-sm text-gray-400">Review student repository listings imported from sheets before launching parallel security audits.</p>
        </div>
        {approvals.length > 0 && (
          <button 
            onClick={handleBulkApprove}
            disabled={selectedIds.size === 0 || bulkLoading}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-800/40 disabled:text-gray-500 text-white rounded-lg font-medium text-sm transition-all"
          >
            {bulkLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
            Approve Selected ({selectedIds.size})
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      ) : approvals.length === 0 ? (
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-12 text-center max-w-xl mx-auto space-y-4">
          <div className="w-16 h-16 bg-emerald-500/10 rounded-2xl flex items-center justify-center mx-auto">
            <ClipboardList className="w-8 h-8 text-emerald-400" />
          </div>
          <h3 className="text-lg font-bold text-white">Queue is Empty</h3>
          <p className="text-sm text-gray-400">
            No projects are currently awaiting admin review. Imported repositories appear here if review is required before auditing.
          </p>
        </div>
      ) : (
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-[#16161c] border-b border-white/5 text-xs text-gray-400 uppercase font-semibold">
                <tr>
                  <th className="p-4 w-12">
                    <button 
                      onClick={toggleSelectAll}
                      className="text-gray-400 hover:text-white"
                    >
                      {selectedIds.size === approvals.length ? (
                        <CheckSquare className="w-5 h-5 text-indigo-400" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>
                  </th>
                  <th className="p-4">Project</th>
                  <th className="p-4">Student</th>
                  <th className="p-4">Company</th>
                  <th className="p-4">Details</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {approvals.map(approval => {
                  const project = approval.project || {};
                  const isPendingApprove = itemLoading[project.id] === 'approve';
                  const isPendingReject = itemLoading[project.id] === 'reject';
                  
                  return (
                    <tr key={approval.id} className="hover:bg-white/[0.01] transition-all">
                      <td className="p-4">
                        <button 
                          onClick={() => toggleSelect(project.id)}
                          className="text-gray-400 hover:text-white"
                        >
                          {selectedIds.has(project.id) ? (
                            <CheckSquare className="w-5 h-5 text-indigo-400" />
                          ) : (
                            <Square className="w-5 h-5" />
                          )}
                        </button>
                      </td>
                      <td className="p-4">
                        <div className="space-y-1">
                          <span className="font-bold text-white text-base">{project.name || 'Unnamed Project'}</span>
                          <div className="flex gap-2">
                            {project.repository_url && (
                              <a 
                                href={project.repository_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-gray-500 hover:text-indigo-400 flex items-center gap-0.5"
                              >
                                Github <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                            {project.prd_url && (
                              <a 
                                href={project.prd_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-gray-500 hover:text-indigo-400 flex items-center gap-0.5"
                              >
                                PRD <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-white font-medium">{project.student_name || 'N/A'}</td>
                      <td className="p-4 text-gray-400">{project.company_name || 'Independent'}</td>
                      <td className="p-4 text-xs text-gray-400">
                        <div className="space-y-0.5">
                          <div>Sync Source: <strong className="text-white">{project.source}</strong></div>
                          <div>Row Index: <strong className="text-white">{project.sheet_row_number || 'N/A'}</strong></div>
                          <div>Imported: <strong className="text-white">{new Date(approval.created_at).toLocaleDateString()}</strong></div>
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="inline-flex gap-2">
                          <button
                            disabled={isPendingApprove || isPendingReject}
                            onClick={() => handleApprove(project.id)}
                            className="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg transition-all flex items-center gap-1 text-xs font-semibold"
                            title="Approve & Queue Audit"
                          >
                            {isPendingApprove ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
                            Approve
                          </button>
                          <button
                            disabled={isPendingApprove || isPendingReject}
                            onClick={() => setRejectingProject(approval)}
                            className="p-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg transition-all flex items-center gap-1 text-xs font-semibold"
                            title="Reject Project"
                          >
                            <ThumbsDown className="w-4 h-4" />
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {rejectingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[#0f0f13] border border-white/10 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-white">Reject Project: {rejectingProject.project?.name}</h3>
              <button onClick={() => setRejectingProject(null)} className="text-gray-400 hover:text-white">&times;</button>
            </div>
            
            <form onSubmit={handleReject} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-400 uppercase">Rejection Notes / Feedback</label>
                <textarea 
                  required
                  rows={4}
                  value={rejectNotes} 
                  onChange={e => setRejectNotes(e.target.value)} 
                  placeholder="Provide reasons for rejection (e.g. Repository link is invalid or PRD document is incomplete)." 
                  className="w-full bg-[#16161c] border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button 
                  type="button" 
                  onClick={() => setRejectingProject(null)}
                  className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-sm transition-all"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={submittingRejection}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50 flex items-center gap-1"
                >
                  {submittingRejection ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4.5 h-4.5" />}
                  Submit Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
