"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import VideoList from "../components/VideoList";
import ApiStatus from "../components/ApiStatus";
import StatsCards from "../components/StatsCards";
import Toast from "../components/Toast";
import Logo from "../components/Logo";
import { FaGoogleDrive } from 'react-icons/fa';
import { FiLogOut, FiSettings, FiUsers, FiUser, FiShield } from 'react-icons/fi';
import { fetchWithAuth } from '../utils/fetchWithAuth';

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

interface User {
  id: number;
  name: string;
  email: string;
  isAdmin?: boolean;
  avatarUrl?: string;
  driveConnected?: boolean;
}

interface StatsData {
  total: number;
  completed: number;
  processing: number;
  pending: number;
  failed: number;
  error: number;
}

interface ToastMessage {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

export default function DashboardPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [stats, setStats] = useState<StatsData>({
    total: 0,
    completed: 0,
    processing: 0,
    pending: 0,
    failed: 0,
    error: 0
  });
  const [apiStatus, setApiStatus] = useState<"online" | "offline" | "error" | "checking">("checking");
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingUser, setLoadingUser] = useState(true);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const router = useRouter();
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898';

  // Função para adicionar toast
  const addToast = useCallback((message: string, type: 'success' | 'error' | 'info' | 'warning') => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message, type }]);
  }, []);

  // Função para remover toast
  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  // Checar autenticação e buscar dados do usuário
  useEffect(() => {
    const checkAuth = async () => {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      if (!token) {
        router.replace('/login');
        return;
      }

      try {
        setLoadingUser(true);
        // Buscar dados do usuário autenticado
        const response = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else {
          // Se não conseguir buscar dados do usuário, usar dados básicos
          setUser({
            id: 1,
            name: 'Usuário',
            email: 'usuario@exemplo.com',
            isAdmin: false,
            driveConnected: false
          });
        }
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Erro ao buscar dados do usuário:', error);
        addToast('Erro ao carregar dados do usuário', 'error');
        router.replace('/login');
      } finally {
        setLoadingUser(false);
      }
    };

    checkAuth();
  }, [router, API_BASE_URL, addToast]);

  // Buscar status da API
  useEffect(() => {
    const checkApiStatus = async () => {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/health`);
        setApiStatus(response.ok ? 'online' : 'error');
      } catch {
        setApiStatus('error');
      }
    };

    if (isAuthenticated) {
      checkApiStatus();
      const interval = setInterval(checkApiStatus, 30000); // Verificar a cada 30 segundos
      return () => clearInterval(interval);
    }
  }, [API_BASE_URL, isAuthenticated]);

  // Buscar estatísticas
  const fetchStats = useCallback(async () => {
    try {
      setLoadingStats(true);
      const response = await fetchWithAuth(`${API_BASE_URL}/api/videos/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Erro ao buscar estatísticas:', error);
      addToast('Erro ao carregar estatísticas', 'error');
    } finally {
      setLoadingStats(false);
    }
  }, [API_BASE_URL, addToast]);

  // Buscar vídeos
  const fetchVideos = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/videos`);
      if (response.ok) {
        const data = await response.json();
        setVideos(data);
      }
    } catch (error) {
      console.error('Erro ao buscar vídeos:', error);
      addToast('Erro ao carregar vídeos', 'error');
    }
  }, [API_BASE_URL, addToast]);

  useEffect(() => {
    if (isAuthenticated && !loadingUser) {
      fetchVideos();
      fetchStats();
    }
  }, [isAuthenticated, loadingUser, fetchVideos, fetchStats]);

  // Logout
  const handleLogout = async () => {
    setLogoutLoading(true);
    try {
      await fetchWithAuth(`${API_BASE_URL}/auth/logout`, { method: 'POST' });
      localStorage.removeItem('token');
      setIsAuthenticated(false);
      setUser(null);
      setVideos([]);
      addToast('Logout realizado com sucesso', 'info');
      router.replace('/login');
    } catch (error) {
      console.error('Erro ao fazer logout:', error);
      addToast('Erro ao fazer logout', 'error');
    } finally {
      setLogoutLoading(false);
    }
  };

  // Google/Drive
  const handleLogin = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/auth/google/url`);
      const data = await response.json();
      if (data.authUrl) {
        window.location.href = data.authUrl;
      } else {
        addToast('Erro ao obter URL de autenticação do Google', 'error');
      }
    } catch (error) {
      console.error('Erro ao iniciar login com Google:', error);
      addToast('Erro ao iniciar login com Google', 'error');
    }
  };

  const handleConnectDrive = async () => {
    if (!isAuthenticated) return;
    handleLogin();
  };

  if (loadingUser) {
    return (
      <div className="container" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="card text-center" style={{ padding: '3rem 2rem' }}>
          <div className="loading" style={{ margin: '0 auto 1rem', width: '40px', height: '40px' }}></div>
          <p style={{ margin: 0, color: '#666' }}>Carregando dashboard...</p>
        </div>
      </div>
    );
  }

  // Novo: Barra superior fixa
  const TopBar = () => (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: 68, zIndex: 20,
      background: 'rgba(17,17,17,0.95)',
      borderBottom: '2px solid #4C000D',
      color: '#FFE1A6',
      borderBottomLeftRadius: 18, borderBottomRightRadius: 18,
      display: 'flex', justifyContent: 'center', alignItems: 'center'
    }}>
      <div style={{
        width: '100%',
        maxWidth: 1200,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 18px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Logo />
          <span style={{ fontWeight: 800, fontSize: 22, color: '#FFE1A6', letterSpacing: '-0.01em', fontFamily: 'Inter, sans-serif' }}>Reconecta Transcript</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => router.push('/configuracoes')} className="button secondary" style={{ fontWeight: 600, fontSize: 15, padding: '0.7rem 1.3rem' }}><FiSettings style={{ marginRight: 6 }} />Configurações</button>
          <button onClick={handleLogout} className="button danger" style={{ fontWeight: 600, fontSize: 15, padding: '0.7rem 1.3rem' }} disabled={logoutLoading}><FiLogOut style={{ marginRight: 6 }} />Sair</button>
          {user && <div style={{ width: 44, height: 44, borderRadius: '50%', background: '#e9eafc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 700, color: '#667eea', marginLeft: 8 }}>{user.name?.[0] || <FiUser />}</div>}
        </div>
      </div>
    </div>
  );

  // Novo: Cards de métricas com ícones e animação
  interface MetricCardProps {
    icon: React.ReactNode;
    value: number;
    label: string;
    desc: string;
    color: string;
    bg: string;
  }
  const MetricCard = ({ icon, value, label, desc, color, bg }: MetricCardProps) => (
    <div style={{
      background: '#111111',
      border: '2px solid #4C000D',
      borderRadius: 18,
      boxShadow: '0 4px 24px rgba(102,126,234,0.07)',
      padding: '1.6rem 1.1rem 1.2rem 1.1rem',
      minWidth: 170,
      textAlign: 'center',
      transition: 'transform 0.18s, box-shadow 0.18s',
      cursor: 'pointer',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      margin: '0 8px',
    }}
      onMouseOver={e => { e.currentTarget.style.transform = 'translateY(-6px) scale(1.03)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(102,126,234,0.13)'; }}
      onMouseOut={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 4px 24px rgba(102,126,234,0.07)'; }}
    >
      <div style={{ fontSize: 38, marginBottom: 8, color }}>{icon}</div>
      <div style={{ fontWeight: 800, fontSize: 32, color }}>{value}</div>
      <div style={{ fontWeight: 700, fontSize: 15, color, marginTop: 2 }}>{label}</div>
      <div style={{ color: '#4a5568', fontSize: 13, marginTop: 4 }}>{desc}</div>
    </div>
  );

  // Novo: Painel do usuário
  const UserPanel = () => (
    <div style={{
      background: 'rgba(17,17,17,0.95)',
      border: '2px solid #4C000D',
      borderRadius: 22,
      boxShadow: '0 4px 24px rgba(102,126,234,0.07)',
      padding: '2.1rem 2.2rem 1.2rem 2.2rem',
      margin: '0 auto 2.2rem auto',
      maxWidth: 650,
      width: '100%',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      alignSelf: 'center',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 16 }}>
        <div style={{ width: 60, height: 60, borderRadius: '50%', background: '#e9eafc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 32, fontWeight: 700, color: '#667eea' }}>{user?.name?.[0] || <FiUser />}</div>
        <div style={{ textAlign: 'left' }}>
          <div style={{ fontWeight: 800, fontSize: 22, color: '#FFE1A6', marginBottom: 2 }}>Dashboard</div>
          <div style={{ color: '#FFE1A6', fontWeight: 500, fontSize: 16 }}>Bem-vindo, <span style={{ color: '#667eea', fontWeight: 700 }}>{user?.name || 'Usuário'}</span>!</div>
          <div style={{ color: '#718096', fontSize: 14 }}>{user?.email}</div>
        </div>
      </div>
      {/* Status horizontalmente alinhados */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        {user?.isAdmin && <span style={{ background: '#111111', color: '#FFE1A6', fontWeight: 700, borderRadius: 12, padding: '0.4rem 1rem', fontSize: 14, display: 'flex', alignItems: 'center', gap: 5, border: '2px solid #4C000D' }}><FiShield /> ADMIN</span>}
        {user?.driveConnected ? (
          <span style={{ background: '#111111', color: '#FFE1A6', fontWeight: 700, borderRadius: 12, padding: '0.4rem 1rem', fontSize: 14, display: 'flex', alignItems: 'center', gap: 5, border: '2px solid #4C000D' }}><FaGoogleDrive /> Drive Conectado</span>
        ) : (
          <span style={{ background: '#111111', color: '#FFE1A6', fontWeight: 700, borderRadius: 12, padding: '0.4rem 1rem', fontSize: 14, display: 'flex', alignItems: 'center', gap: 5, border: '2px solid #4C000D' }}><FaGoogleDrive /> Drive Desconectado <button onClick={handleConnectDrive} style={{ marginLeft: 10, background: '#4C000D', color: '#FFE1A6', border: 'none', borderRadius: 8, padding: '0.2rem 0.8rem', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>Conectar</button></span>
        )}
        <span style={{ background: '#111111', color: '#FFE1A6', fontWeight: 700, borderRadius: 12, padding: '0.4rem 1rem', fontSize: 14, display: 'flex', alignItems: 'center', gap: 5, border: '2px solid #4C000D' }}><span style={{ fontSize: 17 }}>🌐</span> API {apiStatus === 'online' ? 'ONLINE' : 'OFFLINE'}</span>
      </div>
    </div>
  );

  // Mensagem amigável se não houver vídeos e não estiver conectado
  const showConnectMsg = !user?.driveConnected && videos.length === 0;

  return (
    <div style={{ background: '#111111', minHeight: '100vh', paddingTop: 90, display: 'flex', flexDirection: 'column', alignItems: 'center', overflowX: 'hidden' }}>
      <TopBar />
      {/* Toasts */}
      <div style={{ position: 'fixed', top: 24, right: 32, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
      <div style={{ width: '100%', maxWidth: 1200, margin: '0 auto', padding: '0 18px', display: 'flex', flexDirection: 'column', alignItems: 'center', overflowX: 'hidden' }}>
        <UserPanel />
        {showConnectMsg && (
          <div className="card fade-in-up" style={{ margin: '0 auto 2.2rem auto', maxWidth: 500, background: '#111111', color: '#FFE1A6', fontWeight: 600, fontSize: 17, borderRadius: 16, padding: '1.5rem 2rem', textAlign: 'center' }}>
            <FaGoogleDrive style={{ fontSize: 28, marginBottom: 8 }} />
            <div style={{ marginBottom: 6 }}>Conecte seu Google Drive para começar a transcrever vídeos!</div>
            <button onClick={handleConnectDrive} className="button" style={{ marginTop: 10, fontWeight: 700, fontSize: 16 }}>Conectar Drive</button>
          </div>
        )}
        {/* Cards de métricas - Layout melhorado */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: 36, width: '100%', maxWidth: '100%' }}>
          <MetricCard icon={<FiUsers />} value={stats.total} label="TOTAL" desc="Vídeos no sistema" color="#FFE1A6" bg="#111111" />
          <MetricCard icon={<FiShield />} value={stats.completed} label="CONCLUÍDAS" desc="Transcrições finalizadas" color="#FFE1A6" bg="#111111" />
          <MetricCard icon={<FiLogOut />} value={stats.processing} label="PROCESSANDO" desc="Em processamento" color="#FFE1A6" bg="#111111" />
          <MetricCard icon={<FiSettings />} value={stats.pending} label="PENDENTES" desc="Aguardando processamento" color="#FFE1A6" bg="#111111" />
          <MetricCard icon={<FiUser />} value={stats.failed} label="FALHARAM" desc="Com erro" color="#FFE1A6" bg="#111111" />
        </div>
        {/* Botão de Scan Manual */}
        {/* Lista de Vídeos */}
        <div className="fade-in-up" style={{ width: '100%' }}>
          <VideoList videos={videos} onRefresh={fetchVideos} />
        </div>
      </div>
      <style>{`
        .button { transition: box-shadow 0.18s, filter 0.18s; }
        .button:active { filter: brightness(0.97); }
        @media (max-width: 900px) {
          .card, .fade-in-up, .container { padding: 0 !important; }
        }
        @media (max-width: 600px) {
          .card, .fade-in-up, .container { padding: 0 !important; }
          .card { border-radius: 12px !important; }
        }
      `}</style>
    </div>
  );
} 