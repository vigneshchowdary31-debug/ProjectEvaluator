import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';
import { BarChart3, TrendingUp, AlertTriangle, ShieldAlert, Cpu } from 'lucide-react';
import api from '../api';

export default function Analytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/v1/analytics/summary')
      .then(res => setStats(res.data))
      .catch(err => {
        console.error(err);
        setError('Could not retrieve analytics details.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
        <span className="text-gray-400 text-sm font-semibold tracking-wider">Compiling platform statistics...</span>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold leading-relaxed">
        {error || 'Analytics not available.'}
      </div>
    );
  }

  // Format security counts for BarChart
  const securityData = [
    { name: 'Critical', count: stats.security_findings_breakdown.critical, fill: '#ef4444' },
    { name: 'High', count: stats.security_findings_breakdown.high, fill: '#f97316' },
    { name: 'Medium', count: stats.security_findings_breakdown.medium, fill: '#f59e0b' },
    { name: 'Low', count: stats.security_findings_breakdown.low, fill: '#10b981' },
  ];

  // Format trend data
  const trendData = stats.projects_trend.map(p => ({
    name: p.name.substring(0, 12) + '...',
    score: p.completion_percentage
  }));

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-black text-white tracking-wide uppercase flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-indigo-500" />
          Analytics Dashboard
        </h1>
        <p className="text-gray-400 text-xs mt-1.5 uppercase tracking-wider">
          Aggregated codebase indices, vulnerability counts, and project completion trends.
        </p>
      </div>

      {/* Stats Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card rounded-2xl p-6 border border-white/5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Total Projects</span>
            <span className="text-3xl font-black text-white mt-1 block">{stats.total_projects}</span>
          </div>
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
            <Cpu className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-card rounded-2xl p-6 border border-white/5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Audit Runs Logged</span>
            <span className="text-3xl font-black text-white mt-1 block">{stats.total_audit_runs}</span>
          </div>
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        <div className="glass-card rounded-2xl p-6 border border-white/5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest block">Avg Completion Score</span>
            <span className="text-3xl font-black text-white mt-1 block">{stats.average_completion_percentage}%</span>
          </div>
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
            <Percent className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Visual Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Project Completion Trend Chart */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <TrendingUp className="w-4 h-4 text-indigo-400" />
            Project Completion Trend
          </h3>
          <div className="h-72 w-full">
            {trendData.length === 0 ? (
              <span className="text-gray-500 text-xs font-semibold block text-center py-24">No data points.</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" stroke="#6b7280" style={{ fontSize: 10 }} />
                  <YAxis stroke="#6b7280" domain={[0, 100]} style={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#121218', borderColor: '#27272a' }} />
                  <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Security Findings Summary Chart */}
        <div className="glass-card rounded-2xl p-6 border border-white/5 space-y-4">
          <h3 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2 border-b border-white/5 pb-3">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Security Findings Breakdown
          </h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={securityData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#6b7280" style={{ fontSize: 10 }} />
                <YAxis stroke="#6b7280" style={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: '#121218', borderColor: '#27272a' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {securityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
const Percent = ({ className }) => (
  <span className={`font-black text-lg ${className}`}>%</span>
);
