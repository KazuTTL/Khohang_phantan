// frontend/src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from '../components/Router';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const routeByRole = (user) => {
    if (user.role === 'HQ_MANAGER') {
      navigate('/hq');
    } else if (user.branch === 'HN') {
      navigate('/branch/hn');
    } else if (user.branch === 'HCM') {
      navigate('/branch/hcm');
    } else {
      navigate('/hq');
    }
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const user = await login(username.trim(), password);
      routeByRole(user);
    } catch (err) {
      setErrorMsg(err.message || 'Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản hoặc mật khẩu.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (u, p) => {
    setUsername(u);
    setPassword(p);
    setErrorMsg(null);
    // Tự động kích hoạt đăng nhập
    setLoading(true);
    login(u, p)
      .then(user => {
        routeByRole(user);
      })
      .catch(err => {
        setErrorMsg(err.message || 'Lỗi đăng nhập nhanh.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 font-sans text-slate-100">
      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl p-6 sm:p-8 backdrop-blur-sm">
        {/* Logo & Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-900/50">
            <i className="fa-solid fa-warehouse text-white text-xl"></i>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              DISTRIBUTED WMS
            </h1>
            <p className="text-xs text-slate-400">
              Hệ thống Quản lý Kho hàng Phân tán Đa Chi nhánh
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="mb-4 p-3 rounded-lg bg-red-950/70 border border-red-500/40 text-red-300 text-xs flex items-center gap-2">
            <i className="fa-solid fa-circle-exclamation text-red-400 text-sm"></i>
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1.5">
              <i className="fa-solid fa-user text-slate-400"></i>
              Tên tài khoản
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="VD: admin, manager_hn, manager_hcm..."
              required
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2.5 text-white font-mono focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1.5">
              <i className="fa-solid fa-lock text-slate-400"></i>
              Mật khẩu
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Nhập mật khẩu..."
              required
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-bold text-xs shadow-lg shadow-indigo-950/60 transition-all flex items-center justify-center gap-2 disabled:opacity-50 mt-2"
          >
            {loading ? (
              <>
                <i className="fa-solid fa-spinner animate-spin"></i>
                <span>Đang xác thực...</span>
              </>
            ) : (
              <>
                <i className="fa-solid fa-right-to-bracket"></i>
                <span>Đăng Nhập Hệ Thống</span>
              </>
            )}
          </button>
        </form>

        {/* Quick Demo Login Badges */}
        <div className="mt-6 pt-5 border-t border-slate-800/80">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <button
              type="button"
              onClick={() => handleQuickLogin('admin', 'admin123')}
              className="p-2.5 rounded-lg bg-slate-800/70 hover:bg-indigo-600/20 border border-slate-700 hover:border-indigo-500/50 text-left transition-all group"
            >
              <div className="font-bold text-indigo-300 group-hover:text-indigo-200 flex items-center gap-1">
                <i className="fa-solid fa-building-columns text-[10px]"></i>
                Trụ sở chính HQ
              </div>
              <div className="text-slate-400 font-mono text-[10px]">admin / admin123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('manager_hn', 'hn123')}
              className="p-2.5 rounded-lg bg-slate-800/70 hover:bg-blue-600/20 border border-slate-700 hover:border-blue-500/50 text-left transition-all group"
            >
              <div className="font-bold text-blue-300 group-hover:text-blue-200 flex items-center gap-1">
                <i className="fa-solid fa-location-dot text-[10px]"></i>
                Trưởng kho Hà Nội
              </div>
              <div className="text-slate-400 font-mono text-[10px]">manager_hn / hn123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('manager_hcm', 'hcm123')}
              className="p-2.5 rounded-lg bg-slate-800/70 hover:bg-violet-600/20 border border-slate-700 hover:border-violet-500/50 text-left transition-all group"
            >
              <div className="font-bold text-violet-300 group-hover:text-violet-200 flex items-center gap-1">
                <i className="fa-solid fa-location-dot text-[10px]"></i>
                Trưởng kho TP.HCM
              </div>
              <div className="text-slate-400 font-mono text-[10px]">manager_hcm / hcm123</div>
            </button>

            <button
              type="button"
              onClick={() => handleQuickLogin('staff_hn', 'staff123')}
              className="p-2.5 rounded-lg bg-slate-800/70 hover:bg-emerald-600/20 border border-slate-700 hover:border-emerald-500/50 text-left transition-all group"
            >
              <div className="font-bold text-emerald-300 group-hover:text-emerald-200 flex items-center gap-1">
                <i className="fa-solid fa-clipboard-user text-[10px]"></i>
                Thủ kho Hà Nội
              </div>
              <div className="text-slate-400 font-mono text-[10px]">staff_hn / staff123</div>
            </button>
          </div>
        </div>
      </div>

      <footer className="mt-8 text-center text-xs text-slate-500">
        Distributed Warehouse Management System • Kiến trúc Microservices: FastAPI + RabbitMQ + ReactJS
      </footer>
    </div>
  );
}
