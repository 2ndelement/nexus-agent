/**
 * FollowupInput.tsx - Follow-up 消息输入组件
 *
 * 在 Agent 流式响应期间，允许用户发送 follow-up 消息。
 * Follow-up 消息会在下一次工具调用完成后被注入到 Agent 的上下文中。
 */
import React, { useState } from 'react';
import { Send, Loader2, MessageSquarePlus } from 'lucide-react';
import api from '../services/api';
import toast from 'react-hot-toast';

interface FollowupInputProps {
  conversationId: string;
  isStreaming: boolean;
  onFollowupQueued: (followupId: string, content: string) => void;
  disabled?: boolean;
}

const FollowupInput: React.FC<FollowupInputProps> = ({
  conversationId,
  isStreaming,
  onFollowupQueued,
  disabled = false,
}) => {
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || isSending || disabled) return;

    const content = input.trim();
    setInput('');
    setIsSending(true);

    try {
      const response = await api.post('/api/v1/agent/followup', {
        conversation_id: conversationId,
        content: content,
      });

      if (response.data.success) {
        onFollowupQueued(response.data.followup_id, content);
        toast.success('消息已加入队列，将在下一次工具执行时注入');
      } else {
        toast.error(response.data.error || '发送失败');
      }
    } catch (error: unknown) {
      console.error('Follow-up 发送失败:', error);
      const errorMessage = error instanceof Error
        ? error.message
        : '发送失败，请重试';
      toast.error(errorMessage);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isStreaming) {
    return null;
  }

  return (
    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-2">
      <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 mb-2">
        <MessageSquarePlus className="w-4 h-4" />
        <span>追加消息到正在执行的对话</span>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入追加消息..."
          disabled={disabled || isSending}
          className="flex-1 px-3 py-2 text-sm border border-blue-200 dark:border-blue-700 rounded-lg
            bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
            placeholder-gray-400 dark:placeholder-gray-500
            focus:outline-none focus:ring-2 focus:ring-blue-500
            disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isSending || disabled}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg
            disabled:opacity-50 disabled:cursor-not-allowed
            flex items-center gap-2 transition-colors"
        >
          {isSending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          <span className="hidden sm:inline">发送</span>
        </button>
      </div>
      <p className="text-xs text-blue-500 dark:text-blue-400 mt-2">
        消息将在下一次工具调用完成后被 Agent 处理
      </p>
    </div>
  );
};

export default FollowupInput;