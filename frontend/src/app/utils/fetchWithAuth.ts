// frontend/src/app/utils/fetchWithAuth.ts
export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (!token && typeof window !== 'undefined') {
    window.location.href = '/login';
    throw new Error('Token JWT não encontrado');
  }
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
  });

  if (res.status === 401) {
    // Token inválido ou expirado
    localStorage.removeItem('token');
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new Error('Token JWT inválido ou expirado');
  }

  return res;
} 