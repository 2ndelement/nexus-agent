import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { User, ArrowLeft, Camera, Loader2, Save, Key } from 'lucide-react';
import { useAuthStore } from '../stores';
import { authApi } from '../services/api';
import toast from 'react-hot-toast';

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, setAuth, accessToken, refreshToken, organizations } = useAuthStore();

  const [loading, setLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Profile form
  const [profileForm, setProfileForm] = useState({
    nickname: user?.nickname || '',
    email: user?.email || '',
  });

  // Password form
  const [passwordForm, setPasswordForm] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (user) {
      setProfileForm({
        nickname: user.nickname || '',
        email: user.email || '',
      });
    }
  }, [user]);

  async function handleUpdateProfile(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    const newErrors: Record<string, string> = {};

    if (profileForm.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(profileForm.email)) {
      newErrors.email = '邮箱格式不正确';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      const updatedUser = await authApi.updateProfile({
        nickname: profileForm.nickname || undefined,
        email: profileForm.email || undefined,
      });

      // Update local state
      if (user && accessToken && refreshToken) {
        setAuth({
          user: { ...user, ...updatedUser },
          accessToken,
          refreshToken,
          organizations,
        });
      }

      toast.success('个人资料已更新');
    } catch (error: any) {
      const message = error.response?.data?.msg || error.response?.data?.message || '更新失败';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    const newErrors: Record<string, string> = {};

    if (!passwordForm.oldPassword) {
      newErrors.oldPassword = '请输入当前密码';
    }

    if (!passwordForm.newPassword) {
      newErrors.newPassword = '请输入新密码';
    } else if (passwordForm.newPassword.length < 8) {
      newErrors.newPassword = '新密码至少8位';
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      newErrors.confirmPassword = '两次密码不一致';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setPasswordLoading(true);
    try {
      await authApi.changePassword({
        oldPassword: passwordForm.oldPassword,
        newPassword: passwordForm.newPassword,
      });

      // Clear form
      setPasswordForm({
        oldPassword: '',
        newPassword: '',
        confirmPassword: '',
      });

      toast.success('密码已更新');
    } catch (error: any) {
      const status = error.response?.status;
      if (status === 401 || status === 400) {
        setErrors({ oldPassword: '当前密码错误' });
      } else {
        toast.error(error.response?.data?.msg || '更新密码失败');
      }
    } finally {
      setPasswordLoading(false);
    }
  }

  if (!user) {
    return null;
  }

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/chat"
          className="inline-flex items-center gap-2 text-dark-400 hover:text-dark-200 transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </Link>
        <h1 className="text-2xl font-bold text-dark-100">个人资料</h1>
        <p className="text-dark-400 mt-1">管理您的账户信息</p>
      </div>

      {/* Profile Section */}
      <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-medium text-dark-100 mb-6">基本信息</h2>

        <form onSubmit={handleUpdateProfile} className="space-y-6">
          {/* Avatar */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-20 h-20 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white text-2xl font-medium overflow-hidden">
                {user.avatar ? (
                  <img src={user.avatar} alt="" className="w-20 h-20 object-cover" />
                ) : (
                  (user.nickname || user.username)[0].toUpperCase()
                )}
              </div>
              <button
                type="button"
                className="absolute -bottom-1 -right-1 w-8 h-8 bg-dark-700 rounded-full flex items-center justify-center text-dark-300 hover:bg-dark-600 transition-colors border-2 border-dark-800"
              >
                <Camera className="w-4 h-4" />
              </button>
            </div>
            <div>
              <p className="font-medium text-dark-100">{user.nickname || user.username}</p>
              <p className="text-sm text-dark-500">@{user.username}</p>
            </div>
          </div>

          {/* Username (readonly) */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              用户名
            </label>
            <input
              type="text"
              value={user.username}
              disabled
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-400 cursor-not-allowed"
            />
            <p className="mt-1 text-xs text-dark-500">用户名不可修改</p>
          </div>

          {/* Nickname */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              昵称
            </label>
            <input
              type="text"
              value={profileForm.nickname}
              onChange={(e) => setProfileForm({ ...profileForm, nickname: e.target.value })}
              placeholder="您的显示名称"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              maxLength={50}
            />
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              邮箱
            </label>
            <input
              type="email"
              value={profileForm.email}
              onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
              placeholder="用于找回密码和通知"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
            />
            {errors.email && (
              <p className="mt-1 text-sm text-red-400">{errors.email}</p>
            )}
          </div>

          {/* Submit */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  保存更改
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Password Section */}
      <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-medium text-dark-100 mb-6">修改密码</h2>

        <form onSubmit={handleChangePassword} className="space-y-6">
          {/* Current Password */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              当前密码
            </label>
            <input
              type="password"
              value={passwordForm.oldPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, oldPassword: e.target.value })}
              placeholder="输入当前密码"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
            />
            {errors.oldPassword && (
              <p className="mt-1 text-sm text-red-400">{errors.oldPassword}</p>
            )}
          </div>

          {/* New Password */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              新密码
            </label>
            <input
              type="password"
              value={passwordForm.newPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
              placeholder="至少8位"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
            />
            {errors.newPassword && (
              <p className="mt-1 text-sm text-red-400">{errors.newPassword}</p>
            )}
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              确认新密码
            </label>
            <input
              type="password"
              value={passwordForm.confirmPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
              placeholder="再次输入新密码"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
            />
            {errors.confirmPassword && (
              <p className="mt-1 text-sm text-red-400">{errors.confirmPassword}</p>
            )}
          </div>

          {/* Submit */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={passwordLoading}
              className="px-6 py-2.5 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {passwordLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  更新中...
                </>
              ) : (
                <>
                  <Key className="w-4 h-4" />
                  更新密码
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Quotas */}
      <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
        <h2 className="text-lg font-medium text-dark-100 mb-6">账户配额</h2>
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-dark-200">个人 Agent</p>
              <p className="text-sm text-dark-500">个人空间可创建的 Agent 数量</p>
            </div>
            <span className="text-dark-300">{user.personalAgentLimit} 个</span>
          </div>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-dark-200">创建组织</p>
              <p className="text-sm text-dark-500">您可以创建的组织数量</p>
            </div>
            <span className="text-dark-300">{user.orgCreateLimit} 个</span>
          </div>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-dark-200">加入组织</p>
              <p className="text-sm text-dark-500">您可以加入的组织数量</p>
            </div>
            <span className="text-dark-300">{user.orgJoinLimit} 个</span>
          </div>
        </div>
      </div>
    </div>
  );
}
