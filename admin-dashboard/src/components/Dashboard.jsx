import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import socket from '../services/socket';
import OverviewPage from './OverviewPage';
import ApplicationsPage from './ApplicationsPage';
import UsersPage from './UsersPage';
import SettingsPage from './SettingsPage';
import ChartsPage from './ChartsPage';
import AutomationToggle from './AutomationToggle';
import { AnimatedBell, AnimatedRefreshCcw } from './AnimatedIcons';

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [showNotifs, setShowNotifs] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [toasts, setToasts] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const view = useMemo(() => {
    const path = location.pathname.replace('/', '');
    return path || 'overview';
  }, [location.pathname]);

  useEffect(() => {
    const handler = (data) => {
      setNotifications(prev => [{ ...data, _ts: Date.now() }, ...prev].slice(0, 50));
      setUnreadCount(prev => prev + 1);
      const id = Date.now();
      const newToast = {
        id,
        title: data.jobTitle || data.role || 'Application Sent',
        company: data.company || 'N/A',
        platform: data.platform || 'System',
        status: data.status || 'applied'
      };
      setToasts(prev => [newToast, ...prev].slice(0, 5));
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 5000);
    };
    socket.on('newApplication', handler);
    return () => socket.off('newApplication', handler);
  }, []);

  const clearNotifs = useCallback(() => { setUnreadCount(0); setShowNotifs(false); }, []);

  const SidebarItem = ({ icon, label, path, active }) => {
  const iconMap = {
    'LayoutDashboard': 'bx-home-alt',
    'Briefcase': 'bx-briefcase',
    'TrendingUp': 'bx-trending-up',
    'Users': 'bx-user',
    'Settings': 'bx-cog',
    'BarChart': 'bx-bar-chart'
  };
  const iconClass = iconMap[icon] || 'bx-circle';
  
  return (
    <Link
      to={path}
      onClick={() => setSidebarOpen(false)}
      className="d-flex align-items-center gap-3 px-4 py-3 rounded-3 transition-all text-decoration-none"
      style={{
        backgroundColor: active ? 'rgba(115, 103, 240, 0.15)' : 'transparent',
        color: active ? '#7367f0' : '#94a3b8',
        border: active ? '1px solid #7367f0' : '1px solid transparent'
      }}
    >
      <i className={`bx ${iconClass}`} style={{ color: active ? '#7367f0' : '#94a3b8' }}></i>
      <span className="fw-medium" style={{ fontSize: '14px' }}>{label}</span>
    </Link>
  );
};

  return (
<div className="d-flex min-vh-100" style={{ backgroundColor: '#1a1a2e' }}>
      {/* Sidebar - Always visible on desktop */}
      <aside className="sidebar d-none d-lg-flex flex-column" style={{ width: '280px', position: 'sticky', top: 0, height: '100vh', backgroundColor: '#0f0f23' }}>
        <div className="d-flex flex-column h-100 pt-3">
          {/* Brand */}
          <div className="px-4 mb-4">
            <div className="d-flex align-items-center gap-3">
              <div className="d-flex align-items-center justify-content-center rounded-2" style={{ width: 40, height: 40, background: 'linear-gradient(135deg, #7367f0, #a855f7)' }}>
                <i className="bx bx-bar-chart-square text-white fs-5"></i>
              </div>
              <span className="fs-4 fw-bold text-white">
                AI STRIKE
              </span>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex-grow-1 px-3 pb-3" style={{ overflowY: 'auto' }}>
            <nav className="d-grid gap-1">
              <SidebarItem icon="LayoutDashboard" label="Dashboard" path="/" active={view === 'overview'} />
              <SidebarItem icon="BarChart" label="Charts" path="/charts" active={view === 'charts'} />
              <SidebarItem icon="Briefcase" label="Applications" path="/applications" active={view === 'applications'} />
              <SidebarItem icon="Users" label="Users" path="/users" active={view === 'users'} />
              <SidebarItem icon="Settings" label="Settings" path="/settings" active={view === 'settings'} />
            </nav>
          </div>

          {/* Logout */}
          <div className="p-3" style={{ borderTop: '1px solid #1e293b' }}>
            <button onClick={handleLogout} className="d-flex align-items-center gap-3 px-4 py-3 w-100 rounded-3 border-0 bg-transparent" style={{ cursor: 'pointer' }}>
              <i className="bx bx-log-out fs-5" style={{ color: '#ef4444' }}></i>
              <span className="fw-medium" style={{ fontSize: '14px', color: '#ef4444' }}>Sign Out</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-grow-1 p-4" style={{ backgroundColor: '#1a1a2e' }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-center flex-wrap gap-3 mb-4">
          <div>
            <h4 className="mb-1 fw-bold" style={{ color: '#e2e8f0' }}>
              {view === 'charts' ? 'Charts & Analytics' : view === 'overview' ? 'Dashboard' : view.charAt(0).toUpperCase() + view.slice(1)}
              <span className="text-primary" style={{ display: view === 'charts' ? 'none' : 'inline' }}> Overview</span>
            </h4>
            <p className="mb-0" style={{ fontSize: '13px', color: '#64748b' }}>Portal / {view}</p>
          </div>
          <div className="d-flex align-items-center gap-2">
            {/* Mobile Menu Toggle */}
            <button className="d-lg-none btn rounded-2 p-2" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }} onClick={() => setSidebarOpen(!sidebarOpen)}>
              <i className="bx bx-menu fs-5" style={{ color: '#e2e8f0' }}></i>
            </button>
            {/* Automation Toggle */}
            <AutomationToggle />
{/* Refresh */}
            <button onClick={() => setRefreshKey(k => k + 1)} className="btn rounded-2 p-2" title="Refresh data" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
              <AnimatedRefreshCcw size={20} />
            </button>
            {/* Notifications */}
            <div className="dropdown">
              <button onClick={() => { setShowNotifs(!showNotifs); if (!showNotifs) setUnreadCount(0); }} className="btn rounded-2 p-2" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
                <AnimatedBell size={20} count={unreadCount} />
              </button>
              {showNotifs && (
                <div className="dropdown-menu show d-block position-absolute end-0 mt-2" style={{ width: '320px', zIndex: 1050, backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
                  <div className="d-flex justify-content-between align-items-center p-3" style={{ borderBottom: '1px solid #1e293b' }}>
                    <span className="fw-semibold" style={{ color: '#e2e8f0' }}>Notifications</span>
                    <button onClick={clearNotifs} className="btn btn-sm p-0 text-muted">Clear</button>
                  </div>
                  <div className="overflow-auto" style={{ maxHeight: '250px' }}>
                    {notifications.length === 0 ? (
                      <div className="p-4 text-center text-muted">No notifications yet</div>
                    ) : notifications.slice(0, 10).map((n, i) => (
                      <div key={i} className="p-3" style={{ borderBottom: '1px solid #1e293b' }}>
                        <p className="mb-1 fw-semibold" style={{ color: '#e2e8f0', fontSize: '13px' }}>{n.jobTitle || 'New Application'}</p>
                        <p className="mb-0" style={{ color: '#64748b', fontSize: '11px' }}>
                          {n.platform} · {n.company || 'N/A'} · <span style={{ color: n.status === 'applied' ? '#10b981' : '#ef4444' }}>{n.status}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {/* User Avatar */}
            <div className="dropdown">
              <button className="btn p-0 border-0" data-bs-toggle="dropdown">
                <div className="rounded-circle d-flex align-items-center justify-content-center text-white fw-bold" style={{ width: 40, height: 40, background: 'linear-gradient(135deg, #7367f0, #a855f7)' }}>
                  AI
                </div>
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div key={refreshKey}>
          {view === 'overview' && <OverviewPage refreshKey={refreshKey} />}
          {view === 'charts' && <ChartsPage refreshKey={refreshKey} />}
          {view === 'applications' && <ApplicationsPage notifications={notifications} refreshKey={refreshKey} />}
          {view === 'users' && <UsersPage refreshKey={refreshKey} />}
          {view === 'settings' && <SettingsPage />}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;