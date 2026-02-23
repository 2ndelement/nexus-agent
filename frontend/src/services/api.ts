import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';
import type {
  User, Agent, Tool, ApiResponse, ChatResponse, ToolCallInfo,
  LoginRequest, RegisterRequest, AuthResponse, Organization,
  OrganizationWithRole, OrganizationMember, OrganizationInvite, Context
} from '../types';
import { useAuthStore, useAgentStore } from '../stores';

// API base URLs - 使用 Vite 代理，无需硬编码 IP
const API_BASE = '/api/v1';            // Agent Engine (8001)
const AUTH_API = '/api/auth';          // Auth Service (8002)
const RAG_API = '/rag-api/v1';         // RAG Service (8003)
const TOOLS_API = '/tools-api';        // Tool Registry (8011)
const ORG_API = '/api/org';            // Organization Service

// Create axios instance
const api = axios.create({
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// Request Interceptor - 添加 Token 和 Context
// ============================================================================

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const { accessToken, currentContext, user } = useAuthStore.getState();

  // 添加 Authorization 头
  if (accessToken && config.headers) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  // 添加用户 ID 头（供 Python 服务使用）
  if (user?.id && config.headers) {
    config.headers['X-User-Id'] = String(user.id);
  }

  // 添加上下文头（告诉后端当前操作在哪个空间）
  if (currentContext && config.headers) {
    if (currentContext.type === 'personal') {
      config.headers['X-Context'] = 'personal';
      // V5 兼容：Java services 需要 X-Tenant-Id (Long 类型)
      // 个人空间使用 user.id 作为 tenant_id
      if (user?.id) {
        config.headers['X-Tenant-Id'] = String(user.id);
      }
    } else {
      config.headers['X-Context'] = `org:${currentContext.orgCode}`;
      // 组织空间使用 orgId 作为 tenant_id
      if (currentContext.orgId) {
        config.headers['X-Tenant-Id'] = String(currentContext.orgId);
      }
    }
  }

  return config;
});

// ============================================================================
// Response Interceptor - 处理 401 错误
// ============================================================================

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    // 401 错误处理
    if (error.response?.status === 401 && originalRequest) {
      // 登录/注册/刷新接口不需要刷新
      if (originalRequest.url?.includes('/auth/login') ||
          originalRequest.url?.includes('/auth/register') ||
          originalRequest.url?.includes('/auth/refresh')) {
        return Promise.reject(error);
      }

      // 正在刷新中，等待
      if (isRefreshing) {
        return new Promise((resolve) => {
          refreshSubscribers.push((token: string) => {
            originalRequest.headers!.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      isRefreshing = true;

      try {
        const { refreshToken } = useAuthStore.getState();
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const response = await axios.post<ApiResponse<{ accessToken: string; refreshToken: string }>>(
          `${AUTH_API}/refresh`,
          { refreshToken }
        );

        const { accessToken: newAccessToken, refreshToken: newRefreshToken } = response.data.data;
        useAuthStore.getState().setTokens(newAccessToken, newRefreshToken);

        // 通知所有等待的请求
        refreshSubscribers.forEach((callback) => callback(newAccessToken));
        refreshSubscribers = [];

        // 重试原请求
        originalRequest.headers!.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch {
        // 刷新失败，登出
        useAuthStore.getState().logout();
        window.location.href = '/login';
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ============================================================================
// Auth API - V5 新增
// ============================================================================

export const authApi = {
  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await api.post<ApiResponse<AuthResponse>>(`${AUTH_API}/login`, data);
    return response.data.data;
  },

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await api.post<ApiResponse<AuthResponse>>(`${AUTH_API}/register`, data);
    return response.data.data;
  },

  async logout(): Promise<void> {
    await api.post(`${AUTH_API}/logout`);
  },

  async refresh(refreshToken: string): Promise<{ accessToken: string; refreshToken: string }> {
    const response = await api.post<ApiResponse<{ accessToken: string; refreshToken: string }>>(
      `${AUTH_API}/refresh`,
      { refreshToken }
    );
    return response.data.data;
  },

  async getMe(): Promise<{ user: User; organizations: OrganizationWithRole[] }> {
    const response = await api.get<ApiResponse<{ user: User; organizations: OrganizationWithRole[] }>>(
      `${AUTH_API}/me`
    );
    return response.data.data;
  },

  async updateProfile(data: { nickname?: string; avatar?: string; email?: string }): Promise<User> {
    const response = await api.put<ApiResponse<User>>(`${AUTH_API}/profile`, data);
    return response.data.data;
  },

  async changePassword(data: { oldPassword: string; newPassword: string }): Promise<void> {
    await api.post(`${AUTH_API}/change-password`, data);
  },
};

// ============================================================================
// Organization API - V5 新增
// ============================================================================

export const organizationApi = {
  async create(data: { code: string; name: string; description?: string }): Promise<Organization> {
    const response = await api.post<ApiResponse<Organization>>(`${ORG_API}`, data);
    return response.data.data;
  },

  async listMyOrganizations(): Promise<{ owned: Organization[]; joined: OrganizationWithRole[] }> {
    const response = await api.get<ApiResponse<{ owned: Organization[]; joined: OrganizationWithRole[] }>>(
      `${ORG_API}`
    );
    return response.data.data;
  },

  async getByCode(code: string): Promise<Organization> {
    const response = await api.get<ApiResponse<Organization>>(`${ORG_API}/${code}`);
    return response.data.data;
  },

  async update(code: string, data: { name?: string; description?: string; avatar?: string }): Promise<Organization> {
    const response = await api.put<ApiResponse<Organization>>(`${ORG_API}/${code}`, data);
    return response.data.data;
  },

  async delete(code: string): Promise<void> {
    await api.delete(`${ORG_API}/${code}`);
  },

  // 成员管理
  async listMembers(code: string): Promise<OrganizationMember[]> {
    const response = await api.get<ApiResponse<OrganizationMember[]>>(`${ORG_API}/${code}/members`);
    return response.data.data;
  },

  async removeMember(code: string, userId: number): Promise<void> {
    await api.delete(`${ORG_API}/${code}/members/${userId}`);
  },

  async updateMemberRole(code: string, userId: number, role: 'ADMIN' | 'MEMBER'): Promise<void> {
    await api.put(`${ORG_API}/${code}/members/${userId}`, { role });
  },

  async transferOwnership(code: string, newOwnerId: number): Promise<void> {
    await api.post(`${ORG_API}/${code}/transfer`, { newOwnerId });
  },

  async leaveOrganization(code: string): Promise<void> {
    await api.post(`${ORG_API}/${code}/leave`);
  },

  // 邀请管理
  async createInvite(code: string, data: { email?: string; role: 'ADMIN' | 'MEMBER' }): Promise<OrganizationInvite> {
    const response = await api.post<ApiResponse<OrganizationInvite>>(`${ORG_API}/${code}/invite`, data);
    return response.data.data;
  },

  async listInvites(code: string): Promise<OrganizationInvite[]> {
    const response = await api.get<ApiResponse<OrganizationInvite[]>>(`${ORG_API}/${code}/invites`);
    return response.data.data;
  },

  async cancelInvite(code: string, inviteId: number): Promise<void> {
    await api.delete(`${ORG_API}/${code}/invites/${inviteId}`);
  },

  async acceptInvite(inviteCode: string): Promise<OrganizationWithRole> {
    const response = await api.post<ApiResponse<OrganizationWithRole>>(`/api/invite/${inviteCode}/accept`);
    return response.data.data;
  },
};

// ============================================================================
// Agent API - V5 重构：支持个人/组织 Agent
// ============================================================================

export const agentApi = {
  // 获取 Agent 列表（通过拦截器自动添加 X-Context 和 X-User-Id 头）
  async list(): Promise<Agent[]> {
    const response = await api.get<ApiResponse<Agent[]>>(`${API_BASE}/agents`);
    return response.data.data || [];
  },

  async get(id: number): Promise<Agent> {
    const response = await api.get<ApiResponse<Agent>>(`${API_BASE}/agents/${id}`);
    return response.data.data;
  },

  async create(data: Partial<Agent>): Promise<Agent> {
    const response = await api.post<ApiResponse<Agent>>(`${API_BASE}/agents`, data);
    return response.data.data;
  },

  async update(id: number, data: Partial<Agent>): Promise<Agent> {
    const response = await api.put<ApiResponse<Agent>>(`${API_BASE}/agents/${id}`, data);
    return response.data.data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`${API_BASE}/agents/${id}`);
  },
};

// ============================================================================
// Tools API
// ============================================================================

export const toolsApi = {
  async list(): Promise<Tool[]> {
    const response = await api.get<ApiResponse<Tool[]>>(`${TOOLS_API}/tools`);
    return response.data.data || [];
  },

  async execute(name: string, args: Record<string, unknown>): Promise<unknown> {
    const response = await api.post(`${TOOLS_API}/execute`, {
      name,
      arguments: args,
    });
    return response.data.data;
  },
};

// ============================================================================
// Conversation API - V5 重构
// ============================================================================

export const conversationApi = {
  async list(): Promise<Array<{ conversationId: string; title: string; updatedAt: string }>> {
    const response = await api.get<ApiResponse<Array<{ conversationId: string; title: string; updatedAt: string }>>>(
      `${API_BASE}/conversations`
    );
    return response.data.data || [];
  },

  async get(conversationId: string): Promise<{ messages: Array<{ role: string; content: string }> }> {
    const response = await api.get<ApiResponse<{ messages: Array<{ role: string; content: string }> }>>(
      `${API_BASE}/conversations/${conversationId}`
    );
    return response.data.data;
  },

  async delete(conversationId: string): Promise<void> {
    await api.delete(`${API_BASE}/conversations/${conversationId}`);
  },

  async updateTitle(conversationId: string, title: string): Promise<void> {
    await api.patch(`${API_BASE}/conversations/${conversationId}`, { title });
  },
};

// ============================================================================
// Chat API - V5 重构：简化 header，使用拦截器自动添加
// ============================================================================

export const chatApi = {
  async stop(conversationId: string): Promise<void> {
    await api.post(`${API_BASE}/agent/stop/${conversationId}`);
  },

  // Non-streaming chat
  async send(
    message: string,
    conversationId?: string
  ): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>(
      `${API_BASE}/agent/chat`,
      { message },
      {
        headers: conversationId ? { 'X-Conv-Id': conversationId } : {},
      }
    );
    return response.data;
  },

  // SSE streaming chat
  streamChat(
    message: string,
    conversationId: string | null,
    onChunk: (content: string) => void,
    onDone: () => void,
    onError: (error: string) => void,
    onToolCall?: (tool: ToolCallInfo) => void,
    onConversationId?: (id: string) => void,
    onThinking?: (content: string) => void,  // V5: MiniMax thinking 回调
    onMedia?: (media: { mediaType: string; url: string; mimeType?: string; filename?: string }) => void,  // V5: 多媒体回调
    onFollowupPending?: (followup: { followupId: string; content: string }) => void,  // V5: Follow-up 等待回调
    onFollowupInjected?: (followup: { followupId: string; content: string; injectedTool?: string }) => void,  // V5: Follow-up 注入回调
    onContextStats?: (stats: { tokenCount: number; maxContext: number; readTokens?: number; writeTokens?: number; messageTokens?: number }) => void,  // V5: 上下文统计回调
  ): () => void {
    const controller = new AbortController();

    const { accessToken, currentContext, user } = useAuthStore.getState();
    const { currentAgent } = useAgentStore.getState();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    if (currentContext) {
      if (currentContext.type === 'personal') {
        headers['X-Context'] = 'personal';
      } else {
        headers['X-Context'] = `org:${currentContext.orgCode}`;
      }
    }

    if (conversationId) {
      headers['X-Conv-Id'] = conversationId;
    }

    if (user) {
      headers['X-User-Id'] = String(user.id);
    }

    if (currentAgent?.id) {
      headers['X-Agent-Id'] = String(currentAgent.id);
    }

    fetch(`${API_BASE}/agent/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No reader');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.slice(5).trim());
                if (data.type === 'chunk' && data.content) {
                  onChunk(data.content);
                } else if (data.type === 'done') {
                  onDone();
                } else if (data.type === 'error') {
                  onError(data.message || 'Unknown error');
                } else if (data.type === 'tool_call' && onToolCall) {
                  const status = data.status === 'start' ? 'running' :
                                 data.status === 'complete' ? 'success' :
                                 data.status === 'error' ? 'error' : 'running';
                  onToolCall({
                    id: data.tool_call_id,
                    name: data.tool_name || 'unknown',
                    args: data.tool_args || {},
                    status: status,
                    result: data.result,
                    error: data.error,
                  });
                } else if (data.type === 'conversation_id' && onConversationId) {
                  onConversationId(data.conversation_id);
                } else if (data.type === 'thinking' && onThinking) {
                  // V5: MiniMax thinking 事件
                  onThinking(data.content);
                } else if (data.type === 'media' && onMedia) {
                  // V5: 多媒体事件
                  onMedia({
                    mediaType: data.media_type || 'image',
                    url: data.url || '',
                    mimeType: data.mime_type,
                    filename: data.filename,
                  });
                } else if (data.type === 'followup_pending' && onFollowupPending) {
                  // V5: Follow-up 等待事件
                  onFollowupPending({
                    followupId: data.followup_id,
                    content: data.content,
                  });
                } else if (data.type === 'followup_injected' && onFollowupInjected) {
                  // V5: Follow-up 注入事件
                  onFollowupInjected({
                    followupId: data.followup_id,
                    content: data.content,
                    injectedTool: data.injected_tool,
                  });
                } else if (data.type === 'context_stats' && onContextStats) {
                  // V5: 上下文统计事件
                  onContextStats({
                    tokenCount: data.token_count,
                    maxContext: data.max_context,
                    readTokens: data.read_tokens,
                    writeTokens: data.write_tokens,
                    messageTokens: data.message_tokens,
                  });
                }
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(err.message);
        }
      });

    return () => controller.abort();
  },
};

/** @deprecated 使用 authApi 替代 */
export const userApi = {
  async list(): Promise<User[]> {
    console.warn('userApi.list() is deprecated');
    return [];
  },

  async create(data: Partial<User>): Promise<User> {
    console.warn('userApi.create() is deprecated, use authApi.register() instead');
    throw new Error('Deprecated');
  },
};

// ============================================================================
// Bot API - V5: Bot 和 BotBinding 管理
// ============================================================================

export interface BotInfo {
  id: number;
  botName: string;
  platform: string;
  appId?: string;
  agentId: number;
  ownerType: string;
  ownerId: number;
  status: number;
  config?: string;
  createTime?: string;
  updateTime?: string;
}

export interface BotBindingInfo {
  id: number;
  botId: number;
  userId: number;
  puid: string;
  botName?: string;
  botPlatform?: string;
  extraData?: any;
  status: number;
  createTime?: string;
}

export const botApi = {
  // 获取 Bot 列表（分页、过滤）
  async list(params?: {
    page?: number;
    size?: number;
    ownerType?: string;
    ownerId?: number;
    platform?: string;
    status?: number;
  }): Promise<{ records: BotInfo[]; total: number; page: number; size: number }> {
    const response = await api.get<ApiResponse<{ records: BotInfo[]; total: number; page: number; size: number }>>(
      `/api/session/bots`,
      { params }
    );
    return response.data.data;
  },

  // 获取 Bot 详情
  async get(id: number): Promise<BotInfo> {
    const response = await api.get<ApiResponse<BotInfo>>(`/api/session/bots/${id}`);
    return response.data.data;
  },

  // 获取用户的 Bot 绑定列表
  async listBindings(params?: { botId?: number }): Promise<BotBindingInfo[]> {
    const response = await api.get<ApiResponse<BotBindingInfo[]>>(
      `/api/session/bot-bindings`,
      { params }
    );
    return response.data.data || [];
  },

  // 创建 Bot 绑定
  async createBinding(data: { botId: number; puid: string; extraData?: any }): Promise<BotBindingInfo> {
    const response = await api.post<ApiResponse<BotBindingInfo>>(
      `/api/session/bot-bindings`,
      data
    );
    return response.data.data;
  },

  // 解绑
  async deleteBinding(id: number): Promise<void> {
    await api.delete(`/api/session/bot-bindings/${id}`);
  },
};

export default api;
