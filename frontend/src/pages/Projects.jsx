import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  FolderKanban, Plus, ExternalLink, Trash2, Edit, AlertCircle, CheckCircle, Clock 
} from 'lucide-react';
import api from '../api';
import { API_PATHS } from '../constants/apiPaths';

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Create / Edit modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    repository_url: '',
    prd_url: '',
    deployment_url: '',
  });

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await api.get(`${API_PATHS.PROJECTS}?page_size=100`);
      // Fetch latest reports for each project to get details
      const projectsWithDetails = await Promise.all(
        res.data.items.map(async (p) => {
          let completion = 0.0;
          let readiness = 0.0;
          let risk = 'Low';
          let last_audit = 'Never';

          try {
            const repRes = await api.get(`/api/v1/reports/project/${p.id}`);
            if (repRes.data && repRes.data.length > 0) {
              const latest = repRes.data[0];
              completion = latest.completion_percentage;
              readiness = latest.student_report.production_readiness_score || 50.0;
              last_audit = new Date(latest.created_at).toLocaleDateString();

              // Count vulnerabilities to estimate risk
              const vulnsRes = await api.get(`/api/v1/reports/?project_id=${p.id}`);
              const high_count = vulnsRes.data.items.filter(v => v.severity === 'high' || v.severity === 'critical').length;
              const med_count = vulnsRes.data.items.filter(v => v.severity === 'medium').length;

              if (high_count > 0) risk = 'High';
              else if (med_count > 1) risk = 'Medium';
            }
          } catch (e) {
            console.error('Failed to load metrics for project', p.id, e);
          }

          return {
            ...p,
            completion_percentage: completion,
            readiness_score: readiness,
            risk_level: risk,
            last_audit: last_audit
          };
        })
      );
      setProjects(projectsWithDetails);
    } catch (err) {
      console.error(err);
      setError('Could not retrieve projects list.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleOpenCreate = () => {
    setEditingProject(null);
    setFormData({
      name: '',
      description: '',
      repository_url: '',
      prd_url: '',
      deployment_url: '',
    });
    setModalOpen(true);
  };

  const handleOpenEdit = (p) => {
    setEditingProject(p);
    setFormData({
      name: p.name,
      description: p.description || '',
      repository_url: p.repository_url || '',
      prd_url: p.prd_url || '',
      deployment_url: p.deployment_url || '',
    });
    setModalOpen(true);
  };

  const handleModalSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingProject) {
        // Update
        await api.put(API_PATHS.PROJECT_DETAIL(editingProject.id), formData);
      } else {
        // Create
        await api.post(API_PATHS.PROJECTS, formData);
      }
      setModalOpen(false);
      fetchProjects();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to save project.');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this project? All associated reports, audit runs, and evidence will be permanently deleted.')) {
      return;
    }
    try {
      await api.delete(API_PATHS.PROJECT_DETAIL(id));
      fetchProjects();
    } catch (err) {
      console.error(err);
      alert('Failed to delete project.');
    }
  };

  return (
    <div className="space-y-8 animate-shimmer-off">
      {/* Title & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-white tracking-wide uppercase flex items-center gap-3">
            <FolderKanban className="w-8 h-8 text-indigo-500" />
            Projects Dashboard
          </h1>
          <p className="text-gray-400 text-xs mt-1.5 uppercase tracking-wider">
            Create, manage, and perform technical quality audits on software products.
          </p>
        </div>

        <button 
          onClick={handleOpenCreate}
          className="flex items-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-bold tracking-wider text-xs uppercase rounded-xl shadow-lg shadow-indigo-500/10 transition-all self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          Register Project
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold leading-relaxed">
          {error}
        </div>
      )}

      {/* Grid of Projects */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-64 rounded-2xl glass-card animate-shimmer p-6 flex flex-col justify-between">
              <div className="h-4 bg-white/5 rounded w-2/3"></div>
              <div className="space-y-2">
                <div className="h-3 bg-white/5 rounded w-full"></div>
                <div className="h-3 bg-white/5 rounded w-5/6"></div>
              </div>
              <div className="h-8 bg-white/5 rounded-xl w-full"></div>
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 border border-white/5 text-center flex flex-col items-center justify-center gap-3">
          <FolderKanban className="w-12 h-12 text-gray-600" />
          <h3 className="text-lg font-bold text-gray-300">No Projects Configured</h3>
          <p className="text-gray-500 text-sm max-w-sm">
            Add your first project by supplying repository URLs, spec links, and deployment endpoints to begin evaluating.
          </p>
          <button 
            onClick={handleOpenCreate}
            className="mt-3 px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white font-semibold text-sm rounded-xl transition-all"
          >
            Create New Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((p) => {
            const hasAudit = p.last_audit !== 'Never';
            return (
              <div key={p.id} className="glass-card rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden group">
                {/* Glowing subtle border */}
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/0 via-indigo-500/0 to-indigo-500/5 opacity-0 group-hover:opacity-100 transition-all pointer-events-none"></div>

                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <Link to={`/project/${p.id}`} className="hover:underline">
                      <h3 className="text-lg font-extrabold text-white line-clamp-1">{p.name}</h3>
                    </Link>
                    
                    {/* Risk Badge */}
                    <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest ${
                      p.risk_level === 'High' 
                        ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse'
                        : p.risk_level === 'Medium'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }`}>
                      {p.risk_level} Risk
                    </span>
                  </div>

                  <p className="text-gray-400 text-xs line-clamp-2 leading-relaxed">
                    {p.description || 'No project description provided. Update project to configure.'}
                  </p>

                  <div className="space-y-2 pt-2">
                    {/* Completion percent */}
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-gray-400">Completion Score</span>
                      <span className="text-white">{p.completion_percentage.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                      <div 
                        className="bg-gradient-to-r from-indigo-500 to-indigo-400 h-full rounded-full transition-all duration-500" 
                        style={{ width: `${p.completion_percentage}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-1.5 text-gray-500">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Audit: {p.last_audit}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => handleOpenEdit(p)}
                      className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg border border-white/0 hover:border-white/5 transition-all"
                      title="Edit Configuration"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => handleDelete(p.id)}
                      className="p-2 text-gray-400 hover:text-rose-400 hover:bg-rose-500/5 rounded-lg border border-white/0 hover:border-rose-500/10 transition-all"
                      title="Delete Project"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <Link 
                      to={`/project/${p.id}`}
                      className="flex items-center gap-1 px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 font-bold uppercase rounded-lg tracking-wider text-[10px] transition-all"
                    >
                      Inspect
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Register/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-lg glass-card rounded-2xl border border-white/10 shadow-2xl p-8 relative overflow-hidden">
            <h3 className="text-xl font-black text-white uppercase tracking-wider mb-6">
              {editingProject ? 'Edit Project Config' : 'Register New Project'}
            </h3>

            <form onSubmit={handleModalSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">
                  Project Title
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-[#0a0a0d] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition-all"
                  placeholder="E.g., Day Tracker Android App"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows="3"
                  className="w-full bg-[#0a0a0d] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition-all"
                  placeholder="Provide a summary of the project scope and tech stack..."
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">
                  GitHub Repository URL
                </label>
                <input
                  type="url"
                  value={formData.repository_url}
                  onChange={(e) => setFormData({ ...formData, repository_url: e.target.value })}
                  className="w-full bg-[#0a0a0d] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition-all"
                  placeholder="https://github.com/owner/repo"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">
                  PRD Google Doc URL
                </label>
                <input
                  type="url"
                  value={formData.prd_url}
                  onChange={(e) => setFormData({ ...formData, prd_url: e.target.value })}
                  className="w-full bg-[#0a0a0d] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition-all"
                  placeholder="https://docs.google.com/document/d/..."
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">
                  Production Deployment URL
                </label>
                <input
                  type="url"
                  value={formData.deployment_url}
                  onChange={(e) => setFormData({ ...formData, deployment_url: e.target.value })}
                  className="w-full bg-[#0a0a0d] border border-white/5 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition-all"
                  placeholder="https://my-app-live.web.app"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-5 py-2.5 bg-white/5 hover:bg-white/10 rounded-xl text-sm font-semibold text-gray-300 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-bold tracking-wider uppercase transition-all shadow-lg hover:shadow-indigo-500/25"
                >
                  Save Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
