import React, { useState, useEffect } from 'react';
import { 
  User, Key, ShieldCheck, CheckCircle2, XCircle, 
  Database, Sparkles, Github, HardDrive, RefreshCw, 
  Trash2, Loader2, AlertTriangle
} from 'lucide-react';
import api from '../api';

export default function Settings() {
  const [profile, setProfile] = useState({
    email: '',
    full_name: '',
    company_name: '',
    password: ''
  });
  const [status, setStatus] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    fetchProfile();
    fetchStatus();
  }, []);

  const fetchProfile = () => {
    api.get('/api/v1/auth/me')
      .then(res => {
        setProfile({
          email: res.data.email || '',
          full_name: res.data.full_name || '',
          company_name: res.data.company_name || '',
          password: ''
        });
      })
      .catch(err => {
        console.error(err);
        setErrorMsg('Failed to load profile details.');
      })
      .finally(() => setLoadingProfile(false));
  };

  const fetchStatus = () => {
    api.get('/api/v1/settings/status')
      .then(res => {
        setStatus(res.data);
      })
      .catch(err => {
        console.error(err);
      })
      .finally(() => setLoadingStatus(false));
  };

  const handleProfileChange = (e) => {
    setProfile({
      ...profile,
      [e.target.name]: e.target.value
    });
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMsg('');
    setErrorMsg('');

    const payload = {
      email: profile.email,
      full_name: profile.full_name,
      company_name: profile.company_name || null
    };

    if (profile.password) {
      payload.password = profile.password;
    }

    try {
      const res = await api.put('/api/v1/auth/me', payload);
      setSuccessMsg('Profile updated successfully!');
      setProfile(prev => ({
        ...prev,
        password: '',
        email: res.data.email,
        full_name: res.data.full_name,
        company_name: res.data.company_name || ''
      }));
    } catch (err) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setErrorMsg(err.response.data.detail);
      } else {
        setErrorMsg('Failed to update profile details.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeAll = async () => {
    if (!window.confirm('Are you sure you want to revoke all active sessions? You will need to log back in.')) {
      return;
    }

    setRevoking(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      await api.post('/api/v1/auth/logout-all');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.reload();
    } catch (err) {
      console.error(err);
      setErrorMsg('Failed to revoke all sessions.');
      setRevoking(false);
    }
  };

  if (loadingProfile || loadingStatus) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
        <span className="text-gray-400 text-sm font-semibold tracking-wider uppercase">Loading platform configuration...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-black text-white tracking-wide uppercase flex items-center gap-3">
          <Database className="w-8 h-8 text-indigo-500" />
          System Settings & Credentials
        </h1>
        <p className="text-gray-400 text-xs mt-1.5 uppercase tracking-wider">
          Configure dev settings, inspect active service integrations, and update user authentication profiles.
        </p>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Profile Form */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card p-6 rounded-2xl border border-white/5 space-y-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <User className="w-5 h-5 text-indigo-400" />
              Update Profile Details
            </h2>

            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-gray-500 uppercase tracking-wider">Full Name</label>
                  <input
                    type="text"
                    name="full_name"
                    value={profile.full_name}
                    onChange={handleProfileChange}
                    required
                    className="w-full bg-[#0f0f13] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-all"
                    placeholder="John Doe"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-gray-500 uppercase tracking-wider">Email Address</label>
                  <input
                    type="email"
                    name="email"
                    value={profile.email}
                    onChange={handleProfileChange}
                    required
                    className="w-full bg-[#0f0f13] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-all"
                    placeholder="email@example.com"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-gray-500 uppercase tracking-wider">Company / Org Name</label>
                  <input
                    type="text"
                    name="company_name"
                    value={profile.company_name}
                    onChange={handleProfileChange}
                    className="w-full bg-[#0f0f13] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-all"
                    placeholder="Acme Corp"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-gray-500 uppercase tracking-wider">New Password (Leave Blank to Keep Same)</label>
                  <input
                    type="password"
                    name="password"
                    value={profile.password}
                    onChange={handleProfileChange}
                    className="w-full bg-[#0f0f13] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-all"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-widest px-6 py-3 rounded-xl transition-all disabled:opacity-50"
                >
                  {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Profile Changes
                </button>
              </div>
            </form>
          </div>

          {/* Session controls */}
          <div className="glass-card p-6 rounded-2xl border border-white/5 space-y-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Key className="w-5 h-5 text-rose-400" />
              Session & Revocation Management
            </h2>
            <p className="text-xs text-gray-400 leading-relaxed">
              If you suspect session hijacking, or need to clear older login refresh tokens, you can invalidate all active sessions immediately. This forces all devices (including this one) to log in again.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 bg-rose-500/5 border border-rose-500/10 rounded-xl">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-black text-white uppercase tracking-wider">Revoke All Device Tokens</h4>
                  <p className="text-[11px] text-gray-400 mt-1">Clears out rotated database refresh tokens globally.</p>
                </div>
              </div>
              <button
                onClick={handleRevokeAll}
                disabled={revoking}
                className="w-full sm:w-auto flex items-center justify-center gap-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 border border-rose-500/20 font-bold text-xs uppercase tracking-widest px-5 py-3 rounded-xl transition-all"
              >
                {revoking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Revoke All Sessions
              </button>
            </div>
          </div>
        </div>

        {/* Integration Status Diagnostics */}
        <div className="space-y-6">
          <div className="glass-card p-6 rounded-2xl border border-white/5 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-400" />
                Integrations Diagnostics
              </h2>
              <button
                onClick={() => { setLoadingStatus(true); fetchStatus(); }}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-all"
                title="Refresh Status"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            {status && (
              <div className="space-y-4">
                
                {/* Gemini Status */}
                <div className="p-4 bg-[#0a0a0d] border border-white/5 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-purple-400" />
                      Gemini AI API
                    </span>
                    {status.gemini.configured ? (
                      <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Connected
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Unconfigured
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-gray-400">
                    Model: <span className="text-indigo-400 font-mono">{status.gemini.model}</span>
                  </div>
                </div>

                {/* GitHub Status */}
                <div className="p-4 bg-[#0a0a0d] border border-white/5 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-2">
                      <Github className="w-4 h-4 text-slate-300" />
                      GitHub Access Token
                    </span>
                    {status.github.configured ? (
                      <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Active
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Anonymous Mode
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-gray-500 leading-normal">
                    {status.github.configured 
                      ? 'Authenticated. Higher rate-limits and access to private repos enabled.' 
                      : 'Anonymous access has lower API rate limits. Configure GITHUB_TOKEN to bypass limits.'}
                  </p>
                </div>

                {/* Google Drive Status */}
                <div className="p-4 bg-[#0a0a0d] border border-white/5 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-2">
                      <HardDrive className="w-4 h-4 text-amber-500" />
                      Google Drive Backups
                    </span>
                    {status.google_drive.configured ? (
                      <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Initialized
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 font-extrabold text-[9px] uppercase tracking-wider rounded-md">
                        Disabled
                      </span>
                    )}
                  </div>
                  <div className="space-y-1.5 text-[11px] text-gray-400">
                    <div>
                      Folder ID: <span className="text-amber-500 font-mono text-[10px] break-all">{status.google_drive.folder_id}</span>
                    </div>
                    {status.google_drive.error && (
                      <div className="text-[10px] text-rose-400/90 italic mt-1 leading-normal">
                        Error: {status.google_drive.error}
                      </div>
                    )}
                  </div>
                </div>

                {/* Application Metadata */}
                <div className="p-4 bg-[#0a0a0d]/60 border border-white/5 rounded-xl space-y-1.5 text-[11px] text-gray-500">
                  <div className="flex justify-between">
                    <span>App Name:</span>
                    <span className="font-bold text-gray-300">{status.app.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>App Version:</span>
                    <span className="font-bold text-gray-300">{status.app.version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Environment Debug:</span>
                    <span className="font-mono text-gray-300">{status.app.debug ? 'Enabled' : 'Disabled'}</span>
                  </div>
                </div>

              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
