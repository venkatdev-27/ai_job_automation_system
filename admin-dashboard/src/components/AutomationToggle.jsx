import { useState, useEffect } from 'react';
import { Square, Power, CheckCircle, AlertCircle, Zap } from 'lucide-react';
import { fetchAutomationStatus, toggleAutomation, triggerJobRun } from '../services/api';
import socket from '../services/socket';
import { AnimatedLoader } from './AnimatedIcons';

export default function AutomationToggle() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState(null);
  const [runTriggered, setRunTriggered] = useState(false);
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [autoStopEnabled, setAutoStopEnabled] = useState(true);

  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (status?.main_switch === 'on' && status?.jobs_running > 0) {
        fetchStatus();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [status?.jobs_running]);

  useEffect(() => {
    if (status?.auto_stop !== undefined) {
      setAutoStopEnabled(status.auto_stop === 'true');
    }
  }, [status?.auto_stop]);

  useEffect(() => {
    socket.on('auto_stop_triggered', () => fetchStatus());
    socket.on('auto_stop_status', (data) => setStatus(prev => prev ? { ...prev, ...data } : prev));
    return () => {
      socket.off('auto_stop_triggered');
      socket.off('auto_stop_status');
    };
  }, []);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const data = await fetchAutomationStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (toggling || !status) return;
    const newStatus = status.main_switch === 'on' ? 'off' : 'on';
    if (newStatus === 'off' && status.jobs_running > 0) {
      setShowStopConfirm(true);
      return;
    }
    await executeToggle(newStatus);
  };

  const executeToggle = async (newStatus) => {
    try {
      setToggling(true);
      setShowStopConfirm(false);
      await toggleAutomation(newStatus, true);
      if (newStatus === 'on') {
        setTimeout(async () => { await fetchStatus(); }, 15000);
      }
      await fetchStatus();
      setRunTriggered(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setToggling(false);
    }
  };

  const handleStopConfirm = () => executeToggle('off');

  const handleRun = async () => {
    if (toggling || !status || status.main_switch !== 'on') return;
    try {
      setToggling(true);
      setError(null);
      await triggerJobRun();
      setRunTriggered(true);
      setTimeout(async () => { await fetchStatus(); }, 5000);
      setTimeout(() => setRunTriggered(false), 10000);
    } catch (err) {
      setError(err.message);
    } finally {
      setToggling(false);
    }
  };

  const workersUp = status?.workers_up === 'true';
  const isOn = status?.main_switch === 'on';

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2 px-3 py-2" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b', borderRadius: '8px' }}>
        <div className="spinner-border spinner-border-sm" role="status" style={{ color: '#7367f0', width: '16px', height: '16px' }}>
          <span className="visually-hidden">Loading...</span>
        </div>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>Loading...</span>
      </div>
    );
  }

  return (
    <div className="d-flex align-items-center gap-2">
      {showStopConfirm && (
        <div className="position-fixed inset-0 d-flex align-items-center justify-content-center" style={{ backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 9999 }}>
          <div className="p-4" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b', borderRadius: '12px', maxWidth: '360px' }}>
            <div className="d-flex align-items-center gap-3 mb-3">
              <div className="d-flex align-items-center justify-content-center rounded-circle" style={{ width: 40, height: 40, backgroundColor: 'rgba(239, 68, 68, 0.2)' }}>
                <AlertCircle size={24} style={{ color: '#ef4444' }} />
              </div>
              <div>
                <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Stop Workers?</h5>
                <p className="mb-0" style={{ fontSize: '12px', color: '#94a3b8' }}>{status?.jobs_running || 0} jobs running</p>
              </div>
            </div>
            <p className="mb-3" style={{ fontSize: '13px', color: '#64748b' }}>
              Stopping will pause automation. Jobs in progress may be interrupted.
            </p>
            <div className="d-flex gap-2">
              <button
                onClick={() => setShowStopConfirm(false)}
                className="flex-grow-1 py-2"
                style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#94a3b8', fontWeight: 600, fontSize: '13px' }}
              >
                Cancel
              </button>
              <button
                onClick={handleStopConfirm}
                className="flex-grow-1 py-2"
                style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', borderRadius: '8px', color: '#ef4444', fontWeight: 600, fontSize: '13px' }}
              >
                Stop
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={handleToggle}
        disabled={toggling}
        className="d-flex align-items-center gap-2 px-3 py-2"
        style={{
          backgroundColor: isOn ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          border: `1px solid ${isOn ? '#10b981' : '#ef4444'}`,
          borderRadius: '8px',
          color: isOn ? '#10b981' : '#ef4444',
          fontWeight: 700,
          fontSize: '12px',
          cursor: toggling ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s'
        }}
      >
        {toggling ? (
          <AnimatedLoader size={14} style={{ color: isOn ? '#ef4444' : '#10b981' }} />
        ) : isOn ? (
          <Square size={14} />
        ) : (
          <Power size={14} />
        )}
        <span>{isOn ? 'STOP' : 'START'}</span>
      </button>

      {isOn && (
        <button
          onClick={handleRun}
          disabled={toggling || runTriggered}
          className="d-flex align-items-center gap-2 px-3 py-2"
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.15)',
            border: '1px solid #f59e0b',
            borderRadius: '8px',
            color: '#f59e0b',
            fontWeight: 700,
            fontSize: '12px',
            cursor: (toggling || runTriggered) ? 'not-allowed' : 'pointer',
            opacity: (toggling || runTriggered) ? 0.6 : 1,
            transition: 'all 0.2s'
          }}
        >
          {runTriggered ? (
            <AnimatedLoader size={14} style={{ color: '#f59e0b' }} />
          ) : (
            <Zap size={14} />
          )}
          <span>{runTriggered ? 'RUNNING' : 'RUN'}</span>
        </button>
      )}

      <div className="d-flex flex-column">
        <div className="d-flex align-items-center gap-1">
          {isOn && workersUp ? (
            <>
              <CheckCircle size={12} style={{ color: '#10b981' }} />
              <span style={{ fontSize: '10px', fontWeight: 700, color: '#10b981', textTransform: 'uppercase' }}>Running</span>
            </>
          ) : isOn ? (
            <>
              <div className="spinner-grow spinner-grow-sm" style={{ width: '8px', height: '8px', backgroundColor: '#f59e0b' }}></div>
              <span style={{ fontSize: '10px', fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase' }}>Starting</span>
            </>
          ) : (
            <>
              <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ef4444' }}></div>
              <span style={{ fontSize: '10px', fontWeight: 700, color: '#ef4444', textTransform: 'uppercase' }}>Stopped</span>
            </>
          )}
        </div>
        
        {status?.workers && (
          <span style={{ fontSize: '10px', color: '#64748b' }}>
            {status.workers.running}/{status.workers.total} workers
          </span>
        )}
        
        {(status?.jobs_running > 0 || status?.jobs_completed_today > 0) && (
          <span style={{ fontSize: '10px', color: '#64748b' }}>
            {status.jobs_running > 0 
              ? `${status.jobs_running} active • ${status.jobs_completed_today} today`
              : `${status.jobs_completed_today} today`
            }
          </span>
        )}
        
        {runTriggered && (
          <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: 600 }}>
            Triggered...
          </span>
        )}
        
        {autoStopEnabled && isOn && (
          <span style={{ fontSize: '9px', color: '#64748b', fontWeight: 700, textTransform: 'uppercase' }}>
            Auto-Stop
          </span>
        )}
      </div>

      {error && (
        <div className="d-flex align-items-center gap-1">
          <AlertCircle size={14} style={{ color: '#ef4444' }} />
          <span style={{ fontSize: '11px', color: '#ef4444' }}>{error}</span>
        </div>
      )}
    </div>
  );
}