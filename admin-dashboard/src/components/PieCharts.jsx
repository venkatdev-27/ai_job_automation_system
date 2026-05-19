import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const COLORS = ['#7367f0', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4'];

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
        <p style={{ color: '#e2e8f0', margin: '0 0 8px', fontWeight: 600, fontSize: '13px' }}>{label || payload[0]?.name}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color, margin: '4px 0', fontSize: '12px', fontWeight: 500 }}>
            {entry.name}: {entry.value?.toLocaleString()} ({(entry.percent * 100).toFixed(1)}%)
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const SimplePieChart = ({ data, colors = COLORS, width = '100%', height = 300, innerRadius = 0, outerRadius = 100 }) => (
  <ResponsiveContainer width={width} height={height}>
    <PieChart>
      <Pie
        data={data}
        cx="50%"
        cy="50%"
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        paddingAngle={3}
        dataKey="value"
        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        labelLine={{ stroke: '#64748b' }}
      >
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={entry.color || colors[index % colors.length]} />
        ))}
      </Pie>
      <Tooltip content={<ChartTooltip />} />
      <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} />
    </PieChart>
  </ResponsiveContainer>
);

export const DonutChart = ({ data, colors = COLORS, width = '100%', height = 300 }) => (
  <ResponsiveContainer width={width} height={height}>
    <PieChart>
      <Pie
        data={data}
        cx="50%"
        cy="50%"
        innerRadius={60}
        outerRadius={90}
        paddingAngle={4}
        dataKey="value"
        label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
        labelLine={{ stroke: '#64748b', strokeWidth: 1 }}
      >
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={entry.color || colors[index % colors.length]} />
        ))}
      </Pie>
      <Tooltip content={<ChartTooltip />} />
      <Legend 
        layout="vertical"
        formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} 
      />
    </PieChart>
  </ResponsiveContainer>
);

export const PieChartWithCenterLabel = ({ data, colors = COLORS, width = '100%', height = 300, centerLabel, centerValue }) => (
  <ResponsiveContainer width={width} height={height}>
    <PieChart>
      <Pie
        data={data}
        cx="50%"
        cy="50%"
        innerRadius={70}
        outerRadius={100}
        paddingAngle={4}
        dataKey="value"
      >
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={entry.color || colors[index % colors.length]} />
        ))}
      </Pie>
      <Tooltip content={<ChartTooltip />} />
      {/* Center Label */}
      <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '12px' }}>{value}</span>} />
    </PieChart>
  </ResponsiveContainer>
);

export const NestedPieChart = ({ data, colors = COLORS, width = '100%', height = 300 }) => {
  const innerData = data.slice(0, 3);
  const outerData = data;
  
  return (
    <ResponsiveContainer width={width} height={height}>
      <PieChart>
        <Pie
          data={innerData}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={60}
          paddingAngle={2}
          dataKey="value"
        >
          {innerData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
          ))}
        </Pie>
        <Pie
          data={outerData}
          cx="50%"
          cy="50%"
          innerRadius={70}
          outerRadius={95}
          paddingAngle={2}
          dataKey="value"
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        >
          {outerData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
        <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '11px' }}>{value}</span>} />
      </PieChart>
    </ResponsiveContainer>
  );
};

export const RadialPieChart = ({ data, colors = COLORS, width = '100%', height = 300 }) => (
  <ResponsiveContainer width={width} height={height}>
    <PieChart>
      <Pie
        data={data}
        cx="50%"
        cy="50%"
        innerRadius={0}
        outerRadius={100}
        startAngle={180}
        endAngle={0}
        paddingAngle={2}
        dataKey="value"
        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        labelLine={{ stroke: '#64748b' }}
      >
        {data.map((entry, index) => (
          <Cell key={`cell-${index}`} fill={entry.color || colors[index % colors.length]} />
        ))}
      </Pie>
      <Tooltip content={<ChartTooltip />} />
    </PieChart>
  </ResponsiveContainer>
);

export default {
  SimplePieChart,
  DonutChart,
  PieChartWithCenterLabel,
  NestedPieChart,
  RadialPieChart
};