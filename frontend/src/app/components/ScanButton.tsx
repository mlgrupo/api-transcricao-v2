'use client';

import { FiSearch } from 'react-icons/fi';

interface ScanButtonProps {
  onScan: () => void;
  loading?: boolean;
}

export default function ScanButton({ onScan, loading = false }: ScanButtonProps) {
  return (
    <button
      onClick={onScan}
      className="button"
      style={{
        background: '#4C000D',
        color: '#FFE1A6',
        border: '2px solid #4C000D',
        borderRadius: 12,
        fontWeight: 700,
        fontSize: 16,
        padding: '0.8rem 1.2rem',
        display: 'flex',
        alignItems: 'center',
        boxShadow: '0 4px 16px #4C000D33',
        transition: 'box-shadow 0.2s, filter 0.2s',
        cursor: loading ? 'not-allowed' : 'pointer',
        gap: 8,
        opacity: loading ? 0.7 : 1
      }}
      disabled={loading}
    >
      <FiSearch size={18} style={{ marginRight: 6 }} />
      {loading ? 'Procurando...' : 'Procurar Novos Vídeos'}
    </button>
  );
}
