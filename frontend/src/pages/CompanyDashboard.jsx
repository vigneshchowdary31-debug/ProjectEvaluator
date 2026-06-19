import React, { useState, useEffect } from 'react';
import { Landmark, AlertCircle, ShieldAlert, CheckCircle, Heart } from 'lucide-react';
import api from '../api';

export default function CompanyDashboard() {
  const [companyStats, setCompanyStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/v1/analytics/company')
      .then(res => setCompanyStats(res.data))
      .catch(err => {
        console.error(err);
        setError('Could not retrieve company dashboard aggregates.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
        <span className="text-gray-400 text-sm font-semibold tracking-wider">Compiling corporate portfolios...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold leading-relaxed">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-black text-white tracking-wide uppercase flex items-center gap-3">
          <Landmark className="w-8 h-8 text-indigo-500" />
          Company Portfolios
        </h1>
        <p className="text-gray-400 text-xs mt-1.5 uppercase tracking-wider">
          Enterprise risk assessments, health scores, and project delivery indexes grouped by organization.
        </p>
      </div>

      {/* Grid of companies */}
      {companyStats.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center justify-center gap-3">
          <Landmark className="w-12 h-12 text-gray-600" />
          <h3 className="text-lg font-bold text-gray-300">No Enterprise Records</h3>
          <p className="text-gray-500 text-sm max-w-sm">
            Configure student accounts with 'Company Name' fields in registration/settings to compile corporate group stats.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {companyStats.map((c, idx) => {
            const lowRisk = c.risk_level === 'Low';
            const medRisk = c.risk_level === 'Medium';
            return (
              <div key={idx} className="glass-card rounded-2xl p-6 border border-white/5 flex flex-col justify-between gap-6 relative overflow-hidden group">
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-lg font-black text-white tracking-wide uppercase">{c.company_name}</h3>
                    
                    {/* Risk Badge */}
                    <span className={`px-2.5 py-0.5 rounded-lg text-[9px] font-black uppercase tracking-widest border ${
                      lowRisk 
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : medRisk
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/20 animate-pulse'
                    }`}>
                      {c.risk_level} Risk Profile
                    </span>
                  </div>

                  <hr className="border-white/5" />

                  {/* Matrix */}
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Projects</span>
                      <span className="text-lg font-black text-white">{c.projects_count}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Avg Progress</span>
                      <span className="text-lg font-black text-emerald-400">{c.average_completion.toFixed(0)}%</span>
                    </div>
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Avg Maturity</span>
                      <span className="text-lg font-black text-indigo-400">{c.average_readiness.toFixed(0)}%</span>
                    </div>
                  </div>

                  {/* Health rating progress */}
                  <div className="space-y-2 pt-2">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-gray-400 flex items-center gap-1.5">
                        <Heart className="w-3.5 h-3.5 text-rose-500" />
                        Portfolio Health Index
                      </span>
                      <span className="text-white">{c.average_health_score.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${
                          c.average_health_score >= 80 
                            ? 'bg-emerald-500' 
                            : c.average_health_score >= 50
                              ? 'bg-amber-500'
                              : 'bg-rose-500'
                        }`}
                        style={{ width: `${c.average_health_score}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[10px] text-gray-500 font-bold uppercase tracking-wider">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Total logged vulnerabilities: {c.total_vulnerabilities}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
