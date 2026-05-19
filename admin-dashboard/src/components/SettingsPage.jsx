import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Power, RefreshCw, Server, Database, Shield, Activity, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { fetchHealth, fetchStats, fetchAutomationStatus } from '../services/api';

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aiEnabled, setAiEnabled] = useState(null);
  const [togglingAi, setTogglingAi] = useState(false);
  const [autoStopEnabled, setAutoStopEnabled] = useState(true);
  const [togglingAutoStop, setTogglingAutoStop] = useState(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      fetchHealth().catch(() => null),
      fetchStats().catch(() => null),
      fetch('/api/settings/ai-engine').then(r => r.json()).catch(() => ({ enabled: null })),
      fetchAutomationStatus().catch(() => null)
    ])
      .then(([h, s, ai, auto]) => { 
        setHealth(h); 
        setStats(s); 
        setAiEnabled(ai.enabled); 
        if (auto?.auto_stop !== undefined) {
          setAutoStopEnabled(auto.auto_stop === 'true');
        }
      })
      .finally(() => setLoading(false));
  };

  const toggleAi = async () => {
    if (!window.confirm('Restart workers for change to take effect. Continue?')) return;
    setTogglingAi(true);
    try {
      const newValue = !aiEnabled;
      await fetch('/api/settings/ai-engine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newValue })
      });
      setAiEnabled(newValue);
    } catch (e) {
      alert('Failed to update: ' + e.message);
    } finally {
      setTogglingAi(false);
    }
  };

  const toggleAutoStop = async () => {
    setTogglingAutoStop(true);
    try {
      const newValue = !autoStopEnabled;
      await fetch('/api/automation/auto-stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newValue })
      });
      setAutoStopEnabled(newValue);
    } catch (e) {
      alert('Failed to update: ' + e.message);
    } finally {
      setTogglingAutoStop(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const circuitColor = (state) => {
    if (state === 'open') return { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' };
    if (state === 'half_open') return { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' };
    return { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981' };
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <div className="spinner-border" role="status" style={{ color: '#7367f0', width: '3rem', height: '3rem' }}>
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="row g-4">
      {/* Header */}
      <div className="col-12">
        <div className="d-flex justify-content-between align-items-center flex-wrap gap-3">
          <h4 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>System Settings</h4>
          <button onClick={loadData} className="btn d-flex align-items-center gap-2" style={{ backgroundColor: 'rgba(115, 103, 240, 0.15)', color: '#7367f0', border: '1px solid #7367f0', padding: '8px 16px' }}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* AI Engine Toggle */}
      <div className="col-12 col-md-6">
        <div className="card h-100" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
          <div className="card-body p-4">
            <div className="d-flex align-items-center gap-3 mb-4">
              <div className="d-flex align-items-center justify-content-center rounded-2" style={{ width: 48, height: 48, backgroundColor: aiEnabled ? 'rgba(115, 103, 240, 0.15)' : 'rgba(100, 116, 139, 0.15)' }}>
                <Cpu size={24} style={{ color: aiEnabled ? '#7367f0' : '#64748b' }} />
              </div>
              <div className="flex-grow-1">
                <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>AI Engine</h5>
                <span className="badge" style={{ 
                  backgroundColor: aiEnabled === true ? 'rgba(115, 103, 240, 0.15)' : aiEnabled === false ? 'rgba(239, 68, 68, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                  color: aiEnabled === true ? '#7367f0' : aiEnabled === false ? '#ef4444' : '#64748b',
                  border: `1px solid ${aiEnabled === true ? '#7367f0' : aiEnabled === false ? '#ef4444' : '#64748b'}`,
                  padding: '4px 10px'
                }}>
                  {aiEnabled === null ? 'Loading...' : aiEnabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <p className="mb-1 fw-semibold" style={{ color: '#e2e8f0' }}>AI Resume Tailoring</p>
                <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>When enabled, generates tailored resumes</p>
              </div>
              <button
                onClick={toggleAi}
                disabled={togglingAi || aiEnabled === null}
                className="btn position-relative"
                style={{ 
                  width: '56px', height: '30px', padding: 0, borderRadius: '15px',
                  backgroundColor: aiEnabled ? '#10b981' : '#334155',
                  border: 'none',
                  transition: 'all 0.3s ease'
                }}
              >
                {togglingAi ? (
                  <div className="spinner-border spinner-border-sm position-absolute" style={{ width: '16px', height: '16px', color: '#fff' }}>
                    <span className="visually-hidden"></span>
                  </div>
                ) : (
                  <span style={{
                    position: 'absolute',
                    width: '24px', height: '24px', borderRadius: '50%',
                    backgroundColor: '#fff', 
                    left: aiEnabled ? '28px' : '3px',
                    top: '3px',
                    transition: 'all 0.3s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {aiEnabled ? <CheckCircle size={14} style={{ color: '#10b981' }} /> : <XCircle size={14} style={{ color: '#64748b' }} />}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Automation Control */}
      <div className="col-12 col-md-6">
        <div className="card h-100" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
          <div className="card-body p-4">
            <div className="d-flex align-items-center gap-3 mb-4">
              <div className="d-flex align-items-center justify-content-center rounded-2" style={{ width: 48, height: 48, backgroundColor: 'rgba(245, 158, 11, 0.15)' }}>
                <Zap size={24} style={{ color: '#f59e0b' }} />
              </div>
              <div>
                <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Automation</h5>
                <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Worker control</p>
              </div>
            </div>
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <p className="mb-1 fw-semibold" style={{ color: '#e2e8f0' }}>Auto-Stop</p>
                <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Stop workers after idle</p>
              </div>
              <button
                onClick={toggleAutoStop}
                disabled={togglingAutoStop}
                className="btn position-relative"
                style={{ 
                  width: '56px', height: '30px', padding: 0, borderRadius: '15px',
                  backgroundColor: autoStopEnabled ? '#10b981' : '#334155',
                  border: 'none',
                  transition: 'all 0.3s ease'
                }}
              >
                {togglingAutoStop ? (
                  <div className="spinner-border spinner-border-sm position-absolute" style={{ width: '16px', height: '16px', color: '#fff' }}>
                    <span className="visually-hidden"></span>
                  </div>
                ) : (
                  <span style={{
                    position: 'absolute',
                    width: '24px', height: '24px', borderRadius: '50%',
                    backgroundColor: '#fff', 
                    left: autoStopEnabled ? '28px' : '3px',
                    top: '3px',
                    transition: 'all 0.3s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {autoStopEnabled ? <CheckCircle size={14} style={{ color: '#10b981' }} /> : <XCircle size={14} style={{ color: '#64748b' }} />}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* System Health */}
      <div className="col-12">
        <div className="card" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
          <div className="card-body p-4">
            <div className="row g-4">
              <div className="col-12 col-md-4">
                <div className="card" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                  <div className="card-body text-center">
                    <Activity size={20} style={{ color: '#10b981', marginBottom: '8px' }} />
                    <p className="mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Active Browsers</p>
                    <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#10b981' }}>{health?.activeBrowsers ?? 'N/A'}</p>
                  </div>
                </div>
              </div>
              <div className="col-12 col-md-4">
                <div className="card" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                  <div className="card-body text-center">
                    <Server size={20} style={{ color: '#7367f0', marginBottom: '8px' }} />
                    <p className="mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Redis Memory</p>
                    <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#7367f0' }}>{health?.redisMemory || 'N/A'}</p>
                  </div>
                </div>
              </div>
              <div className="col-12 col-md-4">
                <div className="card" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                  <div className="card-body text-center">
                    <Activity size={20} style={{ color: health?.status === 'healthy' ? '#10b981' : '#ef4444', marginBottom: '8px' }} />
                    <p className="mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>System Status</p>
                    <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: health?.status === 'healthy' ? '#10b981' : '#ef4444' }}>{health?.status || 'Unknown'}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Circuit Breakers */}
      <div className="col-12">
        <div className="card" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
          <div className="card-body p-4">
            <div className="d-flex align-items-center gap-3 mb-4">
              <Shield size={24} style={{ color: '#f59e0b' }} />
              <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Circuit Breakers</h5>
            </div>
            <div className="row g-3">
              {health?.circuitStates && Object.entries(health.circuitStates).map(([platform, state]) => {
                const style = circuitColor(state);
                return (
                  <div key={platform} className="col-12 col-md-4">
                    <div className="d-flex justify-content-between align-items-center p-3" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b', borderRadius: '8px' }}>
                      <div>
                        <p className="mb-0 fw-semibold text-capitalize" style={{ color: '#e2e8f0' }}>{platform}</p>
                        <p className="mb-0" style={{ fontSize: '11px', color: '#64748b' }}>Circuit State</p>
                      </div>
                      <span className="badge" style={{ backgroundColor: style.bg, color: style.color, border: `1px solid ${style.color}`, padding: '6px 12px' }}>{state}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Database Stats */}
      <div className="col-12">
        <div className="card" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
          <div className="card-body p-4">
            <div className="d-flex align-items-center gap-3 mb-4">
              <Database size={24} style={{ color: '#3b82f6' }} />
              <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Database Stats</h5>
            </div>
            <div className="row g-3">
              <div className="col-6 col-md-3">
                <div className="text-center p-3" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b', borderRadius: '8px' }}>
                  <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#7367f0' }}>{stats?.total?.toLocaleString() || 0}</p>
                  <p className="mb-0" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Total Apps</p>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="text-center p-3" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b', borderRadius: '8px' }}>
                  <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#10b981' }}>{stats?.applied?.toLocaleString() || 0}</p>
                  <p className="mb-0" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Applied</p>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="text-center p-3" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b', borderRadius: '8px' }}>
                  <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#ef4444' }}>{stats?.failed?.toLocaleString() || 0}</p>
                  <p className="mb-0" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Failed</p>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="text-center p-3" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b', borderRadius: '8px' }}>
                  <p className="mb-0 fw-bold" style={{ fontSize: '28px', color: '#f59e0b' }}>{stats?.pending?.toLocaleString() || 0}</p>
                  <p className="mb-0" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>Pending</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}