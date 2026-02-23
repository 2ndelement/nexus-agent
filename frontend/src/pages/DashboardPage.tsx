import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  Zap,
  MessageSquare,
  Bot,
  Users,
  Database,
  Clock,
  RefreshCw,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useAuthStore } from '../stores';
import axios from 'axios';
import clsx from 'clsx';

const API_BASE = '';
const LLM_PROXY_API = '/llm-api';
const RAG_API_BASE = '/rag-api';

interface Stats {
  total_requests: number;
  total_tokens: number;
  by_model: Record<string, {
    requests: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  }>;
}

interface DashboardStats {
  totalConversations: number;
  totalMessages: number;
  totalAgents: number;
  totalUsers: number;
  totalKnowledgeBases: number;
  activeToday: number;
}

const COLORS = ['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

export default function DashboardPage() {
  const { user, currentContext } = useAuthStore();

  const [llmStats, setLlmStats] = useState<Stats | null>(null);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
    totalConversations: 0,
    totalMessages: 0,
    totalAgents: 0,
    totalUsers: 0,
    totalKnowledgeBases: 0,
    activeToday: 0,
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  useEffect(() => {
    loadAllStats();
    const interval = setInterval(loadAllStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [user?.id, currentContext]);

  async function loadAllStats() {
    setLoading(true);
    await Promise.all([loadLlmStats(), loadDashboardStats()]);
    setLastUpdated(new Date());
    setLoading(false);
  }

  async function loadLlmStats() {
    try {
      const response = await axios.get(`${LLM_PROXY_API}/v1/stats`);
      setLlmStats(response.data);
    } catch (error) {
      console.error('Failed to load LLM stats:', error);
    }
  }

  async function loadDashboardStats() {
    try {
      // Load various stats from different endpoints
      // X-Context header is automatically added by axios interceptor
      const [agentsRes, usersRes] = await Promise.all([
        axios.get(`/api/v1/agents`).catch(() => ({ data: { data: [] } })),
        axios.get(`/api/v1/users`).catch(() => ({ data: { data: [] } })),
      ]);

      const agents = agentsRes.data.data || agentsRes.data || [];
      const users = usersRes.data.data || usersRes.data || [];

      setDashboardStats({
        totalConversations: Math.floor(Math.random() * 100) + 50, // Placeholder
        totalMessages: Math.floor(Math.random() * 500) + 200,
        totalAgents: Array.isArray(agents) ? agents.length : 0,
        totalUsers: Array.isArray(users) ? users.length : 0,
        totalKnowledgeBases: Math.floor(Math.random() * 10) + 1,
        activeToday: Math.floor(Math.random() * 30) + 10,
      });
    } catch (error) {
      console.error('Failed to load dashboard stats:', error);
    }
  }

  // Prepare chart data
  const modelData = llmStats?.by_model
    ? Object.entries(llmStats.by_model).map(([model, data]) => ({
        name: model,
        requests: data.requests,
        input: data.prompt_tokens,
        output: data.completion_tokens,
        total: data.total_tokens,
      }))
    : [];

  // Mock usage trend data
  const usageTrendData = Array.from({ length: 7 }, (_, i) => ({
    date: new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('zh-CN', { weekday: 'short' }),
    tokens: Math.floor(Math.random() * 10000) + 5000,
    requests: Math.floor(Math.random() * 100) + 50,
  }));

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-dark-100">数据统计</h1>
          <p className="text-dark-400 mt-1">查看系统使用情况和 Token 消耗</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-dark-500">
            上次更新: {lastUpdated.toLocaleTimeString()}
          </span>
          <button
            onClick={loadAllStats}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 bg-dark-800 hover:bg-dark-700 border border-dark-700 rounded-lg text-dark-300 transition-colors"
          >
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            刷新
          </button>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <StatCard
          icon={<MessageSquare className="w-5 h-5" />}
          label="对话数"
          value={dashboardStats.totalConversations}
          color="primary"
        />
        <StatCard
          icon={<Zap className="w-5 h-5" />}
          label="消息数"
          value={dashboardStats.totalMessages}
          color="yellow"
        />
        <StatCard
          icon={<Bot className="w-5 h-5" />}
          label="Agent 数"
          value={dashboardStats.totalAgents}
          color="purple"
        />
        <StatCard
          icon={<Users className="w-5 h-5" />}
          label="用户数"
          value={dashboardStats.totalUsers}
          color="green"
        />
        <StatCard
          icon={<Database className="w-5 h-5" />}
          label="知识库"
          value={dashboardStats.totalKnowledgeBases}
          color="blue"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="今日活跃"
          value={dashboardStats.activeToday}
          color="pink"
        />
      </div>

      {/* Token Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-dark-100 mb-4">Token 使用趋势</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usageTrendData}>
                <defs>
                  <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="tokens"
                  stroke="#0ea5e9"
                  fillOpacity={1}
                  fill="url(#colorTokens)"
                  name="Token 数"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-dark-100 mb-4">LLM 调用统计</h3>
          {llmStats ? (
            <div className="space-y-4">
              <div className="text-center py-4">
                <p className="text-4xl font-bold text-primary-400">
                  {(llmStats.total_requests ?? 0).toLocaleString()}
                </p>
                <p className="text-dark-400 mt-1">总请求数</p>
              </div>
              <div className="text-center py-4 border-t border-dark-700">
                <p className="text-4xl font-bold text-green-400">
                  {(llmStats.total_tokens ?? 0).toLocaleString()}
                </p>
                <p className="text-dark-400 mt-1">总 Token 数</p>
              </div>
              <div className="text-center py-4 border-t border-dark-700">
                <p className="text-2xl font-bold text-yellow-400">
                  ${((llmStats.total_tokens ?? 0) * 0.00001).toFixed(4)}
                </p>
                <p className="text-dark-400 mt-1">预估费用</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-dark-500">
              暂无数据
            </div>
          )}
        </div>
      </div>

      {/* Model Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-dark-100 mb-4">模型使用分布</h3>
          {modelData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={modelData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="requests"
                  >
                    {modelData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap justify-center gap-4 mt-4">
                {modelData.map((model, index) => (
                  <div key={model.name} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <span className="text-sm text-dark-300">{model.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-dark-500">
              暂无数据
            </div>
          )}
        </div>

        <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-dark-100 mb-4">模型 Token 消耗</h3>
          {modelData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={modelData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" stroke="#64748b" fontSize={12} />
                  <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={12} width={80} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar dataKey="input" name="输入 Token" stackId="a" fill="#0ea5e9" />
                  <Bar dataKey="output" name="输出 Token" stackId="a" fill="#8b5cf6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-dark-500">
              暂无数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
}) {
  const colorClasses = {
    primary: 'bg-primary-500/10 text-primary-400',
    yellow: 'bg-yellow-500/10 text-yellow-400',
    purple: 'bg-purple-500/10 text-purple-400',
    green: 'bg-green-500/10 text-green-400',
    blue: 'bg-blue-500/10 text-blue-400',
    pink: 'bg-pink-500/10 text-pink-400',
  }[color] || 'bg-dark-700 text-dark-400';

  return (
    <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-4">
      <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center mb-3', colorClasses)}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-dark-100">{(value ?? 0).toLocaleString()}</p>
      <p className="text-sm text-dark-500">{label}</p>
    </div>
  );
}
