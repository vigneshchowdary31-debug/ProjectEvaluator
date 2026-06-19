import React, { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate, Link, useNavigate, useLocation } from 'react-router-dom';
import { 
  ShieldAlert, LayoutDashboard, FolderKanban, FileText, 
  BarChart3, Trophy, Landmark, Settings, LogOut, Sun, Moon, Menu, X
} from 'lucide-react';

import Login from './pages/Login';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import ReportViewer from './pages/ReportViewer';
import Analytics from './pages/Analytics';
import StudentRankings from './pages/StudentRankings';
import CompanyDashboard from './pages/CompanyDashboard';
import SettingsPage from './pages/Settings';
import api from './api';

// Protected layout wrapper
function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    // Fetch profile info on load
    api.get('/api/v1/auth/me')
      .then(res => setUser(res.data))
      .catch(() => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/login');
      });
  }, [navigate]);

  const handleLogout = async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        await api.post('/api/v1/auth/logout', { refresh_token: refreshToken });
      } catch (e) {
        // ignore logout errors
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  const menuItems = [
    { name: 'Projects', path: '/projects', icon: FolderKanban },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
    { name: 'Rankings', path: '/student-rankings', icon: Trophy },
    { name: 'Company', path: '/company-dashboard', icon: Landmark },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-[#08080a] flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#0f0f13]/80 backdrop-blur-md border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-8 h-8 text-indigo-500 animate-pulse" />
          <span className="font-extrabold text-lg tracking-wider bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-500 bg-clip-text text-transparent">
            PROJECT AUDITOR
          </span>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {menuItems.map(item => {
            const Icon = item.icon;
            const active = location.pathname.startsWith(item.path);
            return (
              <Link 
                key={item.name} 
                to={item.path} 
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  active 
                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' 
                    : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Profile / Logout */}
        <div className="hidden md:flex items-center gap-4">
          {user && (
            <div className="flex flex-col items-end">
              <span className="text-xs text-indigo-400 font-bold tracking-widest uppercase">
                {user.is_admin ? 'Platform Admin' : 'Developer'}
              </span>
              <span className="text-sm font-medium text-gray-300">{user.full_name}</span>
            </div>
          )}
          <button 
            onClick={handleLogout}
            className="p-2 text-gray-400 hover:text-rose-400 hover:bg-rose-500/5 rounded-lg border border-transparent hover:border-rose-500/10 transition-all"
            title="Log Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>

        {/* Mobile menu toggle */}
        <button 
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-all"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </header>

      {/* Mobile nav overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#0f0f13] border-b border-white/5 p-4 flex flex-col gap-2">
          {menuItems.map(item => {
            const Icon = item.icon;
            const active = location.pathname.startsWith(item.path);
            return (
              <Link 
                key={item.name} 
                to={item.path} 
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  active 
                    ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' 
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
          <hr className="border-white/5 my-2" />
          <button 
            onClick={() => { setMobileMenuOpen(false); handleLogout(); }}
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-rose-400 hover:bg-rose-500/10 transition-all w-full"
          >
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-[#0a0a0d] border-t border-white/5 py-6 text-center text-xs text-gray-500">
        &copy; {new Date().getFullYear()} AI Project Audit Platform. Built with FastAPI, Playwright & Gemini AI.
      </footer>
    </div>
  );
}

// Protected Route Guard
function PrivateRoute({ children }) {
  const token = localStorage.getItem('access_token');
  return token ? <Layout>{children}</Layout> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/project/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
        <Route path="/report/:id" element={<PrivateRoute><ReportViewer /></PrivateRoute>} />
        <Route path="/analytics" element={<PrivateRoute><Analytics /></PrivateRoute>} />
        <Route path="/student-rankings" element={<PrivateRoute><StudentRankings /></PrivateRoute>} />
        <Route path="/company-dashboard" element={<PrivateRoute><CompanyDashboard /></PrivateRoute>} />
        <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
        
        {/* Default route redirect */}
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </HashRouter>
  );
}
