// frontend/src/pages/LoginPage.jsx
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from '../components/Router';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [showPass, setShowPass] = useState(false);
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
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const loggedUser = await login(username.trim(), password);
      routeByRole(loggedUser);
    } catch (err) {
      setErrorMsg(err.message || 'Tên đăng nhập hoặc mật khẩu không đúng.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (u, p) => {
    setUsername(u);
    setPassword(p);
    setLoading(true);
    setErrorMsg(null);
    try {
      const loggedUser = await login(u, p);
      routeByRole(loggedUser);
    } catch (err) {
      setErrorMsg(err.message || 'Lỗi kết nối máy chủ xác thực.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-xl shadow-slate-200/70 border border-slate-200 overflow-hidden grid grid-cols-1 md:grid-cols-12">
        {/* Left Feature Panel */}
        <div className="md:col-span-5 bg-gradient-to-br from-indigo-600 via-indigo-700 to-slate-900 p-8 text-white flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 rounded-xl bg-white/15 border border-white/25 flex items-center justify-center">
                <i className="fa-solid fa-boxes-stacked text-lg"></i>
              </div>
              <div>
                <div className="text-base font-extrabold tracking-tight">DISTRIBUTED WMS</div>
                <div className="text-[11px] text-indigo-200">Enterprise Inventory Suite</div>
              </div>
            </div>

            <h2 className="text-2xl font-bold leading-snug mb-3">
              Hệ thống Quản lý Kho hàng Đa Chi nhánh
            </h2>
            <p className="text-xs text-indigo-100/90 leading-relaxed mb-6">
              Điều phối tồn kho tập trung tại Trụ sở chính kết hợp vận hành tự trị cục bộ tại từng chi nhánh Hà Nội và TP.HCM.
            </p>

            <div className="space-y-3 text-xs">
              <div className="flex items-start gap-2.5 bg-white/10 rounded-xl p-3 border border-white/10">
                <i className="fa-solid fa-building-columns mt-0.5 text-indigo-200"></i>
                <div>
                  <div className="font-semibold">Site 1: Trụ sở chính (HQ)</div>
                  <div className="text-[11px] text-indigo-100/80">Danh mục gốc, Điều phối Saga, Báo cáo tổng hợp</div>
                </div>
              </div>
              <div className="flex items-start gap-2.5 bg-white/10 rounded-xl p-3 border border-white/10">
                <i className="fa-solid fa-warehouse mt-0.5 text-sky-200"></i>
                <div>
                  <div className="font-semibold">Site 2 & 3: Chi nhánh HN / HCM</div>
                  <div className="text-[11px] text-indigo-100/80">Đơn hàng, Phiếu kho, Kiểm kê & Outbox tự trị</div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-white/15 text-[11px] text-indigo-200">
            Xác thực từ bảng TAI_KHOAN cục bộ tại từng Site
          </div>
        </div>

        {/* Right Login Form */}
        <div className="md:col-span-7 p-6 sm:p-8 flex flex-col justify-center">
          <div className="mb-6">
            <h1 className="text-xl font-bold text-slate-900">Đăng nhập Hệ thống</h1>
            <p className="text-xs text-slate-500 mt-1">
              Sử dụng tài khoản được cấp cho Trụ sở chính hoặc Chi nhánh của bạn
            </p>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <i className="fa-solid fa-circle-exclamation text-rose-500"></i>
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-700 font-semibold mb-1.5">Tên tài khoản</label>
              <div className="relative">
                <i className="fa-solid fa-user absolute left-3.5 top-3 text-slate-400"></i>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nhập tên tài khoản..."
                  required
                  className="w-full bg-white border border-slate-300 rounded-xl pl-10 pr-3.5 py-2.5 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-700 font-semibold mb-1.5">Mật khẩu</label>
              <div className="relative">
                <i className="fa-solid fa-lock absolute left-3.5 top-3 text-slate-400"></i>
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu..."
                  required
                  className="w-full bg-white border border-slate-300 rounded-xl pl-10 pr-10 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  <i className={`fa-solid ${showPass ? 'fa-eye-slash' : 'fa-eye'}`}></i>
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <i className="fa-solid fa-spinner animate-spin"></i>
                  <span>Đang xác thực...</span>
                </>
              ) : (
                <>
                  <i className="fa-solid fa-right-to-bracket"></i>
                  <span>Đăng Nhập</span>
                </>
              )}
            </button>
          </form>

          {/* 5 Accounts Quick Access */}
          <div className="mt-6 pt-5 border-t border-slate-200">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2.5">
              Chọn nhanh tài khoản theo chi nhánh
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
              <button
                type="button"
                onClick={() => handleQuickLogin('admin', 'admin123')}
                className="p-2.5 rounded-xl bg-indigo-50/70 hover:bg-indigo-100/70 border border-indigo-200 text-left transition-colors"
              >
                <div className="font-bold text-indigo-700 flex items-center gap-1.5">
                  <i className="fa-solid fa-building-columns text-[10px]"></i>
                  Trụ sở chính HQ
                </div>
                <div className="text-slate-500 font-mono text-[10px] mt-0.5">admin / admin123</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('manager_hn', 'hn123')}
                className="p-2.5 rounded-xl bg-sky-50/70 hover:bg-sky-100/70 border border-sky-200 text-left transition-colors"
              >
                <div className="font-bold text-sky-700 flex items-center gap-1.5">
                  <i className="fa-solid fa-user-tie text-[10px]"></i>
                  Trưởng kho Hà Nội
                </div>
                <div className="text-slate-500 font-mono text-[10px] mt-0.5">manager_hn / hn123</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('manager_hcm', 'hcm123')}
                className="p-2.5 rounded-xl bg-violet-50/70 hover:bg-violet-100/70 border border-violet-200 text-left transition-colors"
              >
                <div className="font-bold text-violet-700 flex items-center gap-1.5">
                  <i className="fa-solid fa-user-tie text-[10px]"></i>
                  Trưởng kho TP.HCM
                </div>
                <div className="text-slate-500 font-mono text-[10px] mt-0.5">manager_hcm / hcm123</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('staff_hn', 'staff123')}
                className="p-2.5 rounded-xl bg-emerald-50/70 hover:bg-emerald-100/70 border border-emerald-200 text-left transition-colors"
              >
                <div className="font-bold text-emerald-700 flex items-center gap-1.5">
                  <i className="fa-solid fa-clipboard-user text-[10px]"></i>
                  Thủ kho Hà Nội
                </div>
                <div className="text-slate-500 font-mono text-[10px] mt-0.5">staff_hn / staff123</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('staff_hcm', 'staff123')}
                className="sm:col-span-2 p-2.5 rounded-xl bg-teal-50/70 hover:bg-teal-100/70 border border-teal-200 text-left transition-colors flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-teal-700 flex items-center gap-1.5">
                    <i className="fa-solid fa-clipboard-user text-[10px]"></i>
                    Thủ kho TP.HCM
                  </div>
                  <div className="text-slate-500 font-mono text-[10px] mt-0.5">staff_hcm / staff123</div>
                </div>
                <i className="fa-solid fa-arrow-right text-teal-500"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
