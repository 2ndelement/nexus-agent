import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, Agent, Message, Tool, ToolCallInfo, OrganizationWithRole, Context, RegisterRequest, MediaAttachment } from '../types';

// ============================================================================
// Auth Store - V5 重构：用户认证与上下文管理
// ============================================================================

interface AuthState {
  // 认证状态
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;

  // 组织与上下文
  organizations: OrganizationWithRole[];
  currentContext: Context | null;

  // Actions - 认证
  setAuth: (data: {
    user: User;
    accessToken: string;
    refreshToken: string;
    organizations: OrganizationWithRole[];
  }) => void;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;

  // Actions - 上下文
  switchContext: (context: Context) => void;
  refreshOrganizations: (organizations: OrganizationWithRole[]) => void;
  addOrganization: (org: OrganizationWithRole) => void;
  removeOrganization: (orgCode: string) => void;
  updateOrganization: (orgCode: string, data: Partial<OrganizationWithRole>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      organizations: [],
      currentContext: null,

      setAuth: ({ user, accessToken, refreshToken, organizations }) => {
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
          organizations,
          currentContext: { type: 'personal' },  // 默认进入个人空间
        });
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          organizations: [],
          currentContext: null,
        });
      },

      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken });
      },

      switchContext: (context) => {
        set({ currentContext: context });
        // 切换上下文后，清空相关缓存
        useChatStore.getState().resetConversation();
        useAgentStore.getState().setAgents([]);
      },

      refreshOrganizations: (organizations) => {
        set({ organizations });
      },

      addOrganization: (org) => {
        set(state => ({
          organizations: [...state.organizations, org],
        }));
      },

      removeOrganization: (orgCode) => {
        set(state => ({
          organizations: state.organizations.filter(o => o.code !== orgCode),
          // 如果当前在这个组织，切换到个人空间
          currentContext:
            state.currentContext?.type === 'organization' &&
            state.currentContext.orgCode === orgCode
              ? { type: 'personal' }
              : state.currentContext,
        }));
      },

      updateOrganization: (orgCode, data) => {
        set(state => ({
          organizations: state.organizations.map(o =>
            o.code === orgCode ? { ...o, ...data } : o
          ),
        }));
      },
    }),
    {
      name: 'nexus-auth-v2',
      partialize: (state) => ({
        // 只持久化这些字段
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        organizations: state.organizations,
        currentContext: state.currentContext,
      }),
    }
  )
);

// ============================================================================
// Agent Store - V5 重构：支持个人/组织 Agent
// ============================================================================

interface AgentState {
  agents: Agent[];
  currentAgent: Agent | null;
  loading: boolean;

  setAgents: (agents: Agent[]) => void;
  setCurrentAgent: (agent: Agent | null) => void;
  setLoading: (loading: boolean) => void;
  addAgent: (agent: Agent) => void;
  updateAgent: (id: number, data: Partial<Agent>) => void;
  removeAgent: (id: number) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  currentAgent: null,
  loading: false,

  setAgents: (agents) => set({ agents }),
  setCurrentAgent: (currentAgent) => set({ currentAgent }),
  setLoading: (loading) => set({ loading }),

  addAgent: (agent) =>
    set((state) => ({ agents: [...state.agents, agent] })),

  updateAgent: (id, data) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...data } : a)),
      currentAgent: state.currentAgent?.id === id
        ? { ...state.currentAgent, ...data }
        : state.currentAgent,
    })),

  removeAgent: (id) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== id),
      currentAgent: state.currentAgent?.id === id ? null : state.currentAgent,
    })),
}));

// ============================================================================
// Chat Store - V5: 添加 sessionStorage 持久化，支持页面刷新恢复
// ============================================================================

interface ChatState {
  conversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  isSendingNewMessage: boolean;
  setConversationId: (id: string | null) => void;
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  updateLastMessage: (content: string) => void;
  appendToLastMessage: (content: string) => void;
  addToolCallToLastMessage: (toolCall: ToolCallInfo) => void;
  updateToolCallInLastMessage: (toolName: string, updates: Partial<ToolCallInfo>) => void;
  appendTimelineToLastMessage: (item: { type: 'tool_call' | 'followup'; ref: string }) => void;
  upsertFollowupInLastMessage: (followup: { followupId: string; content: string; injectedTool?: string; status?: 'pending' | 'injected' | 'error' }, appendToTimeline?: boolean) => void;
  setContextStatsOnLastMessage: (stats: { tokenCount: number; maxContext: number; compressed?: boolean; timestamp?: number }) => void;
  // V5 新增：错误状态和多媒体附件
  setLastMessageError: (error: string) => void;
  setLastMessageStatus: (status: 'sending' | 'sent' | 'error') => void;
  addAttachmentToLastMessage: (attachment: MediaAttachment) => void;
  setLastMessageThinking: (thinking: string) => void;  // V5: MiniMax thinking
  setStreaming: (streaming: boolean) => void;
  setSendingNewMessage: (sending: boolean) => void;
  clearMessages: () => void;
  resetConversation: () => void;
}

// V5: 使用 sessionStorage 存储聊天状态（页面刷新时可恢复，关闭标签页后清除）
const sessionStoragePersist = {
  getItem: (name: string) => {
    const str = sessionStorage.getItem(name);
    return str ? JSON.parse(str) : null;
  },
  setItem: (name: string, value: unknown) => {
    sessionStorage.setItem(name, JSON.stringify(value));
  },
  removeItem: (name: string) => {
    sessionStorage.removeItem(name);
  },
};

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
  conversationId: null,
  messages: [],
  isStreaming: false,
  isSendingNewMessage: false,
  setConversationId: (conversationId) => set({ conversationId }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  updateLastMessage: (content) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1 ? { ...m, content } : m
      ),
    })),
  appendToLastMessage: (content) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, content: m.content + content }
          : m
      ),
    })),
  addToolCallToLastMessage: (toolCall) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, tool_calls: [...(m.tool_calls || []), toolCall] }
          : m
      ),
    })),
  updateToolCallInLastMessage: (toolName, updates) =>
    set((state) => ({
      messages: state.messages.map((m, i) => {
        if (i !== state.messages.length - 1) return m;
        const toolCalls = m.tool_calls || [];
        const targetIndex = updates.id
          ? toolCalls.findIndex((tc) => tc.id === updates.id)
          : toolCalls.findLastIndex((tc) => tc.name === toolName && tc.status === 'running');
        if (targetIndex === -1) return m;
        return {
          ...m,
          tool_calls: toolCalls.map((tc, idx) =>
            idx === targetIndex ? { ...tc, ...updates } : tc
          ),
        };
      }),
    })),
  appendTimelineToLastMessage: (item) =>
    set((state) => ({
      messages: state.messages.map((m, i) => {
        if (i !== state.messages.length - 1) return m;
        const timeline = m.timeline || [];
        if (timeline.some((existing) => existing.type === item.type && existing.ref === item.ref)) {
          return m;
        }
        return { ...m, timeline: [...timeline, item] };
      }),
    })),
  upsertFollowupInLastMessage: (followup, appendToTimeline = false) =>
    set((state) => ({
      messages: state.messages.map((m, i) => {
        if (i !== state.messages.length - 1) return m;
        const followups = m.followups || [];
        const existingIndex = followups.findIndex((f) => f.followupId === followup.followupId);
        const nextFollowups = existingIndex === -1
          ? [...followups, followup]
          : followups.map((f, idx) => idx === existingIndex ? { ...f, ...followup } : f);
        const timeline = m.timeline || [];
        const nextTimeline = appendToTimeline && !timeline.some((t) => t.type === 'followup' && t.ref === followup.followupId)
          ? [...timeline, { type: 'followup', ref: followup.followupId }]
          : timeline;
        const toolCalls = (m.tool_calls || []).map((tc) => {
          if (followup.injectedTool && tc.name === followup.injectedTool) {
            const injected = tc.injected_followups || [];
            const injectedIndex = injected.findIndex((f) => f.followupId === followup.followupId);
            const nextInjected = injectedIndex === -1
              ? [...injected, followup]
              : injected.map((f, idx) => idx === injectedIndex ? { ...f, ...followup } : f);
            return { ...tc, injected_followups: nextInjected };
          }
          return tc;
        });
        return { ...m, followups: nextFollowups, timeline: nextTimeline, tool_calls: toolCalls };
      }),
    })),
  setContextStatsOnLastMessage: (stats) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, context_stats: stats }
          : m
      ),
    })),
  // V5 新增：设置最后一条消息的错误状态
  setLastMessageError: (error) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, error, status: 'error' as const }
          : m
      ),
    })),
  // V5 新增：设置最后一条消息的状态
  setLastMessageStatus: (status) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, status }
          : m
      ),
    })),
  // V5 新增：添加多媒体附件到最后一条消息
  addAttachmentToLastMessage: (attachment) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, attachments: [...(m.attachments || []), attachment] }
          : m
      ),
    })),
  // V5 新增：设置最后一条消息的思考过程
  setLastMessageThinking: (thinking) =>
    set((state) => ({
      messages: state.messages.map((m, i) =>
        i === state.messages.length - 1
          ? { ...m, thinking: (m.thinking || '') + thinking }
          : m
      ),
    })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  setSendingNewMessage: (isSendingNewMessage) => set({ isSendingNewMessage }),
  clearMessages: () => set({ messages: [] }),
  resetConversation: () => set({ messages: [], conversationId: null, isStreaming: false, isSendingNewMessage: false }),
}),
    {
      name: 'nexus-chat-session',  // sessionStorage key
      storage: sessionStoragePersist,
      // 只持久化必要的状态
      partialize: (state) => ({
        conversationId: state.conversationId,
        messages: state.messages.slice(-50),  // 只保留最近 50 条消息
        isStreaming: state.isStreaming,
      }),
    }
  )
);

// ============================================================================
// Tools Store
// ============================================================================

interface ToolsState {
  tools: Tool[];
  setTools: (tools: Tool[]) => void;
}

export const useToolsStore = create<ToolsState>((set) => ({
  tools: [],
  setTools: (tools) => set({ tools }),
}));

// ============================================================================
// UI Store - V5 重构：更新页面类型
// ============================================================================

interface UIState {
  sidebarOpen: boolean;
  currentPage: 'chat' | 'agents' | 'settings' | 'organization' | 'profile';
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setCurrentPage: (page: UIState['currentPage']) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  currentPage: 'chat',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setCurrentPage: (currentPage) => set({ currentPage }),
}));

// ============================================================================
// Conversation List Store - V5 新增：会话列表
// ============================================================================

interface ConversationListState {
  conversations: Array<{
    conversationId: string;
    title: string;
    updatedAt: string;
  }>;
  loading: boolean;
  setConversations: (conversations: ConversationListState['conversations']) => void;
  setLoading: (loading: boolean) => void;
  addConversation: (conv: ConversationListState['conversations'][0]) => void;
  removeConversation: (conversationId: string) => void;
  updateConversationTitle: (conversationId: string, title: string) => void;
}

export const useConversationListStore = create<ConversationListState>((set) => ({
  conversations: [],
  loading: false,
  setConversations: (conversations) => set({ conversations }),
  setLoading: (loading) => set({ loading }),
  addConversation: (conv) =>
    set((state) => ({ conversations: [conv, ...state.conversations] })),
  removeConversation: (conversationId) =>
    set((state) => ({
      conversations: state.conversations.filter(c => c.conversationId !== conversationId),
    })),
  updateConversationTitle: (conversationId, title) =>
    set((state) => ({
      conversations: state.conversations.map(c =>
        c.conversationId === conversationId ? { ...c, title } : c
      ),
    })),
}));
