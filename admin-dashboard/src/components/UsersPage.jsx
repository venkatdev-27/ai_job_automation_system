import React, { useState, useEffect } from 'react';
import { Users as UsersIcon, Mail, Phone, Briefcase, ArrowLeft, Tag, ShieldCheck, Layers } from 'lucide-react';
import { fetchStudents, fetchStudentDetail } from '../services/api';

export default function UsersPage({ refreshKey = 0 }) {
  const [students, setStudents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQ, setSearchQ] = useState('');

  useEffect(() => {
    setLoading(true);
    fetchStudents()
      .then(data => setStudents(data || []))
      .catch(e => console.error('Failed to load students:', e))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const openDetail = (sid) => {
    setSelected(sid);
    setDetail(null);
    fetchStudentDetail(sid).then(setDetail).catch(console.error);
  };

  const filtered = students.filter(s => {
    if (!searchQ.trim()) return true;
    const q = searchQ.toLowerCase();
    return (s.name || '').toLowerCase().includes(q) || 
           (s.email || '').toLowerCase().includes(q) || 
           (s.phone || '').toLowerCase().includes(q) ||
           (s.primary_role || '').toLowerCase().includes(q);
  });

  const truncateCompany = (name) => {
    if (!name || name.length <= 17) return name || 'N/A';
    return name.substring(0, 14) + '...';
  };

  if (loading) return (
    <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
      <div className="spinner-border" role="status" style={{ color: '#7367f0', width: '3rem', height: '3rem' }}>
        <span className="visually-hidden">Loading...</span>
      </div>
    </div>
  );

  if (selected) {
    if (!detail) return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <div className="spinner-border" role="status" style={{ color: '#7367f0', width: '3rem', height: '3rem' }}>
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );

    return (
      <div className="row g-4">
        <div className="col-12">
          <button 
            onClick={() => { setSelected(null); setDetail(null); }} 
            className="btn d-flex align-items-center gap-2"
            style={{ backgroundColor: 'rgba(115, 103, 240, 0.15)', border: '1px solid #7367f0', color: '#7367f0', padding: '8px 16px' }}
          >
            <ArrowLeft size={18} /> 
            <span style={{ fontWeight: 600 }}>Back to Student Inventory</span>
          </button>
        </div>
        
        <div className="col-12">
          <div className="card" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
            <div className="card-body p-4">
              <div className="row g-4 mb-4 pb-4" style={{ borderBottom: '1px solid #1e293b' }}>
                <div className="col-12 col-md-8">
                  <h4 className="mb-2 fw-bold" style={{ color: '#e2e8f0', fontSize: '1.75rem' }}>{detail.name}</h4>
                  <div className="d-flex flex-wrap gap-4">
                    <div className="d-flex align-items-center gap-2">
                      <Mail size={16} style={{ color: '#7367f0' }} />
                      <span style={{ fontSize: '14px', color: '#94a3b8' }}>{detail.email}</span>
                    </div>
                    <div className="d-flex align-items-center gap-2">
                      <Phone size={16} style={{ color: '#10b981' }} />
                      <span style={{ fontSize: '14px', color: '#94a3b8' }}>{detail.phone}</span>
                    </div>
                  </div>
                </div>
                <div className="col-12 col-md-4">
                  <div className="card h-100" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                    <div className="card-body">
                      <p className="mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Primary Role</p>
                      <div className="d-flex align-items-center gap-2">
                        <ShieldCheck size={16} style={{ color: '#7367f0' }} />
                        <span className="fw-bold" style={{ color: '#e2e8f0', textTransform: 'uppercase' }}>{detail.primary_role || 'Not Set'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <h5 className="mb-3 fw-bold" style={{ color: '#7367f0', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <Layers size={18} className="me-2" />Deep-Link Custom Roles
                </h5>
                <div className="row g-3">
                  {detail.custom_roles && Object.keys(detail.custom_roles).length > 0 ? Object.entries(detail.custom_roles).map(([key, role]) => (
                    <div key={key} className="col-12 col-md-6 col-lg-4">
                      <div className="card h-100" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                        <div className="card-body d-flex align-items-center gap-3">
                          <div className="d-flex align-items-center justify-content-center rounded-2" style={{ width: 40, height: 40, backgroundColor: 'rgba(115, 103, 240, 0.15)' }}>
                            <Tag size={18} style={{ color: '#7367f0' }} />
                          </div>
                          <div>
                            <h6 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{role.title}</h6>
                            <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>{key}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )) : (
                    <div className="col-12">
                      <div className="card text-center py-4" style={{ backgroundColor: '#0f0f23', border: '1px dashed #1e293b' }}>
                        <span style={{ color: '#64748b' }}>No customized roles found.</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h5 className="mb-3 fw-bold" style={{ color: '#64748b', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <Briefcase size={18} className="me-2" />Production Application History
                </h5>
                <div className="card" style={{ backgroundColor: '#0f0f23', border: '1px solid #1e293b' }}>
                  {detail.applications?.length > 0 ? (
                    <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      <table className="table mb-0" style={{ backgroundColor: 'transparent' }}>
                        <thead style={{ position: 'sticky', top: 0, backgroundColor: '#0f0f23' }}>
                          <tr style={{ borderBottom: '1px solid #1e293b' }}>
                            <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', borderBottom: '1px solid #1e293b' }}>Job Title</th>
                            <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', borderBottom: '1px solid #1e293b' }}>Company</th>
                            <th className="px-4 py-3 text-center" style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', borderBottom: '1px solid #1e293b' }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.applications.map((app, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                              <td className="px-4 py-3" style={{ color: '#e2e8f0', fontWeight: 500 }}>{app.job_title || 'N/A'}</td>
                              <td className="px-4 py-3" style={{ color: '#94a3b8' }} title={app.company}>{truncateCompany(app.company)}</td>
                              <td className="px-4 py-3 text-center">
                                <span className="badge" style={{ 
                                  backgroundColor: app.status === 'applied' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                  color: app.status === 'applied' ? '#10b981' : '#ef4444',
                                  border: `1px solid ${app.status === 'applied' ? '#10b981' : '#ef4444'}`,
                                  padding: '6px 10px'
                                }}>
                                  {app.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="card-body text-center py-4">
                      <span style={{ color: '#64748b' }}>No application logs found.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ backgroundColor: '#16213e', overflow: 'hidden', border: '1px solid #1e293b' }}>
      <div className="card-header d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 p-4" style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#0f0f23' }}>
        <div>
          <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Student Inventory</h5>
          <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Master Database • {filtered.length} Profiles</p>
        </div>
        <div className="position-relative">
          <Tag className="position-absolute" style={{ left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b', zIndex: 1 }} size={18} />
          <input 
            type="text" 
            placeholder="Search by name, role, or contact..." 
            value={searchQ} 
            onChange={e => setSearchQ(e.target.value)}
            style={{ 
              backgroundColor: '#0f0f23', 
              border: '1px solid #1e293b', 
              borderRadius: '8px',
              padding: '10px 12px 10px 40px',
              color: '#e2e8f0',
              width: '250px',
              fontSize: '13px'
            }} 
          />
        </div>
      </div>
      
      <div className="card-body p-0" style={{ backgroundColor: '#16213e' }}>
        <div className="table-responsive">
          <table className="table mb-0" style={{ backgroundColor: '#16213e' }}>
            <thead>
              <tr style={{ backgroundColor: 'rgba(15, 15, 35, 0.8)', borderBottom: '1px solid #1e293b' }}>
                <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Identified Student</th>
                <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Primary Role</th>
                <th className="px-4 py-3" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Contact Vector</th>
                <th className="px-4 py-3 text-center" style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderBottom: '1px solid #1e293b' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan="4" className="text-center py-5" style={{ color: '#64748b' }}>No production profiles found in database</td>
                </tr>
              ) : filtered.map(s => (
                <tr 
                  key={s.student_id || s._id} 
                  onClick={() => openDetail(s.student_id)}
                  style={{ cursor: 'pointer', borderBottom: '1px solid #1e293b' }}
                >
                  <td className="px-4 py-3">
                    <div>
                      <p className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{s.name}</p>
                      <p className="mb-0" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase' }}>UID: {s.student_id?.slice(-8)}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="d-flex align-items-center gap-2">
                      <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#7367f0', boxShadow: '0 0 8px rgba(115,103,240,0.5)' }} />
                      <span className="fw-medium" style={{ color: '#94a3b8', textTransform: 'uppercase' }}>{s.primary_role || 'Not Set'}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div>
                      <p className="mb-1 d-flex align-items-center gap-2" style={{ fontSize: '13px', color: '#94a3b8' }}>
                        <Mail size={14} style={{ color: '#64748b' }} /> 
                        <span style={{ marginLeft: '6px' }}>{s.email}</span>
                      </p>
                      <p className="mb-0 d-flex align-items-center gap-2" style={{ fontSize: '13px', color: '#94a3b8' }}>
                        <Phone size={14} style={{ color: '#64748b' }} /> 
                        <span style={{ marginLeft: '6px' }}>{s.phone}</span>
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="badge" style={{ 
                      backgroundColor: s.active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                      color: s.active ? '#10b981' : '#64748b',
                      border: `1px solid ${s.active ? '#10b981' : '#64748b'}`,
                      padding: '6px 10px'
                    }}>
                      {s.active ? 'Active' : 'Offline'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}