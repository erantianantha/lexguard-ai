import { FileText, Clock, Trash2, ChevronRight, AlertTriangle } from 'lucide-react';
import type { DocumentListItem } from '../api';
import './DocumentCard.css';

interface Props {
  doc: DocumentListItem;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const severityConfig: Record<string, { color: string; badge: string }> = {
  CRITICAL: { color: 'var(--severity-critical)', badge: 'badge-critical' },
  HIGH: { color: 'var(--severity-high)', badge: 'badge-high' },
  MEDIUM: { color: 'var(--severity-medium)', badge: 'badge-medium' },
  LOW: { color: 'var(--severity-low)', badge: 'badge-low' },
  NONE: { color: 'var(--severity-none)', badge: 'badge-none' },
};

export default function DocumentCard({ doc, onSelect, onDelete }: Props) {
  const sev = severityConfig[doc.overall_severity] || severityConfig.NONE;
  const isProcessing = ['processing', 'extracting', 'analyzing', 'uploading'].includes(doc.status);
  const isFailed = doc.status === 'failed';

  return (
    <div className="doc-card glass-card animate-fade-in" onClick={() => !isProcessing && onSelect(doc.id)}>
      <div className="doc-card-left">
        <div className="doc-icon" style={{ borderColor: sev.color }}>
          <FileText size={20} style={{ color: sev.color }} />
        </div>
        <div className="doc-info">
          <h4 className="doc-name">{doc.filename}</h4>
          <div className="doc-meta">
            <span><Clock size={12} /> {new Date(doc.upload_date).toLocaleDateString()}</span>
            <span>{doc.file_type.toUpperCase()}</span>
            {doc.clause_count > 0 && <span>{doc.clause_count} clauses</span>}
          </div>
        </div>
      </div>
      <div className="doc-card-right">
        {isProcessing && (
          <div className="doc-status processing">
            <div className="pulse-dot" /> Analyzing...
          </div>
        )}
        {isFailed && (
          <div className="doc-status failed">
            <AlertTriangle size={14} /> Failed
          </div>
        )}
        {doc.status === 'completed' && (
          <>
            <div className="risk-score-mini" style={{ '--score-color': sev.color } as any}>
              <svg viewBox="0 0 36 36" className="risk-ring">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none" stroke={sev.color} strokeWidth="3"
                  strokeDasharray={`${doc.overall_risk_score}, 100`}
                  strokeLinecap="round" />
              </svg>
              <span className="risk-number">{Math.round(doc.overall_risk_score)}</span>
            </div>
            <span className={`badge ${sev.badge}`}>{doc.overall_severity}</span>
          </>
        )}
        <button className="doc-delete" onClick={(e) => { e.stopPropagation(); onDelete(doc.id); }}
          title="Delete document">
          <Trash2 size={14} />
        </button>
        <ChevronRight size={16} className="doc-chevron" />
      </div>
    </div>
  );
}
