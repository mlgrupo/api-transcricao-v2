'use client';

import { FiCheckCircle, FiClock, FiAlertCircle, FiPlay, FiFileText } from 'react-icons/fi';

interface StatsData {
  total: number;
  completed: number;
  processing: number;
  pending: number;
  failed: number;
  error: number;
}

interface StatsCardsProps {
  stats: StatsData;
  loading?: boolean;
}

export default function StatsCards({ stats, loading = false }: StatsCardsProps) {
  if (loading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: 36, width: '100%' }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="card" style={{ 
            padding: '1.5rem', 
            textAlign: 'center', 
            minHeight: '140px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            <div className="skeleton" style={{ 
              width: '48px', 
              height: '48px', 
              borderRadius: '12px',
              marginBottom: '1rem'
            }}></div>
            <div className="skeleton" style={{ 
              height: '2rem', 
              width: '60%', 
              marginBottom: '0.5rem',
              borderRadius: '8px'
            }}></div>
            <div className="skeleton" style={{ 
              height: '1rem', 
              width: '40%', 
              borderRadius: '6px'
            }}></div>
          </div>
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: 'Total',
      value: stats.total,
      icon: FiFileText,
      color: '#FFE1A6',
      bg: '#111111',
      borderColor: '#4C000D',
      delay: 0,
      description: 'Vídeos no sistema'
    },
    {
      title: 'Concluídas',
      value: stats.completed,
      icon: FiCheckCircle,
      color: '#FFE1A6',
      bg: '#111111',
      borderColor: '#4C000D',
      delay: 0.1,
      description: 'Transcrições finalizadas'
    },
    {
      title: 'Processando',
      value: stats.processing,
      icon: FiPlay,
      color: '#FFE1A6',
      bg: '#111111',
      borderColor: '#4C000D',
      delay: 0.2,
      description: 'Em processamento'
    },
    {
      title: 'Pendentes',
      value: stats.pending,
      icon: FiClock,
      color: '#FFE1A6',
      bg: '#111111',
      borderColor: '#4C000D',
      delay: 0.3,
      description: 'Aguardando processamento'
    },
    {
      title: 'Falharam',
      value: stats.failed + stats.error,
      icon: FiAlertCircle,
      color: '#FFE1A6',
      bg: '#111111',
      borderColor: '#4C000D',
      delay: 0.4,
      description: 'Com erro'
    }
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: 36, width: '100%' }}>
      {cards.map((card, index) => {
        const IconComponent = card.icon;
        return (
          <div 
            key={index} 
            className="card fade-in-up" 
            style={{ 
              padding: '1.5rem', 
              textAlign: 'center',
              minHeight: '140px',
              background: card.bg,
              border: `2px solid ${card.borderColor}`,
              animationDelay: `${card.delay}s`,
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              color: card.color
            }}
          >
            <div style={{ position: 'relative', zIndex: 1, width: '100%' }}>
              {/* Icon */}
              <div style={{ 
                color: card.color, 
                margin: '0 auto 1rem',
                display: 'flex',
                justifyContent: 'center',
                fontSize: '2rem',
                background: '#4C000D22',
                borderRadius: '12px',
                padding: '12px',
                alignItems: 'center',
                border: `2px solid #4C000D`,
                width: 'fit-content'
              }}>
                <IconComponent size={24} />
              </div>
              {/* Value */}
              <div style={{ 
                fontSize: '2rem', 
                fontWeight: '800', 
                color: card.color, 
                marginBottom: '0.5rem',
                textShadow: '0 2px 4px #000a',
                lineHeight: 1
              }}>
                {card.value.toLocaleString()}
              </div>
              {/* Title */}
              <div style={{ 
                fontSize: '1rem', 
                color: card.color, 
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginBottom: '0.25rem'
              }}>
                {card.title}
              </div>
              {/* Description */}
              <div style={{ 
                fontSize: '0.875rem', 
                color: '#FFE1A6bb', 
                fontWeight: '500',
                lineHeight: 1.4
              }}>
                {card.description}
              </div>
              {/* Progress bar for completed */}
              {card.title === 'Concluídas' && stats.total > 0 && (
                <div style={{ 
                  marginTop: '1rem',
                  background: '#222',
                  borderRadius: '10px',
                  height: '6px',
                  overflow: 'hidden',
                  border: '1px solid #4C000D',
                  width: '100%'
                }}>
                  <div style={{
                    width: `${(stats.completed / stats.total) * 100}%`,
                    height: '100%',
                    background: '#FFE1A6',
                    borderRadius: '10px',
                    transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: `0 0 10px #FFE1A6aa`
                  }} />
                </div>
              )}
              {/* Processing animation for processing */}
              {card.title === 'Processando' && stats.processing > 0 && (
                <div style={{ 
                  marginTop: '1rem',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  <div className="loading" style={{ 
                    width: '16px', 
                    height: '16px',
                    borderColor: '#FFE1A6',
                    borderTopColor: '#4C000D'
                  }}></div>
                  <span style={{ 
                    fontSize: '0.875rem', 
                    color: card.color, 
                    fontWeight: '600' 
                  }}>
                    Ativo
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
} 