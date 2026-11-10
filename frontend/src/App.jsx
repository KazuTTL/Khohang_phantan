// frontend/src/App.jsx
import React, { useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RouterProvider, useLocation, useNavigate } from './components/Router';
import LoginPage from './pages/LoginPage';
import HQDashboardPage from './pages/HQDashboardPage';
import BranchDashboardPage from './pages/BranchDashboardPage';

function AppContent() {
  const { isAuthenticated, currentUser } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  // Xử lý điều hướng thông minh theo trạng thái đăng nhập
  useEffect(() => {
    if (!isAuthenticated) {
      if (pathname !== '/login') {
        navigate('/login');
      }
    } else {
      if (pathname === '/login' || pathname === '/') {
        if (currentUser?.role === 'HQ_MANAGER') {
          navigate('/hq');
        } else if (currentUser?.branch === 'HN') {
          navigate('/branch/hn');
        } else if (currentUser?.branch === 'HCM') {
          navigate('/branch/hcm');
        } else {
          navigate('/hq');
        }
      }
    }
  }, [isAuthenticated, pathname, currentUser]);

  // Nếu chưa đăng nhập, luôn render màn hình Login
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  // Nếu người dùng yêu cầu đường dẫn Trụ sở chính (/hq hoặc /)
  if (pathname === '/hq' || pathname === '/') {
    if (currentUser?.role === 'HQ_MANAGER') {
      return <HQDashboardPage />;
    } else {
      // Nếu nhân sự chi nhánh cố vào /hq -> tự động đưa về kho của họ
      const targetBranch = currentUser?.branch?.toLowerCase() || 'hn';
      return <BranchDashboardPage branchCode={currentUser?.branch || 'HN'} />;
    }
  }

  // Tuyến Chi nhánh Hà Nội
  if (pathname === '/branch/hn') {
    return <BranchDashboardPage branchCode="HN" />;
  }

  // Tuyến Chi nhánh TP.HCM
  if (pathname === '/branch/hcm') {
    return <BranchDashboardPage branchCode="HCM" />;
  }

  // Tuyến mặc định cho mọi URL khác
  if (currentUser?.role === 'HQ_MANAGER') {
    return <HQDashboardPage />;
  }
  return <BranchDashboardPage branchCode={currentUser?.branch || 'HN'} />;
}

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider>
        <AppContent />
      </RouterProvider>
    </AuthProvider>
  );
}
