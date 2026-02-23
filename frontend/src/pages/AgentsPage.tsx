import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  Plus,
  Search,
  MoreVertical,
  Edit,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Sparkles,
  Wrench,
  Thermometer,
} from 'lucide-react';
import { useAuthStore, useAgentStore } from '../stores';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { agentApi } from '../services/api';

export default function AgentsPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { agents, setAgents, removeAgent, updateAgent } = useAgentStore();
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState<number | null>(null);

  useEffect(() => {
    loadAgents();
  }, [user?.id]);

  async function loadAgents() {
    if (!user?.id) return;
    setLoading(true);
    try {
      const data = await agentApi.list();
      setAgents(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load agents:', error);
      toast.error('加载 Agent 列表失败');
    } finally {
      setLoading(false);
    }
  }

  async function toggleAgentStatus(id: number, currentStatus: number) {
    try {
      await agentApi.update(id, {
        status: currentStatus === 1 ? 0 : 1,
      });
      updateAgent(id, { status: currentStatus === 1 ? 0 : 1 });
      toast.success(currentStatus === 1 ? 'Agent 已禁用' : 'Agent 已启用');
    } catch (error) {
      toast.error('操作失败');
    }
    setMenuOpen(null);
  }

  async function deleteAgent(id: number) {
    if (!confirm('确定要删除这个 Agent 吗？')) return;
    try {
      await agentApi.delete(id);
      removeAgent(id);
      toast.success('Agent 已删除');
    } catch (error) {
      toast.error('删除失败');
    }
    setMenuOpen(null);
  }

  const filteredAgents = agents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(search.toLowerCase()) ||
      agent.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-dark-100">Agent 管理</h1>
          <p className="text-dark-400 mt-1">创建和管理您的 AI Agent</p>
        </div>
        <button
          onClick={() => navigate('/agents/new')}
          className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
        >
          <Plus className="w-5 h-5" />
          创建 Agent
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-500" />
        <input
          type="text"
          placeholder="搜索 Agent..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-dark-100 placeholder-dark-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
        />
      </div>

      {/* Agent Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filteredAgents.length === 0 ? (
        <EmptyState onCreateClick={() => navigate('/agents/new')} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              menuOpen={menuOpen === agent.id}
              onMenuToggle={() => setMenuOpen(menuOpen === agent.id ? null : agent.id)}
              onEdit={() => navigate(`/agents/${agent.id}`)}
              onToggleStatus={() => toggleAgentStatus(agent.id, agent.status)}
              onDelete={() => deleteAgent(agent.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  menuOpen,
  onMenuToggle,
  onEdit,
  onToggleStatus,
  onDelete,
}: {
  agent: any;
  menuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onToggleStatus: () => void;
  onDelete: () => void;
}) {
  const tools = agent.tools_enabled ? JSON.parse(agent.tools_enabled) : [];

  return (
    <div
      className={clsx(
        'bg-dark-800/50 border rounded-xl p-5 hover:border-primary-500/50 transition-all cursor-pointer group relative',
        agent.status === 1 ? 'border-dark-700' : 'border-dark-700/50 opacity-60'
      )}
      onClick={onEdit}
    >
      {/* Menu button */}
      <div
        className="absolute top-4 right-4"
        onClick={(e) => {
          e.stopPropagation();
          onMenuToggle();
        }}
      >
        <button className="p-1.5 hover:bg-dark-700 rounded-lg text-dark-400 hover:text-dark-200 transition-colors">
          <MoreVertical className="w-4 h-4" />
        </button>

        {/* Dropdown menu */}
        {menuOpen && (
          <div className="absolute right-0 top-8 w-36 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-10 py-1">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-dark-300 hover:bg-dark-700 hover:text-dark-100"
            >
              <Edit className="w-4 h-4" />
              编辑
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleStatus();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-dark-300 hover:bg-dark-700 hover:text-dark-100"
            >
              {agent.status === 1 ? (
                <>
                  <ToggleLeft className="w-4 h-4" />
                  禁用
                </>
              ) : (
                <>
                  <ToggleRight className="w-4 h-4" />
                  启用
                </>
              )}
            </button>
            <hr className="my-1 border-dark-700" />
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4" />
              删除
            </button>
          </div>
        )}
      </div>

      {/* Icon */}
      <div className="w-12 h-12 bg-gradient-to-br from-primary-400 to-primary-600 rounded-xl flex items-center justify-center mb-4">
        <Bot className="w-7 h-7 text-white" />
      </div>

      {/* Name & Status */}
      <div className="flex items-center gap-2 mb-2">
        <h3 className="font-semibold text-dark-100 truncate">{agent.name}</h3>
        <span
          className={clsx(
            'px-2 py-0.5 text-xs rounded-full',
            agent.status === 1
              ? 'bg-green-500/10 text-green-400'
              : 'bg-dark-600 text-dark-400'
          )}
        >
          {agent.status === 1 ? '启用' : '禁用'}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-dark-400 line-clamp-2 mb-4">
        {agent.description || '暂无描述'}
      </p>

      {/* Meta info */}
      <div className="flex items-center gap-4 text-xs text-dark-500">
        <span className="flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5" />
          {agent.model}
        </span>
        <span className="flex items-center gap-1">
          <Thermometer className="w-3.5 h-3.5" />
          {agent.temperature}
        </span>
        {tools.length > 0 && (
          <span className="flex items-center gap-1">
            <Wrench className="w-3.5 h-3.5" />
            {tools.length} 工具
          </span>
        )}
      </div>
    </div>
  );
}

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-dark-800 rounded-2xl flex items-center justify-center mb-4">
        <Bot className="w-8 h-8 text-dark-500" />
      </div>
      <h3 className="text-lg font-medium text-dark-200 mb-2">还没有 Agent</h3>
      <p className="text-dark-400 mb-6 max-w-md">
        创建您的第一个 AI Agent，配置系统提示词和工具，开始智能对话
      </p>
      <button
        onClick={onCreateClick}
        className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
      >
        <Plus className="w-5 h-5" />
        创建 Agent
      </button>
    </div>
  );
}
