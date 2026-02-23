import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Building2, ArrowLeft, Check, Loader2 } from 'lucide-react';
import { useAuthStore } from '../stores';
import { organizationApi } from '../services/api';
import toast from 'react-hot-toast';

export default function CreateOrgPage() {
  const navigate = useNavigate();
  const { user, addOrganization, switchContext } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [form, setForm] = useState({
    name: '',
    code: '',
    description: '',
  });

  // 自动生成 code
  function handleNameChange(name: string) {
    setForm(prev => ({
      ...prev,
      name,
      // 自动生成 code（如果用户没有手动修改过）
      code: prev.code === generateCode(prev.name) || prev.code === ''
        ? generateCode(name)
        : prev.code,
    }));
  }

  function generateCode(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .slice(0, 50);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    // 验证
    const newErrors: Record<string, string> = {};

    if (!form.name.trim()) {
      newErrors.name = '请输入组织名称';
    }

    if (!form.code.trim()) {
      newErrors.code = '请输入组织代码';
    } else if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(form.code)) {
      newErrors.code = '组织代码只能包含小写字母、数字和横线，且不能以横线开头或结尾';
    } else if (form.code.length < 3 || form.code.length > 50) {
      newErrors.code = '组织代码长度应在 3-50 字符之间';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      const org = await organizationApi.create({
        code: form.code,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      });

      // 添加到本地状态
      addOrganization({
        ...org,
        role: 'OWNER',
      });

      // 切换到新组织
      switchContext({
        type: 'organization',
        orgCode: org.code,
        orgId: org.id,
      });

      toast.success('组织创建成功！');
      navigate(`/org/${org.code}`);
    } catch (error: any) {
      const message = error.response?.data?.msg || error.response?.data?.message || '创建失败，请重试';
      if (message.includes('code') || message.includes('已存在')) {
        setErrors({ code: '该组织代码已被使用' });
      } else {
        toast.error(message);
      }
    } finally {
      setLoading(false);
    }
  }

  // 检查配额
  const ownedCount = useAuthStore.getState().organizations.filter(o => o.role === 'OWNER').length;
  const canCreate = user ? ownedCount < user.orgCreateLimit : false;

  if (!canCreate) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-dark-800/50 border border-dark-700 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 bg-yellow-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-yellow-500" />
          </div>
          <h1 className="text-xl font-semibold text-dark-100 mb-2">
            已达创建上限
          </h1>
          <p className="text-dark-400 mb-6">
            您已创建 {ownedCount} 个组织，达到上限（{user?.orgCreateLimit} 个）。
            如需创建更多组织，请升级账户或删除现有组织。
          </p>
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            返回
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-950 p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 text-dark-400 hover:text-dark-200 transition-colors mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            返回
          </Link>
          <h1 className="text-2xl font-bold text-dark-100">创建组织</h1>
          <p className="text-dark-400 mt-1">
            创建一个新组织，邀请团队成员协作使用 Agent
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6 space-y-6">
            {/* 组织名称 */}
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                组织名称 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="例如：我的团队"
                className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                maxLength={100}
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-400">{errors.name}</p>
              )}
            </div>

            {/* 组织代码 */}
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                组织代码 <span className="text-red-400">*</span>
              </label>
              <div className="flex items-center gap-2">
                <span className="text-dark-500">/org/</span>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="my-team"
                  className="flex-1 px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                  maxLength={50}
                />
              </div>
              <p className="mt-1 text-xs text-dark-500">
                用于 URL 和 API 调用，只能包含小写字母、数字和横线
              </p>
              {errors.code && (
                <p className="mt-1 text-sm text-red-400">{errors.code}</p>
              )}
            </div>

            {/* 组织描述 */}
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                组织描述 <span className="text-dark-500">(可选)</span>
              </label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="简要描述您的组织..."
                rows={3}
                className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors resize-none"
                maxLength={500}
              />
            </div>
          </div>

          {/* 配额提示 */}
          <div className="bg-primary-500/10 border border-primary-500/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-primary-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="text-dark-200 font-medium">免费套餐包含：</p>
                <ul className="text-dark-400 mt-1 space-y-0.5">
                  <li>• 最多 5 名成员</li>
                  <li>• 最多 10 个 Agent</li>
                  <li>• 基础工具和知识库</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Submit */}
          <div className="flex items-center justify-end gap-4">
            <Link
              to="/chat"
              className="px-6 py-2.5 text-dark-300 hover:text-dark-100 transition-colors"
            >
              取消
            </Link>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  创建中...
                </>
              ) : (
                <>
                  <Building2 className="w-4 h-4" />
                  创建组织
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
