import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Bot,
  Settings,
  LogOut,
  Menu,
  X,
  Sparkles,
  BarChart3,
  Database,
  User,
  Link2,
} from 'lucide-react';
import { useAuthStore, useUIStore } from '../stores';
import ContextSwitcher from './ContextSwitcher';
import clsx from 'clsx';

export default function MainLayout() {
  const navigate = useNavigate();
  const { user, logout, currentContext } = useAuthStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // 基础导航项
  const baseNavItems = [
    { path: '/chat', icon: MessageSquare, label: '对话' },
    { path: '/agents', icon: Bot, label: 'Agent 管理' },
    { path: '/knowledge', icon: Database, label: '知识库' },
    { path: '/dashboard', icon: BarChart3, label: '数据统计' },
  ];

  // 组织导航项（仅在组织上下文中显示）
  const orgNavItems = currentContext?.type === 'organization' ? [
    { path: `/org/${currentContext.orgCode}`, icon: Settings, label: '组织设置' },
  ] : [];

  // 通用设置
  const settingsNavItems = [
    { path: '/settings', icon: Settings, label: '设置' },
    { path: '/profile', icon: User, label: '个人资料' },
    { path: '/bot-bindings', icon: Link2, label: 'Bot 绑定' },
  ];

  return (
    <div className="flex h-screen bg-dark-950">
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed lg:relative inset-y-0 left-0 z-50 flex flex-col bg-dark-900 border-r border-dark-800 transition-all duration-300',
          sidebarOpen ? 'w-64' : 'w-0 lg:w-16'
        )}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-dark-800">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="font-semibold text-dark-100">NexusAgent</span>
            </div>
          )}
          <button
            onClick={toggleSidebar}
            className="p-2 hover:bg-dark-800 rounded-lg text-dark-400 hover:text-dark-200 transition-colors"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Context Switcher (collapsed view shows icon only) */}
        {sidebarOpen && (
          <div className="px-3 py-3 border-b border-dark-800">
            <ContextSwitcher />
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {/* Base navigation */}
          {baseNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all',
                  isActive
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                )
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {sidebarOpen && <span className="font-medium">{item.label}</span>}
            </NavLink>
          ))}

          {/* Organization navigation */}
          {sidebarOpen && orgNavItems.length > 0 && (
            <>
              <div className="pt-3 pb-1 px-3">
                <p className="text-xs font-medium text-dark-500 uppercase tracking-wider">
                  组织
                </p>
              </div>
              {orgNavItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all',
                      isActive
                        ? 'bg-primary-500/10 text-primary-400'
                        : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                    )
                  }
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" />
                  {sidebarOpen && <span className="font-medium">{item.label}</span>}
                </NavLink>
              ))}
            </>
          )}

          {/* Settings navigation */}
          {sidebarOpen && (
            <>
              <div className="pt-3 pb-1 px-3">
                <p className="text-xs font-medium text-dark-500 uppercase tracking-wider">
                  账户
                </p>
              </div>
              {settingsNavItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all',
                      isActive
                        ? 'bg-primary-500/10 text-primary-400'
                        : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                    )
                  }
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" />
                  {sidebarOpen && <span className="font-medium">{item.label}</span>}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* User info */}
        {sidebarOpen && (
          <div className="p-4 border-t border-dark-800">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white font-medium overflow-hidden">
                {user?.avatar ? (
                  <img src={user.avatar} alt="" className="w-10 h-10 object-cover" />
                ) : (
                  (user?.nickname || user?.username || 'U')[0].toUpperCase()
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-dark-100 truncate">
                  {user?.nickname || user?.username}
                </p>
                <p className="text-xs text-dark-500 truncate">
                  {user?.email || `@${user?.username}`}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 py-2 text-sm text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              退出登录
            </button>
          </div>
        )}
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden h-14 flex items-center justify-between px-4 border-b border-dark-800 bg-dark-900">
          <div className="flex items-center gap-3">
            <button
              onClick={toggleSidebar}
              className="p-2 hover:bg-dark-800 rounded-lg text-dark-400"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary-400" />
              <span className="font-semibold text-dark-100">NexusAgent</span>
            </div>
          </div>
          <ContextSwitcher />
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
