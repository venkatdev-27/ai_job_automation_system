import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';

const COLORS = ['#7367f0', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

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

export const VerticalBarChart = ({ data, dataKey = 'value', nameKey = 'name', title, subtitle }) => (
  <ResponsiveContainer width="100%" height={300}>
    <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
      <XAxis dataKey={nameKey} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <Tooltip content={<ChartTooltip />} />
      <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} />
      <Bar dataKey={dataKey} fill="#7367f0" radius={[6, 6, 0, 0]} name={title || 'Value'}>
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
        ))}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
);

export const GroupedBarChart = ({ data, bars = [], title }) => (
  <ResponsiveContainer width="100%" height={300}>
    <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <Tooltip content={<ChartTooltip />} />
      <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} />
      {bars.map((bar, index) => (
        <Bar 
          key={bar.key} 
          dataKey={bar.key} 
          fill={bar.color || COLORS[index % COLORS.length]} 
          radius={[4, 4, 0, 0]} 
          name={bar.name} 
        />
      ))}
    </BarChart>
  </ResponsiveContainer>
);

export const StackedBarChart = ({ data, bars = [], title }) => (
  <ResponsiveContainer width="100%" height={300}>
    <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
      <Tooltip content={<ChartTooltip />} />
      <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} />
      {bars.map((bar, index) => (
        <Bar 
          key={bar.key} 
          dataKey={bar.key} 
          stackId="a" 
          fill={bar.color || COLORS[index % COLORS.length]} 
          radius={index === bars.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} 
          name={bar.name} 
        />
      ))}
    </BarChart>
  </ResponsiveContainer>
);

export const HorizontalBarChart = ({ data, layout = 'vertical' }) => {
  const sortedData = [...data].sort((a, b) => b.value - a.value).slice(0, 10);
  
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart 
        data={sortedData} 
        layout={layout}
        margin={{ top: 10, right: 30, left: 80, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        {layout === 'vertical' ? (
          <>
            <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
            <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} width={70} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
            <YAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
 </>
        )}
        <Tooltip content={<ChartTooltip />} />
        <Bar dataKey="value" fill="#7367f0" radius={[0, 6, 6, 0]} name="Value">
          {sortedData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default {
  VerticalBarChart,
  GroupedBarChart,
  StackedBarChart,
  HorizontalBarChart
};