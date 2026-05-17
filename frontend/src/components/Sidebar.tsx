import { Shield, LayoutDashboard, Upload, Settings, HelpCircle } from 'lucide-react';
import './Sidebar.css';

interface Props {
  currentView: string;
  onNavigate: (view: string) => void;
  documentCount: number;
}

export default function Sidebar({ currentView, onNavigate, documentCount }: Props) {
  const navItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'upload', icon: Upload, label: 'Upload' },
  ];

  return (
    <nav className="sidebar" id="main-sidebar">
      <div className="sidebar-brand" onClick={() => onNavigate('dashboard')}>
        <div className="brand-icon">
          <Shield size={22} />
        </div>
        <div>
          <h1 className="brand-name">LexGuard</h1>
          <p className="brand-tag">Contract Intelligence</p>
        </div>
      </div>

      <div className="sidebar-nav">
        {navItems.map(item => (
          <button key={item.id}
            className={`nav-item ${currentView === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}>
            <item.icon size={18} />
            <span>{item.label}</span>
            {item.id === 'dashboard' && documentCount > 0 && (
              <span className="nav-count">{documentCount}</span>
            )}
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-divider" />
        <button className="nav-item" onClick={() => {}}>
          <HelpCircle size={18} /> <span>Help & Docs</span>
        </button>
        <button className={`nav-item ${currentView === 'settings' ? 'active' : ''}`} onClick={() => onNavigate('settings')}>
          <Settings size={18} /> <span>Settings</span>
        </button>
        <div className="sidebar-version">v1.0.0 · Powered by AI</div>
      </div>
    </nav>
  );
}
