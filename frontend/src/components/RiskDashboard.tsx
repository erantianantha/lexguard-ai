import { PieChart, Pie, Cell, ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import type { RiskSummary, RiskAnalysis } from '../api';
import './RiskDashboard.css';

interface Props {
  summary: RiskSummary;
  risks: RiskAnalysis[];
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e', NONE: '#6366f1',
};

export default function RiskDashboard({ summary, risks }: Props) {
  const pieData = [
    { name: 'Critical', value: summary.critical_count, color: SEVERITY_COLORS.CRITICAL },
    { name: 'High', value: summary.high_count, color: SEVERITY_COLORS.HIGH },
    { name: 'Medium', value: summary.medium_count, color: SEVERITY_COLORS.MEDIUM },
    { name: 'Low', value: summary.low_count, color: SEVERITY_COLORS.LOW },
    { name: 'None', value: summary.none_count, color: SEVERITY_COLORS.NONE },
  ].filter(d => d.value > 0);

  const pieFromRisks = risks.reduce<Record<string, number>>((acc, r) => {
    const level = (r.severity_level || 'NONE').toUpperCase();
    acc[level] = (acc[level] || 0) + 1;
    return acc;
  }, {});
  const displayPie = pieData.length > 0 ? pieData : Object.entries(pieFromRisks).map(([level, value]) => ({
    name: level.charAt(0) + level.slice(1).toLowerCase(),
    value,
    color: SEVERITY_COLORS[level] || '#6366f1',
  })).filter(d => d.value > 0);

  const categories = Object.entries(summary.risk_by_category || {});

  const heatmapData = risks.map((r) => ({
    x: r.likelihood_percentage,
    y: r.severity_score,
    name: r.subcategory || r.primary_category,
    level: (r.severity_level || 'NONE').toUpperCase(),
    fill: SEVERITY_COLORS[(r.severity_level || 'NONE').toUpperCase()] || '#6366f1',
  }));

  const severityKey = (summary.severity_level || 'LOW').toUpperCase();
  const scoreColor = SEVERITY_COLORS[severityKey] || '#6366f1';

  return (
    <div className="risk-dashboard animate-slide-up">
      {/* Executive Summary */}
      <div className="risk-header glass-card">
        <div className="risk-score-circle" style={{ '--ring-color': scoreColor } as any}>
          <svg viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
            <circle cx="60" cy="60" r="52" fill="none" stroke={scoreColor} strokeWidth="8"
              strokeDasharray={`${summary.overall_score * 3.267} 326.7`}
              strokeLinecap="round" transform="rotate(-90 60 60)"
              style={{ filter: `drop-shadow(0 0 8px ${scoreColor}50)` }} />
          </svg>
          <div className="score-text">
            <span className="score-number">{Math.round(summary.overall_score)}</span>
            <span className="score-label">/ 100</span>
          </div>
        </div>
        <div className="risk-header-info">
          <span className={`badge badge-${severityKey.toLowerCase()}`}>{severityKey} RISK</span>
          <h2>Risk Assessment</h2>
          <p className="signing-rec">{summary.signing_recommendation}</p>
          <div className="risk-stats">
            <div className="stat"><span className="stat-num" style={{ color: SEVERITY_COLORS.CRITICAL }}>{summary.critical_count}</span><span className="stat-label">Critical</span></div>
            <div className="stat"><span className="stat-num" style={{ color: SEVERITY_COLORS.HIGH }}>{summary.high_count}</span><span className="stat-label">High</span></div>
            <div className="stat"><span className="stat-num" style={{ color: SEVERITY_COLORS.MEDIUM }}>{summary.medium_count}</span><span className="stat-label">Medium</span></div>
            <div className="stat"><span className="stat-num" style={{ color: SEVERITY_COLORS.LOW }}>{summary.low_count}</span><span className="stat-label">Low</span></div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="charts-row">
        {/* Pie Chart */}
        <div className="chart-card glass-card">
          <h3>Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={displayPie} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                paddingAngle={3} dataKey="value" stroke="none">
                {displayPie.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#f1f5f9' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="legend">
            {displayPie.map(d => (
              <div key={d.name} className="legend-item">
                <span className="legend-dot" style={{ background: d.color }} />
                {d.name}: {d.value}
              </div>
            ))}
          </div>
        </div>

        {/* Heatmap */}
        <div className="chart-card glass-card">
          <h3>Risk Heatmap</h3>
          <p className="chart-subtitle">Severity × Likelihood</p>
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis type="number" dataKey="x" name="Likelihood" domain={[0, 100]}
                tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <YAxis type="number" dataKey="y" name="Severity" domain={[0, 10]}
                tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#f1f5f9' }}
                formatter={(val, name) => {
                  const num = typeof val === 'number' ? val : Number(val ?? 0);
                  const label = String(name ?? '');
                  return [label === 'Severity' ? `${num}/10` : `${num}%`, label];
                }} />
              
              {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'NONE'].map((level) => {
                const data = heatmapData.filter(d => d.level === level);
                if (data.length === 0) return null;
                return (
                  <Scatter key={level} name={level} data={data} fill={SEVERITY_COLORS[level] || '#6366f1'} shape="circle" />
                );
              })}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Risk by category */}
      {categories.length > 0 && (
        <div className="findings glass-card">
          <h3>Risk by Category</h3>
          <div className="category-bars">
            {categories.map(([cat, count]) => (
              <div key={cat} className="category-row">
                <span className="category-name">{cat.replace(/_/g, ' ')}</span>
                <div className="category-bar-track">
                  <div
                    className="category-bar-fill"
                    style={{ width: `${Math.min(100, (count / Math.max(risks.length, 1)) * 100)}%` }}
                  />
                </div>
                <span className="category-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key Findings */}
      {summary.key_findings.length > 0 && (
        <div className="findings glass-card">
          <h3>⚠️ Key Findings</h3>
          <ul>{summary.key_findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
