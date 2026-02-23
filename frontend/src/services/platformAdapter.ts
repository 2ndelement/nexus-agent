/**
 * platformAdapter.ts - 跨平台消息适配器
 *
 * 设计目标：
 * - 统一内部消息格式与各平台消息格式的转换
 * - 支持 Web、QQ、飞书等多平台
 * - 预留扩展接口，便于后续添加新平台
 *
 * 架构：
 * - PlatformMessage: 平台无关的统一消息格式
 * - PlatformAdapter: 平台适配器接口
 * - WebAdapter: Web 前端默认适配器
 * - 后续可扩展 QQAdapter, FeishuAdapter 等
 */

import type { Message, MediaAttachment } from '../types';

/**
 * 平台无关的统一消息格式
 */
export interface PlatformMessage {
  /** 文本内容 */
  text?: string;
  /** 多媒体附件 */
  media?: MediaAttachment[];
  /** 原始消息 ID（用于引用） */
  messageId?: string;
  /** 发送者信息 */
  sender?: {
    id: string;
    name?: string;
    avatar?: string;
  };
  /** 时间戳 */
  timestamp?: number;
}

/**
 * 平台适配器接口
 */
export interface PlatformAdapter {
  /** 平台名称 */
  readonly platformName: string;

  /**
   * 将内部消息格式转换为平台格式
   * @param message 内部消息
   * @returns 平台消息格式
   */
  formatOutgoing(message: Message): PlatformMessage;

  /**
   * 将平台消息格式转换为内部格式
   * @param platformData 平台原始数据
   * @returns 内部消息格式
   */
  parseIncoming(platformData: unknown): Message;

  /**
   * 转换媒体 URL（某些平台需要特殊处理）
   * @param url 原始 URL
   * @param type 媒体类型
   * @returns 转换后的 URL
   */
  transformMediaUrl?(url: string, type: MediaAttachment['type']): string;
}

/**
 * Web 前端适配器（默认）
 *
 * Web 端直接使用内部格式，无需复杂转换
 */
export class WebAdapter implements PlatformAdapter {
  readonly platformName = 'web';

  formatOutgoing(message: Message): PlatformMessage {
    return {
      text: message.content,
      media: message.attachments,
      messageId: message.id?.toString(),
      timestamp: message.created_at ? new Date(message.created_at).getTime() : Date.now(),
    };
  }

  parseIncoming(data: unknown): Message {
    // Web 端直接使用内部格式
    return data as Message;
  }

  transformMediaUrl(url: string): string {
    // Web 端直接使用原始 URL
    return url;
  }
}

/**
 * QQ 适配器（示例，待完整实现）
 *
 * QQ 消息格式特点：
 * - 图片使用 file:// 或 base64:// 协议
 * - 需要特殊的 CQ 码格式
 * - 消息长度有限制
 */
export class QQAdapter implements PlatformAdapter {
  readonly platformName = 'qq';

  formatOutgoing(message: Message): PlatformMessage {
    return {
      text: message.content,
      media: message.attachments?.map(a => ({
        ...a,
        // QQ 特有的 URL 处理（示例）
        url: this.transformMediaUrl(a.url, a.type),
      })),
    };
  }

  parseIncoming(data: unknown): Message {
    // TODO: 解析 QQ 消息格式
    const qqData = data as Record<string, unknown>;
    return {
      conversation_id: String(qqData.group_id || qqData.user_id || ''),
      role: 'user',
      content: String(qqData.message || ''),
    };
  }

  transformMediaUrl(url: string, type: MediaAttachment['type']): string {
    // QQ 可能需要将 HTTP URL 转换为 QQ 可访问的格式
    // 例如：通过 QQ 的图片代理服务
    if (type === 'image' && url.startsWith('http')) {
      // 示例：实际实现需要根据 QQ 机器人框架调整
      return url;
    }
    return url;
  }
}

/**
 * 飞书适配器（示例，待完整实现）
 *
 * 飞书消息格式特点：
 * - 使用 JSON 卡片格式
 * - 图片需要先上传获取 image_key
 * - 支持富文本和交互卡片
 */
export class FeishuAdapter implements PlatformAdapter {
  readonly platformName = 'feishu';

  formatOutgoing(message: Message): PlatformMessage {
    return {
      text: message.content,
      media: message.attachments?.map(a => ({
        ...a,
        url: this.transformMediaUrl(a.url, a.type),
      })),
    };
  }

  parseIncoming(data: unknown): Message {
    // TODO: 解析飞书消息格式
    const feishuData = data as Record<string, unknown>;
    return {
      conversation_id: String(feishuData.chat_id || ''),
      role: 'user',
      content: String(feishuData.content || ''),
    };
  }

  transformMediaUrl(url: string, type: MediaAttachment['type']): string {
    // 飞书需要将 URL 转换为 image_key
    // 实际实现需要调用飞书 API 上传图片
    return url;
  }
}

// ============================================================================
// 适配器工厂
// ============================================================================

/** 已注册的适配器 */
const adapters: Map<string, PlatformAdapter> = new Map([
  ['web', new WebAdapter()],
  ['qq', new QQAdapter()],
  ['feishu', new FeishuAdapter()],
]);

/**
 * 获取指定平台的适配器
 * @param platform 平台名称，默认为 'web'
 * @returns 平台适配器
 */
export function getPlatformAdapter(platform: string = 'web'): PlatformAdapter {
  const adapter = adapters.get(platform);
  if (!adapter) {
    console.warn(`Unknown platform: ${platform}, falling back to web adapter`);
    return adapters.get('web')!;
  }
  return adapter;
}

/**
 * 注册自定义平台适配器
 * @param adapter 适配器实例
 */
export function registerAdapter(adapter: PlatformAdapter): void {
  adapters.set(adapter.platformName, adapter);
}

/**
 * 获取所有已注册的平台名称
 */
export function getRegisteredPlatforms(): string[] {
  return Array.from(adapters.keys());
}

// 默认导出 Web 适配器
export default WebAdapter;
