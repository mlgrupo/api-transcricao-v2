"use client";

import { useState } from "react";

interface User {
  id: number;
  name: string;
  email: string;
  isAdmin?: boolean;
  avatarUrl?: string;
  driveConnected?: boolean;
}

interface LoginFormProps {
  onLoginSuccess: (user: User, token: string) => void;
}

export default function LoginForm({ onLoginSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9898'}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Erro ao fazer login.");
      } else {
        onLoginSuccess(data.user, data.token);
      }
    } catch {
      setError("Erro de conexão com o servidor.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mb-3" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <input
          type="email"
          placeholder="E-mail"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="input login-input"
          required
          autoFocus
        />
      </div>
      <div>
        <input
          type="password"
          placeholder="Senha"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="input login-input"
          required
        />
      </div>
      {error && <div style={{ color: "#e53e3e", marginBottom: 4, fontWeight: 500, fontSize: 15 }}>{error}</div>}
      <button
        type="submit"
        className="button login-btn"
        disabled={loading}
        style={{ width: "100%", marginTop: 6 }}
      >
        <span style={{ display: 'inline-block', width: '100%', textAlign: 'center', fontWeight: 700, fontSize: 18, letterSpacing: 0 }}>{loading ? "Entrando..." : "Entrar"}</span>
      </button>
      <style>{`
        .login-input {
          padding: 1.1rem 1.1rem;
          font-size: 1.08rem;
          border-radius: 12px;
          border: 2px solid #4C000D;
          background: #191919;
          color: #FFE1A6;
          transition: border 0.2s, box-shadow 0.2s;
        }
        .login-input:focus {
          border: 2px solid #FFE1A6;
          box-shadow: 0 0 0 2px #FFE1A633;
          background: #111111;
        }
        .login-input::placeholder {
          color: #FFE1A677;
          opacity: 1;
        }
        .login-btn {
          height: 48px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.13rem;
          font-weight: 700;
          border-radius: 12px;
          box-shadow: 0 4px 16px #4C000D33;
          background: #4C000D;
          color: #FFE1A6;
          border: 2px solid #4C000D;
          transition: box-shadow 0.2s, filter 0.2s;
          letter-spacing: 0.01em;
        }
        .login-btn:hover:not(:disabled) {
          filter: brightness(1.09) saturate(1.18);
          box-shadow: 0 8px 32px #4C000D55;
        }
        .login-btn:active:not(:disabled) {
          filter: brightness(0.98);
        }
        @media (max-width: 480px) {
          .login-input { font-size: 1rem; padding: 0.95rem 0.9rem; }
          .login-btn { font-size: 1rem; height: 44px; }
        }
      `}</style>
    </form>
  );
} 