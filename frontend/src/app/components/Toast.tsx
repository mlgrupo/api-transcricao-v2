'use client';

import { useEffect } from 'react';
import { FiCheckCircle, FiAlertCircle, FiInfo, FiX, FiAlertTriangle } from 'react-icons/fi';

interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  onClose: () => void;
  duration?: number;
}

export default function Toast({ message, type, onClose, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const getToastConfig = () => {
    switch (type) {
      case 'success':
        return {
          icon: FiCheckCircle,
          color: '#48bb78',
          bg: '#f0fff4',
          borderColor: '#48bb78'
        };
      case 'error':
        return {
          icon: FiAlertCircle,
          color: '#f56565',
          bg: '#fff5f5',
          borderColor: '#f56565'
        };
      case 'warning':
        return {
          icon: FiAlertTriangle,
          color: '#ed8936',
          bg: '#fffaf0',
          borderColor: '#ed8936'
        };
      case 'info':
        return {
          icon: FiInfo,
          color: '#4299e1',
          bg: '#ebf8ff',
          borderColor: '#4299e1'
        };
      default:
        return {
          icon: FiInfo,
          color: '#718096',
          bg: '#f7fafc',
          borderColor: '#718096'
        };
    }
  };

  const config = getToastConfig();
  const IconComponent = config.icon;

  return (
    <div 
      className="toast"
      style={{
        background: 'rgba(17, 17, 17, 0.85)',
        borderLeft: `4px solid ${config.borderColor}`,
        border: '2px solid #4C000D',
        borderRadius: '12px',
        padding: '1rem 1.5rem',
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
        backdropFilter: 'blur(8px)',
        maxWidth: '400px',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        position: 'fixed',
        top: 24,
        right: 32,
        zIndex: 9999,
        overflow: 'hidden',
        marginBottom: 16
      }}
    >
      {/* Icon */}
      <div style={{
        background: `${config.color}15`,
        borderRadius: '8px',
        padding: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }}>
        <IconComponent size={20} style={{ color: config.color }} />
      </div>

      {/* Message */}
      <div style={{ 
        flex: 1, 
        fontSize: '0.95rem', 
        color: '#FFE1A6',
        fontWeight: '500',
        lineHeight: 1.4
      }}>
        {message}
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          color: '#a0aec0',
          cursor: 'pointer',
          padding: '4px',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
          flexShrink: 0
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#e2e8f0';
          e.currentTarget.style.color = '#4a5568';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'none';
          e.currentTarget.style.color = '#a0aec0';
        }}
      >
        <FiX size={18} />
      </button>

      {/* Progress bar */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        height: '3px',
        background: config.color,
        animation: `shrink ${duration}ms linear forwards`
      }} />

      <style jsx>{`
        @keyframes shrink {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
} 