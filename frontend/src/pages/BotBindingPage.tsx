import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Bot,
  Plus,
  Trash2,
  Loader2,
  CheckCircle,
  XCircle,
  Link2,
  ExternalLink,
} from 'lucide-react';
import { useAuthStore } from '../stores';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { botApi, BotInfo, BotBindingInfo } from '../services/api';

// 平台标签映射
const platformLabels: Record<string, string> = {
  WEB: 'Web',
  QQ: 'QQ',
  QQ_GUILD: 'QQ 频道',
  QQ_GROUP: 'QQ 群聊',
  FEISHU: '飞书',
  WECHAT: '微信',
  TELEGRAM: 'Telegram',
};

export default function BotBindingPage() {
  const navigate = useNavigate();
  const { user, currentContext } = useAuthStore();

  const [bindings, setBindings] = useState<BotBindingInfo[]>([]);
  const [availableBots, setAvailableBots] = useState<BotInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showBindModal, setShowBindModal] = useState(false);
  const [bindingBotId, setBindingBotId] = useState<number | null>(null);
  const [bindingPuid, setBindingPuid] = useState('');
  const [binding, setBinding] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      // 加载用户的绑定列表
      const bindingsData = await botApi.listBindings();
      setBindings(bindingsData);

      // 加载可用的 Bot 列表
      const ownerType = currentContext?.type === 'organization' ? 'ORGANIZATION' : 'PERSONAL';
      const ownerId = currentContext?.type === 'organization'
        ? currentContext.orgId
        : user?.id;

      const botsResult = await botApi.list({
        ownerType,
        ownerId,
        status: 1,
      });
      setAvailableBots(botsResult.records || []);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleUnbind(bindingId: number) {
    if (!confirm('确定要解除此绑定吗？')) return;

    try {
      await botApi.deleteBinding(bindingId);
      toast.success('解绑成功');
      loadData();
    } catch (error) {
      console.error('Failed to unbind:', error);
      toast.error('解绑失败');
    }
  }

  async function handleBind() {
    if (!bindingBotId || !bindingPuid.trim()) {
      toast.error('请选择 Bot 并输入平台用户 ID');
      return;
    }

    setBinding(true);
    try {
      await botApi.createBinding({
        botId: bindingBotId,
        puid: bindingPuid.trim(),
      });
      toast.success('绑定成功');
      setShowBindModal(false);
      setBindingBotId(null);
      setBindingPuid('');
      loadData();
    } catch (error: any) {
      console.error('Failed to bind:', error);
      toast.error(error.response?.data?.message || '绑定失败');
    } finally {
      setBinding(false);
    }
  }

  // 获取 Bot 信息
  function getBotInfo(botId: number): BotInfo | undefined {
    return availableBots.find(b => b.id === botId);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-6 border-b border-dark-800 bg-dark-900/50">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-dark-800 rounded-lg text-dark-400 hover:text-dark-200 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-semibold text-dark-100">我的 Bot 绑定</h1>
          </div>
        </div>

        <button
          onClick={() => setShowBindModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          绑定新平台
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          {/* 已绑定列表 */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-dark-100 mb-4">已绑定的平台账号</h2>

            {bindings.length === 0 ? (
              <div className="text-center py-12 bg-dark-800/30 border border-dark-700 rounded-xl">
                <Link2 className="w-12 h-12 text-dark-600 mx-auto mb-4" />
                <p className="text-dark-400">暂无平台账号绑定</p>
                <p className="text-sm text-dark-500 mt-1">
                  绑定平台账号后，可以通过该平台与 Agent 对话
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {bindings.map((binding) => {
                  const botInfo = getBotInfo(binding.botId);
                  return (
                    <div
                      key={binding.id}
                      className="flex items-center justify-between p-4 bg-dark-800/50 border border-dark-700 rounded-xl"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-dark-700 rounded-xl flex items-center justify-center">
                          <Bot className="w-6 h-6 text-dark-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-dark-100">
                              {binding.botName || `Bot #${binding.botId}`}
                            </p>
                            {binding.status === 1 ? (
                              <span className="flex items-center gap-1 text-xs text-green-400">
                                <CheckCircle className="w-3 h-3" />
                                正常
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-xs text-red-400">
                                <XCircle className="w-3 h-3" />
                                已解绑
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-dark-500 mt-0.5">
                            {platformLabels[binding.botPlatform || ''] || binding.botPlatform || '未知平台'}
                            {binding.puid && ` · ${binding.puid}`}
                          </p>
                        </div>
                      </div>

                      <button
                        onClick={() => handleUnbind(binding.id)}
                        className="p-2 text-dark-400 hover:text-red-400 hover:bg-dark-700 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 可用 Bot 列表 */}
          <div>
            <h2 className="text-lg font-semibold text-dark-100 mb-4">可用的 Bot</h2>

            {availableBots.length === 0 ? (
              <div className="text-center py-8 bg-dark-800/30 border border-dark-700 rounded-xl">
                <p className="text-dark-400">暂无可用的 Bot</p>
              </div>
            ) : (
              <div className="space-y-2">
                {availableBots.map((bot) => (
                  <div
                    key={bot.id}
                    className="flex items-center justify-between p-4 bg-dark-800/30 border border-dark-700 rounded-xl"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-dark-700 rounded-lg flex items-center justify-center">
                        <Bot className="w-5 h-5 text-dark-400" />
                      </div>
                      <div>
                        <p className="font-medium text-dark-200">{bot.botName}</p>
                        <p className="text-sm text-dark-500">
                          {platformLabels[bot.platform] || bot.platform}
                          {bot.appId && ` · ${bot.appId}`}
                        </p>
                      </div>
                    </div>

                    {/* 检查是否已绑定 */}
                    {bindings.some(b => b.botId === bot.id && b.status === 1) ? (
                      <span className="text-xs text-dark-500">已绑定</span>
                    ) : (
                      <span className="text-xs text-dark-500">未绑定</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 绑定 Modal */}
      {showBindModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-800 border border-dark-700 rounded-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-dark-700">
              <h3 className="font-semibold text-dark-100">绑定平台账号</h3>
              <button
                onClick={() => setShowBindModal(false)}
                className="p-1 text-dark-400 hover:text-dark-200"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* 选择 Bot */}
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  选择 Bot <span className="text-red-400">*</span>
                </label>
                <select
                  value={bindingBotId || ''}
                  onChange={(e) => setBindingBotId(Number(e.target.value) || null)}
                  className="w-full px-4 py-2.5 bg-dark-900 border border-dark-700 rounded-lg text-dark-100"
                >
                  <option value="">请选择 Bot</option>
                  {availableBots.map((bot) => (
                    <option key={bot.id} value={bot.id}>
                      {bot.botName} ({platformLabels[bot.platform] || bot.platform})
                    </option>
                  ))}
                </select>
              </div>

              {/* 输入平台用户 ID */}
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  平台用户 ID (puid) <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={bindingPuid}
                  onChange={(e) => setBindingPuid(e.target.value)}
                  placeholder="在对应平台的 User ID"
                  className="w-full px-4 py-2.5 bg-dark-900 border border-dark-700 rounded-lg text-dark-100"
                />
                <p className="mt-2 text-xs text-dark-500">
                  请输入你在该平台的用户标识，不同平台格式不同。如 QQ 号、飞书用户 ID 等。
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 p-4 border-t border-dark-700">
              <button
                onClick={() => setShowBindModal(false)}
                className="px-4 py-2 text-dark-300 hover:bg-dark-700 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleBind}
                disabled={binding || !bindingBotId || !bindingPuid.trim()}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                  binding || !bindingBotId || !bindingPuid.trim()
                    ? 'bg-dark-700 text-dark-500 cursor-not-allowed'
                    : 'bg-primary-500 text-white hover:bg-primary-400'
                )}
              >
                {binding && <Loader2 className="w-4 h-4 animate-spin" />}
                确认绑定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
