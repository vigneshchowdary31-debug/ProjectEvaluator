import React, { useState, useEffect } from 'react';
import { 
  FileSpreadsheet, Plus, RefreshCw, Trash2, CheckCircle2, 
  AlertTriangle, Play, HelpCircle, History, ListRestart, ExternalLink 
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';

export default function SheetsManagement() {
  const [sheets, setSheets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [selectedSheet, setSelectedSheet] = useState(null);
  const [syncLogs, setSyncLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Form State
  const [sheetName, setSheetName] = useState('');
  const [sheetUrl, setSheetUrl] = useState('');
  const [syncFreq, setSyncFreq] = useState('manual');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Individual row action loading states
  const [actionLoading, setActionLoading] = useState({});

  useEffect(() => {
    fetchSheets();
  }, []);

  // Handle Escape key to close modals
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setShowAddModal(false);
        setShowLogsModal(false);
      }
    };
    if (showAddModal || showLogsModal) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showAddModal, showLogsModal]);

  const fetchSheets = async () => {
    setLoading(true);
    try {
      const res = await api.get(API_PATHS.SHEETS);
      setSheets(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      await api.post(API_PATHS.SHEETS_CONNECT, {
        sheet_name: sheetName,
        sheet_url: sheetUrl,
        sync_frequency: syncFreq
      });
      setSuccessMsg('Successfully connected Google Sheet!');
      setSheetName('');
      setSheetUrl('');
      setSyncFreq('manual');
      setTimeout(() => {
        setShowAddModal(false);
        setSuccessMsg('');
        fetchSheets();
      }, 1500);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to connect Google Sheet. Verify the URL and service account access.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestConnection = async (id) => {
    setActionLoading(prev => ({ ...prev, [id + '_test']: true }));
    try {
      const res = await api.post(API_PATHS.SHEETS_TEST(id));
      alert(res.data?.message || 'Connection test successful!');
      fetchSheets();
    } catch (err) {
      alert(err.response?.data?.detail || 'Connection test failed.');
    } finally {
      setActionLoading(prev => ({ ...prev, [id + '_test']: false }));
    }
  };

  const handleSync = async (id) => {
    setActionLoading(prev => ({ ...prev, [id + '_sync']: true }));
    try {
      const res = await api.post(API_PATHS.SHEETS_SYNC(id));
      alert(res.data?.message || 'Sync job triggered in background!');
      fetchSheets();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to trigger sync job.');
    } finally {
      setActionLoading(prev => ({ ...prev, [id + '_sync']: false }));
    }
  };

  const handleDisconnect = async (id) => {
    if (!window.confirm('Are you sure you want to disconnect this Google Sheet connection?')) return;
    setActionLoading(prev => ({ ...prev, [id + '_del']: true }));
    try {
      await api.post(API_PATHS.SHEETS_DISCONNECT(id));
      fetchSheets();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to disconnect sheet.');
    } finally {
      setActionLoading(prev => ({ ...prev, [id + '_del']: false }));
    }
  };

  const handleOpenLogs = async (sheet) => {
    setSelectedSheet(sheet);
    setShowLogsModal(true);
    setLogsLoading(true);
    try {
      const res = await api.get(API_PATHS.SHEETS_LOGS(sheet.id));
      setSyncLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Google Sheets Intake Connection</h1>
          <p className="text-sm text-gray-400">Automate project setup and sync student data from spreadsheet templates.</p>
        </div>
        <div className="flex items-center gap-3">
          <a 
            href="/project_intake_template.csv" 
            download="project_intake_template.csv"
            className="flex items-center gap-2 px-4 py-2 bg-[#16161c] border border-white/5 hover:bg-white/10 text-gray-300 rounded-lg font-medium text-sm transition-all"
          >
            Download CSV Template
          </a>
          <button 
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition-all shadow-lg shadow-indigo-600/10"
          >
            <Plus className="w-4 h-4" />
            Connect Sheet
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      ) : sheets.length === 0 ? (
        <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-12 text-center max-w-xl mx-auto space-y-4">
          <div className="w-16 h-16 bg-indigo-500/10 rounded-2xl flex items-center justify-center mx-auto">
            <FileSpreadsheet className="w-8 h-8 text-indigo-400" />
          </div>
          <h3 className="text-lg font-bold text-white">No Connected Sheets</h3>
          <p className="text-sm text-gray-400">
            Connect a Google Sheet containing student project credentials to eliminate manual input. Ensure the sheet is shared with the platform's service account email.
          </p>
          <button 
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition-all"
          >
            Connect First Sheet
          </button>
        </div>
      ) : (
        <div className="grid gap-6">
          {sheets.map(sheet => (
            <div 
              key={sheet.id}
              className="bg-[#0f0f13] border border-white/5 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 hover:border-white/10 transition-all"
            >
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-emerald-500/10 rounded-xl flex items-center justify-center">
                    <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-lg flex items-center gap-2">
                      {sheet.sheet_name}
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${
                        sheet.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {sheet.status}
                      </span>
                    </h3>
                    <a 
                      href={sheet.sheet_url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="text-xs text-gray-500 hover:text-indigo-400 flex items-center gap-1 mt-0.5"
                    >
                      View Google Sheet <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-1 text-xs text-gray-400 pt-2">
                  <div>Rows Detected: <strong className="text-white">{sheet.row_count}</strong></div>
                  <div>Sync Frequency: <strong className="text-white uppercase">{sheet.sync_frequency}</strong></div>
                  <div>Last Sync: <strong className="text-white">{sheet.last_sync_at ? new Date(sheet.last_sync_at).toLocaleString() : 'Never'}</strong></div>
                  <div>Last Status: <span className={`font-semibold uppercase ${sheet.last_sync_status === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>{sheet.last_sync_status || 'N/A'}</span></div>
                </div>
                {sheet.last_sync_error && (
                  <p className="text-xs text-rose-400 flex items-center gap-1 mt-1">
                    <AlertTriangle className="w-3 h-3" /> Error: {sheet.last_sync_error}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap gap-2 w-full md:w-auto">
                <button
                  disabled={actionLoading[sheet.id + '_test']}
                  onClick={() => handleTestConnection(sheet.id)}
                  className="flex-1 md:flex-initial px-3 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                >
                  Test Connection
                </button>
                <button
                  disabled={actionLoading[sheet.id + '_sync']}
                  onClick={() => handleSync(sheet.id)}
                  className="flex-1 md:flex-initial px-3 py-2 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 rounded-lg text-xs font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                >
                  <Play className="w-3 h-3" /> Sync Now
                </button>
                <button
                  onClick={() => handleOpenLogs(sheet)}
                  className="flex-1 md:flex-initial px-3 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1"
                >
                  <History className="w-3 h-3" /> History
                </button>
                <button
                  disabled={actionLoading[sheet.id + '_del']}
                  onClick={() => handleDisconnect(sheet.id)}
                  className="px-3 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <div 
          onClick={(e) => { if (e.target === e.currentTarget) setShowAddModal(false); }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        >
          <div className="bg-[#0f0f13] border border-white/10 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-white">Connect New Google Sheet</h3>
              <button onClick={() => setShowAddModal(false)} className="text-gray-400 hover:text-white">&times;</button>
            </div>
            
            <form onSubmit={handleConnect} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-400 uppercase">Sheet Display Name</label>
                <input 
                  type="text" 
                  required
                  value={sheetName} 
                  onChange={e => setSheetName(e.target.value)} 
                  placeholder="e.g. Cohort 5 Intake" 
                  className="w-full bg-[#16161c] border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-400 uppercase">Google Sheet URL</label>
                <input 
                  type="url" 
                  required
                  value={sheetUrl} 
                  onChange={e => setSheetUrl(e.target.value)} 
                  placeholder="https://docs.google.com/spreadsheets/d/..." 
                  className="w-full bg-[#16161c] border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <p className="text-[10px] text-gray-500">
                  Note: Share your sheet as "Viewer" or "Editor" with the credentials client email before connecting.
                </p>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-400 uppercase">Sync Frequency</label>
                <select 
                  value={syncFreq} 
                  onChange={e => setSyncFreq(e.target.value)} 
                  className="w-full bg-[#16161c] border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="manual">Manual Pull Only</option>
                  <option value="hourly">Hourly Auto-Sync</option>
                  <option value="daily">Daily Auto-Sync</option>
                </select>
              </div>

              {errorMsg && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {successMsg && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{successMsg}</span>
                </div>
              )}

              <div className="flex gap-2 justify-end pt-2">
                <button 
                  type="button" 
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-sm transition-all"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={submitting}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50"
                >
                  {submitting ? 'Connecting...' : 'Connect Sheet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {showLogsModal && (
        <div 
          onClick={(e) => { if (e.target === e.currentTarget) setShowLogsModal(false); }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        >
          <div className="bg-[#0f0f13] border border-white/10 rounded-2xl max-w-4xl w-full p-6 space-y-4 shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex justify-between items-center shrink-0">
              <h3 className="text-lg font-bold text-white">Sync Execution Logs - {selectedSheet?.sheet_name}</h3>
              <button onClick={() => setShowLogsModal(false)} className="text-gray-400 hover:text-white">&times;</button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {logsLoading ? (
                <div className="flex justify-center items-center py-20">
                  <RefreshCw className="w-6 h-6 text-indigo-500 animate-spin" />
                </div>
              ) : syncLogs.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">No sync runs recorded for this sheet connection yet.</p>
              ) : (
                <div className="space-y-4">
                  {syncLogs.map(log => (
                    <div 
                      key={log.id}
                      className="p-4 rounded-xl border border-white/5 bg-[#16161c] space-y-2 text-xs"
                    >
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            log.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                          }`}>
                            {log.status}
                          </span>
                          <span className="text-gray-400">Triggered: {new Date(log.started_at).toLocaleString()}</span>
                        </div>
                        <span className="text-gray-500">Duration: {log.completed_at ? `${Math.round((new Date(log.completed_at) - new Date(log.started_at)) / 1000)}s` : 'running'}</span>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-gray-400 bg-black/10 p-2.5 rounded-lg">
                        <div>Imported: <strong className="text-emerald-400 font-bold">{log.imported_count}</strong></div>
                        <div>Updated: <strong className="text-indigo-400 font-bold">{log.updated_count}</strong></div>
                        <div>Skipped: <strong className="text-white">{log.skipped_count}</strong></div>
                        <div>Errors: <strong className="text-rose-400 font-bold">{log.error_count}</strong></div>
                      </div>

                      {log.errors && log.errors.length > 0 && (
                        <div className="space-y-1 bg-rose-500/5 p-3 rounded-lg border border-rose-500/10">
                          <h4 className="font-semibold text-rose-400 flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" /> Sync Anomalies/Errors
                          </h4>
                          <div className="max-h-28 overflow-y-auto space-y-1 text-gray-400">
                            {log.errors.map((err, i) => (
                              <div key={i} className="border-b border-white/5 pb-1 last:border-0">
                                Row {err.row || 'global'}: {err.error || err.global_error}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="shrink-0 flex justify-end pt-2">
              <button 
                onClick={() => setShowLogsModal(false)}
                className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-sm transition-all"
              >
                Close Logs
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
