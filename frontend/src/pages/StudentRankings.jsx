import React, { useState, useEffect } from 'react';
import { Trophy, Medal, Search, TrendingUp, ShieldAlert, Percent } from 'lucide-react';
import api from '../api';

export default function StudentRankings() {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    api.get('/api/v1/analytics/rankings/students')
      .then(res => setRankings(res.data))
      .catch(err => {
        console.error(err);
        setError('Could not fetch student leaderboard rankings.');
      })
      .finally(() => setLoading(false));
  }, []);

  const filteredRankings = rankings.filter(r => 
    r.student_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.company_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
        <span className="text-gray-400 text-sm font-semibold tracking-wider">Compiling students leaderboard...</span>
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-white tracking-wide uppercase flex items-center gap-3">
            <Trophy className="w-8 h-8 text-amber-500 animate-bounce-slow" />
            Student Leaderboard
          </h1>
          <p className="text-gray-400 text-xs mt-1.5 uppercase tracking-wider">
            Rankings compiled by averaging project completion rates, code readiness, and clean security scans.
          </p>
        </div>

        {/* Search */}
        <div className="relative max-w-sm w-full">
          <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-gray-500">
            <Search className="w-4 h-4" />
          </span>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#0f0f13] border border-white/5 rounded-xl py-2.5 pl-11 pr-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-all"
            placeholder="Search student or company..."
          />
        </div>
      </div>

      {/* Leaderboard list */}
      <div className="glass-card rounded-2xl border border-white/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-[#0f0f13]/60 text-[10px] font-black text-gray-500 uppercase tracking-widest">
                <th className="py-4 px-6 text-center w-20">Rank</th>
                <th className="py-4 px-6">Student Developer</th>
                <th className="py-4 px-6">Company / Org</th>
                <th className="py-4 px-6 text-center">Projects</th>
                <th className="py-4 px-6 text-center">Avg Completion</th>
                <th className="py-4 px-6 text-center">Avg Readiness</th>
                <th className="py-4 px-6 text-center">Vulnerabilities</th>
                <th className="py-4 px-6 text-center">Overall Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredRankings.length === 0 ? (
                <tr>
                  <td colSpan="8" className="py-12 text-center text-gray-500 text-sm font-semibold uppercase tracking-wider">
                    No matching student records found.
                  </td>
                </tr>
              ) : (
                filteredRankings.map((r, index) => {
                  const rank = index + 1;
                  return (
                    <tr key={r.student_id} className="hover:bg-white/[0.01] transition-all text-xs font-medium text-gray-300">
                      {/* Rank Column */}
                      <td className="py-4 px-6 text-center">
                        {rank === 1 ? (
                          <span className="inline-flex items-center justify-center p-1.5 bg-amber-500/10 border border-amber-500/20 text-amber-500 rounded-lg">
                            <Medal className="w-5 h-5" />
                          </span>
                        ) : rank === 2 ? (
                          <span className="inline-flex items-center justify-center p-1.5 bg-slate-300/10 border border-slate-300/20 text-slate-300 rounded-lg">
                            <Medal className="w-5 h-5" />
                          </span>
                        ) : rank === 3 ? (
                          <span className="inline-flex items-center justify-center p-1.5 bg-amber-700/10 border border-amber-700/20 text-amber-700 rounded-lg">
                            <Medal className="w-5 h-5" />
                          </span>
                        ) : (
                          <span className="font-extrabold text-gray-500 text-sm">{rank}</span>
                        )}
                      </td>

                      {/* Name */}
                      <td className="py-4 px-6 font-extrabold text-white text-sm">{r.student_name}</td>

                      {/* Company */}
                      <td className="py-4 px-6 text-gray-400 font-semibold">{r.company_name}</td>

                      {/* Projects count */}
                      <td className="py-4 px-6 text-center font-bold">{r.projects_count}</td>

                      {/* Completion */}
                      <td className="py-4 px-6 text-center font-black text-emerald-400">
                        {r.average_completion_percentage}%
                      </td>

                      {/* Readiness */}
                      <td className="py-4 px-6 text-center font-black text-indigo-400">
                        {r.average_production_readiness}%
                      </td>

                      {/* Vulnerabilities */}
                      <td className="py-4 px-6 text-center font-bold text-rose-400">
                        {r.total_vulnerabilities}
                      </td>

                      {/* Score */}
                      <td className="py-4 px-6 text-center">
                        <span className="inline-block px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-black rounded-lg text-sm">
                          {r.score}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
