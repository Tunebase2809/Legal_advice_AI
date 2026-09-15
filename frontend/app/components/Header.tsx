import React from 'react';

type HeaderProps = {
  title: string;
  iconClass: string;
  onBack: () => void;
};

export const Header: React.FC<HeaderProps> = ({ title, iconClass, onBack }) => {
  return (
    <header className="app-header" style={{ padding: '12px 20px', backgroundColor: '#fff', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', width: '100%', flexShrink: 0 }}>
      <button onClick={onBack} className="header-back-btn" title="Quay lại Dashboard">
        <i className="fa-solid fa-arrow-left"></i> Quay lại Dashboard
      </button>
      <div className="header-content">
        <h1 style={{ fontSize: '1.2rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontWeight: 'bold' }}>
          <i className={iconClass}></i> {title}
        </h1>
      </div>
    </header>
  );
};
