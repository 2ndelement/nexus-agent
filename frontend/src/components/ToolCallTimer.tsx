/**
 * ToolCallTimer - 工具调用实时计时器组件
 *
 * 功能：
 * - 工具执行中显示实时计时（每 100ms 更新）
 * - 工具完成后显示最终耗时
 * - 支持分钟级长时间任务的格式化显示
 */

import { useState, useEffect } from 'react';

interface ToolCallTimerProps {
  startTime?: number;
  endTime?: number;
  status: 'pending' | 'running' | 'success' | 'error';
}

/**
 * 格式化时间为可读字符串
 * @param ms 毫秒数
 * @returns 格式化的时间字符串，如 "1.2s" 或 "2m 30s"
 */
function formatTime(ms: number): string {
  const seconds = ms / 1000;

  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

export function ToolCallTimer({ startTime, endTime, status }: ToolCallTimerProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    // 只在运行状态且有开始时间时启动计时器
    if (status !== 'running' || !startTime) return;

    // 初始化已过去时间
    setElapsed(Date.now() - startTime);

    // 每 100ms 更新一次
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 100);

    return () => clearInterval(interval);
  }, [status, startTime]);

  // 已完成：显示最终耗时
  if (endTime && startTime) {
    const duration = endTime - startTime;
    return (
      <span className="text-gray-500 text-xs ml-2">
        {formatTime(duration)}
      </span>
    );
  }

  // 运行中：显示实时计时
  if (status === 'running' && startTime) {
    return (
      <span className="text-blue-500 text-xs ml-2 animate-pulse">
        {formatTime(elapsed)}
      </span>
    );
  }

  // 待执行或无时间数据
  return null;
}

export default ToolCallTimer;
