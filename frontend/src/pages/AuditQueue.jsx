import React, { useState, useEffect } from 'react';
import { 
  Play, Pause, RefreshCw, AlertTriangle, CheckCircle2, 
  Clock, Ban, Server, KanbanSquare, HelpCircle, Activity 
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';

export default function AuditQueue() {
  const [queueItems, setQueueItems] = useState([]);
  const [statusCounts, setStatusCounts] = useState({});
  const [workerLimit, setWorkerLimit] = useState(0);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState(null);

  useEffect(() => {
    fetchQueueData();
    // Poll queue status every 8 seconds for real-time monitoring
    const interval = setInterval(fetchQueueData, 8000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueueData = async () => {
    try {
      const [listRes, statusRes] = await Promise.all([
        api.get(API_PATHS.QUEUE),
        api.get(API_PATHS.QUEUE_STATUS)
      ]);
      setQueueItems(listRes.data);
      setStatusCounts(statusRes.data.counts || {});
      setWorkerLimit(statusRes.data.active_worker_threads || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (id) => {
    if (!window.confirm('Are you sure you want to cancel this queued audit task?')) return;
    setCancellingId(id);
    try {
      await api.post(API_PATHS.QUEUE_CANCEL(id));
      fetchQueueData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to cancel audit task.');
    } finally {
      setCancellingId(null);
    }
  };

  const getStatusBadge = (status) => {
    switch (status.toLowerCase()) {
      case 'queued':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Clock className="w-3.5 h-3.5" /> QUEUED
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
            <Activity className="w-3.5 h-3.5 animate-spin" /> RUNNING
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" /> COMPLETED
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="w-3.5 h-3.5" /> FAILED
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/20">
            <Ban className="w-3.5 h-3.5" /> CANCELLED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-500/10 text-gray-400 border border-gray-500/20">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Parallel Audit Queue Monitor</h1>
          <p className="text-sm text-gray-400">Track database-backed audit jobs, background worker allocations, and pipeline statuses.</p>
        </div>
        <button 
          onClick={fetchQueueData}
          className="p-2 bg-[#0f0f13] border border-white/5 rounded-lg text-gray-400 hover:text-white transition-all"
          title="Refresh Queue Data"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* Stats Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4 space-y-1">
          <div className="text-xs font-semibold text-gray-500 uppercase">Concurrency Limit</div>
          <div className="text-2xl font-extrabold text-indigo-400 flex items-center gap-1">
            <Server className="w-5 h-5" /> {workerLimit} Workers
          </div>
        </div>
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4 space-y-1">
          <div className="text-xs font-semibold text-gray-500 uppercase">Tasks Running</div>
          <div className="text-2xl font-extrabold text-amber-400">{statusCounts.running || 0}</div>
        </div>
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4 space-y-1">
          <div className="text-xs font-semibold text-gray-500 uppercase">Tasks Queued</div>
          <div className="text-2xl font-extrabold text-blue-400">{statusCounts.queued || 0}</div>
        </div>
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4 space-y-1">
          <div className="text-xs font-semibold text-gray-500 uppercase">Completed</div>
          <div className="text-2xl font-extrabold text-emerald-400">{statusCounts.completed || 0}</div>
        </div>
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4 space-y-1">
          <div className="text-xs font-semibold text-gray-500 uppercase">Failed / Errored</div>
          <div className="text-2xl font-extrabold text-rose-400">{statusCounts.failed || 0}</div>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      ) : queueItems.length === 0 ? (
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-12 text-center max-w-xl mx-auto space-y-4">
          <div className="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center mx-auto">
            <KanbanSquare className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-bold text-white">Queue Empty</h3>
          <p className="text-sm text-gray-400">
            No audits have been executed or queued recently. Approve projects from the Admin Approval page to start auditing.
          </p>
        </div>
      ) : (
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-[#16161c] border-b border-white/5 text-xs text-gray-400 uppercase font-semibold">
                <tr>
                  <th className="p-4">Project Name</th>
                  <th className="p-4">Queue Status</th>
                  <th className="p-4">Trigger / Priority</th>
                  <th className="p-4">Timestamps</th>
                  <th className="p-4">Failure Reason</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {queueItems.map(item => {
                  const project = item.project || {};
                  const isQueued = item.status.toLowerCase() === 'queued';
                  
                  return (
                    <tr key={item.id} className="hover:bg-white/[0.01] transition-all">
                      <td className="p-4">
                        <div className="space-y-0.5">
                          <span className="font-bold text-white text-base">{project.name || 'Unnamed Project'}</span>
                          <div className="text-xs text-gray-500">Student: {project.student_name || 'N/A'}</div>
                        </div>
                      </td>
                      <td className="p-4">{getStatusBadge(item.status)}</td>
                      <td className="p-4">
                        <div className="space-y-0.5">
                          <div className="text-xs text-gray-300 uppercase">{item.trigger_reason.replace('_', ' ')}</div>
                          <div className="text-[10px] text-gray-500 font-semibold">Priority: {item.priority}/10</div>
                        </div>
                      </td>
                      <td className="p-4 text-xs text-gray-400">
                        <div className="space-y-0.5">
                          <div>Queued: {new Date(item.created_at).toLocaleString()}</div>
                          {item.started_at && <div>Started: {new Date(item.started_at).toLocaleString()}</div>}
                          {item.completed_at && <div>Finished: {new Date(item.completed_at).toLocaleString()}</div>}
                        </div>
                      </td>
                      <td className="p-4 max-w-xs truncate text-xs text-rose-400 font-medium" title={item.failure_reason}>
                        {item.failure_reason || '-'}
                      </td>
                      <td className="p-4 text-right">
                        {isQueued && (
                          <button
                            disabled={cancellingId === item.id}
                            onClick={() => handleCancel(item.id)}
                            className="p-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg transition-all text-xs font-semibold flex items-center gap-1 ml-auto"
                            title="Cancel queued run"
                          >
                            {cancellingId === item.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
