import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './stores';

// Pages
import LoginPage from './pages/LoginPage';
import MainLayout from './components/MainLayout';
import ChatPage from './pages/ChatPage';
import AgentsPage from './pages/AgentsPage';
import AgentEditorPage from './pages/AgentEditorPage';
import SettingsPage from './pages/SettingsPage';
import DashboardPage from './pages/DashboardPage';
import KnowledgePage from './pages/KnowledgePage';
// V5 新页面
import CreateOrgPage from './pages/CreateOrgPage';
import JoinOrgPage from './pages/JoinOrgPage';
import OrganizationPage from './pages/OrganizationPage';
import ProfilePage from './pages/ProfilePage';
import BotBindingPage from './pages/BotBindingPage';

// Protected Route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <div className="h-screen overflow-hidden">
        <Toaster
          position="top-right"
          containerStyle={{
            position: 'fixed',
            zIndex: 9999,
          }}
          toastOptions={{
            duration: 4000,
            style: {
              background: '#1e293b',
              color: '#f1f5f9',
              border: '1px solid #334155',
            },
            success: {
              iconTheme: {
                primary: '#10b981',
                secondary: '#f1f5f9',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#f1f5f9',
              },
            },
          }}
        />
      <Routes>
        {/* 公开页面 */}
        <Route path="/login" element={<LoginPage />} />

        {/* 邀请链接（可公开访问，登录后自动处理） */}
        <Route
          path="/join/:inviteCode"
          element={
            <ProtectedRoute>
              <JoinOrgPage />
            </ProtectedRoute>
          }
        />

        {/* 受保护页面 */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/chat" replace />} />

          {/* 通用页面 */}
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:conversationId" element={<ChatPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="agents/new" element={<AgentEditorPage />} />
          <Route path="agents/:id" element={<AgentEditorPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="settings" element={<SettingsPage />} />

          {/* 用户资料 */}
          <Route path="profile" element={<ProfilePage />} />

          {/* Bot 管理 */}
          <Route path="bot-bindings" element={<BotBindingPage />} />

          {/* 组织管理 */}
          <Route path="org/new" element={<CreateOrgPage />} />
          <Route path="join-org" element={<JoinOrgPage />} />
          <Route path="org/:code" element={<OrganizationPage />} />
          <Route path="org/:code/settings" element={<OrganizationPage />} />
        </Route>
      </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
