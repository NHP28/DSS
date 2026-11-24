'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import type { Account } from '@/lib/types';

type RegisterForm = { username: string; displayName: string; password: string; interests: string[] };
type Auth = {
  account: Account | null; loading: boolean;
  login(username: string, password: string): Promise<void>;
  register(form: RegisterForm): Promise<void>;
  logout(): Promise<void>;
};
const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    // A 401 here just means "guest".
    api<{ account: Account }>('auth/me').then(data => setAccount(data.account)).catch(() => setAccount(null)).finally(() => setLoading(false));
  }, []);
  const login = useCallback(async (username: string, password: string) => {
    setAccount((await api<{ account: Account }>('auth/login', { username, password })).account);
  }, []);
  const register = useCallback(async (form: RegisterForm) => {
    setAccount((await api<{ account: Account }>('auth/register', form)).account);
  }, []);
  const logout = useCallback(async () => { await api('auth/logout', {}); setAccount(null); }, []);
  const value = useMemo(() => ({ account, loading, login, register, logout }), [account, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
