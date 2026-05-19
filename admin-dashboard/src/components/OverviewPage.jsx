import React, { useState, useEffect } from 'react';
import { TotalRevenueChart, PlatformDistribution, DailyActivityChart, StrikeRatioChart } from './Charts';
import { fetchStats, fetchChartData, fetchPlatforms } from '../services/api';

const TF_MAP = { '24h': '24h', '7d': '7d', '15d': '15d', '30d': '30d' };

export default function OverviewPage({ refreshKey = 0 }) {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [platformData, setPlatformData] = useState([]);
  const [activeFilter, setActiveFilter] = useState('7d');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchStats(), fetchChartData(activeFilter), fetchPlatforms()])
      .then(([s, c, p]) => {
        setStats(s);
        setChartData(c);
        setPlatformData(p);
      })
      .catch(e => console.error('Failed to load overview:', e))
      .finally(() => setLoading(false));
  }, [refreshKey, activeFilter]);

  const handleFilter = (f) => {
    setActiveFilter(f);
    fetchChartData(f).then(setChartData).catch(console.error);
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
      {/* Stats Cards - Sneat Dark Style */}
      <div className="col-12 col-sm-6 col-lg-3">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <span className="d-block mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Total Students
                </span>
                <h3 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{stats?.totalStudents?.toLocaleString() || 0}</h3>
              </div>
              <div className="rounded-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, backgroundColor: 'rgba(115, 103, 240, 0.15)' }}>
                <i className="bx bx-users" style={{ color: '#7367f0', fontSize: '20px' }}></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="col-12 col-sm-6 col-lg-3">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <span className="d-block mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Total Applications
                </span>
                <h3 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{stats?.total?.toLocaleString() || 0}</h3>
              </div>
              <div className="rounded-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, backgroundColor: 'rgba(59, 130, 246, 0.15)' }}>
                <i className="bx bx-briefcase" style={{ color: '#3b82f6', fontSize: '20px' }}></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="col-12 col-sm-6 col-lg-3">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <span className="d-block mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Success Rate
                </span>
                <h3 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{stats?.successRate || 0}%</h3>
              </div>
              <div className="rounded-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, backgroundColor: 'rgba(16, 185, 129, 0.15)' }}>
                <i className="bx bx-check-circle" style={{ color: '#10b981', fontSize: '20px' }}></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="col-12 col-sm-6 col-lg-3">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <span className="d-block mb-1" style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Applied Jobs
                </span>
                <h3 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>{stats?.applied?.toLocaleString() || 0}</h3>
              </div>
              <div className="rounded-2 d-flex align-items-center justify-content-center" style={{ width: 40, height: 40, backgroundColor: 'rgba(245, 158, 11, 0.15)' }}>
                <i className="bx bx-globe" style={{ color: '#f59e0b', fontSize: '20px' }}></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Total Revenue Chart - Area */}
      <div className="col-12">
        <div className="card" style={{ backgroundColor: '#16213e' }}>
          <div className="card-header d-flex justify-content-between flex-wrap gap-2 p-4" style={{ borderBottom: '1px solid #1e293b' }}>
            <div>
              <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Applications Flow</h5>
              <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Real-time Volume</p>
            </div>
            <div className="btn-group" role="group">
              {Object.keys(TF_MAP).map(f => (
                <button
                  key={f}
                  onClick={() => handleFilter(TF_MAP[f])}
                  type="button"
                  className={`btn btn-sm`}
                  style={{
                    backgroundColor: activeFilter === TF_MAP[f] ? '#7367f0' : 'transparent',
                    border: activeFilter === TF_MAP[f] ? '#7367f0' : '1px solid #334155',
                    color: activeFilter === TF_MAP[f] ? '#fff' : '#94a3b8'
                  }}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="card-body p-4">
            {chartData.length > 0 ? (
              <TotalRevenueChart data={chartData} />
            ) : (
              <div className="text-center py-5" style={{ color: '#64748b' }}>No data for this period</div>
            )}
          </div>
        </div>
      </div>

      {/* Pie Charts Row */}
      <div className="col-12 col-md-6">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-header p-4" style={{ borderBottom: '1px solid #1e293b' }}>
            <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Strike Ratio</h5>
            <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Applied vs Failed</p>
          </div>
          <div className="card-body p-4">
            <StrikeRatioChart
              applied={stats?.applied || 0}
              failed={stats?.failed || 0}
              skipped={stats?.skipped || 0}
            />
          </div>
        </div>
      </div>

      <div className="col-12 col-md-6">
        <div className="card h-100" style={{ backgroundColor: '#16213e' }}>
          <div className="card-header p-4" style={{ borderBottom: '1px solid #1e293b' }}>
            <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Platforms</h5>
            <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Distribution</p>
          </div>
          <div className="card-body p-4">
            <PlatformDistribution data={platformData} />
          </div>
        </div>
      </div>

      {/* Daily Activity Bar Chart */}
      <div className="col-12">
        <div className="card" style={{ backgroundColor: '#16213e' }}>
          <div className="card-header p-4" style={{ borderBottom: '1px solid #1e293b' }}>
            <div>
              <h5 className="mb-0 fw-bold" style={{ color: '#e2e8f0' }}>Daily Activity</h5>
              <p className="mb-0" style={{ fontSize: '12px', color: '#64748b' }}>Total Applications Per Day</p>
            </div>
          </div>
          <div className="card-body p-4">
            {chartData.length > 0 ? (
              <DailyActivityChart data={chartData} />
            ) : (
              <div className="text-center py-5" style={{ color: '#64748b' }}>No data available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}