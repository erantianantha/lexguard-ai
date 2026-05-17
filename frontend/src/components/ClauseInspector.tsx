import { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, Lightbulb, Scale, Zap, Shield } from 'lucide-react';
import type { 
  ExtractedClause, RiskAnalysis, ImplicationsResult, AmbiguityResult,
  MarketBenchmarkResult, PrivacyComplianceResult, RelationshipMappingResult, NegotiationGuidanceResult 
} from '../api';
import './ClauseInspector.css';

interface Props {
  clauses: ExtractedClause[];
  risks: RiskAnalysis[];
  implications: ImplicationsResult[];
  ambiguities: AmbiguityResult[];
  marketBenchmarks?: MarketBenchmarkResult[];
  privacyCompliance?: PrivacyComplianceResult[];
  relationships?: RelationshipMappingResult[];
  negotiationGuidance?: NegotiationGuidanceResult[];
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e', NONE: '#6366f1',
};

export default function ClauseInspector({ 
  clauses, risks, implications, ambiguities,
  marketBenchmarks = [], privacyCompliance = [], relationships = [], negotiationGuidance = []
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const riskMap = new Map(risks.map(r => [r.clause_id, r]));
  const implMap = new Map(implications.map(i => [i.clause_id, i]));
  const ambMap = new Map(ambiguities.map(a => [a.clause_id, a]));
  const benchMap = new Map(marketBenchmarks.map(b => [b.clause_id, b]));
  const privMap = new Map(privacyCompliance.map(p => [p.clause_id, p]));
  const relMap = new Map(relationships.map(r => [r.clause_id, r]));
  const negMap = new Map(negotiationGuidance.map(n => [n.clause_id, n]));

  const sorted = [...clauses].sort((a, b) => {
    const ra = riskMap.get(a.id)?.severity_score || 0;
    const rb = riskMap.get(b.id)?.severity_score || 0;
    return rb - ra;
  });

  const filtered = filter === 'all' ? sorted :
    sorted.filter(c => riskMap.get(c.id)?.severity_level === filter);

  return (
    <div className="clause-inspector animate-slide-up">
      <div className="inspector-header">
        <h3><Scale size={18} /> Clause Analysis ({clauses.length} clauses)</h3>
        <div className="filter-tabs">
          {['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(f => (
            <button key={f} className={`filter-tab ${filter === f ? 'active' : ''}`}
              style={f !== 'all' ? { '--tab-color': SEVERITY_COLORS[f] } as any : {}}
              onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="clauses-list">
        {filtered.map(clause => {
          const risk = riskMap.get(clause.id);
          const impl = implMap.get(clause.id);
          const amb = ambMap.get(clause.id);
          const bench = benchMap.get(clause.id);
          const priv = privMap.get(clause.id);
          const rel = relMap.get(clause.id);
          const neg = negMap.get(clause.id);
          const isExpanded = expandedId === clause.id;
          const color = SEVERITY_COLORS[risk?.severity_level || 'NONE'];

          return (
            <div key={clause.id} className={`clause-item glass-card ${isExpanded ? 'expanded' : ''}`}
              style={{ '--clause-color': color } as any}>
              <div className="clause-header" onClick={() => setExpandedId(isExpanded ? null : clause.id)}>
                <div className="clause-severity-bar" style={{ background: color }} />
                <div className="clause-header-content">
                  <div className="clause-title-row">
                    <span className="clause-ref">{clause.section_reference || clause.id}</span>
                    <span className={`badge badge-${(risk?.severity_level || 'none').toLowerCase()}`}>
                      {risk?.severity_level || 'N/A'} · {risk?.severity_score?.toFixed(1) || '—'}/10
                    </span>
                    <span className="clause-type-badge">{clause.type.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="clause-preview">{clause.text.slice(0, 150)}...</p>
                </div>
                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </div>

              {isExpanded && (
                <div className="clause-details animate-fade-in">
                  {/* Full Clause Text */}
                  <div className="detail-section">
                    <h4>📄 Full Clause Text</h4>
                    <blockquote>{clause.text}</blockquote>
                  </div>

                  {/* Risk Analysis */}
                  {risk && (
                    <div className="detail-section">
                      <h4><AlertTriangle size={14} /> Risk Analysis</h4>
                      <p>{risk.severity_reasoning}</p>
                      <div className="detail-grid">
                        <div className="detail-item">
                          <span className="detail-label">Category</span>
                          <span>{risk.primary_category.replace(/_/g, ' ')}</span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Likelihood</span>
                          <span>{risk.likelihood_percentage}%</span>
                        </div>
                        {risk.financial_exposure && (
                          <div className="detail-item">
                            <span className="detail-label">Financial Exposure</span>
                            <span>{risk.financial_exposure.currency} {risk.financial_exposure.amount?.toLocaleString() || 'Variable'}</span>
                          </div>
                        )}
                      </div>
                      {risk.market_comparison && (
                        <div className="market-comparison">
                          <span className="detail-label">Market Comparison</span>
                          <p>{risk.market_comparison}</p>
                        </div>
                      )}
                      {risk.user_impact && (
                        <div className="impact-cards">
                          {risk.user_impact.financial && <div className="impact-card"><Zap size={14} /> <span><strong>Financial:</strong> {risk.user_impact.financial}</span></div>}
                          {risk.user_impact.operational && <div className="impact-card"><Shield size={14} /> <span><strong>Operational:</strong> {risk.user_impact.operational}</span></div>}
                          {risk.user_impact.legal && <div className="impact-card"><Scale size={14} /> <span><strong>Legal:</strong> {risk.user_impact.legal}</span></div>}
                        </div>
                      )}
                      {risk.contributing_factors.length > 0 && (
                        <div className="contributing-factors">
                          <span className="detail-label">Risk Factors</span>
                          {risk.contributing_factors.map((f, i) => (
                            <div key={i} className="factor-card">
                              <div className="factor-header">
                                <strong>{f.factor}</strong>
                                <span className="factor-pct">{f.contribution}%</span>
                              </div>
                              <p>{f.explanation}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recommendations */}
                  {risk && risk.recommendations.length > 0 && (
                    <div className="detail-section">
                      <h4><Lightbulb size={14} /> Recommendations</h4>
                      {risk.recommendations.map((r, i) => (
                        <div key={i} className="rec-card">
                          <p className="rec-action">{r.action}</p>
                          {r.suggested_language && (
                            <div className="rec-language">
                              <span className="detail-label">Suggested Language:</span>
                              <code>{r.suggested_language}</code>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Implications */}
                  {impl && impl.scenarios.length > 0 && (
                    <div className="detail-section">
                      <h4>🔮 Scenario Analysis</h4>
                      {impl.scenarios.map((s, i) => (
                        <div key={i} className="scenario-card">
                          <p><strong>Trigger:</strong> {s.trigger}</p>
                          <p><strong>Legal:</strong> {s.legal_implications}</p>
                          <p><strong>Timeline:</strong> {s.timeline}</p>
                          {s.mitigations.length > 0 && (
                            <div className="mitigations">
                              <strong>Mitigations:</strong>
                              <ul>{s.mitigations.map((m, j) => <li key={j}>{m}</li>)}</ul>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Ambiguities */}
                  {amb && amb.ambiguities.length > 0 && (
                    <div className="detail-section">
                      <h4>🔍 Ambiguities Detected</h4>
                      {amb.ambiguities.map((a: any, i: number) => (
                        <div key={i} className="ambiguity-card">
                          <p><strong>Term:</strong> "{a.term}"</p>
                          <p>{a.issue}</p>
                          {a.exploitation_risk && <p className="exploit-warning">⚠️ {a.exploitation_risk}</p>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Market Benchmark */}
                  {bench && (
                    <div className="detail-section">
                      <h4>📊 Market Benchmark</h4>
                      <div className="benchmark-card">
                        <div className="benchmark-header">
                          <span className={`badge badge-${bench.deviation_level.toLowerCase()}`}>{bench.deviation_level}</span>
                          <span>{bench.prevalence_percentage}% Market Prevalence</span>
                        </div>
                        <p className="market-norm"><strong>Norm:</strong> {bench.market_norm_description}</p>
                        {bench.fair_alternative && (
                          <div className="fair-alternative">
                            <strong>Alternative:</strong> <code>{bench.fair_alternative}</code>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Privacy & Compliance */}
                  {priv && (priv.violations.length > 0 || !priv.gdpr_compliant || !priv.ccpa_compliant) && (
                    <div className="detail-section">
                      <h4>🛡️ Privacy & Compliance</h4>
                      <div className="privacy-card">
                        <div className="compliance-badges">
                          <span className={`badge ${priv.gdpr_compliant ? 'badge-low' : 'badge-critical'}`}>GDPR {priv.gdpr_compliant ? '✓' : '✗'}</span>
                          <span className={`badge ${priv.ccpa_compliant ? 'badge-low' : 'badge-critical'}`}>CCPA {priv.ccpa_compliant ? '✓' : '✗'}</span>
                        </div>
                        {priv.violations.length > 0 && (
                          <ul className="violations-list">
                            {priv.violations.map((v, i) => <li key={i}>{v}</li>)}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Relationship Mapping */}
                  {rel && (rel.depends_on.length > 0 || rel.conflicts_with.length > 0) && (
                    <div className="detail-section">
                      <h4>🔗 Clause Relationships</h4>
                      <div className="relationships-card">
                        {rel.depends_on.length > 0 && (
                          <p><strong>Depends On:</strong> {rel.depends_on.join(', ')}</p>
                        )}
                        {rel.conflicts_with.length > 0 && (
                          <p><strong>Conflicts With:</strong> {rel.conflicts_with.join(', ')}</p>
                        )}
                        {rel.compound_risk_description && (
                          <p className="compound-risk">⚠️ {rel.compound_risk_description}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Negotiation Guidance */}
                  {neg && (neg.leverage_points.length > 0 || neg.suggested_redline) && (
                    <div className="detail-section">
                      <h4>🤝 Negotiation Tactics</h4>
                      <div className="negotiation-card">
                        {neg.leverage_points.length > 0 && (
                          <div className="leverage-points">
                            <strong>Leverage:</strong>
                            <ul>{neg.leverage_points.map((lp, i) => <li key={i}>{lp}</li>)}</ul>
                          </div>
                        )}
                        {neg.trade_off_options.length > 0 && (
                          <div className="trade-offs">
                            <strong>Trade-offs:</strong>
                            <ul>{neg.trade_off_options.map((to, i) => <li key={i}>{to}</li>)}</ul>
                          </div>
                        )}
                        {neg.walk_away_threshold && (
                          <p className="walk-away"><strong>Walk Away:</strong> {neg.walk_away_threshold}</p>
                        )}
                        {neg.suggested_redline && (
                          <div className="redline">
                            <strong>Redline:</strong>
                            <code>{neg.suggested_redline}</code>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Key Terms */}
                  {clause.key_terms.length > 0 && (
                    <div className="key-terms">
                      {clause.key_terms.map((t, i) => <span key={i} className="term-badge">{t}</span>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
