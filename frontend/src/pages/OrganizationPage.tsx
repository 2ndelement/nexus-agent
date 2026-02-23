import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Building2,
  Users,
  Settings,
  ArrowLeft,
  Trash2,
  Copy,
  Check,
  Loader2,
  Bot,
  Crown,
  Shield,
  UserMinus,
  MoreVertical,
} from 'lucide-react';
import { useAuthStore } from '../stores';
import { organizationApi } from '../services/api';
import type { Organization, OrganizationMember, OrganizationInvite } from '../types';
import toast from 'react-hot-toast';

export default function OrganizationPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { user, organizations, updateOrganization, removeOrganization, switchContext } = useAuthStore();

  const [loading, setLoading] = useState(true);
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [invites, setInvites] = useState<OrganizationInvite[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'members' | 'settings'>('overview');

  // 当前用户在组织中的角色
  const myRole = organizations.find(o => o.code === code)?.role;
  const isOwner = myRole === 'OWNER';
  const isAdmin = myRole === 'ADMIN' || isOwner;

  useEffect(() => {
    if (code) {
      loadOrganization();
    }
  }, [code]);

  async function loadOrganization() {
    if (!code) return;

    setLoading(true);
    try {
      const [orgData, membersData] = await Promise.all([
        organizationApi.getByCode(code),
        isAdmin ? organizationApi.listMembers(code) : Promise.resolve([]),
      ]);

      setOrg(orgData);
      setMembers(membersData);

      if (isAdmin) {
        const invitesData = await organizationApi.listInvites(code);
        setInvites(invitesData);
      }
    } catch (error) {
      toast.error('加载组织信息失败');
      navigate('/chat');
    } finally {
      setLoading(false);
    }
  }

  // 创建邀请
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteRole, setInviteRole] = useState<'ADMIN' | 'MEMBER'>('MEMBER');
  const [newInviteCode, setNewInviteCode] = useState<string | null>(null);

  async function handleCreateInvite() {
    if (!code) return;

    setInviteLoading(true);
    try {
      const invite = await organizationApi.createInvite(code, { role: inviteRole });
      setNewInviteCode(invite.inviteCode);
      setInvites([invite, ...invites]);
      toast.success('邀请码已创建');
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '创建邀请失败');
    } finally {
      setInviteLoading(false);
    }
  }

  // 复制邀请码
  const [copied, setCopied] = useState(false);
  function copyInviteCode() {
    if (newInviteCode) {
      navigator.clipboard.writeText(newInviteCode);
      setCopied(true);
      toast.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    }
  }

  // 移除成员
  async function handleRemoveMember(memberId: number, memberUsername: string) {
    if (!code) return;
    if (!confirm(`确定要移除成员 ${memberUsername} 吗？`)) return;

    try {
      await organizationApi.removeMember(code, memberId);
      setMembers(members.filter(m => m.userId !== memberId));
      toast.success('成员已移除');
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '移除失败');
    }
  }

  // 离开组织
  async function handleLeave() {
    if (!code) return;
    if (!confirm('确定要离开此组织吗？')) return;

    try {
      await organizationApi.leaveOrganization(code);
      removeOrganization(code);
      toast.success('已离开组织');
      navigate('/chat');
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '离开失败');
    }
  }

  // 删除组织
  const [deleteConfirm, setDeleteConfirm] = useState('');
  async function handleDelete() {
    if (!code || !org) return;
    if (deleteConfirm !== org.name) {
      toast.error('请输入正确的组织名称确认');
      return;
    }

    try {
      await organizationApi.delete(code);
      removeOrganization(code);
      toast.success('组织已删除');
      navigate('/chat');
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '删除失败');
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
      </div>
    );
  }

  if (!org) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-dark-400">组织不存在</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start gap-4 mb-8">
        <Link
          to="/chat"
          className="p-2 hover:bg-dark-800 rounded-lg text-dark-400 hover:text-dark-200 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>

        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 bg-dark-800 rounded-xl flex items-center justify-center">
              {org.avatar ? (
                <img src={org.avatar} alt="" className="w-12 h-12 rounded-xl object-cover" />
              ) : (
                <Building2 className="w-6 h-6 text-dark-400" />
              )}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-dark-100">{org.name}</h1>
              <p className="text-dark-500 text-sm">/{org.code}</p>
            </div>
          </div>
          {org.description && (
            <p className="text-dark-400 mt-2">{org.description}</p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-dark-800 mb-6">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'overview'
              ? 'text-primary-400 border-primary-400'
              : 'text-dark-400 border-transparent hover:text-dark-200'
          }`}
        >
          概览
        </button>
        {isAdmin && (
          <button
            onClick={() => setActiveTab('members')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'members'
                ? 'text-primary-400 border-primary-400'
                : 'text-dark-400 border-transparent hover:text-dark-200'
            }`}
          >
            成员
          </button>
        )}
        {isOwner && (
          <button
            onClick={() => setActiveTab('settings')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'settings'
                ? 'text-primary-400 border-primary-400'
                : 'text-dark-400 border-transparent hover:text-dark-200'
            }`}
          >
            设置
          </button>
        )}
      </div>

      {/* Content */}
      {activeTab === 'overview' && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Stats */}
          <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
            <h3 className="text-lg font-medium text-dark-100 mb-4">组织信息</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-dark-400">套餐</span>
                <span className="text-dark-200">{org.plan}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">成员数量</span>
                <span className="text-dark-200">{org.memberCount || members.length} / {org.memberLimit}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">Agent 数量</span>
                <span className="text-dark-200">- / {org.agentLimit}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">您的角色</span>
                <span className="text-dark-200">{getRoleLabel(myRole || 'MEMBER')}</span>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
            <h3 className="text-lg font-medium text-dark-100 mb-4">快捷操作</h3>
            <div className="space-y-3">
              <Link
                to="/agents"
                className="flex items-center gap-3 p-3 bg-dark-900 rounded-lg hover:bg-dark-800 transition-colors"
              >
                <Bot className="w-5 h-5 text-primary-400" />
                <span className="text-dark-200">管理 Agent</span>
              </Link>
              {!isOwner && (
                <button
                  onClick={handleLeave}
                  className="w-full flex items-center gap-3 p-3 bg-dark-900 rounded-lg hover:bg-red-500/10 text-dark-400 hover:text-red-400 transition-colors"
                >
                  <UserMinus className="w-5 h-5" />
                  <span>离开组织</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'members' && isAdmin && (
        <div className="space-y-6">
          {/* Invite */}
          <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
            <h3 className="text-lg font-medium text-dark-100 mb-4">邀请成员</h3>

            {newInviteCode ? (
              <div className="space-y-4">
                <p className="text-dark-400 text-sm">将此邀请码发送给要邀请的成员：</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-4 py-3 bg-dark-900 rounded-lg text-primary-400 font-mono text-lg">
                    {newInviteCode}
                  </code>
                  <button
                    onClick={copyInviteCode}
                    className="p-3 bg-dark-900 rounded-lg hover:bg-dark-800 transition-colors"
                  >
                    {copied ? (
                      <Check className="w-5 h-5 text-green-400" />
                    ) : (
                      <Copy className="w-5 h-5 text-dark-400" />
                    )}
                  </button>
                </div>
                <button
                  onClick={() => setNewInviteCode(null)}
                  className="text-sm text-dark-400 hover:text-dark-200"
                >
                  创建新邀请
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'ADMIN' | 'MEMBER')}
                  className="px-4 py-2 bg-dark-900 border border-dark-600 rounded-lg text-dark-200"
                >
                  <option value="MEMBER">成员</option>
                  <option value="ADMIN">管理员</option>
                </select>
                <button
                  onClick={handleCreateInvite}
                  disabled={inviteLoading}
                  className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors disabled:opacity-50"
                >
                  {inviteLoading ? '创建中...' : '生成邀请码'}
                </button>
              </div>
            )}
          </div>

          {/* Members List */}
          <div className="bg-dark-800/50 border border-dark-700 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-dark-700">
              <h3 className="text-lg font-medium text-dark-100">成员列表</h3>
            </div>
            <div className="divide-y divide-dark-700">
              {members.map((member) => (
                <div key={member.id} className="flex items-center gap-4 p-4">
                  <div className="w-10 h-10 bg-dark-700 rounded-full flex items-center justify-center text-dark-300">
                    {member.avatar ? (
                      <img src={member.avatar} alt="" className="w-10 h-10 rounded-full object-cover" />
                    ) : (
                      member.nickname?.[0] || member.username[0]
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-dark-100 truncate">
                      {member.nickname || member.username}
                    </p>
                    <p className="text-sm text-dark-500 truncate">
                      @{member.username}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {member.role === 'OWNER' && (
                      <span className="flex items-center gap-1 px-2 py-1 bg-yellow-500/10 text-yellow-500 rounded text-xs">
                        <Crown className="w-3 h-3" />
                        所有者
                      </span>
                    )}
                    {member.role === 'ADMIN' && (
                      <span className="flex items-center gap-1 px-2 py-1 bg-blue-500/10 text-blue-500 rounded text-xs">
                        <Shield className="w-3 h-3" />
                        管理员
                      </span>
                    )}
                    {isOwner && member.role !== 'OWNER' && member.userId !== user?.id && (
                      <button
                        onClick={() => handleRemoveMember(member.userId, member.username)}
                        className="p-1 text-dark-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'settings' && isOwner && (
        <div className="space-y-6">
          {/* Danger Zone */}
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-6">
            <h3 className="text-lg font-medium text-red-400 mb-4">危险区域</h3>
            <div className="space-y-4">
              <p className="text-dark-400 text-sm">
                删除组织将永久移除所有成员、Agent 和数据。此操作不可撤销。
              </p>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                  placeholder={`输入 "${org.name}" 确认`}
                  className="flex-1 px-4 py-2 bg-dark-900 border border-dark-600 rounded-lg text-dark-200 placeholder-dark-500"
                />
                <button
                  onClick={handleDelete}
                  disabled={deleteConfirm !== org.name}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  删除组织
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function getRoleLabel(role: string): string {
  switch (role) {
    case 'OWNER': return '所有者';
    case 'ADMIN': return '管理员';
    case 'MEMBER': return '成员';
    default: return role;
  }
}
