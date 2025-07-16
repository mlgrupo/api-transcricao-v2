'use client';

import { FiWifi, FiWifiOff, FiAlertTriangle, FiLoader } from 'react-icons/fi';

interface ApiStatusProps {
  status: 'online' | 'offline' | 'error' | 'checking';
}

export default function ApiStatus({ status }: ApiStatusProps) {
  const getStatusInfo = () => {
    switch (status) {
      case 'online':
        return { 
          text: 'API Online', 
          className: 'status success',
          icon: FiWifi,
          color: '#28a745'
        };
      case 'offline':
        return { 
          text: 'API Offline', 
          className: 'status error',
          icon: FiWifiOff,
          color: '#dc3545'
        };
      case 'error':
        return { 
          text: 'Erro na API', 
          className: 'status error',
          icon: FiAlertTriangle,
          color: '#dc3545'
        };
      case 'checking':
        return { 
          text: 'Verificando...', 
          className: 'status info',
          icon: FiLoader,
          color: '#17a2b8'
        };
      default:
        return { 
          text: 'Desconhecido', 
          className: 'status warning',
          icon: FiAlertTriangle,
          color: '#ffc107'
        };
    }
  };

  const statusInfo = getStatusInfo();
  const StatusIcon = statusInfo.icon;

  return (
    <div className="flex-center" style={{ marginTop: '1rem' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        padding: '0.5rem 1rem',
        borderRadius: '25px',
        background: 'rgba(17, 17, 17, 0.85)',
        border: '2px solid #4C000D',
        boxShadow: '0 2px 8px #4C000D33',
        width: '100%',
        maxWidth: 220,
        margin: '0 auto'
      }}>
        <div style={{
          animation: status === 'checking' ? 'spin 1s linear infinite' : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <StatusIcon size={16} style={{ color: '#FFE1A6' }} />
        </div>
        <span className={statusInfo.className} style={{ fontSize: '0.8rem', color: '#FFE1A6', textAlign: 'center', width: '100%' }}>
          {statusInfo.text}
        </span>
      </div>
    </div>
  );
} 