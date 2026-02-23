import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Send,
  Bot,
  User,
  Sparkles,
  Plus,
  Copy,
  Check,
  StopCircle,
  MessageSquare,
  Trash2,
  Edit3,
  MoreHorizontal,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Clock,
  X,
  AlertCircle,
  Terminal,
  Loader2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import mermaid from 'mermaid';
import { useAuthStore, useChatStore, useAgentStore } from '../stores';
import api, { chatApi } from '../services/api';
import type { ToolCallInfo, MediaAttachment, MessageTimelineItem, ContextStatsInfo } from '../types';
import { ToolCallTimer } from '../components/ToolCallTimer';
import { MediaRenderer } from '../components/MediaRenderer';
import FollowupInput from '../components/FollowupInput';
import FollowupQueueStatus, { type FollowupInfo } from '../components/FollowupQueueStatus';
import ContextTokenStatus from '../components/ContextTokenStatus';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

const API_BASE = '';

interface Conversation {
  id: number;
  conversation_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export default function ChatPage() {
  const { conversationId: urlConvId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { agents, setAgents, currentAgent, setCurrentAgent } = useAgentStore();
  const {
    conversationId,
    messages,
    isStreaming,
    isSendingNewMessage,
    setConversationId,
    addMessage,
    appendToLastMessage,
    addToolCallToLastMessage,
    updateToolCallInLastMessage,
    appendTimelineToLastMessage,
    upsertFollowupInLastMessage,
    setContextStatsOnLastMessage,
    setLastMessageError,
    setLastMessageStatus,
    addAttachmentToLastMessage,
    setLastMessageThinking,
    setStreaming,
    setSendingNewMessage,
    clearMessages,
    resetConversation,
  } = useChatStore();

  const [input, setInput] = useState('');
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [followups, setFollowups] = useState<FollowupInfo[]>([]);  // V5: Follow-up 消息队列
  const [contextStats, setContextStats] = useState<ContextStatsInfo>({ tokenCount: 0, maxContext: 128000 });  // V5: 上下文统计
  const [editingTitle, setEditingTitle] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<number, 'up' | 'down'>>({});
  const [showClearModal, setShowClearModal] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  // Load agents and conversations
  useEffect(() => {
    if (user?.id) {
      loadAgents();
      loadConversations();
    }
  }, [user?.id]);

  // Initialize conversation - 只在 URL 有 convId 时加载消息
  useEffect(() => {
    if (urlConvId) {
      setConversationId(urlConvId);
      setStreaming(false);
      // 如果是发送消息触发的导航，不要加载消息（会清空刚添加的消息）
      if (isSendingNewMessage) {
        // 重置标记，但不加载消息
        setSendingNewMessage(false);
      } else {
        loadMessages(urlConvId);
      }
    } else {
      // 新对话模式：清空状态，不创建记录
      resetConversation();
      setConversationId(null);
    }
  }, [urlConvId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on load
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  async function loadAgents() {
    try {
      // X-Context header is automatically added by axios interceptor
      const response = await api.get(`/api/v1/agents`);
      const data = response.data.data || response.data || [];
      setAgents(Array.isArray(data) ? data : []);
      if (data.length > 0 && !currentAgent) {
        setCurrentAgent(data[0]);
      }
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  }

  async function loadConversations() {
    try {
      const response = await api.get(`/api/session/conversations`, {
        headers: {
          'X-User-Id': user?.id,
        },
      });
      // Java session service returns {data: {records: [...], total, page, ...}}
      const data = response.data.data?.records || response.data.data || response.data || [];
      // Map Java field names to frontend expected format
      // 只保留有消息的对话（过滤空对话）
      const mapped: Conversation[] = Array.isArray(data) ? data
        .map((c: Record<string, unknown>) => ({
          id: Number(c.id || 0),
          conversation_id: String(c.conversationId || c.conversation_id || ''),
          title: String(c.title || ''),
          agent_id: c.agentId || c.agent_id,
          message_count: Number(c.messageCount || c.message_count || 0),
          created_at: String(c.createTime || c.created_at || ''),
          updated_at: String(c.updateTime || c.updated_at || ''),
        }))
        .filter((c) => c.message_count > 0)
        : [];
      setConversations(mapped);
      // 不再自动创建对话
    } catch (error) {
      // API might not exist yet, use empty list
      setConversations([]);
    }
  }

  async function loadMessages(convId: string) {
    try {
      const response = await api.get(`/api/session/conversations/${convId}/messages`, {
        headers: {
          'X-User-Id': user?.id,
        },
      });
      // Java session service returns {data: {records: [...], ...}}
      const records = response.data.data?.records || response.data.data || response.data || [];

      // Clear existing messages and add loaded ones
      clearMessages();
      setFollowups([]);
      setContextStats({ tokenCount: 0, maxContext: 128000 });

      // Map Java field names to frontend message format and add to store
      records.forEach((msg: Record<string, unknown>, index: number) => {
        // Parse metadata to extract tool_calls, attachments and followups if present
        let toolCalls: ToolCallInfo[] | undefined;
        let attachments: MediaAttachment[] | undefined;
        let followups: { followupId: string; content: string; injectedTool?: string; status?: 'pending' | 'injected' | 'error' }[] | undefined;
        let timeline: MessageTimelineItem[] | undefined;
        let contextStatsFromMessage: ContextStatsInfo | undefined;
        const metadataRaw = msg.metadata;
        console.log('[loadMessages] msg id:', msg.id, 'role:', msg.role, 'metadataRaw:', metadataRaw);
        if (metadataRaw) {
          try {
            // metadata 可能是 JSON 字符串或已解析的对象
            const metadata = typeof metadataRaw === 'string'
              ? JSON.parse(metadataRaw)
              : metadataRaw;

            console.log('[loadMessages] parsed metadata:', metadata);
            if (metadata?.tool_calls && Array.isArray(metadata.tool_calls)) {
              toolCalls = metadata.tool_calls.map((tc: Record<string, unknown>) => ({
                id: (tc.id || tc.tool_call_id) as string | undefined,
                name: tc.name as string,
                args: (tc.args || {}) as Record<string, unknown>,
                status: (tc.status as 'pending' | 'running' | 'success' | 'error') || 'success',
                result: tc.result as string | undefined,
                error: tc.error as string | undefined,
                startTime: typeof tc.startTime === 'number' ? tc.startTime : undefined,
                endTime: typeof tc.endTime === 'number' ? tc.endTime : undefined,
                injected_followups: Array.isArray(tc.injected_followups)
                  ? tc.injected_followups.map((f: Record<string, unknown>) => ({
                      followupId: (f.followup_id || f.followupId) as string,
                      content: f.content as string,
                      injectedTool: (f.injected_tool || f.injectedTool) as string | undefined,
                      status: (f.status as 'pending' | 'injected' | 'error') || 'injected',
                    }))
                  : undefined,
              }));
              console.log('[loadMessages] parsed toolCalls:', toolCalls);
            }
            // V5: 解析多媒体附件
            if (metadata?.attachments && Array.isArray(metadata.attachments)) {
              attachments = metadata.attachments.map((att: Record<string, unknown>) => ({
                type: att.type as 'image' | 'video' | 'audio' | 'file',
                url: att.url as string,
                mimeType: att.mime_type as string | undefined,
                filename: att.filename as string | undefined,
              }));
              console.log('[loadMessages] parsed attachments:', attachments);
            }
            // V5: 解析 follow-up 注入记录
            if (metadata?.followups && Array.isArray(metadata.followups)) {
              followups = metadata.followups.map((f: Record<string, unknown>) => ({
                followupId: (f.followup_id || f.followupId) as string,
                content: f.content as string,
                injectedTool: (f.injected_tool || f.injectedTool) as string | undefined,
                status: (f.status as 'pending' | 'injected' | 'error') || 'injected',
              }));
              console.log('[loadMessages] parsed followups:', followups);
            }
            if (metadata?.timeline && Array.isArray(metadata.timeline)) {
              timeline = metadata.timeline.map((item: Record<string, unknown>) => ({
                type: item.type as 'tool_call' | 'followup',
                ref: item.ref as string,
              }));
            }
            if (metadata?.context_stats) {
              const stats = metadata.context_stats as Record<string, unknown>;
              contextStatsFromMessage = {
                tokenCount: Number(stats.token_count ?? stats.tokenCount ?? 0),
                maxContext: Number(stats.max_context ?? stats.maxContext ?? 128000),
                compressed: Boolean(stats.compressed),
                timestamp: typeof stats.timestamp === 'number' ? stats.timestamp : undefined,
                readTokens: Number(stats.read_tokens ?? stats.readTokens ?? 0),
                writeTokens: Number(stats.write_tokens ?? stats.writeTokens ?? 0),
                messageTokens: Number(stats.message_tokens ?? stats.messageTokens ?? 0),
              };
            }
            if (metadata?.thinking && typeof metadata.thinking === 'string') {
              // thinking 会在 addMessage 时直接挂载
            }
            if (contextStatsFromMessage) {
              setContextStats(contextStatsFromMessage);
            }
          } catch (e) {
            console.warn('Failed to parse message metadata:', e);
          }
        }

        addMessage({
          id: (msg.id as number) || index,
          conversation_id: urlConvId || '',
          role: msg.role as 'user' | 'assistant',
          content: msg.content as string,
          created_at: msg.createTime as string || new Date().toISOString(),
          tool_calls: toolCalls,
          attachments: attachments,
          followups: followups,
          timeline: timeline,
          context_stats: contextStatsFromMessage,
          thinking: (typeof metadataRaw === 'string' ? (() => { try { return JSON.parse(metadataRaw)?.thinking; } catch { return undefined; } })() : (metadataRaw as any)?.thinking),
        });
      });
    } catch (error) {
      console.error('Failed to load messages:', error);
      // Don't show error to user, just start with empty messages
    }
  }

  function startNewConversation() {
    // 清空当前状态，进入新对话模式
    resetConversation();
    setConversationId(null);
    navigate('/chat', { replace: true });
  }

  async function sendMessage() {
    if (!input.trim() || isStreaming) return;
    if (!user) {
      toast.error('请先登录');
      return;
    }

    const userMessage = input.trim();
    setInput('');

    // 如果是新对话（没有 conversationId），先创建对话
    let activeConvId = conversationId;
    if (!activeConvId) {
      try {
        setSendingNewMessage(true);  // 在 store 中标记开始发送，避免 navigate 触发 loadMessages
        const response = await api.post(`/api/session/conversations`, {
          title: '新对话',
          agentId: currentAgent?.id || 1,
        }, {
          headers: {
            'X-User-Id': String(user.id),
          },
        });
        const conv = response.data.data || response.data;
        activeConvId = conv.conversationId || conv.conversation_id || conv.id;

        // 先设置 conversationId 和添加消息
        setConversationId(activeConvId);
        addMessage({
          conversation_id: activeConvId,
          role: 'user',
          content: userMessage,
        });
        addMessage({
          conversation_id: activeConvId,
          role: 'assistant',
          content: '',
          tool_calls: [],
        });

        // 导航到新对话 URL
        navigate(`/chat/${activeConvId}`, { replace: true });
        // 注意：isSendingNewMessage 会在 useEffect 中被重置
      } catch (error) {
        setSendingNewMessage(false);  // 出错时重置
        toast.error('创建对话失败');
        return;
      }
    } else {
      // 已有对话，正常添加消息
      addMessage({
        conversation_id: activeConvId,
        role: 'user',
        content: userMessage,
      });
      addMessage({
        conversation_id: activeConvId,
        role: 'assistant',
        content: '',
        tool_calls: [],
      });
    }

    setStreaming(true);

    // Stream response
    abortRef.current = chatApi.streamChat(
      userMessage,
      activeConvId,  // conversationId
      (chunk) => {
        appendToLastMessage(chunk);
      },
      () => {
        setStreaming(false);
        abortRef.current = null;
        setFollowups([]);  // V5: 清除 followup 队列
        // 延迟刷新会话列表，等待异步标题生成完成
        setTimeout(() => {
          loadConversations();
        }, 2500);
      },
      (error) => {
        setStreaming(false);
        abortRef.current = null;
        // V5: 将错误状态存储到消息中，而不仅仅显示 toast
        setLastMessageError(error);
        toast.error(`发送失败: ${error}`);
      },
      // 工具调用回调 - 存储到消息中
      (toolCall) => {
        if (toolCall.status === 'running') {
          // 新的工具调用开始
          const toolCallId = toolCall.id || `${toolCall.name}-${Date.now()}`;
          addToolCallToLastMessage({
            id: toolCallId,
            name: toolCall.name,
            args: toolCall.args,
            status: 'running',
            startTime: Date.now(),
          });
          appendTimelineToLastMessage({ type: 'tool_call', ref: toolCallId });
        } else {
          // 工具调用完成（success 或 error）
          updateToolCallInLastMessage(toolCall.name, {
            id: toolCall.id,
            status: toolCall.status,
            result: toolCall.result,
            error: toolCall.error,
            endTime: Date.now(),
          });
        }
      },
      undefined,  // onConversationId
      // V5: thinking 回调 - MiniMax 思考过程
      (thinkingContent) => {
        setLastMessageThinking(thinkingContent);
      },
      // V5: media 回调 - 发送多媒体
      (media) => {
        addAttachmentToLastMessage({
          type: media.mediaType as 'image' | 'video' | 'audio' | 'file',
          url: media.url,
          mimeType: media.mimeType || 'image/png',
          filename: media.filename,
        });
      },
      // V5: followup pending 回调
      (followup) => {
        setFollowups(prev => [...prev, {
          id: followup.followupId,
          content: followup.content,
          status: 'pending',
        }]);
        upsertFollowupInLastMessage({
          followupId: followup.followupId,
          content: followup.content,
          status: 'pending',
        });
      },
      // V5: followup injected 回调 - 显示注入到哪个工具
      (followup) => {
        setFollowups(prev => prev.map(f =>
          f.id === followup.followupId
            ? { ...f, status: 'injected', injectedTool: followup.injectedTool }
            : f
        ));
        upsertFollowupInLastMessage({
          followupId: followup.followupId,
          content: followup.content,
          injectedTool: followup.injectedTool,
          status: 'injected',
        }, true);
      },
      // V5: context stats 回调 - 更新上下文统计
      (stats) => {
        const nextStats = {
          tokenCount: stats.tokenCount,
          maxContext: stats.maxContext,
          readTokens: stats.readTokens,
          writeTokens: stats.writeTokens,
          messageTokens: stats.messageTokens,
        };
        setContextStats(nextStats);
        setContextStatsOnLastMessage(nextStats);
      }
    );
  }

  async function stopStreaming() {
    if (conversationId) {
      try {
        await chatApi.stop(conversationId);
      } catch (error) {
        console.error('Stop conversation failed:', error);
      }
    }

    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    setStreaming(false);
    setFollowups([]);  // V5: 清除 followup 队列
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  async function copyMessage(content: string, index: number) {
    await navigator.clipboard.writeText(content);
    setCopiedId(index);
    toast.success('已复制到剪贴板');
    setTimeout(() => setCopiedId(null), 2000);
  }

  async function regenerateMessage() {
    if (messages.length < 2 || isStreaming) return;

    // Find the last user message
    const lastUserMsgIndex = messages.length - 2;
    const lastUserMsg = messages[lastUserMsgIndex];

    if (lastUserMsg?.role !== 'user') return;

    // Remove the last assistant message
    // Re-send the user message
    setInput(lastUserMsg.content);
  }

  // V5: 重试失败的消息
  function retryLastMessage() {
    if (messages.length < 2) return;

    const lastUserMsgIndex = messages.length - 2;
    const lastUserMsg = messages[lastUserMsgIndex];

    if (lastUserMsg?.role !== 'user') return;

    // 清除错误状态并重新设置 input 让用户重新发送
    setInput(lastUserMsg.content);
  }

  async function selectConversation(conv: Conversation) {
    setConversationId(conv.conversation_id);
    navigate(`/chat/${conv.conversation_id}`);
    await loadMessages(conv.conversation_id);
    setMenuOpenId(null);
  }

  async function deleteConversation(convId: string) {
    if (!confirm('确定要删除这个对话吗？')) return;

    try {
      await api.delete(`/api/session/conversations/${convId}`, {
        headers: {
          'X-User-Id': user?.id,
        },
      });
      setConversations(prev => prev.filter(c => c.conversation_id !== convId));

      if (conversationId === convId) {
        startNewConversation();
      }
      toast.success('对话已删除');
    } catch (error) {
      toast.error('删除失败，请重试');
      console.error('Delete conversation failed:', error);
    }
    setMenuOpenId(null);
  }

  async function renameConversation(convId: string, newTitle: string) {
    try {
      await api.put(`/api/session/conversations/${convId}/title`, {
        title: newTitle,
      });
      setConversations(prev =>
        prev.map(c =>
          c.conversation_id === convId ? { ...c, title: newTitle } : c
        )
      );
    } catch (error) {
      // Update locally anyway
      setConversations(prev =>
        prev.map(c =>
          c.conversation_id === convId ? { ...c, title: newTitle } : c
        )
      );
    }
    setEditingConvId(null);
  }

  async function clearAllConversations() {
    setIsClearing(true);
    try {
      // 循环删除所有对话
      for (const conv of conversations) {
        await api.delete(`/api/session/conversations/${conv.conversation_id}`, {
          headers: {
            'X-User-Id': user?.id,
          },
        });
      }
      setConversations([]);
      resetConversation();
      // 创建新对话
      await createNewConversationInternal();
      toast.success('已清空所有对话');
    } catch (error) {
      toast.error('清空失败，请重试');
      console.error('Clear all conversations failed:', error);
    }
    setIsClearing(false);
    setShowClearModal(false);
  }

  function handleFeedback(index: number, type: 'up' | 'down') {
    setFeedback(prev => ({
      ...prev,
      [index]: prev[index] === type ? undefined : type,
    }));
    toast.success(type === 'up' ? '感谢您的反馈！' : '我们会继续改进');
  }

  const filteredConversations = conversations.filter(conv =>
    conv.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    conv.conversation_id.includes(searchQuery)
  );

  return (
    <div className="flex h-full">
      {/* Conversation Sidebar */}
      <div
        className={clsx(
          'flex flex-col border-r border-dark-800 bg-dark-900/50 transition-all duration-300',
          sidebarOpen ? 'w-72' : 'w-0'
        )}
      >
        {sidebarOpen && (
          <>
            {/* Sidebar Header */}
            <div className="p-3 border-b border-dark-800">
              <button
                onClick={startNewConversation}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
              >
                <Plus className="w-4 h-4" />
                新建对话
              </button>
              {conversations.length > 0 && (
                <button
                  onClick={() => setShowClearModal(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 mt-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg border border-red-500/20 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  清空所有对话
                </button>
              )}
            </div>

            {/* Search */}
            <div className="p-3 border-b border-dark-800">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
                <input
                  type="text"
                  placeholder="搜索对话..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-sm bg-dark-800 border border-dark-700 rounded-lg text-dark-200 placeholder-dark-500"
                />
              </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {filteredConversations.length === 0 ? (
                <div className="text-center py-8 text-dark-500 text-sm">
                  {searchQuery ? '没有找到匹配的对话' : '暂无对话历史'}
                </div>
              ) : (
                filteredConversations.map((conv) => (
                  <div
                    key={conv.conversation_id}
                    className={clsx(
                      'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all',
                      conversationId === conv.conversation_id
                        ? 'bg-primary-500/10 text-primary-400'
                        : 'hover:bg-dark-800 text-dark-300'
                    )}
                    onClick={() => selectConversation(conv)}
                  >
                    <MessageSquare className="w-4 h-4 flex-shrink-0" />

                    {editingConvId === conv.conversation_id ? (
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onBlur={() => renameConversation(conv.conversation_id, editingTitle)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            renameConversation(conv.conversation_id, editingTitle);
                          } else if (e.key === 'Escape') {
                            setEditingConvId(null);
                          }
                        }}
                        className="flex-1 bg-dark-700 px-2 py-1 rounded text-sm"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="flex-1 truncate text-sm">
                        {conv.title || '新对话'}
                      </span>
                    )}

                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenId(menuOpenId === conv.conversation_id ? null : conv.conversation_id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-dark-700 rounded transition-all"
                      >
                        <MoreHorizontal className="w-4 h-4" />
                      </button>

                      {menuOpenId === conv.conversation_id && (
                        <div className="absolute right-0 top-6 w-32 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-10 py-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingConvId(conv.conversation_id);
                              setEditingTitle(conv.title || '新对话');
                              setMenuOpenId(null);
                            }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-dark-300 hover:bg-dark-700"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                            重命名
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteConversation(conv.conversation_id);
                            }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Toggle Sidebar Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute left-0 top-1/2 -translate-y-1/2 z-10 p-1 bg-dark-800 border border-dark-700 rounded-r-lg hover:bg-dark-700 transition-colors"
        style={{ left: sidebarOpen ? '286px' : '0' }}
      >
        {sidebarOpen ? (
          <ChevronLeft className="w-4 h-4 text-dark-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-dark-400" />
        )}
      </button>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-dark-800 bg-dark-900/50 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-medium text-dark-100">
                {currentAgent?.name || '通用助手'}
              </h1>
              <p className="text-xs text-dark-500">
                {currentAgent?.description || 'AI 对话助手'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Agent selector */}
            {agents.length > 0 && (
              <select
                value={currentAgent?.id || ''}
                onChange={(e) => {
                  const agent = agents.find(a => a.id === Number(e.target.value));
                  setCurrentAgent(agent || null);
                }}
                className="px-3 py-1.5 text-sm bg-dark-800 border border-dark-700 rounded-lg text-dark-200"
              >
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onSuggestionClick={(text) => setInput(text)} />
          ) : (
            <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
              {messages.map((message, index) => (
                <MessageBubble
                  key={index}
                  message={message}
                  index={index}
                  isStreaming={isStreaming && index === messages.length - 1}
                  onCopy={() => copyMessage(message.content, index)}
                  copied={copiedId === index}
                  feedback={feedback[index]}
                  onFeedback={(type) => handleFeedback(index, type)}
                  onRegenerate={index === messages.length - 1 ? regenerateMessage : undefined}
                  onRetry={index === messages.length - 1 && message.status === 'error' ? retryLastMessage : undefined}
                />
              ))}

              <div ref={messagesEndRef} />
            </div>
          )}

          {/* V5: Follow-up 输入和状态显示 */}
          {isStreaming && conversationId && (
            <div className="max-w-4xl mx-auto mt-2">
              <FollowupInput
                conversationId={conversationId}
                isStreaming={isStreaming}
                onFollowupQueued={(id, content) => {
                  setFollowups(prev => [...prev, { id, content, status: 'pending' }]);
                }}
              />
              {followups.length > 0 && (
                <FollowupQueueStatus followups={followups} className="mt-2" />
              )}
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-dark-800 bg-dark-900/50 backdrop-blur p-4">
          <div className="max-w-4xl mx-auto">
            {/* V5: 非 streaming 时也显示 followup 状态 */}
            {!isStreaming && followups.length > 0 && (
              <FollowupQueueStatus followups={followups} className="mb-3" />
            )}
            <div className="relative flex items-end gap-2 bg-dark-800 border border-dark-700 rounded-xl p-2 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
                rows={1}
                className="flex-1 bg-transparent border-none resize-none text-dark-100 placeholder-dark-500 focus:outline-none px-2 py-1.5 max-h-48"
                style={{ minHeight: '40px' }}
                disabled={isStreaming}
              />

              {isStreaming ? (
                <button
                  onClick={stopStreaming}
                  className="flex items-center justify-center w-10 h-10 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
                >
                  <StopCircle className="w-5 h-5" />
                </button>
              ) : (
                <button
                  onClick={sendMessage}
                  disabled={!input.trim()}
                  className={clsx(
                    'flex items-center justify-center w-10 h-10 rounded-lg transition-colors',
                    input.trim()
                      ? 'bg-primary-500 text-white hover:bg-primary-400'
                      : 'bg-dark-700 text-dark-500 cursor-not-allowed'
                  )}
                >
                  <Send className="w-5 h-5" />
                </button>
              )}
            </div>

            <p className="mt-2 text-xs text-dark-500 text-center">
              NexusAgent 可能会产生不准确的信息，请注意核实重要内容
            </p>
          </div>
        </div>

        {/* V5: 上下文 Token 统计 - 右下角固定显示 */}
        <ContextTokenStatus
          tokenCount={contextStats.tokenCount}
          maxContext={contextStats.maxContext}
          readTokens={contextStats.readTokens}
          writeTokens={contextStats.writeTokens}
          messageTokens={contextStats.messageTokens}
          className="absolute bottom-20 right-4 z-10"
        />
      </div>

      {/* Clear All Conversations Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-dark-900 border border-dark-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-red-500/20 rounded-lg flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-dark-100">清空所有对话</h3>
                <p className="text-sm text-dark-400">此操作不可撤销</p>
              </div>
            </div>
            <p className="text-dark-300 mb-6">
              确定要删除所有 {conversations.length} 个对话吗？删除后将无法恢复。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowClearModal(false)}
                disabled={isClearing}
                className="px-4 py-2 text-sm text-dark-300 hover:text-dark-100 hover:bg-dark-800 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={clearAllConversations}
                disabled={isClearing}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-400 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {isClearing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    清空中...
                  </>
                ) : (
                  '确认清空'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Welcome screen component
function WelcomeScreen({ onSuggestionClick }: { onSuggestionClick: (text: string) => void }) {
  const suggestions = [
    { icon: '👋', text: '你好，请介绍一下你自己' },
    { icon: '🔢', text: '帮我计算 123 * 456 等于多少' },
    { icon: '💻', text: '用 Python 写一个快速排序算法' },
    { icon: '📚', text: '解释一下什么是 LangGraph' },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-12">
      <div className="w-20 h-20 bg-gradient-to-br from-primary-400 to-primary-600 rounded-2xl flex items-center justify-center mb-6 shadow-xl shadow-primary-500/20">
        <Sparkles className="w-10 h-10 text-white" />
      </div>
      <h1 className="text-3xl font-bold text-dark-100 mb-3">欢迎使用 NexusAgent</h1>
      <p className="text-dark-400 mb-8 text-center max-w-md">
        我是您的 AI 助手，可以帮助您回答问题、编写代码、进行计算等
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="flex items-center gap-3 p-4 text-left bg-dark-800/50 hover:bg-dark-800 border border-dark-700 hover:border-dark-600 rounded-xl transition-all group"
          >
            <span className="text-2xl">{suggestion.icon}</span>
            <span className="text-sm text-dark-300 group-hover:text-dark-100">
              {suggestion.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// ThinkingBlock - 思考内容打字机效果组件
// ============================================================================
// 积存消息越多，打字越快的动态速度算法
const ThinkingBlock = React.memo(function ThinkingBlock({
  thinking,
  isStreaming,
}: {
  thinking: string;
  isStreaming: boolean;
}) {
  const [displayedLength, setDisplayedLength] = useState(0);
  const bufferRef = useRef<string>('');  // 累积的思考内容缓冲区
  const lastUpdateRef = useRef<number>(Date.now());
  const speedRef = useRef<number>(1);  // 当前打字速度倍数
  const animationRef = useRef<number | null>(null);

  // 当 thinking 更新时，追加到缓冲区
  useEffect(() => {
    if (thinking.length > bufferRef.current.length) {
      const newContent = thinking.slice(bufferRef.current.length);
      bufferRef.current = thinking;
      lastUpdateRef.current = Date.now();

      // 收到新内容时稍微加速
      speedRef.current = Math.min(speedRef.current * 1.2, 5);
    }
  }, [thinking]);

  // 打字机动画
  useEffect(() => {
    if (isStreaming) {
      // 流式中：使用动态速度打字
      const BASE_SPEED = 15; // 基础速度：每帧显示的字符数
      const MIN_SPEED = 5;   // 最低速度
      const MAX_SPEED = 80;  // 最高速度

      const tick = () => {
        setDisplayedLength(prev => {
          const bufferLen = bufferRef.current.length;
          if (prev >= bufferLen) {
            return prev;
          }

          // 根据距上次更新的时间动态调整速度
          const timeSinceUpdate = Date.now() - lastUpdateRef.current;
          let currentSpeed = BASE_SPEED * speedRef.current;

          // 如果超过 500ms 没有新内容，速度逐渐恢复
          if (timeSinceUpdate > 500) {
            speedRef.current = Math.max(speedRef.current * 0.95, 1);
          }

          // 缓冲区越大，速度越快（有内容等着被显示）
          const bufferSize = bufferLen - prev;
          if (bufferSize > 200) {
            currentSpeed = Math.min(currentSpeed * 2, MAX_SPEED);
          } else if (bufferSize > 50) {
            currentSpeed = Math.min(currentSpeed * 1.3, MAX_SPEED);
          }

          // 添加随机性让打字更自然
          const randomizedSpeed = currentSpeed * (0.8 + Math.random() * 0.4);
          return Math.min(prev + Math.ceil(randomizedSpeed), bufferLen);
        });

        animationRef.current = requestAnimationFrame(tick);
      };

      animationRef.current = requestAnimationFrame(tick);

      return () => {
        if (animationRef.current) {
          cancelAnimationFrame(animationRef.current);
        }
      };
    } else {
      // 流式结束：立即显示所有内容
      setDisplayedLength(bufferRef.current.length);
    }
  }, [isStreaming]);

  // 流式结束时清理
  useEffect(() => {
    if (!isStreaming && displayedLength < bufferRef.current.length) {
      setDisplayedLength(bufferRef.current.length);
    }
  }, [isStreaming, displayedLength]);

  const displayedText = bufferRef.current.slice(0, displayedLength);
  const hasMore = displayedLength < bufferRef.current.length;

  return (
    <details className="mt-2 max-w-[85%] rounded-lg bg-dark-800/50 border border-dark-700 overflow-hidden" open={isStreaming || displayedLength > 0}>
      <summary className="px-3 py-2 cursor-pointer text-xs text-dark-400 hover:text-dark-300 hover:bg-dark-800/50 flex items-center gap-2 select-none">
        <ChevronDown className="w-3.5 h-3.5 chevron-icon transition-transform" />
        <span>思考过程</span>
        {isStreaming && hasMore && (
          <span className="ml-auto flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 bg-primary-400 rounded-full animate-pulse" />
            <span className="text-primary-400/70">{Math.round((displayedLength / bufferRef.current.length) * 100)}%</span>
          </span>
        )}
      </summary>
      <div className="px-3 py-2 text-xs text-dark-400 whitespace-pre-wrap border-t border-dark-700 font-mono leading-relaxed">
        {displayedText}
        {isStreaming && hasMore && (
          <span className="inline-block w-2 h-3.5 bg-primary-400/70 ml-0.5 animate-pulse" />
        )}
      </div>
    </details>
  );
});

// Message bubble component with syntax highlighting
// MessageBubble 组件 - 使用 React.memo 防止不必要的重渲染
const MessageBubble = React.memo(function MessageBubble({
  message,
  index,
  isStreaming,
  onCopy,
  copied,
  feedback,
  onFeedback,
  onRegenerate,
  onRetry,
}: {
  message: { role: string; content: string; tool_calls?: ToolCallInfo[]; status?: string; error?: string; attachments?: MediaAttachment[]; thinking?: string; followups?: { followupId: string; content: string; injectedTool?: string; status?: 'pending' | 'injected' | 'error' }[]; timeline?: MessageTimelineItem[]; context_stats?: ContextStatsInfo };
  index: number;
  isStreaming: boolean;
  onCopy: () => void;
  copied: boolean;
  feedback?: 'up' | 'down';
  onFeedback: (type: 'up' | 'down') => void;
  onRegenerate?: () => void;
  onRetry?: () => void;
}) {
  const isUser = message.role === 'user';
  const toolCalls = message.tool_calls || [];
  const thinking = message.thinking;
  const followups = message.followups || [];
  const timeline = message.timeline || [];
  const toolCallMap = new Map(toolCalls.filter(tc => tc.id).map(tc => [tc.id as string, tc]));
  const followupMap = new Map(followups.map(f => [f.followupId, f]));
  const hasTimeline = timeline.length > 0;

  // 预处理 LaTeX 公式分隔符，将 \(...\) 转换为 $...$ 格式
  // 同时将 \[...\] 转换为 $$...$$ 格式
  const processedContent = useMemo(() => {
    if (!message.content) return '';
    let content = message.content;
    // 行内公式：\(...\) → $...$
    content = content.replace(/\\\((.+?)\\\)/g, (_, math) => `$${math}$`);
    // 块级公式：\[...\] → $$...$$
    content = content.replace(/\\\[(.+?)\\\]/gs, (_, math) => `$$${math}$$`);
    return content;
  }, [message.content]);

  // 使用 useMemo 缓存 ReactMarkdown 的 components，防止每次渲染都创建新对象
  // 这是防止 Mermaid 重复渲染的关键！
  const markdownComponents = useMemo(() => ({
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';

      if (!inline && language === 'mermaid') {
        // Mermaid 图表 - 传入 isStreaming 以在流式传输时避免渲染不完整的图
        return (
          <MermaidChart code={String(children)} isStreaming={isStreaming} />
        );
      }

      if (!inline && language) {
        return (
          <div className="relative group my-4">
            <div className="absolute right-2 top-2 flex items-center gap-2">
              <span className="text-xs text-dark-500 uppercase">{language}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(String(children));
                  toast.success('代码已复制');
                }}
                className="p-1.5 bg-dark-700 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-200 opacity-0 group-hover:opacity-100 transition-all"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
            <SyntaxHighlighter
              style={oneDark}
              language={language}
              PreTag="div"
              className="rounded-lg !bg-dark-900 !my-0"
              {...props}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          </div>
        );
      }

      return (
        <code className={clsx(className, 'bg-dark-700 px-1.5 py-0.5 rounded text-primary-300')} {...props}>
          {children}
        </code>
      );
    },
    pre({ children }: any) {
      return <>{children}</>;
    },
    table({ children }: any) {
      return (
        <div className="overflow-x-auto my-4">
          <table className="min-w-full border-collapse border border-dark-700">
            {children}
          </table>
        </div>
      );
    },
    th({ children }: any) {
      return (
        <th className="border border-dark-700 px-3 py-2 bg-dark-800 text-left">
          {children}
        </th>
      );
    },
    td({ children }: any) {
      return (
        <td className="border border-dark-700 px-3 py-2">
          {children}
        </td>
      );
    },
  }), [isStreaming]); // 只在 isStreaming 变化时重新创建 components

  return (
    <div className={clsx('flex gap-4', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={clsx(
          'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
          isUser
            ? 'bg-primary-500'
            : 'bg-gradient-to-br from-primary-400 to-primary-600'
        )}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      {/* Content */}
      <div className={clsx('flex-1 min-w-0', isUser && 'flex flex-col items-end')}>
        <div
          className={clsx(
            'max-w-[85%] rounded-2xl px-4 py-3 break-words',
            isUser
              ? 'bg-primary-500 text-white'
              : 'bg-dark-800 text-dark-100'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div className="markdown-content prose prose-invert prose-sm max-w-none">
              {message.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={markdownComponents}
                >
                  {processedContent}
                </ReactMarkdown>
              ) : isStreaming ? (
                <div className="flex items-center gap-2">
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span className="text-dark-500 text-sm">思考中...</span>
                </div>
              ) : null}
              {isStreaming && message.content && (
                <span className="cursor-blink" />
              )}
            </div>
          )}

          {/* V5: 多媒体附件显示 */}
          {message.attachments && message.attachments.length > 0 && (
            <MediaRenderer attachments={message.attachments} />
          )}
        </div>

        {/* V5: 思考过程显示 - MiniMax 等模型的思考内容，带打字机效果 */}
        {!isUser && thinking && (
          <ThinkingBlock thinking={thinking} isStreaming={isStreaming} />
        )}

        {/* V5: 工具调用 / Follow-up 时间线显示 */}
        {!isUser && hasTimeline && (
          <div className="mt-3 w-full space-y-3">
            {timeline.map((item, index) => {
              if (item.type === 'tool_call') {
                const toolCall = toolCallMap.get(item.ref);
                if (!toolCall) return null;
                return (
                  <div key={`timeline-tool-${item.ref}-${index}`}>
                    <ToolCallsDisplay toolCalls={[toolCall]} />
                  </div>
                );
              }
              if (item.type === 'followup') {
                return null;
              }
              return null;
            })}
          </div>
        )}

        {/* 兼容旧历史：没有 timeline 时沿用旧展示 */}
        {!isUser && !hasTimeline && toolCalls.length > 0 && (
          <div className="mt-3 w-full">
            <ToolCallsDisplay toolCalls={toolCalls} />
          </div>
        )}

        {!isUser && !hasTimeline && followups.length > 0 && (
          <div className="mt-3 w-full">
            <FollowupQueueStatus
              followups={followups.map(f => ({
                id: f.followupId,
                content: f.content,
                status: f.status || 'injected',
                injectedTool: f.injectedTool,
              }))}
              compact
            />
          </div>
        )}

        {/* 历史消息上下文统计回放 */}
        {!isUser && message.context_stats && (
          <div className="mt-3 text-xs text-dark-400 space-y-1">
            <div>
              上下文：{message.context_stats.tokenCount}/{message.context_stats.maxContext}
              {message.context_stats.compressed ? '（已压缩）' : ''}
            </div>
            <div className="text-[11px] text-dark-500">
              读 {message.context_stats.readTokens ?? 0} · 写 {message.context_stats.writeTokens ?? 0} · 本条 {message.context_stats.messageTokens ?? 0}
            </div>
          </div>
        )}

        {/* 流式中的 follow-up 队列仍保留在消息下方（尚未注入） */}
        {!isUser && !hasTimeline && isStreaming && followups.some(f => (f.status || 'pending') === 'pending') && (
          <div className="mt-3 w-full">
            <FollowupQueueStatus
              followups={followups.filter(f => (f.status || 'pending') === 'pending').map(f => ({
                id: f.followupId,
                content: f.content,
                status: f.status || 'pending',
                injectedTool: f.injectedTool,
              }))}
              compact
            />
          </div>
        )}

        {/* V5: 错误状态显示 */}
        {!isUser && message.status === 'error' && (
          <div className="mt-2 flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{message.error || '发送失败'}</span>
            {onRetry && (
              <button
                onClick={onRetry}
                className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
              >
                重试
              </button>
            )}
          </div>
        )}

        {/* Actions */}
        {!isUser && message.content && !isStreaming && (
          <div className="flex items-center gap-1 mt-2">
            <button
              onClick={onCopy}
              className="flex items-center gap-1 px-2 py-1 text-xs text-dark-500 hover:text-dark-300 hover:bg-dark-800 rounded transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  已复制
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  复制
                </>
              )}
            </button>

            <button
              onClick={() => onFeedback('up')}
              className={clsx(
                'p-1.5 rounded transition-colors',
                feedback === 'up'
                  ? 'text-green-400 bg-green-500/10'
                  : 'text-dark-500 hover:text-dark-300 hover:bg-dark-800'
              )}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={() => onFeedback('down')}
              className={clsx(
                'p-1.5 rounded transition-colors',
                feedback === 'down'
                  ? 'text-red-400 bg-red-500/10'
                  : 'text-dark-500 hover:text-dark-300 hover:bg-dark-800'
              )}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>

            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1 px-2 py-1 text-xs text-dark-500 hover:text-dark-300 hover:bg-dark-800 rounded transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                重新生成
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  // 自定义比较函数：精确控制何时重新渲染
  // 消息内容变化 → 重新渲染
  if (prevProps.message.content !== nextProps.message.content) return false;
  // 消息角色变化 → 重新渲染
  if (prevProps.message.role !== nextProps.message.role) return false;
  // 工具调用变化 → 重新渲染
  if (JSON.stringify(prevProps.message.tool_calls) !== JSON.stringify(nextProps.message.tool_calls)) return false;
  // V5: 消息状态变化 → 重新渲染
  if (prevProps.message.status !== nextProps.message.status) return false;
  // V5: 错误信息变化 → 重新渲染
  if (prevProps.message.error !== nextProps.message.error) return false;
  // V5: 附件变化 → 重新渲染
  if (JSON.stringify(prevProps.message.attachments) !== JSON.stringify(nextProps.message.attachments)) return false;
  // V5: 思考过程变化 → 重新渲染
  if (prevProps.message.thinking !== nextProps.message.thinking) return false;
  // isStreaming 变化 → 重新渲染（用于流式结束后渲染 Mermaid）
  if (prevProps.isStreaming !== nextProps.isStreaming) return false;
  // copied 状态变化 → 重新渲染
  if (prevProps.copied !== nextProps.copied) return false;
  // feedback 状态变化 → 重新渲染
  if (prevProps.feedback !== nextProps.feedback) return false;
  // 其他情况不重新渲染（如父组件因输入框变化而渲染）
  return true;
});

// Mermaid 图表组件 - 使用 React.memo 防止不必要的重渲染
// 只有当 code 变化时才重新渲染，忽略 isStreaming 的变化
const MermaidChart = React.memo(function MermaidChart({ code, isStreaming }: { code: string; isStreaming?: boolean }) {
  const [showCode, setShowCode] = useState(false);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isRendering, setIsRendering] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const lastRenderedCode = useRef<string>('');
  const svgContainerRef = useRef<HTMLDivElement>(null);
  // 记录初始的 isStreaming 状态，用于判断首次渲染时机
  const initialStreamingRef = useRef<boolean>(isStreaming ?? false);
  // 标记是否已完成首次渲染
  const hasRenderedRef = useRef<boolean>(false);

  // 复制图片到剪贴板
  const copyAsImage = async () => {
    if (!svg) return;

    try {
      // 创建临时 canvas
      const svgElement = svgContainerRef.current?.querySelector('svg');
      if (!svgElement) return;

      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // 获取 SVG 尺寸
      const svgRect = svgElement.getBoundingClientRect();
      const scale = 2; // 2x 分辨率
      canvas.width = svgRect.width * scale;
      canvas.height = svgRect.height * scale;

      // 将 SVG 转为图片
      const svgData = new XMLSerializer().serializeToString(svgElement);
      const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      const img = new Image();
      img.onload = async () => {
        ctx.fillStyle = '#1a1a2e'; // 深色背景
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);

        // 复制到剪贴板
        canvas.toBlob(async (blob) => {
          if (blob) {
            try {
              await navigator.clipboard.write([
                new ClipboardItem({ 'image/png': blob })
              ]);
              setCopySuccess(true);
              setTimeout(() => setCopySuccess(false), 2000);
            } catch {
              // 如果剪贴板 API 不支持，下载图片
              downloadAsImage();
            }
          }
        }, 'image/png');
      };
      img.src = url;
    } catch (e) {
      console.error('复制图片失败:', e);
    }
  };

  // 下载为图片
  const downloadAsImage = () => {
    if (!svg) return;

    const svgElement = svgContainerRef.current?.querySelector('svg');
    if (!svgElement) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const svgRect = svgElement.getBoundingClientRect();
    const scale = 2;
    canvas.width = svgRect.width * scale;
    canvas.height = svgRect.height * scale;

    const svgData = new XMLSerializer().serializeToString(svgElement);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
      ctx.fillStyle = '#1a1a2e';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);

      const link = document.createElement('a');
      link.download = `mermaid-${Date.now()}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    };
    img.src = url;
  };

  useEffect(() => {
    // 已经渲染过且代码没变，不做任何事
    if (hasRenderedRef.current && code === lastRenderedCode.current) {
      return;
    }

    // 如果代码没变化且有 SVG，不重新渲染
    if (code === lastRenderedCode.current && svg) {
      return;
    }

    // 如果当前正在流式传输，不渲染（等待流式结束）
    if (isStreaming) {
      initialStreamingRef.current = true; // 标记曾经在流式传输中
      return;
    }

    let mounted = true;

    async function renderMermaid() {
      if (!code.trim()) return;

      setIsRendering(true);

      try {
        // 初始化 mermaid（只需一次，但多次调用也安全）
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'loose',
          suppressErrorRendering: true, // 阻止 mermaid 自己渲染错误到 body
        });

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        // 先用 parse 验证语法
        const isValid = await mermaid.parse(code, { suppressErrors: true });
        if (!isValid) {
          if (mounted) {
            setError('Mermaid 语法错误');
            setSvg('');
          }
          return;
        }

        const { svg: renderedSvg } = await mermaid.render(id, code);
        if (mounted) {
          setSvg(renderedSvg);
          setError('');
          lastRenderedCode.current = code;
          hasRenderedRef.current = true; // 标记已渲染完成
          initialStreamingRef.current = false; // 重置流式状态
        }
      } catch (e) {
        if (mounted) {
          setError(`渲染失败: ${String(e).slice(0, 100)}`);
          setSvg('');
        }
      } finally {
        if (mounted) {
          setIsRendering(false);
        }
        // 清理 mermaid 可能在 body 创建的元素
        requestAnimationFrame(() => {
          document.querySelectorAll('body > [id^="dmermaid-"], body > [id^="mermaid-"]').forEach(el => {
            el.remove();
          });
        });
      }
    }

    // 使用 setTimeout 防抖，避免频繁渲染
    const timer = setTimeout(renderMermaid, 100);
    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [code, isStreaming]); // 依赖 code 和 isStreaming

  // 流式传输时显示代码预览
  if (isStreaming && !svg) {
    return (
      <div className="my-4 border border-dark-700 rounded-lg overflow-hidden min-h-[100px]">
        <div className="flex items-center justify-between bg-dark-800 px-3 py-2">
          <span className="text-xs text-dark-400 uppercase flex items-center gap-2">
            <Loader2 className="w-3 h-3 animate-spin" />
            Mermaid 图表生成中...
          </span>
        </div>
        <div className="p-4 bg-dark-900">
          <pre className="text-dark-400 text-sm overflow-x-auto whitespace-pre-wrap">{code}</pre>
        </div>
      </div>
    );
  }

  // 全屏展开的模态框
  const ExpandedModal = () => (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8"
      onClick={() => setIsExpanded(false)}
    >
      <div
        className="bg-dark-900 rounded-xl max-w-[95vw] max-h-[95vh] overflow-auto p-6 relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 关闭按钮 */}
        <button
          onClick={() => setIsExpanded(false)}
          className="absolute top-4 right-4 p-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-dark-300 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* 工具栏 */}
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={copyAsImage}
            className="flex items-center gap-2 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-dark-300 hover:text-white transition-colors"
          >
            {copySuccess ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
            {copySuccess ? '已复制' : '复制图片'}
          </button>
          <button
            onClick={downloadAsImage}
            className="flex items-center gap-2 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-dark-300 hover:text-white transition-colors"
          >
            <ChevronDown className="w-4 h-4" />
            下载图片
          </button>
          <button
            onClick={() => {
              navigator.clipboard.writeText(code);
              toast.success('源码已复制');
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-dark-300 hover:text-white transition-colors"
          >
            <Terminal className="w-4 h-4" />
            复制源码
          </button>
        </div>

        {/* 图表内容 */}
        <div
          ref={svgContainerRef}
          className="flex justify-center"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  );

  return (
    <>
      {isExpanded && <ExpandedModal />}
      <div className="my-4 border border-dark-700 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between bg-dark-800 px-3 py-2">
          <span className="text-xs text-dark-400 uppercase">Mermaid 图表</span>
          <div className="flex items-center gap-1">
            {svg && !showCode && (
              <>
                <button
                  onClick={copyAsImage}
                  className="p-1.5 text-dark-400 hover:text-dark-200 hover:bg-dark-700 rounded transition-colors"
                  title="复制图片"
                >
                  {copySuccess ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={downloadAsImage}
                  className="p-1.5 text-dark-400 hover:text-dark-200 hover:bg-dark-700 rounded transition-colors"
                  title="下载图片"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setIsExpanded(true)}
                  className="p-1.5 text-dark-400 hover:text-dark-200 hover:bg-dark-700 rounded transition-colors"
                  title="放大查看"
                >
                  <ChevronUp className="w-3.5 h-3.5 rotate-45" />
                </button>
              </>
            )}
            <button
              onClick={() => setShowCode(!showCode)}
              className="text-xs text-dark-400 hover:text-dark-200 flex items-center gap-1 px-2 py-1 hover:bg-dark-700 rounded transition-colors"
            >
              {showCode ? <Sparkles className="w-3 h-3" /> : <Terminal className="w-3 h-3" />}
              {showCode ? '图表' : '源码'}
            </button>
          </div>
        </div>
        <div className="p-4 bg-dark-900 min-h-[100px]">
          {isRendering ? (
            <div className="flex items-center justify-center gap-2 text-dark-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">渲染中...</span>
            </div>
          ) : error ? (
            <div className="space-y-2">
              <pre className="text-red-400 text-sm overflow-x-auto">{error}</pre>
              <pre className="text-dark-500 text-xs overflow-x-auto">{code}</pre>
            </div>
          ) : showCode ? (
            <pre className="text-dark-200 text-sm overflow-x-auto whitespace-pre-wrap">{code}</pre>
          ) : svg ? (
            <div
              ref={svgContainerRef}
              className="flex justify-center overflow-x-auto cursor-pointer"
              onClick={() => setIsExpanded(true)}
              title="点击放大"
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          ) : (
            <pre className="text-dark-400 text-sm overflow-x-auto whitespace-pre-wrap">{code}</pre>
          )}
        </div>
      </div>
    </>
  );
}, (prevProps, nextProps) => {
  // 自定义比较函数：
  // 1. code 变化 → 重新渲染
  // 2. isStreaming 从 true 变为 false → 重新渲染（触发首次渲染）
  // 3. 其他情况 → 不重新渲染
  if (prevProps.code !== nextProps.code) {
    return false; // 代码变化，需要重新渲染
  }
  if (prevProps.isStreaming === true && nextProps.isStreaming === false) {
    return false; // 流式结束，需要重新渲染
  }
  return true; // 其他情况不重新渲染
});

// 工具调用显示组件
function ToolCallsDisplay({ toolCalls }: { toolCalls: ToolCallInfo[] }) {
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedTools(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusIcon = (status: ToolCallInfo['status']) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-400" />;
      case 'success':
        return <Check className="w-4 h-4 text-green-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-dark-500" />;
    }
  };

  const getStatusColor = (status: ToolCallInfo['status']) => {
    switch (status) {
      case 'running':
        return 'border-blue-500/30 bg-blue-500/5';
      case 'success':
        return 'border-green-500/30 bg-green-500/5';
      case 'error':
        return 'border-red-500/30 bg-red-500/5';
      default:
        return 'border-dark-700 bg-dark-800/50';
    }
  };

  const getStatusText = (status: ToolCallInfo['status']) => {
    switch (status) {
      case 'running':
        return '执行中';
      case 'success':
        return '成功';
      case 'error':
        return '失败';
      default:
        return '等待';
    }
  };

  // 获取工具名称的友好显示
  const getToolDisplayName = (name: string) => {
    const nameMap: Record<string, string> = {
      calculator: '计算器',
      web_search: '网络搜索',
      sandbox_execute: '代码执行',
      skill_browser: '技能浏览',
      knowledge_retrieve: '知识库检索',
    };
    return nameMap[name] || name;
  };

  // 获取参数摘要（用于在卡片头部显示）
  const stripInjectedNotice = (result?: string): string | undefined => {
    if (!result) return result;
    const marker = '\n\n[SYSTEM NOTICE]';
    const idx = result.indexOf(marker);
    return idx === -1 ? result : result.slice(0, idx);
  };

  const getArgsSummary = (args: Record<string, unknown>): string => {
    const keys = Object.keys(args);
    if (keys.length === 0) return '';

    // 优先显示常见的参数
    const priorityKeys = ['expression', 'query', 'code', 'question', 'input', 'text'];
    const displayKey = priorityKeys.find(k => k in args) || keys[0];
    const value = args[displayKey];

    if (typeof value === 'string') {
      // 截断长字符串
      const truncated = value.length > 40 ? value.slice(0, 40) + '...' : value;
      return truncated;
    } else if (typeof value === 'number') {
      return String(value);
    } else if (value !== null && typeof value === 'object') {
      return JSON.stringify(value).slice(0, 40) + (JSON.stringify(value).length > 40 ? '...' : '');
    }
    return '';
  };

  return (
    <div className="space-y-2">
      {toolCalls.map((tool, idx) => {
        const toolId = tool.id || `${tool.name}-${idx}`;
        const isExpanded = expandedTools[toolId] ?? Boolean(tool.result || tool.error);
        const argsSummary = getArgsSummary(tool.args);

        const injectedFollowups = tool.injected_followups?.map((f) => ({
          id: f.followupId,
          content: f.content,
          status: f.status || 'injected',
          injectedTool: f.injectedTool,
        })) || [];

        return (
          <div key={toolId} className="space-y-2">
            <div
              className={clsx(
                'rounded-lg border transition-all',
                getStatusColor(tool.status)
              )}
            >
              {/* Header */}
              <button
                onClick={() => toggleExpand(toolId)}
                className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-dark-700/30 transition-colors rounded-lg"
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <Terminal className="w-4 h-4 text-dark-400 flex-shrink-0" />
                  <span className="font-medium text-sm text-dark-200 truncate">
                    {getToolDisplayName(tool.name)}
                  </span>
                  {/* 参数摘要 - 直接显示在工具名后面 */}
                  {argsSummary && (
                    <span className="text-xs text-dark-500 truncate max-w-[200px] font-mono">
                      {argsSummary}
                    </span>
                  )}
                  <span className={clsx(
                    'text-xs px-1.5 py-0.5 rounded flex-shrink-0',
                    tool.status === 'running' && 'bg-blue-500/20 text-blue-400',
                    tool.status === 'success' && 'bg-green-500/20 text-green-400',
                    tool.status === 'error' && 'bg-red-500/20 text-red-400',
                    tool.status === 'pending' && 'bg-dark-600 text-dark-400'
                  )}>
                    {getStatusText(tool.status)}
                  </span>
                  <ToolCallTimer
                    startTime={tool.startTime}
                    endTime={tool.endTime}
                    status={tool.status}
                  />
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {getStatusIcon(tool.status)}
                  {(tool.result || tool.error || Object.keys(tool.args).length > 0) && (
                    isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-dark-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-dark-500" />
                    )
                  )}
                </div>
              </button>

              {/* Expanded content */}
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2">
                  {Object.keys(tool.args).length > 0 && (
                    <div>
                      <div className="text-xs text-dark-500 mb-1">参数</div>
                      <pre className="text-xs bg-dark-900/50 rounded p-2 overflow-x-auto text-dark-300 font-mono">
                        {JSON.stringify(tool.args, null, 2)}
                      </pre>
                    </div>
                  )}

                  {tool.status === 'success' && tool.result && (
                    <div>
                      <div className="text-xs text-dark-500 mb-1">结果</div>
                      <div className="text-xs bg-dark-900/50 rounded p-2 max-h-32 overflow-y-auto text-dark-300 whitespace-pre-wrap">
                        {stripInjectedNotice(tool.result)}
                      </div>
                    </div>
                  )}

                  {tool.status === 'error' && tool.error && (
                    <div>
                      <div className="text-xs text-red-400 mb-1">错误</div>
                      <div className="text-xs bg-red-900/20 border border-red-500/30 rounded p-2 max-h-32 overflow-y-auto text-red-300">
                        {tool.error}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {injectedFollowups.length > 0 && (
              <div className="pl-4">
                <FollowupQueueStatus
                  followups={injectedFollowups}
                  compact
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
