/**
 * MediaRenderer - 多媒体消息渲染组件
 *
 * 功能：
 * - 支持图片、视频、音频、文件四种类型
 * - 图片支持点击放大查看
 * - 视频支持缩略图和播放控制
 * - 文件支持下载
 *
 * 设计原则：
 * - 使用 Tailwind CSS 保持与项目风格一致
 * - 组件可复用，支持跨平台适配
 */

import { Download, File, Image, Film, Music } from 'lucide-react';
import type { MediaAttachment } from '../types';

interface MediaRendererProps {
  attachments: MediaAttachment[];
  className?: string;
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * 根据媒体类型获取对应的图标
 */
function getMediaIcon(type: MediaAttachment['type']) {
  switch (type) {
    case 'image':
      return <Image className="w-5 h-5" />;
    case 'video':
      return <Film className="w-5 h-5" />;
    case 'audio':
      return <Music className="w-5 h-5" />;
    case 'file':
    default:
      return <File className="w-5 h-5" />;
  }
}

/**
 * 图片渲染组件
 */
function ImageRenderer({ attachment }: { attachment: MediaAttachment }) {
  return (
    <a
      href={attachment.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block group"
    >
      <div className="relative overflow-hidden rounded-lg">
        <img
          src={attachment.url}
          alt={attachment.filename || 'Image'}
          className="max-w-xs max-h-48 object-cover cursor-pointer transition-opacity group-hover:opacity-90"
          loading="lazy"
        />
        {/* 悬停时显示放大提示 */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
          <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium">
            点击查看大图
          </span>
        </div>
      </div>
      {attachment.filename && (
        <p className="text-xs text-gray-500 mt-1 truncate max-w-xs">
          {attachment.filename}
        </p>
      )}
    </a>
  );
}

/**
 * 视频渲染组件
 */
function VideoRenderer({ attachment }: { attachment: MediaAttachment }) {
  return (
    <div className="max-w-md">
      <video
        src={attachment.url}
        poster={attachment.thumbnail}
        controls
        preload="metadata"
        className="rounded-lg w-full"
      />
      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
        {attachment.filename && (
          <span className="truncate">{attachment.filename}</span>
        )}
        {attachment.duration && (
          <span>
            {Math.floor(attachment.duration / 60)}:{String(Math.floor(attachment.duration % 60)).padStart(2, '0')}
          </span>
        )}
        {attachment.size && (
          <span>({formatFileSize(attachment.size)})</span>
        )}
      </div>
    </div>
  );
}

/**
 * 音频渲染组件
 */
function AudioRenderer({ attachment }: { attachment: MediaAttachment }) {
  return (
    <div className="w-64">
      <audio
        src={attachment.url}
        controls
        preload="metadata"
        className="w-full"
      />
      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
        {attachment.filename && (
          <span className="truncate">{attachment.filename}</span>
        )}
        {attachment.duration && (
          <span>
            {Math.floor(attachment.duration / 60)}:{String(Math.floor(attachment.duration % 60)).padStart(2, '0')}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * 文件渲染组件
 */
function FileRenderer({ attachment }: { attachment: MediaAttachment }) {
  return (
    <a
      href={attachment.url}
      download={attachment.filename}
      className="flex items-center gap-3 p-3 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors max-w-xs"
    >
      <div className="flex-shrink-0 text-gray-500">
        {getMediaIcon(attachment.type)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
          {attachment.filename || '未命名文件'}
        </p>
        {attachment.size && (
          <p className="text-xs text-gray-500">
            {formatFileSize(attachment.size)}
          </p>
        )}
      </div>
      <Download className="w-4 h-4 text-gray-400 flex-shrink-0" />
    </a>
  );
}

/**
 * 单个媒体项渲染
 */
function MediaItem({ attachment }: { attachment: MediaAttachment }) {
  switch (attachment.type) {
    case 'image':
      return <ImageRenderer attachment={attachment} />;
    case 'video':
      return <VideoRenderer attachment={attachment} />;
    case 'audio':
      return <AudioRenderer attachment={attachment} />;
    case 'file':
    default:
      return <FileRenderer attachment={attachment} />;
  }
}

/**
 * 多媒体消息渲染主组件
 */
export function MediaRenderer({ attachments, className = '' }: MediaRendererProps) {
  if (!attachments || attachments.length === 0) {
    return null;
  }

  return (
    <div className={`flex flex-wrap gap-3 mt-3 ${className}`}>
      {attachments.map((attachment, index) => (
        <MediaItem key={`${attachment.url}-${index}`} attachment={attachment} />
      ))}
    </div>
  );
}

export default MediaRenderer;
