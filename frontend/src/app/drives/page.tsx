"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FaGoogleDrive } from 'react-icons/fa';
import { FiRefreshCw, FiLink, FiX } from 'react-icons/fi';
import { fetchWithAuth } from '../utils/fetchWithAuth';

interface Drive {
  id: string;
  name: string;
  email: string;
  status: 'conectado' | 'desconectado';
  lastConnection?: string;
  driveToken?: string;
}

export default function DrivesPage() {
  const [drives, setDrives] = useState<Drive[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const router = useRouter();
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898';

  // Função para buscar drives conectados
  const fetchDrives = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetchWithAuth(`${API_BASE_URL}/api/drives`);

      if (response.ok) {
        const data = await response.json();
        setDrives(data);
      } else {
        setError('Erro ao carregar drives conectados');
      }
    } catch (error) {
      console.error('Erro ao buscar drives:', error);
      setError('Erro de conexão');
    } finally {
      setLoading(false);
    }
  };

  // Carregar drives ao montar componente
  useEffect(() => {
    fetchDrives();
  }, [fetchDrives]);

  // Gerar link de conexão
  const handleGenerateLink = async (email: string) => {
    try {
      setConnecting(email);
      const response = await fetchWithAuth(`${API_BASE_URL}/api/drives/${encodeURIComponent(email)}/connect`, { method: 'POST' });

      if (response.ok) {
        const data = await response.json();
        alert(`Link de conexão gerado para ${email}:\n${data.authUrl}`);
      } else {
        const errorData = await response.json();
        alert(`Erro: ${errorData.error || 'Falha ao gerar link'}`);
      }
    } catch (error) {
      console.error('Erro ao gerar link:', error);
      alert('Erro de conexão');
    } finally {
      setConnecting(null);
    }
  };

  // Desconectar drive
  const handleDisconnect = async (email: string) => {
    if (!confirm(`Tem certeza que deseja desconectar o drive de ${email}?`)) {
      return;
    }

    try {
      setDisconnecting(email);
      const response = await fetchWithAuth(`${API_BASE_URL}/api/drives/${encodeURIComponent(email)}/disconnect`, { method: 'DELETE' });

      if (response.ok) {
        const data = await response.json();
        alert(`✅ ${data.message}`);
        fetchDrives(); // Recarregar lista
      } else {
        const errorData = await response.json();
        alert(`❌ Erro: ${errorData.error || 'Falha ao desconectar'}`);
      }
    } catch (error) {
      console.error('Erro ao desconectar:', error);
      alert('Erro de conexão');
    } finally {
      setDisconnecting(null);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Nunca';
    const date = new Date(dateString);
    return isNaN(date.getTime()) ? 'Data inválida' : date.toLocaleString('pt-BR');
  };

  return (
    <div style={{ 
      maxWidth: 900, 
      margin: '40px auto', 
      padding: 24,
      background: '#111111',
      color: '#FFE1A6'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0, color: '#FFE1A6' }}>
          <div style={{ color: '#FFE1A6' }}>
            <FaGoogleDrive size={28} />
          </div> Drives Conectados
        </h2>
        <button 
          onClick={fetchDrives} 
          className="button secondary"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          disabled={loading}
        >
          <FiRefreshCw size={16} />
          {loading ? 'Carregando...' : 'Atualizar'}
        </button>
      </div>

      {error && (
        <div style={{ color: '#FFE1A6', marginBottom: 16, padding: '0.75rem', background: 'rgba(76, 0, 13, 0.2)', borderRadius: '4px', border: '1px solid rgba(76, 0, 13, 0.4)' }}>
          ❌ {error}
        </div>
      )}

      {loading ? (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="loading" style={{ margin: '0 auto 1rem' }}></div>
          <p style={{ color: '#FFE1A6' }}>Carregando drives conectados...</p>
        </div>
      ) : drives.length === 0 ? (
        <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
          <div style={{ color: 'rgba(255, 225, 166, 0.7)', marginBottom: '1rem' }}>
            <FaGoogleDrive size={48} />
          </div>
          <h3 style={{ marginBottom: '0.5rem', color: '#FFE1A6' }}>Nenhum drive conectado</h3>
          <p style={{ color: 'rgba(255, 225, 166, 0.7)', marginBottom: '1rem' }}>
            Conecte drives para começar a monitorar vídeos e áudios.
          </p>
          <button 
            onClick={() => router.push('/dashboard')}
            className="button"
          >
            Voltar ao Dashboard
          </button>
        </div>
      ) : (
        <div className="card">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(76, 0, 13, 0.1)' }}>
                <th style={{ textAlign: 'left', padding: 12, color: '#FFE1A6', fontWeight: 700 }}>Nome</th>
                <th style={{ textAlign: 'left', padding: 12, color: '#FFE1A6', fontWeight: 700 }}>E-mail</th>
                <th style={{ textAlign: 'left', padding: 12, color: '#FFE1A6', fontWeight: 700 }}>Status</th>
                <th style={{ textAlign: 'left', padding: 12, color: '#FFE1A6', fontWeight: 700 }}>Última Conexão</th>
                <th style={{ textAlign: 'left', padding: 12, color: '#FFE1A6', fontWeight: 700 }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {drives.map((drive) => (
                <tr key={drive.id} style={{ borderBottom: '1px solid rgba(76, 0, 13, 0.3)' }}>
                  <td style={{ padding: 12, fontWeight: '500', color: '#FFE1A6' }}>{drive.name}</td>
                  <td style={{ padding: 12, color: '#FFE1A6' }}>{drive.email}</td>
                  <td style={{ padding: 12 }}>
                    <span className={drive.status === 'conectado' ? 'status success' : 'status error'}>
                      {drive.status === 'conectado' ? 'Conectado' : 'Desconectado'}
                    </span>
                  </td>
                  <td style={{ padding: 12, fontSize: '0.875rem', color: 'rgba(255, 225, 166, 0.7)' }}>
                    {formatDate(drive.lastConnection)}
                  </td>
                  <td style={{ padding: 12 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button 
                        className="button secondary" 
                        style={{ fontSize: 13, padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: 4 }}
                        onClick={() => handleGenerateLink(drive.email)}
                        disabled={connecting === drive.email}
                      >
                        <FiLink size={14} />
                        {connecting === drive.email ? 'Gerando...' : 'Gerar Link'}
                      </button>
                      <button 
                        className="button danger" 
                        style={{ fontSize: 13, padding: '0.4rem 0.8rem', display: 'flex', alignItems: 'center', gap: 4 }}
                        onClick={() => handleDisconnect(drive.email)}
                        disabled={disconnecting === drive.email}
                      >
                        <FiX size={14} />
                        {disconnecting === drive.email ? 'Desconectando...' : 'Desconectar'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <button 
          onClick={() => router.push('/dashboard')}
          className="button secondary"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
} 