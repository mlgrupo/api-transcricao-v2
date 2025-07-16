'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function CallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    if (code) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898'}/auth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
        credentials: 'include'
      })
        .then(async res => {
          if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data?.message || data?.error || 'Erro desconhecido');
          }
          return res.json();
        })
        .then(() => {
          router.replace('/');
        })
        .catch((err) => {
          setError(err.message || 'Erro ao autenticar com o Google.');
        });
    }
  }, [searchParams, router]);

  if (error) {
    return (
      <div style={{ 
        color: '#FFE1A6', 
        textAlign: 'center', 
        marginTop: 40,
        background: '#111111',
        padding: '2rem',
        borderRadius: '12px',
        border: '1px solid rgba(76, 0, 13, 0.4)'
      }}>
        Erro: {error}
      </div>
    );
  }

  return (
    <div style={{ 
      textAlign: 'center', 
      marginTop: 40,
      background: '#111111',
      color: '#FFE1A6',
      padding: '2rem',
      borderRadius: '12px',
      border: '1px solid rgba(76, 0, 13, 0.4)'
    }}>
      Autenticando com Google...
    </div>
  );
}

export default function Callback() {
  return (
    <Suspense fallback={
      <div style={{ 
        textAlign: 'center', 
        marginTop: 40,
        background: '#111111',
        color: '#FFE1A6',
        padding: '2rem',
        borderRadius: '12px',
        border: '1px solid rgba(76, 0, 13, 0.4)'
      }}>
        Carregando...
      </div>
    }>
      <CallbackInner />
    </Suspense>
  );
} 