"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import LoginForm from "../components/LoginForm";
import ApiStatus from "../components/ApiStatus";
import Image from "next/image";

export default function LoginPage() {
  const [apiStatus, setApiStatus] = useState<'online' | 'offline' | 'error' | 'checking'>('checking');
  const router = useRouter();

  // Checar status da API ao carregar
  useState(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898'}/health`)
      .then(res => setApiStatus(res.ok ? 'online' : 'error'))
      .catch(() => setApiStatus('error'));
  });

  return (
    <div className="login-bg">
      <div className="card fade-in-up login-card">
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Image src="/logo.png" alt="Logo" width={48} height={48} style={{ marginBottom: 6 }} priority />
        </div>
        <h2 className="login-title">Reconecta Transcript</h2>
        <p className="login-desc">Acesse sua conta para transcrever vídeos com IA.</p>
        <LoginForm onLoginSuccess={(user, token) => {
          localStorage.setItem('token', token);
          router.replace('/dashboard');
        }} />
        <ApiStatus status={apiStatus} />
      </div>
      <style>{`
        .login-bg {
          min-height: 100vh;
          width: 100vw;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-bg);
          overflow: hidden;
          position: fixed;
          top: 0;
          left: 0;
          z-index: 0;
          animation: fadeInUp 0.7s cubic-bezier(.4,0,.2,1);
        }
        .login-card {
          max-width: 390px;
          width: 100%;
          margin: 0 auto;
          border-radius: 22px;
          padding: 2.1rem 1.5rem 1.5rem 1.5rem;
          text-align: center;
          background: var(--color-card-glass);
          box-shadow: var(--color-shadow);
          border: 2px solid var(--color-border);
          animation: fadeInUp 0.7s cubic-bezier(.4,0,.2,1);
        }
        .login-title {
          font-weight: 800;
          font-size: 1.55rem;
          color: var(--color-accent);
          margin-bottom: 7px;
          letter-spacing: -0.01em;
          font-family: 'Inter', sans-serif;
          line-height: 1.18;
          text-shadow: 0 2px 8px #000a;
        }
        .login-desc {
          color: #ffe1a6cc;
          font-size: 1.01rem;
          margin-bottom: 18px;
          font-weight: 500;
          line-height: 1.4;
        }
        @media (max-width: 480px) {
          .login-card { padding: 1.2rem 0.5rem 1rem 0.5rem !important; max-width: 98vw !important; }
          .login-title { font-size: 1.13rem !important; }
        }
      `}</style>
    </div>
  );
} 