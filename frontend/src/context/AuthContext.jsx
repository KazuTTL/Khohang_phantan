// frontend/src/context/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem('wms_token') || null;
    } catch {
      return null;
    }
  });

  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('wms_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const login = async (username, password) => {
    const res = await api.login({ username, password });
    if (res && res.access_token && res.user) {
      setToken(res.access_token);
      setCurrentUser(res.user);
      localStorage.setItem('wms_token', res.access_token);
      localStorage.setItem('wms_user', JSON.stringify(res.user));
      return res.user;
    }
    throw new Error("Phản hồi xác thực không hợp lệ từ máy chủ.");
  };

  const logout = () => {
    setToken(null);
    setCurrentUser(null);
    try {
      localStorage.removeItem('wms_token');
      localStorage.removeItem('wms_user');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <AuthContext.Provider value={{ token, currentUser, login, logout, isAuthenticated: Boolean(token && currentUser) }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
