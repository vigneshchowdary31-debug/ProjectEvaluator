import React, { useState, useEffect } from 'react';
import { 
  Building2, Landmark, RefreshCw, AlertTriangle, ShieldCheck, 
  ChevronsRight, ExternalLink, Activity, ArrowLeft, FolderGit2 
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';
import { Link } from 'react-router-dom';

export default function PortfolioDashboard() {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  
  // Drill-down detailed company view
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [companyProjects, setCompanyProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);

  useEffect(() => {
    fetchPortfolios();
    fetchUser();
  }, []);

  const fetchUser = async () => {
    try {
      const res = await api.get('/api/v1/auth/me');
      setCurrentUser(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPortfolios = async () => {
    setLoading(true);
    try {
      const res = await api.get(API_PATHS.PORTFOLIO_COMPANIES);
      setPortfolios(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshAll = async () => {
    setRefreshing(true);
    try {
      await api.post(API_PATHS.PORTFOLIO_GENERATE);
      fetchPortfolios();
      if (selectedCompany) {
        // Refresh detail view projects if selected
        handleSelectCompany(selectedCompany.company_name);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to refresh portfolios.');
    } finally {
      setRefreshing(false);
    }
  };

  const handleSelectCompany = async (companyName) => {
    const portfolio = portfolios.find(p => p.company_name === companyName);
    setSelectedCompany(portfolio);
    setProjectsLoading(true);
    try {
      // Find all projects belonging to this company name
      const res = await api.get(API_PATHS.PROJECTS, { params: { page_size: 250 } });
      const projects = res.data.items || [];
      const filtered = projects.filter(p => p.company_name === companyName);
      setCompanyProjects(filtered);
    } catch (err) {
      console.error(err);
    } finally {
      setProjectsLoading(false);
    }
  };

  const getHealthBadge = (rating) => {
    const classes = {
      excellent: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      good: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      average: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      poor: 'bg-rose-500/10 text-rose-400 border-rose-500/20'
    };
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border uppercase ${classes[rating.toLowerCase()] || ''}`}>
        {rating}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Detail Drill-down View */}
      {selectedCompany ? (
        <div className="space-y-6">
          <button 
            onClick={() => setSelectedCompany(null)}
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-all font-semibold uppercase tracking-wider bg-[#0f0f13] border border-white/5 px-3 py-2 rounded-lg"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Portfolios
          </button>

          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
                <Landmark className="w-7 h-7 text-indigo-400" />
                Company Portfolio: {selectedCompany.company_name}
              </h1>
              <p className="text-sm text-gray-400">Inventory and aggregated analysis report overview.</p>
            </div>
            
            {selectedCompany.report_url && (
              <a 
                href={selectedCompany.report_url} 
                target="_blank" 
                rel="noreferrer"
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 rounded-lg text-xs font-semibold transition-all"
              >
                View Drive Report <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase">Projects Count</div>
              <div className="text-2xl font-extrabold text-white mt-1">{selectedCompany.projects_count}</div>
            </div>
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase">Avg Completion</div>
              <div className="text-2xl font-extrabold text-indigo-400 mt-1">{selectedCompany.avg_completion}%</div>
            </div>
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase">Avg Security</div>
              <div className="text-2xl font-extrabold text-emerald-400 mt-1">{selectedCompany.avg_security}%</div>
            </div>
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-4">
              <div className="text-xs font-semibold text-gray-500 uppercase">Avg Readiness</div>
              <div className="text-2xl font-extrabold text-amber-400 mt-1">{selectedCompany.avg_readiness}%</div>
            </div>
          </div>

          {/* Top Risks */}
          {selectedCompany.top_risks && selectedCompany.top_risks.length > 0 && (
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-6 space-y-3">
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                Aggregated Top Vulnerabilities & Risks
              </h3>
              <div className="grid md:grid-cols-2 gap-4">
                {selectedCompany.top_risks.map((risk, idx) => (
                  <div key={idx} className="p-3 bg-rose-500/5 border border-rose-500/10 rounded-xl flex justify-between items-center text-xs">
                    <span className="font-semibold text-rose-300">{risk.finding}</span>
                    <span className="px-2 py-0.5 bg-rose-500/25 text-rose-200 rounded font-bold uppercase text-[10px]">
                      {risk.frequency} Project(s)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Projects Table */}
          <div className="bg-[#0f0f13] border border-white/5 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-white/5 bg-[#16161c]">
              <h3 className="font-bold text-white text-md">Projects Inventory List</h3>
            </div>
            
            {projectsLoading ? (
              <div className="flex justify-center items-center py-10">
                <RefreshCw className="w-6 h-6 text-indigo-500 animate-spin" />
              </div>
            ) : companyProjects.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-10">No projects linked to this company portfolio.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-gray-300">
                  <thead className="bg-black/10 border-b border-white/5 text-xs text-gray-400 uppercase font-semibold">
                    <tr>
                      <th className="p-4">Project Name</th>
                      <th className="p-4">Student Name</th>
                      <th className="p-4">Repository</th>
                      <th className="p-4">Intake Source</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {companyProjects.map(proj => (
                      <tr key={proj.id} className="hover:bg-white/[0.01] transition-all">
                        <td className="p-4 font-bold text-white text-base">{proj.name}</td>
                        <td className="p-4 text-gray-200 font-medium">{proj.student_name || 'N/A'}</td>
                        <td className="p-4 text-xs font-mono text-gray-400 max-w-xs truncate">{proj.repository_url || 'N/A'}</td>
                        <td className="p-4 text-xs text-gray-400 uppercase">{proj.source}</td>
                        <td className="p-4 text-right">
                          <Link 
                            to={`/project/${proj.id}`} 
                            className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-semibold uppercase tracking-wider"
                          >
                            Dashboard <ChevronsRight className="w-4 h-4" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
                <Building2 className="w-7 h-7 text-indigo-500" />
                Company Portfolios Hub
              </h1>
              <p className="text-sm text-gray-400">View aggregated health indices, technical gaps, and vulnerability profiles by student organization.</p>
            </div>
            
            {currentUser?.is_admin && (
              <button 
                onClick={handleRefreshAll}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition-all"
              >
                {refreshing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                Refresh Portfolios
              </button>
            )}
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-20">
              <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
            </div>
          ) : portfolios.length === 0 ? (
            <div className="bg-[#0f0f13] border border-white/5 rounded-2xl p-12 text-center max-w-xl mx-auto space-y-4">
              <div className="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center mx-auto">
                <Building2 className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-bold text-white">No Portfolios Found</h3>
              <p className="text-sm text-gray-400">
                Company portfolios aggregate projects grouped by Company Name. Sync or import student projects containing Company details to populate this hub.
              </p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-6">
              {portfolios.map(p => (
                <div 
                  key={p.id}
                  className="bg-[#0f0f13] border border-white/5 rounded-2xl p-6 space-y-4 hover:border-white/10 transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex justify-between items-start">
                      <h3 className="font-bold text-white text-lg flex items-center gap-2">
                        <Landmark className="w-5 h-5 text-indigo-400" />
                        {p.company_name}
                      </h3>
                      {getHealthBadge(p.health_rating)}
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center py-2 bg-white/[0.02] border border-white/5 rounded-xl">
                      <div>
                        <div className="text-[10px] text-gray-500 uppercase font-semibold">Avg Completion</div>
                        <div className="text-lg font-extrabold text-indigo-400 mt-0.5">{p.avg_completion}%</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-gray-500 uppercase font-semibold">Avg Security</div>
                        <div className="text-lg font-extrabold text-emerald-400 mt-0.5">{p.avg_security}%</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-gray-500 uppercase font-semibold">Projects</div>
                        <div className="text-lg font-extrabold text-white mt-0.5">{p.projects_count}</div>
                      </div>
                    </div>

                    <div className="flex justify-between text-xs text-gray-400">
                      <span>At-Risk Projects: <strong className={p.projects_at_risk > 0 ? 'text-rose-400' : 'text-emerald-400'}>{p.projects_at_risk}</strong></span>
                      <span>Last Updated: {new Date(p.last_generated_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={() => handleSelectCompany(p.company_name)}
                      className="flex-1 px-4 py-2 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 rounded-lg text-xs font-semibold transition-all text-center uppercase tracking-wider"
                    >
                      View Details
                    </button>
                    {p.report_url && (
                      <a 
                        href={p.report_url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-2 bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white rounded-lg transition-all border border-white/5"
                        title="View Drive Portfolio Document"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
