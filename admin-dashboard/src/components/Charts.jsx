import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, Legend } from 'recharts';
import BarGraphs from './BarGraphs';
import PieCharts from './PieCharts';

export const VerticalBarChart = BarGraphs.VerticalBarChart;
export const GroupedBarChart = BarGraphs.GroupedBarChart;
export const StackedBarChart = BarGraphs.StackedBarChart;
export const HorizontalBarChart = BarGraphs.HorizontalBarChart;

export const DonutChart = PieCharts.DonutChart;
export const NestedPieChart = PieCharts.NestedPieChart;

const COLORS = ['#7367f0', '#10b981', '#f59e0b', '#ef4444'];

const ChartTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ 
        backgroundColor: '#16213e', 
        border: '1px solid #334155', 
        padding: '10px', 
        borderRadius: '8px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
      }}>
        <p style={{ color: '#e2e8f0', margin: 0, fontWeight: 600 }}>{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color, margin: '4px 0 0', fontSize: '12px' }}>
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export const TotalRevenueChart = ({ data = [] }) => {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorApplied" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#7367f0" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#7367f0" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis 
          dataKey="date" 
          tick={{ fontSize: 11, fill: '#64748b' }} 
          axisLine={{ stroke: '#1e293b' }}
          tickLine={false}
        />
        <YAxis 
          tick={{ fontSize: 11, fill: '#64748b' }} 
          axisLine={{ stroke: '#1e293b' }}
          tickLine={false}
        />
        <Tooltip content={<ChartTooltip />} />
        <Legend 
          wrapperStyle={{ paddingTop: '20px' }}
          formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>}
        />
        <Area 
          type="monotone" 
          dataKey="applied" 
          stroke="#7367f0" 
          strokeWidth={2} 
          fillOpacity={1} 
          fill="url(#colorApplied)" 
          name="Applied" 
        />
        <Area 
          type="monotone" 
          dataKey="failed" 
          stroke="#ef4444" 
          strokeWidth={2} 
          fillOpacity={1} 
          fill="url(#colorFailed)" 
          name="Failed" 
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

export const PlatformDistribution = ({ data = [] }) => {
  const chartData = data.slice(0, 3).map(p => ({ name: p.name, value: p.total }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={5}
          dataKey="value"
          label={({ name, percent }) => (
            <span style={{ fill: '#94a3b8', fontSize: '12px' }}>
              {name} {(percent * 100).toFixed(0)}%
            </span>
          )}
        >
          {chartData.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
        <Legend 
          formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export const DailyActivityChart = ({ data = [] }) => {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis 
          dataKey="date" 
          tick={{ fontSize: 11, fill: '#64748b' }} 
          axisLine={{ stroke: '#1e293b' }}
          tickLine={false}
        />
        <YAxis 
          tick={{ fontSize: 11, fill: '#64748b' }} 
          axisLine={{ stroke: '#1e293b' }}
          tickLine={false}
        />
        <Tooltip content={<ChartTooltip />} />
        <Legend 
          formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>}
        />
        <Bar dataKey="applied" fill="#7367f0" radius={[4, 4, 0, 0]} name="Applied" />
        <Bar dataKey="failed" fill="#ef4444" radius={[4, 4, 0, 0]} name="Failed" />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const StrikeRatioChart = ({ applied = 0, failed = 0, skipped = 0 }) => {
  const data = [
    { name: 'Applied', value: applied },
    { name: 'Failed', value: failed },
    { name: 'Skipped', value: skipped }
  ];
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={5}
          dataKey="value"
          label={({ name, percent }) => (
            <span style={{ fill: '#94a3b8', fontSize: '12px' }}>
              {name} {(percent * 100).toFixed(0)}%
            </span>
          )}
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
        <Legend 
          formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default {
  TotalRevenueChart,
  PlatformDistribution,
  DailyActivityChart,
  StrikeRatioChart,
  VerticalBarChart,
  GroupedBarChart,
  StackedBarChart,
  HorizontalBarChart,
  DonutChart,
  NestedPieChart
};