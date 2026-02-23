/**
 * ContextTokenStatus.tsx - 上下文 Token 统计组件
 *
 * 在右下角显示当前上下文使用的 token 数量和最大上下文限制。
 * 包含进度条，颜色随使用率变化。
 */
import React from 'react';
import { BarChart3 } from 'lucide-react';

interface ContextTokenStatusProps {
  tokenCount: number;
  maxContext: number;
  readTokens?: number;
  writeTokens?: number;
  messageTokens?: number;
  className?: string;
}

const ContextTokenStatus: React.FC<ContextTokenStatusProps> = ({
  tokenCount,
  maxContext,
  readTokens = 0,
  writeTokens = 0,
  messageTokens = 0,
  className = '',
}) => {
  // 计算使用率
  const usagePercent = maxContext > 0 ? (tokenCount / maxContext) * 100 : 0;

  // 格式化数字显示
  const formatNumber = (num: number): string => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  };

  // 获取颜色类名
  const getColorClass = (): string => {
    if (usagePercent < 60) {
      return 'text-green-600 dark:text-green-400';
    } else if (usagePercent < 80) {
      return 'text-yellow-600 dark:text-yellow-400';
    } else {
      return 'text-red-600 dark:text-red-400';
    }
  };

  // 获取进度条颜色类名
  const getProgressColorClass = (): string => {
    if (usagePercent < 60) {
      return 'bg-green-500';
    } else if (usagePercent < 80) {
      return 'bg-yellow-500';
    } else {
      return 'bg-red-500';
    }
  };

  // 获取背景颜色类名
  const getBgColorClass = (): string => {
    if (usagePercent < 60) {
      return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
    } else if (usagePercent < 80) {
      return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800';
    } else {
      return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
    }
  };

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${getBgColorClass()} ${className}`}
      title={`上下文使用: ${tokenCount} / ${maxContext} tokens\n读取: ${readTokens} · 输出: ${writeTokens} · 当前消息: ${messageTokens}`}
    >
      {/* 图标 */}
      <BarChart3 className={`w-4 h-4 flex-shrink-0 ${getColorClass()}`} />

      {/* 数字显示 */}
      <div className="flex flex-col min-w-0">
        <div className={`text-sm font-medium ${getColorClass()}`}>
          <span>{formatNumber(tokenCount)}</span>
          <span className="text-gray-400 mx-1">/</span>
          <span className="text-gray-500 dark:text-gray-400">{formatNumber(maxContext)}</span>
        </div>

        <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 whitespace-nowrap">
          读 {formatNumber(readTokens)} · 写 {formatNumber(writeTokens)} · 本条 {formatNumber(messageTokens)}
        </div>

        {/* 进度条 */}
        <div className="w-24 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mt-1">
          <div
            className={`h-full rounded-full transition-all duration-300 ${getProgressColorClass()}`}
            style={{ width: `${Math.min(usagePercent, 100)}%` }}
          />
        </div>
      </div>

      {/* 百分比 */}
      <div className={`text-xs font-medium ${getColorClass()}`}>
        {usagePercent.toFixed(0)}%
      </div>
    </div>
  );
};

export default ContextTokenStatus;
