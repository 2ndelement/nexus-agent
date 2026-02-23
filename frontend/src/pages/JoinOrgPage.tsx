import React, { useState } from 'react';
import { useNavigate, Link, useParams } from 'react-router-dom';
import { Link as LinkIcon, ArrowLeft, Loader2, Users, CheckCircle } from 'lucide-react';
import { useAuthStore } from '../stores';
import { organizationApi } from '../services/api';
import toast from 'react-hot-toast';

export default function JoinOrgPage() {
  const navigate = useNavigate();
  const { inviteCode: urlInviteCode } = useParams();
  const { user, addOrganization, switchContext, organizations } = useAuthStore();

  const [loading, setLoading] = useState(false);
  const [inviteCode, setInviteCode] = useState(urlInviteCode || '');
  const [success, setSuccess] = useState(false);
  const [joinedOrg, setJoinedOrg] = useState<{ name: string; code: string } | null>(null);

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault();

    if (!inviteCode.trim()) {
      toast.error('请输入邀请码');
      return;
    }

    setLoading(true);
    try {
      const org = await organizationApi.acceptInvite(inviteCode.trim());

      // 添加到本地状态
      addOrganization(org);

      setJoinedOrg({ name: org.name, code: org.code });
      setSuccess(true);

      toast.success(`成功加入 ${org.name}！`);
    } catch (error: any) {
      const status = error.response?.status;
      const message = error.response?.data?.msg || error.response?.data?.message;

      if (status === 404) {
        toast.error('邀请码无效或已过期');
      } else if (status === 409) {
        toast.error('您已经是该组织的成员');
      } else {
        toast.error(message || '加入失败，请重试');
      }
    } finally {
      setLoading(false);
    }
  }

  function handleGoToOrg() {
    if (joinedOrg) {
      switchContext({
        type: 'organization',
        orgCode: joinedOrg.code,
        orgId: 0, // Will be resolved by the context
      });
      navigate('/chat');
    }
  }

  // 检查配额
  const joinedCount = organizations.length;
  const canJoin = user ? joinedCount < user.orgJoinLimit : false;

  if (!canJoin && !success) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-dark-800/50 border border-dark-700 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 bg-yellow-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Users className="w-8 h-8 text-yellow-500" />
          </div>
          <h1 className="text-xl font-semibold text-dark-100 mb-2">
            已达加入上限
          </h1>
          <p className="text-dark-400 mb-6">
            您已加入 {joinedCount} 个组织，达到上限（{user?.orgJoinLimit} 个）。
            如需加入更多组织，请升级账户或退出现有组织。
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

  if (success && joinedOrg) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-dark-800/50 border border-dark-700 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-xl font-semibold text-dark-100 mb-2">
            加入成功！
          </h1>
          <p className="text-dark-400 mb-6">
            您已成功加入 <span className="text-dark-200 font-medium">{joinedOrg.name}</span>
          </p>
          <div className="flex flex-col gap-3">
            <button
              onClick={handleGoToOrg}
              className="w-full px-4 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors font-medium"
            >
              进入组织
            </button>
            <Link
              to="/chat"
              className="w-full px-4 py-2.5 text-dark-400 hover:text-dark-200 transition-colors"
            >
              返回首页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <LinkIcon className="w-8 h-8 text-primary-400" />
          </div>
          <h1 className="text-2xl font-bold text-dark-100">加入组织</h1>
          <p className="text-dark-400 mt-2">
            输入邀请码加入团队
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleJoin} className="bg-dark-800/50 border border-dark-700 rounded-2xl p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              邀请码
            </label>
            <input
              type="text"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value.trim())}
              placeholder="输入邀请码"
              className="w-full px-4 py-3 rounded-lg border border-dark-600 bg-dark-900 text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors text-center text-lg tracking-wider font-mono"
              autoFocus
            />
            <p className="mt-2 text-xs text-dark-500 text-center">
              向组织管理员获取邀请码
            </p>
          </div>

          <button
            type="submit"
            disabled={loading || !inviteCode.trim()}
            className="w-full py-3 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                加入中...
              </>
            ) : (
              '加入组织'
            )}
          </button>
        </form>

        {/* Back link */}
        <div className="text-center mt-6">
          <Link
            to="/chat"
            className="inline-flex items-center gap-2 text-dark-400 hover:text-dark-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            返回
          </Link>
        </div>
      </div>
    </div>
  );
}
