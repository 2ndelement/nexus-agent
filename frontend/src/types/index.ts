// Types for NexusAgent Frontend
// V5 重构：用户独立注册，支持个人空间和组织

// ============================================================================
// 用户相关
// ============================================================================

export interface User {
  id: number;
  username: string;
  email?: string;
  nickname?: string;
  avatar?: string;
  status: number;
  // 配额
  personalAgentLimit: number;
  orgCreateLimit: number;
  orgJoinLimit: number;
  createdAt?: string;
}

export interface LoginRequest {
  username: string;  // 用户名或邮箱
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
  nickname?: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
  user: User;
  organizations: OrganizationWithRole[];
}

// ============================================================================
// 组织相关
// ============================================================================

export interface Organization {
  id: number;
  code: string;
  name: string;
  description?: string;
  avatar?: string;
  ownerId: number;
  plan: 'FREE' | 'PRO' | 'ENTERPRISE';
  status: number;
  memberLimit: number;
  agentLimit: number;
  memberCount?: number;
  createdAt?: string;
}

export interface OrganizationWithRole extends Organization {
  role: 'OWNER' | 'ADMIN' | 'MEMBER';  // 当前用户在此组织的角色
}

export interface OrganizationMember {
  id: number;
  userId: number;
  username: string;
  nickname?: string;
  avatar?: string;
  email?: string;
  role: 'OWNER' | 'ADMIN' | 'MEMBER';
  joinedAt: string;
  invitedBy?: number;
}

export interface OrganizationInvite {
  id: number;
  organizationId: number;
  email?: string;
  inviteCode: string;
  role: 'ADMIN' | 'MEMBER';
  invitedBy: number;
  status: 0 | 1 | 2 | 3;  // 0=待接受 1=已接受 2=已过期 3=已取消
  expireAt: string;
  createdAt: string;
}

// ============================================================================
// 上下文相关
// ============================================================================

export type Context =
  | { type: 'personal' }
  | { type: 'organization'; orgCode: string; orgId: number };

// ============================================================================
// Agent 相关（V5 重构）
// ============================================================================

export interface Agent {
  id: number;
  ownerType: 'PERSONAL' | 'ORGANIZATION';
  ownerId: number;
  name: string;
  description?: string;
  systemPrompt?: string;
  model: string;
  temperature: number;
  maxTokens: number;
  toolsEnabled?: string[];
  status: number;
  createdAt?: string;
  updatedAt?: string;
}

// ============================================================================
// 会话相关（V5 重构）
// ============================================================================

export interface Conversation {
  id: number;
  conversationId: string;
  ownerType: 'PERSONAL' | 'ORGANIZATION';
  ownerId: number;
  userId: number;
  agentId?: number;
  title?: string;
  status: number;
  messageCount: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface MessageTimelineItem {
  type: 'tool_call' | 'followup';
  ref: string;
}

export interface ContextStatsInfo {
  tokenCount: number;
  maxContext: number;
  compressed?: boolean;
  timestamp?: number;
  readTokens?: number;
  writeTokens?: number;
  messageTokens?: number;
}

export interface Message {
  id?: number;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tool_calls?: ToolCallInfo[];
  created_at?: string;
  // V5 新增：消息状态和错误信息
  status?: 'sending' | 'sent' | 'error';
  error?: string;
  // V5 新增：多媒体附件
  attachments?: MediaAttachment[];
  // V5 新增：思考过程（MiniMax 等模型）
  thinking?: string;
  // V5 新增：follow-up 注入记录
  followups?: { followupId: string; content: string; injectedTool?: string; status?: 'pending' | 'injected' | 'error' }[];
  // V5 新增：上下文统计
  context_stats?: ContextStatsInfo;
  // V5 新增：可回放事件时间线
  timeline?: MessageTimelineItem[];
}

export interface ChatRequest {
  message: string;
  user_id?: string;
  conversation_id?: string;
  // V5 重构：添加上下文信息
  context?: Context;
}

export interface ChatResponse {
  conversation_id: string;
  content: string;
}

export interface SSEEvent {
  type: 'chunk' | 'done' | 'error' | 'tool_call' | 'media';
  content?: string;
  conversation_id?: string;
  message?: string;
  // 工具调用字段
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  status?: 'start' | 'complete' | 'error';
  result?: string;
  error?: string;
  // 多媒体字段
  media_type?: MediaType;
  url?: string;
  mime_type?: string;
  filename?: string;
  size?: number;
  width?: number;
  height?: number;
  duration?: number;
  thumbnail?: string;
}

export interface ToolCallInfo {
  id?: string;
  name: string;
  args: Record<string, unknown>;
  status: 'pending' | 'running' | 'success' | 'error';
  result?: string;
  error?: string;
  startTime?: number;
  endTime?: number;
  injected_followups?: { followupId: string; content: string; injectedTool?: string; status?: 'pending' | 'injected' | 'error' }[];
}

// ============================================================================
// 多媒体相关（V5 新增）
// ============================================================================

export type MediaType = 'image' | 'video' | 'audio' | 'file';

export interface MediaAttachment {
  type: MediaType;
  url: string;              // MinIO/S3 URL
  mimeType: string;         // image/png, video/mp4, audio/mp3
  filename?: string;
  size?: number;            // 字节
  width?: number;           // 图片/视频
  height?: number;
  duration?: number;        // 音频/视频时长（秒）
  thumbnail?: string;       // 视频缩略图 URL
}

// ============================================================================
// 工具相关
// ============================================================================

export interface Tool {
  id: number;
  name: string;
  description: string;
  parameters: {
    type: string;
    properties: Record<string, unknown>;
    required?: string[];
  };
  scope: 'BUILTIN' | 'MCP' | 'CUSTOM';
  status: number;
}

// ============================================================================
// 知识库相关（V5 重构）
// ============================================================================

export interface KnowledgeBase {
  id: number;
  ownerType: 'PERSONAL' | 'ORGANIZATION';
  ownerId: number;
  name: string;
  description?: string;
  embeddingModel: string;
  chunkSize: number;
  chunkOverlap: number;
  docCount: number;
  status: number;
}

// ============================================================================
// 模型相关
// ============================================================================

export type ModelCategory = 'recommended' | 'powerful' | 'lightweight' | 'coding' | 'chinese' | 'other';

export interface ModelInfo {
  id: string;
  name: string;
  vendor: string;
  category: ModelCategory;
  description?: string;
  maxOutputTokens?: number;
  maxContextTokens?: number;
  supportsVision?: boolean;
  supportsTools?: boolean;
  supportsStreaming?: boolean;
  preview?: boolean;
}

export interface ModelCategoryGroup {
  id: ModelCategory;
  name: string;
  description: string;
  models: ModelInfo[];
}

export interface ModelsResponse {
  categories: ModelCategoryGroup[];
  total: number;
}

// ============================================================================
// 角色相关
// ============================================================================

export interface Role {
  id: number;
  name: string;
  code: string;
  description?: string;
}

// ============================================================================
// API 响应
// ============================================================================

export interface ApiResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

