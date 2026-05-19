import React, { useState, useEffect, useMemo } from 'react';
import { fetchApplications } from '../services/api';

const ITEMS_PER_PAGE = 25;

const STATUS_STYLES = {
  applied: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '#10b981' },
  failed: { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '#ef4444' },
  pending: { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '#f59e0b' },
  skipped: { bg: 'rgba(100, 116, 139, 0.15)', color: '#64748b', border: '#64748b' },
  duplicate: { bg: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6', border: '#8b5cf6' },
};

const PLATFORM_STYLES = {
  LinkedIn: { bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' },
  Naukri: { bg: 'rgba(99, 102, 241, 0.15)', color: '#6366f1' },
  Foundit: { bg: 'rgba(20, 184, 166, 0.15)', color: '#14b4b6' },
};

export default function ApplicationsPage({ notifications, refreshKey = 0 }) {
  const [apps, setApps] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);

  useEffect(() => {
    setLoading(true);
    fetchApplications('all')
      .then(data => setApps(data || []))
      .catch(e => console.error('Failed to load applications:', e))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  useEffect(() => {
    if (notifications.length > 0) {
      setApps(prev => {
        const ids = new Set(prev.map(a => a._id));
        const newOnes = notifications.filter(n => !ids.has(n._id));
        return [...newOnes, ...prev];
      });
    }
  }, [notifications]);

  useEffect(() => {
    setPage(0);
  }, [search, statusFilter]);

  const filtered = useMemo(() => {
    let result = apps;
    if (statusFilter !== 'all') result = result.filter(a => a.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(a =>
        (a.jobTitle || '').toLowerCase().includes(q) ||
        (a.company || '').toLowerCase().includes(q) ||
        (a.studentName || a.candidateName || '').toLowerCase().includes(q) ||
        (a.platform || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [apps, search, statusFilter]);

  const paginated = useMemo(() => {
    const start = page * ITEMS_PER_PAGE;
    return filtered.slice(start, start + ITEMS_PER_PAGE);
  }, [filtered, page]);

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE);

  const goToPage = (p) => {
    if (p >= 0 && p < totalPages) setPage(p);
  };

  const formatDate = (d) => {
    if (!d) return 'N/A';
    try { return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }
    catch { return d; }
  };

  const truncateCompany = (name) => {
    if (!name || name.length <= 17) return name || 'N/A';
    return name.substring(0, 14) + '...';
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
    <div className="card" style={{ backgroundColor: '#16213e', overflow: 'hidden', border: '1px solid #1e293b' }}>
      {/* Header */}
      <div className="card-header d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 p-4" style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#0f0f23' }}>
        <div>
          <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Application Feed</h5>
          <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>{filtered.length} applications • Page {page + 1} of {totalPages}</p>
        </div>
        <div className="d-flex flex-wrap gap-2 align-items-center">
          {/* Search */}
          <div className="position-relative">
            <i className="bx bx-search position-absolute" style={{ left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b', zIndex: 1 }}></i>
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ 
                paddingLeft: '36px', 
                backgroundColor: '#0f0f23', 
                border: '1px solid #1e293b', 
                borderRadius: '8px',
                color: '#e2e8f0', 
                width: '180px',
                fontSize: '13px',
                padding: '8px 12px 8px 36px'
              }}
            />
          </div>
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            style={{ 
              backgroundColor: '#0f0f23', 
              border: '1px solid #1e293b', 
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '13px',
              padding: '8px 12px'
            }}
          >
            <option value="all">All Status</option>
            <option value="applied">Applied</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
            <option value="skipped">Skipped</option>
          </select>
          {/* Live Badge */}
          <span className="badge" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid #10b981', padding: '6px 10px' }}>
            <i className="bx bx-radio-circle-marked bx-fade-left" style={{ fontSize: '10px', marginRight: '4px' }}></i>
            Live
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="table-responsive">
        <table className="table mb-0" style={{ backgroundColor: '#16213e' }}>
          <thead>
            <tr style={{ backgroundColor: 'rgba(15, 15, 35, 0.8)', borderBottom: '1px solid #1e293b' }}>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Date</th>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Student</th>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Role</th>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Company</th>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Platform</th>
              <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan="6" className="text-center py-5" style={{ color: '#64748b' }}>No applications found</td>
              </tr>
            ) : paginated.map((app, idx) => {
              const statusStyle = STATUS_STYLES[app.status] || STATUS_STYLES.pending;
              const platformStyle = PLATFORM_STYLES[app.platform] || PLATFORM_STYLES.Naukri;
              
              return (
                <tr key={app._id || idx} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td className="px-4 py-3" style={{ fontSize: '12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{formatDate(app.appliedAt)}</td>
                  <td className="px-4 py-3" style={{ fontSize: '14px', fontWeight: 500, color: '#e2e8f0' }}>{app.studentName || app.candidateName || app.studentId || 'N/A'}</td>
                  <td className="px-4 py-3" style={{ fontSize: '14px', fontWeight: 500, color: '#e2e8f0' }}>{app.jobTitle || app.role || 'N/A'}</td>
                  <td className="px-4 py-3" style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' }} title={app.company}>{truncateCompany(app.company)}</td>
                  <td className="px-4 py-3">
                    <span
                      className="badge"
                      style={{ ...platformStyle, padding: '4px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px' }}
                    >
                      {app.platform}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="badge"
                      style={{ ...statusStyle, padding: '4px 8px', fontSize: '10px', fontWeight: 600, borderRadius: '4px', border: `1px solid ${statusStyle.border}` }}
                    >
                      {app.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="card-footer d-flex justify-content-between align-items-center p-3" style={{ borderTop: '1px solid #1e293b', backgroundColor: '#0f0f23' }}>
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page === 0}
            className="btn btn-sm"
            style={{ color: page === 0 ? '#474d5a' : '#e2e8f0', cursor: page === 0 ? 'not-allowed' : 'pointer', backgroundColor: 'transparent', border: 'none' }}
          >
            <i className="bx bx-chevron-left me-1"></i> Previous
          </button>
          <div className="d-flex gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = i === 0 ? i : i === 4 ? totalPages - 1 : page + i;
              if (pageNum < 0 || pageNum >= totalPages) return null;
              return (
                <button
                  key={pageNum}
                  onClick={() => goToPage(pageNum)}
                  className="btn btn-sm"
                  style={{
                    width: '32px',
                    height: '32px',
                    padding: 0,
                    backgroundColor: page === pageNum ? '#7367f0' : 'transparent',
                    color: page === pageNum ? '#fff' : '#94a3b8',
                    border: page === pageNum ? '#7367f0' : '1px solid #334155',
                    fontSize: '13px'
                  }}
                >
                  {pageNum + 1}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => goToPage(page + 1)}
            disabled={page >= totalPages - 1}
            className="btn btn-sm"
            style={{ color: page >= totalPages - 1 ? '#474d5a' : '#e2e8f0', cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer', backgroundColor: 'transparent', border: 'none' }}
          >
            Next <i className="bx bx-chevron-right ms-1"></i>
          </button>
        </div>
      )}
    </div>
  );
}