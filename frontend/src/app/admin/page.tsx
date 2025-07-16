"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchWithAuth } from "../utils/fetchWithAuth";
import StatsCards from "../components/StatsCards";
import Toast from "../components/Toast";
import { FaUsers, FaCogs, FaLink, FaUserPlus, FaTimes } from 'react-icons/fa';

interface Video {
  id: number;
  videoId: string;
  videoName: string;
  userEmail?: string;
  status: string;
  createdAt: string;
  googleDocsUrl?: string;
  transcrito?: string;
}

interface User {
  id: string;
  name: string;
  email: string;
  status: string;
  lastConnection?: string;
  isAdmin?: boolean;
  driveConnected?: boolean;
}

export default function AdminPanel() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const router = useRouter();
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898';
  const [processingNow, setProcessingNow] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);
  const [createUserError, setCreateUserError] = useState<string | null>(null);
  const [createUserSuccess, setCreateUserSuccess] = useState<string | null>(null);
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '', isAdmin: false });

  // Checar se usuário é admin
  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
        if (res.ok) {
          const userData = await res.json();
          setUser(userData);
          if (!userData.isAdmin) {
            router.replace("/dashboard");
          }
        } else {
          router.replace("/login");
        }
      } catch {
        router.replace("/login");
      }
    };
    checkAdmin();
  }, [API_BASE_URL, router]);

  // Buscar todos os vídeos
  const fetchVideos = async () => {
    // Não mostrar loading durante polling automático
    if (!videos.length) {
      setLoading(true);
    }
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/videos`);
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
      } else {
        setError("Erro ao buscar vídeos.");
      }
    } catch {
      setError("Erro de conexão.");
    } finally {
      setLoading(false);
    }
  };

  // Buscar usuários/colaboradores
  const fetchUsers = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/drives`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch {}
  };

  // Buscar webhooks
  const fetchWebhooks = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/config/webhooks`);
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data);
      }
    } catch {}
  };

  useEffect(() => {
    if (!user || !user.isAdmin) return;
    fetchVideos();
    fetchUsers();
    fetchWebhooks();
    // Removido o polling automático!
  }, [user, API_BASE_URL]);

  // Agrupar vídeos por status (lógica robusta)
  const grouped = {
    processing: [] as Video[],
    pending: [] as Video[],
    completed: [] as Video[],
    failed: [] as Video[],
    cancelled: [] as Video[],
    other: [] as Video[],
  };
  videos.forEach(v => {
    const transcritoValido = v.transcrito && typeof v.transcrito === 'string' && v.transcrito.trim() !== '' && v.transcrito !== 'ERRO';
    if (v.status === 'processing') grouped.processing.push(v);
    else if (v.status === 'error' || v.transcrito === 'ERRO') grouped.failed.push(v);
    else if (v.status === 'cancelled') grouped.cancelled.push(v);
    else if (v.status === 'completed' && transcritoValido) grouped.completed.push(v);
    else grouped.pending.push(v);
  });

  // Métricas
  const metrics = [
    { label: 'Total', value: videos.length, color: '#2d3748' },
    { label: 'Concluídos', value: grouped.completed.length, color: '#48bb78' },
    { label: 'Processando', value: grouped.processing.length, color: '#4299e1' },
    { label: 'Pendentes', value: grouped.pending.length, color: '#ed8936' },
    { label: 'Cancelados', value: grouped.cancelled.length, color: '#a0aec0' },
    { label: 'Falharam', value: grouped.failed.length, color: '#f56565' },
  ];

  const statusLabels: Record<string, string> = {
    processing: "Processando",
    pending: "Pendente",
    completed: "Concluído",
    failed: "Erro",
    error: "Erro",
    other: "Outro"
  };

  const statusColors: Record<string, string> = {
    processing: "#4299e1",
    pending: "#ed8936",
    completed: "#48bb78",
    failed: "#f56565",
    error: "#f56565",
    other: "#a0aec0"
  };

  // Função para atualizar status de um vídeo localmente (otimista)
  const updateVideoStatusLocal = (videoId: string, newStatus: string) => {
    setVideos(prev => prev.map(v => v.videoId === videoId ? { ...v, status: newStatus } : v));
  };

  // Atualiza um vídeo específico após fetch
  const refreshSingleVideo = async (videoId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/videos`);
      if (res.ok) {
        const data = await res.json();
        const updated = data.find((v: Video) => v.videoId === videoId);
        if (updated) {
          setVideos(prev => prev.map(v => v.videoId === videoId ? updated : v));
        }
      }
    } catch {}
  };

  const handleDownloadDocx = async (videoId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/videos/${videoId}/docx`);
      if (!res.ok) {
        alert("Erro ao baixar DOCX");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transcricao_${videoId}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert("Erro ao baixar DOCX");
    }
  };

  const handleProcessNow = async (videoId: string) => {
    setProcessingNow(videoId);
    updateVideoStatusLocal(videoId, 'processing'); // Otimista
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/videos/${videoId}/process-now`, { method: 'POST' });
      if (res.ok) {
        // Feedback já dado, mas faz fetch em background para garantir
        refreshSingleVideo(videoId);
      } else {
        alert('Erro ao processar vídeo.');
        refreshSingleVideo(videoId);
      }
    } catch {
      alert('Erro de conexão.');
      refreshSingleVideo(videoId);
    } finally {
      setProcessingNow(null);
    }
  };

  const handleCancel = async (videoId: string) => {
    setCancelling(videoId);
    updateVideoStatusLocal(videoId, 'cancelled'); // Otimista
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/videos/${videoId}/cancel`, { method: 'POST' });
      if (res.ok) {
        // Feedback já dado, mas faz fetch em background para garantir
        refreshSingleVideo(videoId);
      } else {
        alert('Erro ao cancelar vídeo.');
        refreshSingleVideo(videoId);
      }
    } catch {
      alert('Erro de conexão.');
      refreshSingleVideo(videoId);
    } finally {
      setCancelling(null);
    }
  };

  // Função para criar usuário
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingUser(true);
    setCreateUserError(null);
    setCreateUserSuccess(null);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newUser)
      });
      if (res.ok) {
        setCreateUserSuccess('Usuário criado com sucesso!');
        setNewUser({ name: '', email: '', password: '', isAdmin: false });
        fetchUsers();
        setTimeout(() => {
          setShowCreateUser(false);
          setCreateUserSuccess(null);
        }, 1500);
      } else {
        const data = await res.json();
        setCreateUserError(data.error || 'Erro ao criar usuário.');
      }
    } catch {
      setCreateUserError('Erro de conexão.');
    } finally {
      setCreatingUser(false);
    }
  };

  if (loading) {
    return <div className="card" style={{ maxWidth: 800, margin: "40px auto", padding: 32, textAlign: "center" }}>
      <div className="loading" style={{ margin: "0 auto 1rem" }}></div>
      <p>Carregando vídeos...</p>
    </div>;
  }

  return (
    <div style={{ 
      background: '#111111', 
      minHeight: '100vh', 
      paddingTop: 90, 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center',
      overflowX: 'hidden'
    }}>
      <div style={{ 
        width: '100%', 
        maxWidth: 1200, 
        margin: '0 auto', 
        padding: '0 18px', 
        display: 'flex', 
        flexDirection: 'column',
        overflowX: 'hidden'
      }}>
        <h2 style={{ 
          fontSize: "2.2rem", 
          fontWeight: 700, 
          marginBottom: 32, 
          color: "#FFE1A6",
          textAlign: 'center'
        }}>
          Painel Administrativo
        </h2>
        {/* Botão de criar usuário */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap', gap: 16 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 20, color: '#FFE1A6' }}><FaUsers /> Usuários/Colaboradores</h3>
          <button className="button" style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 15, padding: '0.6rem 1.2rem' }} onClick={() => setShowCreateUser(true)}><FaUserPlus /> Criar Usuário</button>
        </div>
        {/* Modal/Card de criação de usuário */}
        {showCreateUser && (
          <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="card fade-in-up" style={{ minWidth: 340, maxWidth: 400, padding: 32, borderRadius: 18, background: 'rgba(17, 17, 17, 0.95)', border: '2px solid #4C000D', position: 'relative' }}>
              <button onClick={() => setShowCreateUser(false)} style={{ position: 'absolute', top: 14, right: 14, background: 'none', border: 'none', fontSize: 22, color: '#FFE1A6', cursor: 'pointer' }}><FaTimes /></button>
              <h3 style={{ fontWeight: 700, fontSize: 20, marginBottom: 18, color: '#FFE1A6', display: 'flex', alignItems: 'center', gap: 8 }}><FaUserPlus /> Criar Novo Usuário</h3>
              <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <input type="text" placeholder="Nome" value={newUser.name} onChange={e => setNewUser({ ...newUser, name: e.target.value })} required className="input" />
                <input type="email" placeholder="E-mail" value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} required className="input" />
                <input type="password" placeholder="Senha" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} required className="input" />
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, fontSize: 15, color: '#FFE1A6' }}>
                  <input type="checkbox" checked={newUser.isAdmin} onChange={e => setNewUser({ ...newUser, isAdmin: e.target.checked })} style={{ marginRight: 6 }} />
                  Administrador
                </label>
                {createUserError && <div style={{ color: '#FFE1A6', fontWeight: 500, fontSize: 15 }}>{createUserError}</div>}
                {createUserSuccess && <div style={{ color: '#FFE1A6', fontWeight: 500, fontSize: 15 }}>{createUserSuccess}</div>}
                <button type="submit" className="button" style={{ fontWeight: 700, fontSize: 17, marginTop: 8 }} disabled={creatingUser}>{creatingUser ? 'Criando...' : 'Criar Usuário'}</button>
              </form>
            </div>
          </div>
        )}
        {/* Métricas - Layout corrigido */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: 36, width: '100%' }}>
          <div className="card" style={{ padding: '1.5rem', textAlign: 'center', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem', color: '#FFE1A6' }}>{videos.length}</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#FFE1A6', marginBottom: '0.25rem' }}>TOTAL</div>
            <div style={{ fontSize: '0.875rem', color: '#FFE1A6bb' }}>Vídeos no sistema</div>
          </div>
          <div className="card" style={{ padding: '1.5rem', textAlign: 'center', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem', color: '#FFE1A6' }}>{grouped.completed.length}</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#FFE1A6', marginBottom: '0.25rem' }}>CONCLUÍDAS</div>
            <div style={{ fontSize: '0.875rem', color: '#FFE1A6bb' }}>Transcrições finalizadas</div>
            {videos.length > 0 && (
              <div style={{ marginTop: '1rem', background: '#222', borderRadius: '10px', height: '6px', overflow: 'hidden', border: '1px solid #4C000D', width: '100%' }}>
                <div style={{
                  width: `${(grouped.completed.length / videos.length) * 100}%`,
                  height: '100%',
                  background: '#FFE1A6',
                  borderRadius: '10px',
                  transition: 'width 0.8s ease'
                }} />
              </div>
            )}
          </div>
          <div className="card" style={{ padding: '1.5rem', textAlign: 'center', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem', color: '#FFE1A6' }}>{grouped.processing.length}</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#FFE1A6', marginBottom: '0.25rem' }}>PROCESSANDO</div>
            <div style={{ fontSize: '0.875rem', color: '#FFE1A6bb' }}>Em processamento</div>
          </div>
          <div className="card" style={{ padding: '1.5rem', textAlign: 'center', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem', color: '#FFE1A6' }}>{grouped.pending.length}</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#FFE1A6', marginBottom: '0.25rem' }}>PENDENTES</div>
            <div style={{ fontSize: '0.875rem', color: '#FFE1A6bb' }}>Aguardando processamento</div>
          </div>
          <div className="card" style={{ padding: '1.5rem', textAlign: 'center', minHeight: '140px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem', color: '#FFE1A6' }}>{grouped.failed.length}</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: '#FFE1A6', marginBottom: '0.25rem' }}>FALHARAM</div>
            <div style={{ fontSize: '0.875rem', color: '#FFE1A6bb' }}>Com erro</div>
          </div>
        </div>
        {/* Tabela de usuários */}
        <div className="card" style={{ margin: '32px 0', padding: 24 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 20, marginBottom: 18, color: '#FFE1A6' }}><FaUsers /> Usuários/Colaboradores</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: 'transparent', borderRadius: 8, minWidth: 600 }}>
              <thead>
                <tr style={{ background: 'rgba(76, 0, 13, 0.1)' }}>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Nome</th>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>E-mail</th>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Status</th>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Última Conexão</th>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Admin</th>
                  <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Drive</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id} style={{ borderBottom: '1px solid rgba(76, 0, 13, 0.3)' }}>
                    <td style={{ padding: 12, color: '#FFE1A6' }}>{user.name}</td>
                    <td style={{ padding: 12, color: '#FFE1A6' }}>{user.email}</td>
                    <td style={{ padding: 12 }}>
                      <span style={{ 
                        background: user.status === 'conectado' ? '#111111' : '#111111', 
                        color: '#FFE1A6', 
                        border: '2px solid #4C000D',
                        borderRadius: '8px',
                        padding: '4px 8px',
                        fontSize: '0.875rem',
                        fontWeight: '600'
                      }}>
                        {user.status === 'conectado' ? 'Conectado' : 'Desconectado'}
                      </span>
                    </td>
                    <td style={{ padding: 12, fontSize: '0.95rem', color: 'rgba(255, 225, 166, 0.7)' }}>{user.lastConnection ? new Date(user.lastConnection).toLocaleString('pt-BR') : 'Nunca'}</td>
                    <td style={{ padding: 12, color: '#FFE1A6' }}>{user.isAdmin ? 'Sim' : 'Não'}</td>
                    <td style={{ padding: 12 }}>
                      {user.driveConnected ? (
                        <span style={{ color: '#FFE1A6', fontWeight: 700 }}>Conectado</span>
                      ) : (
                        <span style={{ color: 'rgba(255, 225, 166, 0.7)', fontWeight: 700 }}>Desconectado</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {/* Tabela de vídeos (agrupada por status) */}
        {error && <div style={{ color: "#FFE1A6", marginBottom: 24 }}>{error}</div>}
        {/* Seções por status */}
        {Object.entries({ processing: grouped.processing, pending: grouped.pending, cancelled: grouped.cancelled, completed: grouped.completed, failed: grouped.failed }).map(([status, vids]) => (
          vids.length > 0 && (
            <div key={status} style={{ marginBottom: 48 }}>
              <h3 style={{ color: '#FFE1A6', fontWeight: 700, fontSize: "1.3rem", marginBottom: 16, textTransform: 'capitalize' }}>
                {status.charAt(0).toUpperCase() + status.slice(1)} ({vids.length})
              </h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", background: "transparent", borderRadius: 8, minWidth: 800 }}>
                  <thead>
                    <tr style={{ background: "rgba(76, 0, 13, 0.1)" }}>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Nome do Vídeo</th>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Usuário</th>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Data</th>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Status</th>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Transcrição</th>
                      <th style={{ padding: 12, textAlign: "left", color: '#FFE1A6', fontWeight: 700 }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vids.map(video => (
                      <tr key={video.videoId} style={{ borderBottom: "1px solid rgba(76, 0, 13, 0.3)" }}>
                        <td style={{ padding: 10, color: '#FFE1A6' }}>{video.videoName}</td>
                        <td style={{ padding: 10, color: '#FFE1A6' }}>{video.userEmail || "-"}</td>
                        <td style={{ padding: 10, color: '#FFE1A6' }}>{video.createdAt ? new Date(video.createdAt).toLocaleString() : '-'}</td>
                        <td style={{ padding: 10, color: '#FFE1A6', fontWeight: 600 }}>{status.charAt(0).toUpperCase() + status.slice(1)}</td>
                        <td style={{ padding: 10 }}>
                          {video.googleDocsUrl ? (
                            <a href={video.googleDocsUrl} target="_blank" rel="noopener noreferrer" style={{ color: "#FFE1A6", textDecoration: "underline" }}>Ver no Google Docs</a>
                          ) : (
                            <span style={{ color: "rgba(255, 225, 166, 0.7)" }}>-</span>
                          )}
                        </td>
                        <td style={{ padding: 10 }}>
                          {/* Completed */}
                          {status === "completed" ? (
                            <button className="button" onClick={() => handleDownloadDocx(video.videoId)}>
                              Baixar DOCX
                            </button>
                          ) : /* Pending ou Cancelled: pode processar */
                          (status === "pending" || status === "cancelled") ? (
                            <>
                              <button className="button" onClick={() => handleProcessNow(video.videoId)} disabled={processingNow === video.videoId}>
                                {processingNow === video.videoId ? 'Processando...' : 'Processar Agora'}
                              </button>
                              {status === "pending" && (
                                <button className="button danger" style={{ marginLeft: 8 }} onClick={() => handleCancel(video.videoId)} disabled={cancelling === video.videoId}>
                                  {cancelling === video.videoId ? 'Cancelando...' : 'Cancelar'}
                                </button>
                              )}
                            </>
                          ) : /* Processing: pode cancelar */
                          status === "processing" ? (
                            <button className="button danger" onClick={() => handleCancel(video.videoId)} disabled={cancelling === video.videoId}>
                              {cancelling === video.videoId ? 'Cancelando...' : 'Cancelar'}
                            </button>
                          ) : /* Failed/Error: pode reprocessar */
                          (status === "failed" || status === "error") ? (
                            <button className="button" onClick={() => handleProcessNow(video.videoId)} disabled={processingNow === video.videoId}>
                              {processingNow === video.videoId ? 'Reprocessando...' : 'Reprocessar'}
                            </button>
                          ) : (
                            <span style={{ color: "rgba(255, 225, 166, 0.7)" }}>-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        ))}
        {videos.length === 0 && <div style={{ color: "rgba(255, 225, 166, 0.7)", textAlign: "center", marginTop: 40 }}>Nenhum vídeo encontrado.</div>}
        {/* Seção de webhooks/configurações globais */}
        <div className="card" style={{ margin: '32px 0', padding: 24 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 20, marginBottom: 18, color: '#FFE1A6' }}><FaLink /> Webhooks Globais</h3>
          {webhooks.length === 0 ? (
            <p style={{ color: 'rgba(255, 225, 166, 0.7)' }}>Nenhum webhook cadastrado.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', background: 'transparent', borderRadius: 8, minWidth: 600 }}>
                <thead>
                  <tr style={{ background: 'rgba(76, 0, 13, 0.1)' }}>
                    <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Nome</th>
                    <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>URL</th>
                    <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Eventos</th>
                    <th style={{ padding: 12, textAlign: 'left', color: '#FFE1A6', fontWeight: 700 }}>Ativo</th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map((wh, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(76, 0, 13, 0.3)' }}>
                      <td style={{ padding: 12, color: '#FFE1A6' }}>{wh.name}</td>
                      <td style={{ padding: 12, color: '#FFE1A6' }}>{wh.url}</td>
                      <td style={{ padding: 12, color: '#FFE1A6' }}>{(wh.events || []).join(', ')}</td>
                      <td style={{ padding: 12, color: '#FFE1A6' }}>{wh.active ? 'Sim' : 'Não'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {/* Toast feedback visual */}
        {toast && (
          <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
        )}
      </div>
    </div>
  );
} 