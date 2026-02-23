import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Eye, EyeOff, LogIn, UserPlus, Sparkles, Zap, Shield, Globe, Home, Building2 } from 'lucide-react';
import { useAuthStore } from '../stores';
import { authApi } from '../services/api';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // 登录表单
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: '',
    rememberMe: false,
  });

  // 注册表单
  const [registerForm, setRegisterForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  // 表单验证错误
  const [errors, setErrors] = useState<Record<string, string>>({});

  // 登录处理
  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    // 验证
    const newErrors: Record<string, string> = {};
    if (!loginForm.username) {
      newErrors.username = '请输入用户名或邮箱';
    }
    if (!loginForm.password) {
      newErrors.password = '请输入密码';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.login({
        username: loginForm.username,
        password: loginForm.password,
      });

      // 保存到 store
      setAuth({
        user: response.user,
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        organizations: response.organizations,
      });

      toast.success(`欢迎回来，${response.user.nickname || response.user.username}！`);
      navigate('/chat');
    } catch (error: any) {
      const message = error.response?.data?.msg || error.response?.data?.message || '用户名或密码错误';
      toast.error(message);
      setErrors({ general: message });
    } finally {
      setLoading(false);
    }
  }

  // 注册处理
  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    // 验证
    const newErrors: Record<string, string> = {};

    if (!registerForm.username) {
      newErrors.username = '请输入用户名';
    } else if (!/^[a-zA-Z0-9_]{3,50}$/.test(registerForm.username)) {
      newErrors.username = '用户名只能包含字母、数字、下划线，3-50字符';
    }

    if (registerForm.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerForm.email)) {
      newErrors.email = '邮箱格式不正确';
    }

    if (!registerForm.password) {
      newErrors.password = '请输入密码';
    } else if (registerForm.password.length < 8) {
      newErrors.password = '密码至少8位';
    }

    if (registerForm.password !== registerForm.confirmPassword) {
      newErrors.confirmPassword = '两次密码不一致';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.register({
        username: registerForm.username,
        email: registerForm.email || undefined,
        password: registerForm.password,
      });

      // 保存到 store
      setAuth({
        user: response.user,
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        organizations: response.organizations || [],
      });

      toast.success('注册成功！欢迎加入 NexusAgent');
      navigate('/chat');
    } catch (error: any) {
      const message = error.response?.data?.msg || error.response?.data?.message || '注册失败，请重试';
      toast.error(message);
      setErrors({ general: message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-950 via-dark-900 to-dark-950 flex items-center justify-center p-4">
      {/* 背景装饰 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-5xl flex gap-8 relative">
        {/* 左侧品牌区 */}
        <div className="hidden lg:flex flex-col justify-center flex-1 pr-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-gradient-to-br from-primary-400 to-primary-600 rounded-xl flex items-center justify-center">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white">NexusAgent</h1>
          </div>

          <p className="text-xl text-dark-300 mb-8">
            下一代 AI Agent 平台，让智能助手为您的业务赋能
          </p>

          <div className="space-y-4">
            <FeatureItem
              icon={<Home className="w-5 h-5" />}
              title="个人空间"
              description="每个用户都有独立的工作空间和 Agent"
            />
            <FeatureItem
              icon={<Building2 className="w-5 h-5" />}
              title="组织协作"
              description="创建或加入组织，团队共享 Agent 资源"
            />
            <FeatureItem
              icon={<Shield className="w-5 h-5" />}
              title="权限隔离"
              description="组织内 Agent 权限独立，数据安全可控"
            />
            <FeatureItem
              icon={<Globe className="w-5 h-5" />}
              title="丰富的工具生态"
              description="内置工具 + MCP Server，无限扩展可能"
            />
          </div>
        </div>

        {/* 右侧表单区 */}
        <div className="flex-1 max-w-md">
          <div className="bg-dark-800/50 backdrop-blur-xl border border-dark-700 rounded-2xl p-8 shadow-2xl">
            {/* Tab 切换 */}
            <div className="flex bg-dark-900 rounded-lg p-1 mb-6">
              <button
                onClick={() => setMode('login')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                  mode === 'login'
                    ? 'bg-primary-500 text-white'
                    : 'text-dark-400 hover:text-dark-200'
                }`}
              >
                <LogIn className="w-4 h-4 inline-block mr-2" />
                登录
              </button>
              <button
                onClick={() => setMode('register')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                  mode === 'register'
                    ? 'bg-primary-500 text-white'
                    : 'text-dark-400 hover:text-dark-200'
                }`}
              >
                <UserPlus className="w-4 h-4 inline-block mr-2" />
                注册
              </button>
            </div>

            {mode === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                {/* 用户名/邮箱 */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    用户名 / 邮箱
                  </label>
                  <input
                    type="text"
                    value={loginForm.username}
                    onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                    placeholder="请输入用户名或邮箱"
                    className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                    autoComplete="username"
                  />
                  {errors.username && (
                    <p className="mt-1 text-sm text-red-400">{errors.username}</p>
                  )}
                </div>

                {/* 密码 */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    密码
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={loginForm.password}
                      onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                      placeholder="请输入密码"
                      className="w-full px-4 py-3 pr-12 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="mt-1 text-sm text-red-400">{errors.password}</p>
                  )}
                </div>

                {/* 记住我 & 忘记密码 */}
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm text-dark-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={loginForm.rememberMe}
                      onChange={(e) => setLoginForm({ ...loginForm, rememberMe: e.target.checked })}
                      className="rounded border-dark-600 bg-dark-900 text-primary-500 focus:ring-primary-500"
                    />
                    记住我
                  </label>
                  <Link to="/forgot-password" className="text-sm text-primary-400 hover:text-primary-300 transition-colors">
                    忘记密码？
                  </Link>
                </div>

                {/* 通用错误 */}
                {errors.general && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <p className="text-sm text-red-400 text-center">{errors.general}</p>
                  </div>
                )}

                {/* 登录按钮 */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg font-medium hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg shadow-primary-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      登录中...
                    </span>
                  ) : '登录'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                {/* 用户名 */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    用户名 <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={registerForm.username}
                    onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                    placeholder="3-50位，字母数字下划线"
                    className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                    autoComplete="username"
                  />
                  {errors.username && (
                    <p className="mt-1 text-sm text-red-400">{errors.username}</p>
                  )}
                </div>

                {/* 邮箱（可选） */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    邮箱 <span className="text-dark-500">(可选)</span>
                  </label>
                  <input
                    type="email"
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                    placeholder="用于找回密码"
                    className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                    autoComplete="email"
                  />
                  {errors.email && (
                    <p className="mt-1 text-sm text-red-400">{errors.email}</p>
                  )}
                </div>

                {/* 密码 */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    密码 <span className="text-red-400">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                      placeholder="至少8位"
                      className="w-full px-4 py-3 pr-12 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="mt-1 text-sm text-red-400">{errors.password}</p>
                  )}
                </div>

                {/* 确认密码 */}
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    确认密码 <span className="text-red-400">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={registerForm.confirmPassword}
                      onChange={(e) => setRegisterForm({ ...registerForm, confirmPassword: e.target.value })}
                      placeholder="再次输入密码"
                      className="w-full px-4 py-3 pr-12 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200 transition-colors"
                    >
                      {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <p className="mt-1 text-sm text-red-400">{errors.confirmPassword}</p>
                  )}
                </div>

                {/* 通用错误 */}
                {errors.general && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <p className="text-sm text-red-400 text-center">{errors.general}</p>
                  </div>
                )}

                {/* 注册按钮 */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg font-medium hover:from-primary-400 hover:to-primary-500 transition-all shadow-lg shadow-primary-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      注册中...
                    </span>
                  ) : '注册'}
                </button>

                {/* 提示信息 */}
                <div className="p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
                  <p className="text-xs text-primary-300 text-center">
                    注册后您将获得个人空间，可随时创建或加入组织
                  </p>
                </div>
              </form>
            )}

            <p className="mt-6 text-center text-xs text-dark-500">
              登录即表示您同意我们的
              <Link to="/terms" className="text-primary-400 hover:underline mx-1">服务条款</Link>
              和
              <Link to="/privacy" className="text-primary-400 hover:underline mx-1">隐私政策</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureItem({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-4">
      <div className="w-10 h-10 bg-primary-500/10 rounded-lg flex items-center justify-center text-primary-400 flex-shrink-0">
        {icon}
      </div>
      <div>
        <h3 className="font-medium text-dark-100">{title}</h3>
        <p className="text-sm text-dark-400">{description}</p>
      </div>
    </div>
  );
}
