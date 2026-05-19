import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, Legend } from 'recharts';
import { fetchStats, fetchChartData, fetchPlatforms } from '../services/api';

const COLORS = ['#7367f0', '#10b981', '#f59e0b'];

const ChartTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ 
        backgroundColor: '#16213e', 
        border: '1px solid #334155', 
        padding: '12px', 
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
      }}>
        <p style={{ color: '#e2e8f0', margin: '0 0 8px', fontWeight: 600, fontSize: '13px' }}>{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color, margin: '4px 0', fontSize: '12px', fontWeight: 500 }}>
            {entry.name}: {entry.value?.toLocaleString()}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const Card = ({ title, subtitle, children }) => (
  <div className="card h-100" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
    <div className="card-header border-bottom" style={{ borderColor: '#1e293b', padding: '16px 20px', backgroundColor: '#0f0f23' }}>
      <h6 className="mb-1 fw-bold" style={{ color: '#e2e8f0' }}>{title}</h6>
      {subtitle && <p className="mb-0" style={{ color: '#64748b', fontSize: '12px' }}>{subtitle}</p>}
    </div>
    <div className="card-body p-3" style={{ minHeight: '280px' }}>
      {children}
    </div>
  </div>
);

const StatCard = ({ icon, label, value, color }) => (
  <div className="card" style={{ backgroundColor: '#16213e', border: '1px solid #1e293b' }}>
    <div className="card-body p-4">
      <div className="d-flex align-items-center gap-3">
        <div className="d-flex align-items-center justify-content-center rounded-2" style={{ width: 48, height: 48, backgroundColor: `${color}20` }}>
          <i className={`bx ${icon}`} style={{ fontSize: '24px', color }}></i>
        </div>
        <div>
          <p className="mb-0" style={{ color: '#64748b', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</p>
          <p className="mb-0 fw-bold" style={{ color: '#e2e8f0', fontSize: '24px' }}>{value?.toLocaleString()}</p>
        </div>
      </div>
    </div>
  </div>
);

const FILTERS = [
  { key: '24h', label: '1 Day' },
  { key: '7d', label: '1 Week' },
  { key: '15d', label: '15 Days' },
  { key: '30d', label: '30 Days' }
];

export default function ChartsPage({ refreshKey = 0 }) {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [platformData, setPlatformData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('7d');

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchStats(), fetchChartData(activeFilter), fetchPlatforms()])
      .then(([s, c, p]) => {
        setStats(s);
        setChartData(c || []);
        setPlatformData(p || []);
      })
      .catch(e => console.error('Failed to load charts:', e))
      .finally(() => setLoading(false));
  }, [refreshKey, activeFilter]);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <div className="spinner-border" role="status" style={{ color: '#7367f0', width: '3rem', height: '3rem' }}>
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  const totalApplied = stats?.applied || 0;
  const totalFailed = stats?.failed || 0;
  const totalPending = stats?.pending || 0;
  const strikeRate = totalApplied + totalFailed > 0 ? ((totalApplied / (totalApplied + totalFailed)) * 100).toFixed(1) : 0;

  const pieData = [
    { name: 'Applied', value: totalApplied, color: '#10b981' },
    { name: 'Failed', value: totalFailed, color: '#ef4444' },
    { name: 'Pending', value: totalPending, color: '#f59e0b' }
  ];

  const uniquePlatforms = [];
  const seen = new Set();
  platformData.forEach(p => {
    if (p.name && !seen.has(p.name)) {
      seen.add(p.name);
      uniquePlatforms.push({ name: p.name, value: p.total, color: COLORS[uniquePlatforms.length % COLORS.length] });
    }
  });

  let dailyData = [];
  if (activeFilter === '24h') {
    dailyData = chartData.slice(-1).map(d => ({ date: d.date, applied: d.applied || 0, failed: d.failed || 0 }));
  } else if (activeFilter === '7d') {
    dailyData = chartData.slice(-7).map(d => ({ date: d.date, applied: d.applied || 0, failed: d.failed || 0 }));
  } else if (activeFilter === '15d') {
    dailyData = chartData.slice(-15).map(d => ({ date: d.date, applied: d.applied || 0, failed: d.failed || 0 }));
  } else {
    dailyData = chartData.slice(-30).map(d => ({ date: d.date, applied: d.applied || 0, failed: d.failed || 0 }));
  }

  const totalForPeriod = dailyData.reduce((sum, d) => sum + (d.applied || 0), 0);

  return (
    <div className="row g-4">
      {/* Time Range Buttons */}
      <div className="col-12">
        <div className="d-flex gap-2 flex-wrap">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setActiveFilter(f.key)}
              className="btn btn-sm"
              style={{ 
                backgroundColor: activeFilter === f.key ? '#7367f0' : '#1e293b',
                color: activeFilter === f.key ? '#fff' : '#94a3b8',
                border: 'none',
                padding: '8px 16px'
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stat Cards */}
      <div className="col-6 col-md-3">
        <StatCard icon="bx-check-circle" label="Applied" value={totalApplied} color="#10b981" />
      </div>
      <div className="col-6 col-md-3">
        <StatCard icon="bx-x-circle" label="Failed" value={totalFailed} color="#ef4444" />
      </div>
      <div className="col-6 col-md-3">
        <StatCard icon="bx-time-five" label="Pending" value={totalPending} color="#f59e0b" />
      </div>
      <div className="col-6 col-md-3">
        <StatCard icon="bx-target-lock" label="Strike Rate" value={`${strikeRate}%`} color="#7367f0" />
      </div>

      {/* Horizontal Bar Chart - Target vs Applications */}
      <div className="col-12 col-lg-6">
        <Card title="Applications Performance" subtitle={`Total: ${totalForPeriod} applications in ${FILTERS.find(f => f.key === activeFilter)?.label.toLowerCase()}`}>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={dailyData} layout="vertical" margin={{ top: 10, right: 10, left: 60, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} />
                <YAxis dataKey="date" type="category" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} width={50} />
                <Tooltip content={<ChartTooltip />} />
                <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '11px' }}>{value}</span>} />
                <Bar dataKey="applied" fill="#10b981" radius={[0, 4, 4, 0]} name="Applied" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="d-flex align-items-center justify-content-center h-100" style={{ color: '#64748b' }}>No data available</div>
          )}
        </Card>
      </div>

      {/* Donut Chart */}
      <div className="col-12 col-lg-6">
        <Card title="Status Distribution" subtitle="Applied vs Failed vs Pending">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={100}
                paddingAngle={4}
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
              <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '11px' }}>{value}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Platform Stats - Only 3 platforms */}
      <div className="col-12 col-lg-6">
        <Card title="Platform Performance" subtitle="Applications by platform">
          {uniquePlatforms.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={uniquePlatforms.slice(0, 3)} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} name="Applications">
                  {uniquePlatforms.slice(0, 3).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="d-flex align-items-center justify-content-center h-100" style={{ color: '#64748b' }}>No platform data</div>
          )}
        </Card>
      </div>

      {/* Platform Distribution Pie */}
      <div className="col-12 col-lg-6">
        <Card title="Platform Distribution" subtitle="Percentage by platform">
          {uniquePlatforms.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={uniquePlatforms.slice(0, 3)}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {uniquePlatforms.slice(0, 3).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="d-flex align-items-center justify-content-center h-100" style={{ color: '#64748b' }}>No platform data</div>
          )}
        </Card>
      </div>
    </div>
  );
}