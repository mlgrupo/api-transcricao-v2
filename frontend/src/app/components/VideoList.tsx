'use client';

import React, { useState } from 'react';
import { FiFileText, FiPlay, FiClock, FiCheckCircle, FiAlertCircle, FiExternalLink, FiVideo, FiRefreshCw, FiSearch, FiFilter } from 'react-icons/fi';

interface Video {
  id: number;
  videoId: string;
  videoName: string;
  status: string;
  progress?: number;
  etapaAtual?: string;
  createdAt: string;
  transcription?: string;
  googleDocsUrl?: string;
}

interface VideoListProps {
  videos: Video[];
  onRefresh: () => void;
}

const STATUS_ORDER = {
  processing: 0,
  pending: 1,
  completed: 2,
  failed: 3,
  error: 4,
  default: 5
};

const PAGE_SIZE = 6;

const STATUS_THEME = {
  completed: { icon: FiCheckCircle, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'CONCLUÍDO' },
  processing: { icon: FiPlay, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'PROCESSANDO' },
  pending: { icon: FiClock, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'PENDENTE' },
  failed: { icon: FiAlertCircle, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'ERRO' },
  error: { icon: FiAlertCircle, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'ERRO' },
  default: { icon: FiClock, color: '#FFE1A6', bg: '#111111', border: '#4C000D', text: 'PENDENTE' }
};

export default function VideoList({ videos, onRefresh }: VideoListProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [refreshing, setRefreshing] = useState(false);

  // Ordenar vídeos: processing > pending > completed > outros
  const orderedVideos = [...videos].sort((a, b) => {
    const statusA = a.status || 'pending';
    const statusB = b.status || 'pending';
    const orderA = STATUS_ORDER[statusA as keyof typeof STATUS_ORDER] ?? STATUS_ORDER.default;
    const orderB = STATUS_ORDER[statusB as keyof typeof STATUS_ORDER] ?? STATUS_ORDER.default;
    if (orderA !== orderB) return orderA - orderB;
    return (b.createdAt || '').localeCompare(a.createdAt || '');
  });

  // Filtro e busca
  const filtered = orderedVideos.filter(v => {
    const status = v.status || 'pending';
    const matchesStatus = !statusFilter ||
      (statusFilter === 'pending' ? (status === 'pending' || status === '' || status === undefined) : status === statusFilter);
    return matchesStatus && (!search || v.videoName.toLowerCase().includes(search.toLowerCase()));
  });

  // Paginação
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE) || 1;
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setTimeout(() => setRefreshing(false), 1000);
  };

  const getStatusInfo = (status: string) => STATUS_THEME[status as keyof typeof STATUS_THEME] || STATUS_THEME.default;

  if (videos.length === 0) {
    return (
      <div className="card text-center fade-in-up" style={{ padding: '4rem 2rem' }}>
        <div style={{ 
          fontSize: '4rem', 
          color: '#667eea', 
          marginBottom: '1.5rem',
          opacity: 0.7
        }}>
          <FiFileText size={80} />
        </div>
        <h3 style={{ 
          margin: '0 0 1rem 0', 
          color: '#2d3748', 
          fontSize: '1.75rem',
          fontWeight: '600'
        }}>
          Nenhum vídeo encontrado
        </h3>
        <p style={{ 
          margin: '0 0 2rem 0', 
          color: '#718096', 
          fontSize: '1.1rem',
          maxWidth: '400px',
          marginLeft: 'auto',
          marginRight: 'auto'
        }}>
          Nenhum vídeo encontrado no momento. Novos vídeos serão detectados automaticamente.
        </p>
        <button 
          onClick={handleRefresh} 
          className="button success"
          disabled={refreshing}
        >
          {refreshing ? (
            <>
              <div className="loading" style={{ width: '16px', height: '16px' }}></div>
              Atualizando...
            </>
          ) : (
            <>
              <FiRefreshCw size={18} />
              Atualizar Lista
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="fade-in-up">
      {/* Header com filtros */}
      <div className="card mb-4" style={{ 
        background: '#111111',
        border: '2px solid #4C000D',
        padding: '2rem',
        color: '#FFE1A6'
      }}>
        <div className="flex-between mb-4" style={{ flexWrap: 'wrap', gap: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ 
              margin: '0 0 0.5rem 0', 
              color: '#FFE1A6', 
              fontSize: '1.75rem', 
              fontWeight: '700' 
            }}>
              Transcrições
            </h3>
            <p style={{ 
              margin: 0, 
              color: '#FFE1A6bb', 
              fontSize: '0.95rem' 
            }}>
              {filtered.length} vídeo{filtered.length !== 1 ? 's' : ''} encontrado{filtered.length !== 1 ? 's' : ''}
            </p>
            <p style={{ margin: 0, color: '#FFE1A677', fontSize: '0.93rem', marginTop: 2 }}>Gerencie e acompanhe suas transcrições.</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button 
              onClick={handleRefresh} 
              className="button" 
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#4C000D', color: '#FFE1A6', border: '2px solid #4C000D' }}
              disabled={refreshing}
            >
              {refreshing ? (
                <>
                  <div className="loading" style={{ width: '16px', height: '16px' }}></div>
                  Atualizando...
                </>
              ) : (
                <>
                  <FiRefreshCw size={16} />
                  Atualizar
                </>
              )}
            </button>
          </div>
        </div>
        <div className="flex" style={{ gap: 16, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 250 }}>
            <FiSearch 
              size={18} 
              style={{ 
                position: 'absolute', 
                left: 16, 
                top: '50%', 
                transform: 'translateY(-50%)', 
                color: '#FFE1A6aa' 
              }} 
            />
            <input
              type="text"
              placeholder="Buscar por título..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="input"
              style={{ 
                paddingLeft: '3rem',
                background: '#191919',
                border: '2px solid #4C000D',
                color: '#FFE1A6'
              }}
            />
          </div>
          <div style={{ position: 'relative', minWidth: 180 }}>
            <FiFilter 
              size={18} 
              style={{ 
                position: 'absolute', 
                left: 16, 
                top: '50%', 
                transform: 'translateY(-50%)', 
                color: '#FFE1A6aa',
                zIndex: 1
              }} 
            />
            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
              className="input"
              style={{ 
                paddingLeft: '3rem',
                background: '#191919',
                border: '2px solid #4C000D',
                color: '#FFE1A6',
                cursor: 'pointer'
              }}
            >
              <option value="">Todos os status</option>
              <option value="completed">Concluídos</option>
              <option value="processing">Processando</option>
              <option value="pending">Pendentes</option>
              <option value="failed">Falharam</option>
            </select>
          </div>
        </div>
      </div>
      {/* Grid de vídeos */}
      <div className="video-grid-modern" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginTop: 18, width: '100%', maxWidth: '100%' }}>
        {paginated.map((video) => {
          const isProcessing = video.status === 'processing';
          const isCompleted = video.status === 'completed';
          const videoDriveUrl = `https://drive.google.com/file/d/${video.videoId}/view`;
          const docUrl = video.googleDocsUrl || '';
          const statusInfo = getStatusInfo(video.status || 'pending');
          const StatusIcon = statusInfo.icon;
          // Borda colorida conforme status
          return (
            <div key={video.videoId} className="card fade-in-up" style={{
              width: '100%',
              minHeight: 170,
              border: `3px solid ${statusInfo.border}`,
              background: statusInfo.bg,
              color: statusInfo.color,
              boxShadow: '0 8px 32px rgba(76, 0, 13, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '1.5rem 1.3rem 1.3rem 1.3rem',
              position: 'relative',
              transition: 'box-shadow 0.2s, border 0.2s, transform 0.2s',
              marginBottom: 8,
              borderRadius: 16
            }}
            onMouseOver={e => { 
              e.currentTarget.style.transform = 'translateY(-4px)'; 
              e.currentTarget.style.boxShadow = '0 12px 40px rgba(76, 0, 13, 0.4)'; 
            }}
            onMouseOut={e => { 
              e.currentTarget.style.transform = 'none'; 
              e.currentTarget.style.boxShadow = '0 8px 32px rgba(76, 0, 13, 0.3)'; 
            }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <FiFileText size={24} style={{ color: '#FFE1A6', marginRight: 6 }} />
                <span style={{ fontWeight: 700, fontSize: 18, color: '#FFE1A6', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{video.videoName}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700, fontSize: 13, color: statusInfo.color, background: '#4C000D', borderRadius: 10, padding: '4px 12px', border: '2px solid #4C000D', marginLeft: 8 }}>
                  <StatusIcon size={15} style={{ marginRight: 3 }} />
                  {statusInfo.text}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <a href={videoDriveUrl} target="_blank" rel="noopener noreferrer" className="button" style={{ background: '#4C000D', color: '#FFE1A6', border: '2px solid #4C000D', fontWeight: 700, fontSize: 15, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 12, padding: '0.8rem' }}>
                  <FiPlay size={16} /> Ver Vídeo
                </a>
                {isCompleted && docUrl && (
                  <a href={docUrl} target="_blank" rel="noopener noreferrer" className="button" style={{ background: '#111111', color: '#FFE1A6', border: '2px solid #4C000D', fontWeight: 700, fontSize: 15, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 12, padding: '0.8rem' }}>
                    <FiFileText size={16} /> Transcrição
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {/* Paginação */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 24 }}>
          {Array.from({ length: totalPages }, (_, i) => (
            <button
              key={i}
              className="button"
              style={{ background: page === i + 1 ? '#4C000D' : '#111111', color: '#FFE1A6', border: '2px solid #4C000D', fontWeight: 700, fontSize: 15, minWidth: 38 }}
              onClick={() => setPage(i + 1)}
            >
              {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
} 