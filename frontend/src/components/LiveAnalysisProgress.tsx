import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { subscribeDocumentProgress, type ProgressEvent } from '../api';
import './LiveAnalysisProgress.css';

interface Props {
  documentId: string;
  onComplete?: () => void;
}

const STEPS = [
  { id: 'parse', label: 'Parse document' },
  { id: 'rag', label: 'Build knowledge index (RAG)' },
  { id: 'extract', label: 'Extract clauses' },
  { id: 'analyze', label: 'Score risks' },
  { id: 'deep', label: 'Deep analysis' },
  { id: 'report', label: 'Generate report' },
  { id: 'done', label: 'Complete' },
];

function stepIndex(step: string): number {
  const i = STEPS.findIndex((s) => s.id === step);
  return i >= 0 ? i : 0;
}

export default function LiveAnalysisProgress({ documentId, onComplete }: Props) {
  const [percent, setPercent] = useState(0);
  const [message, setMessage] = useState('Connecting to analysis stream…');
  const [currentStep, setCurrentStep] = useState('parse');
  const [logs, setLogs] = useState<ProgressEvent[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const completedRef = useRef(false);

  useEffect(() => {
    completedRef.current = false;
    setPercent(0);
    setMessage('Starting analysis…');
    setLogs([]);

    const unsubscribe = subscribeDocumentProgress(documentId, (event) => {
      setLogs((prev) => [...prev, event].slice(-40));
      if (event.percent != null) setPercent(event.percent);
      if (event.message) setMessage(event.message);
      if (event.step) setCurrentStep(event.step);

      if (
        !completedRef.current &&
        (event.status === 'completed' || event.status === 'failed' || event.type === 'error')
      ) {
        completedRef.current = true;
        onComplete?.();
      }
    });

    return unsubscribe;
  }, [documentId, onComplete]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const activeIdx = stepIndex(currentStep);

  return (
    <div className="live-progress animate-fade-in">
      <div className="live-progress-header glass-card">
        <div className="live-progress-title">
          <Loader2 className="spinning" size={22} />
          <div>
            <h3>Analyzing contract</h3>
            <p>{message}</p>
          </div>
        </div>
        <div className="live-percent">{Math.round(percent)}%</div>
      </div>

      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="live-steps glass-card">
        {STEPS.map((step, idx) => {
          const done = idx < activeIdx || (percent >= 100 && step.id === 'done');
          const active = step.id === currentStep && percent < 100;
          return (
            <div key={step.id} className={`live-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
              {done ? <CheckCircle2 size={18} /> : active ? <Loader2 size={18} className="spinning" /> : <Circle size={18} />}
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>

      <div className="live-log glass-card">
        <div className="live-log-title">Live updates</div>
        <div className="live-log-body">
          {logs.map((log, i) => (
            <div key={`${log.timestamp}-${i}`} className="live-log-line">
              <span className="log-time">
                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
              </span>
              <span className="log-msg">{log.message}</span>
              {log.detail && <span className="log-detail">{log.detail}</span>}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
}
