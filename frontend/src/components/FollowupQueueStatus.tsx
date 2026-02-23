/**
 * FollowupQueueStatus.tsx - Follow-up 队列状态显示组件
 *
 * 显示正在等待注入的 follow-up 消息列表及其状态。
 * V5: 增强版 - 显示注入到哪个工具，使用链条样式
 */
import React from 'react';
import { Clock, CheckCircle, AlertCircle, MessageSquare, ArrowDown, Zap } from 'lucide-react';

export interface FollowupInfo {
  id: string;
  content: string;
  status: 'pending' | 'injected' | 'error';
  injectedTool?: string;  // 注入到哪个工具
  createdAt?: number;
}

interface FollowupQueueStatusProps {
  followups: FollowupInfo[];
  className?: string;
  compact?: boolean;  // 紧凑模式，用于工具调用框内
}

const FollowupQueueStatus: React.FC<FollowupQueueStatusProps> = ({
  followups,
  className = '',
  compact = false,
}) => {
  if (followups.length === 0) {
    return null;
  }

  const getStatusIcon = (status: FollowupInfo['status']) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500 animate-pulse" />;
      case 'injected':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusText = (status: FollowupInfo['status'], injectedTool?: string) => {
    switch (status) {
      case 'pending':
        return '等待注入';
      case 'injected':
        return injectedTool ? `已注入到 ${injectedTool}` : '已注入';
      case 'error':
        return '注入失败';
      default:
        return '';
    }
  };

  const getStatusColor = (status: FollowupInfo['status']) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800';
      case 'injected':
        return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
      case 'error':
        return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
      default:
        return 'bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-800';
    }
  };

  // 紧凑模式 - 用于工具调用框内
  if (compact) {
    return (
      <div className={`space-y-1 ${className}`}>
        {followups.map((followup, index) => (
          <div
            key={followup.id}
            className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
              followup.status === 'pending'
                ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                : followup.status === 'injected'
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
            }`}
          >
            {getStatusIcon(followup.status)}
            <span className="truncate flex-1">{followup.content}</span>
            {followup.injectedTool && (
              <span className="text-xs opacity-70">→ {followup.injectedTool}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        <MessageSquare className="w-4 h-4" />
        <span>追加消息队列 ({followups.length})</span>
      </div>
      {followups.map((followup, index) => (
        <div
          key={followup.id}
          className={`relative flex items-start gap-3 p-3 rounded-lg border ${getStatusColor(followup.status)}`}
        >
          {/* 连接线到下一个 */}
          {index < followups.length - 1 && (
            <div className="absolute left-6 top-10 w-0.5 h-2 bg-gray-300 dark:bg-gray-600" />
          )}
          <div className="flex-shrink-0 mt-0.5">
            {getStatusIcon(followup.status)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                #{index + 1}
              </span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                followup.status === 'pending' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-800 dark:text-yellow-200' :
                followup.status === 'injected' ? 'bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200' :
                'bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200'
              }`}>
                {getStatusText(followup.status, followup.injectedTool)}
              </span>
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300 mt-1 break-words">
              {followup.content}
            </p>
            {followup.status === 'injected' && followup.injectedTool && (
              <div className="flex items-center gap-1 mt-1 text-xs text-gray-500 dark:text-gray-400">
                <Zap className="w-3 h-3" />
                <span>注入点: {followup.injectedTool}</span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default FollowupQueueStatus;