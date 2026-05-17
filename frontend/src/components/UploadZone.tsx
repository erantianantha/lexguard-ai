import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, AlertCircle, CheckCircle, Loader, FileText } from 'lucide-react';
import { uploadDocument } from '../api';
import './UploadZone.css';

interface Props {
  onUploadComplete: (docId: string) => void;
}

const ACCEPTED_TYPES = [
  { label: 'PDF', mime: 'application/pdf', ext: ['.pdf'] },
  { label: 'DOCX', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: ['.docx'] },
  { label: 'TXT', mime: 'text/plain', ext: ['.txt'] },
  { label: 'JPG', mime: 'image/jpeg', ext: ['.jpg', '.jpeg'] },
  { label: 'PNG', mime: 'image/png', ext: ['.png'] },
];

export default function UploadZone({ onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState('');

  const onDrop = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    const file = files[0];

    // Client-side size check (50 MB)
    if (file.size > 50 * 1024 * 1024) {
      setError(`File "${file.name}" is too large. Maximum size is 50 MB.`);
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');
    setFileName(file.name);
    setProgress(20);

    try {
      setProgress(50);
      const result = await uploadDocument(file);
      setProgress(100);
      setSuccess(`"${file.name}" uploaded successfully. AI analysis is starting...`);
      setTimeout(() => onUploadComplete(result.document_id), 800);
    } catch (err: any) {
      const msg = err.message || 'Upload failed. Please check your connection and try again.';
      setError(msg);
      setProgress(0);
    } finally {
      setUploading(false);
    }
  }, [onUploadComplete]);

  const acceptObj = Object.fromEntries(
    ACCEPTED_TYPES.map(t => [t.mime, t.ext])
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    maxFiles: 1,
    accept: acceptObj,
    disabled: uploading,
  });

  const zoneClass = [
    'upload-zone glass-card',
    isDragActive && !isDragReject ? 'drag-active' : '',
    isDragReject ? 'drag-reject' : '',
    uploading ? 'uploading' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className="upload-zone-wrapper animate-fade-in">
      <div
        {...getRootProps()}
        className={zoneClass}
        role="button"
        aria-label="Upload contract document — click or drag and drop"
        aria-describedby="upload-hint upload-formats"
        tabIndex={0}
      >
        <input
          {...getInputProps()}
          id="file-upload-input"
          aria-label="Select a contract file to upload"
        />
        <div className="upload-zone-content">
          {uploading ? (
            <>
              <Loader className="upload-icon spinning" size={48} aria-hidden="true" />
              <h3>Uploading & Analysing…</h3>
              <p aria-live="polite">{fileName}</p>
              <div
                className="progress-bar"
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Upload progress: ${progress}%`}
              >
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p>AI is analysing your contract — live progress will appear shortly</p>
            </>
          ) : isDragReject ? (
            <>
              <AlertCircle className="upload-icon" size={48} color="#ef4444" aria-hidden="true" />
              <h3>Unsupported File Type</h3>
              <p>Please upload a PDF, DOCX, TXT, JPG, or PNG file.</p>
            </>
          ) : (
            <>
              <div className="upload-icon-wrapper" aria-hidden="true">
                {isDragActive ? <FileText size={48} /> : <Upload size={40} />}
              </div>
              <h3>{isDragActive ? 'Drop your contract here' : 'Upload a Contract'}</h3>
              <p id="upload-hint">Drag &amp; drop a document or click to browse</p>
              <div id="upload-formats" className="file-types">
                {ACCEPTED_TYPES.map(t => (
                  <span key={t.label} className="file-type-badge">{t.label}</span>
                ))}
              </div>
              <p className="upload-hint">Maximum file size: 50 MB</p>
            </>
          )}
        </div>
      </div>

      {error && (
        <div
          className="upload-message error animate-fade-in"
          role="alert"
          aria-live="assertive"
        >
          <AlertCircle size={18} aria-hidden="true" /> {error}
        </div>
      )}
      {success && (
        <div
          className="upload-message success animate-fade-in"
          role="status"
          aria-live="polite"
        >
          <CheckCircle size={18} aria-hidden="true" /> {success}
        </div>
      )}
    </div>
  );
}
