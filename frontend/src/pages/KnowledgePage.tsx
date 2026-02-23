import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database,
  Plus,
  Search,
  FileText,
  Upload,
  Trash2,
  MoreVertical,
  FolderOpen,
  File,
  X,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useAuthStore } from '../stores';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import axios from 'axios';

const API_BASE = '';
const RAG_API = '/rag-api';

// 本地存储 key
const KB_STORAGE_KEY = 'nexus_knowledge_bases';

interface KnowledgeBase {
  id: string;
  context_key: string;  // V5: personal:userId or org:orgCode
  name: string;
  description?: string;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  doc_count: number;
  status: number;
  created_at?: string;
}

interface Document {
  id: string;
  kb_id: string;
  title: string;
  file_type?: string;
  file_size?: number;
  chunk_count: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  created_at?: string;
}

// 本地存储工具函数
function loadKbsFromStorage(contextKey: string): KnowledgeBase[] {
  try {
    const data = localStorage.getItem(`${KB_STORAGE_KEY}_${contextKey}`);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function saveKbsToStorage(contextKey: string, kbs: KnowledgeBase[]) {
  localStorage.setItem(`${KB_STORAGE_KEY}_${contextKey}`, JSON.stringify(kbs));
}

function loadDocsFromStorage(kbId: string): Document[] {
  try {
    const data = localStorage.getItem(`${KB_STORAGE_KEY}_docs_${kbId}`);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function saveDocsToStorage(kbId: string, docs: Document[]) {
  localStorage.setItem(`${KB_STORAGE_KEY}_docs_${kbId}`, JSON.stringify(docs));
}

export default function KnowledgePage() {
  const navigate = useNavigate();
  const { user, currentContext } = useAuthStore();

  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Build context key for localStorage isolation
  const contextKey = currentContext?.type === 'organization'
    ? `org:${currentContext.orgCode}`
    : `personal:${user?.id || 'unknown'}`;

  useEffect(() => {
    if (user?.id) {
      loadKnowledgeBases();
    }
  }, [user?.id]);

  useEffect(() => {
    if (selectedKb) {
      loadDocuments(selectedKb.id);
    }
  }, [selectedKb]);

  async function loadKnowledgeBases() {
    setLoading(true);
    try {
      // 使用本地存储
      const kbs = loadKbsFromStorage(contextKey);
      setKnowledgeBases(kbs);
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments(kbId: string) {
    const docs = loadDocsFromStorage(kbId);
    setDocuments(docs);
  }

  async function createKnowledgeBase(name: string, description: string) {
    try {
      const newKb: KnowledgeBase = {
        id: `kb_${Date.now()}`,
        context_key: contextKey,
        name,
        description,
        embedding_model: 'BAAI/bge-base-zh-v1.5',
        chunk_size: 500,
        chunk_overlap: 50,
        doc_count: 0,
        status: 1,
        created_at: new Date().toISOString(),
      };
      const updatedKbs = [...knowledgeBases, newKb];
      setKnowledgeBases(updatedKbs);
      saveKbsToStorage(contextKey, updatedKbs);
      toast.success('知识库创建成功');
      setShowCreateModal(false);
    } catch (error: any) {
      toast.error('创建失败');
    }
  }

  async function deleteKnowledgeBase(kb: KnowledgeBase) {
    if (!confirm(`确定要删除知识库 "${kb.name}" 吗？这将删除所有相关文档。`)) return;

    try {
      const updatedKbs = knowledgeBases.filter(k => k.id !== kb.id);
      setKnowledgeBases(updatedKbs);
      saveKbsToStorage(contextKey, updatedKbs);
      // 删除文档
      localStorage.removeItem(`${KB_STORAGE_KEY}_docs_${kb.id}`);
      if (selectedKb?.id === kb.id) {
        setSelectedKb(null);
        setDocuments([]);
      }
      toast.success('知识库已删除');
    } catch (error) {
      toast.error('删除失败');
    }
  }

  async function uploadDocument(file: File, title: string) {
    if (!selectedKb) return;

    setUploading(true);
    try {
      // Read file content
      const content = await file.text();
      const docId = `doc-${Date.now()}`;

      // Ingest to RAG service (X-Context header added by axios interceptor)
      const response = await axios.post(
        `${RAG_API}/v1/knowledge/ingest`,
        {
          doc_id: docId,
          knowledge_base_id: String(selectedKb.id),
          content,
          metadata: {
            title,
            file_type: file.type,
            file_size: file.size,
          },
        },
        {
          timeout: 120000,
        }
      );

      const result = response.data;

      // 保存文档到本地存储
      const newDoc: Document = {
        id: docId,
        kb_id: selectedKb.id,
        title,
        file_type: file.type,
        file_size: file.size,
        chunk_count: result.chunks_count,
        status: 'completed',
        created_at: new Date().toISOString(),
      };
      const updatedDocs = [...documents, newDoc];
      setDocuments(updatedDocs);
      saveDocsToStorage(selectedKb.id, updatedDocs);

      // 更新知识库文档数
      const updatedKbs = knowledgeBases.map(kb =>
        kb.id === selectedKb.id ? { ...kb, doc_count: kb.doc_count + 1 } : kb
      );
      setKnowledgeBases(updatedKbs);
      saveKbsToStorage(contextKey, updatedKbs);

      toast.success(`文档上传成功，已分割为 ${result.chunks_count} 个片段`);
      setShowUploadModal(false);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '上传失败');
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(doc: Document) {
    if (!selectedKb) return;
    if (!confirm(`确定要删除文档 "${doc.title}" 吗？`)) return;

    try {
      // X-Context header added by axios interceptor
      await axios.post(
        `${RAG_API}/v1/knowledge/delete`,
        {
          doc_id: String(doc.id),
          knowledge_base_id: String(selectedKb.id),
        }
      );

      // 更新本地存储
      const updatedDocs = documents.filter(d => d.id !== doc.id);
      setDocuments(updatedDocs);
      saveDocsToStorage(selectedKb.id, updatedDocs);

      // 更新知识库文档数
      const updatedKbs = knowledgeBases.map(kb =>
        kb.id === selectedKb.id ? { ...kb, doc_count: Math.max(0, kb.doc_count - 1) } : kb
      );
      setKnowledgeBases(updatedKbs);
      saveKbsToStorage(contextKey, updatedKbs);

      toast.success('文档已删除');
    } catch (error) {
      toast.error('删除失败');
    }
  }

  const filteredKbs = knowledgeBases.filter(kb =>
    kb.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-full">
      {/* Knowledge Base List */}
      <div className="w-72 border-r border-dark-800 bg-dark-900/50 flex flex-col">
        <div className="p-4 border-b border-dark-800">
          <h2 className="text-lg font-semibold text-dark-100 mb-3">知识库</h2>
          <button
            onClick={() => setShowCreateModal(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建知识库
          </button>
        </div>

        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
            <input
              type="text"
              placeholder="搜索知识库..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-dark-800 border border-dark-700 rounded-lg"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
            </div>
          ) : filteredKbs.length === 0 ? (
            <div className="text-center py-8 text-dark-500 text-sm">
              {search ? '没有找到匹配的知识库' : '暂无知识库'}
            </div>
          ) : (
            filteredKbs.map((kb) => (
              <div
                key={kb.id}
                onClick={() => setSelectedKb(kb)}
                className={clsx(
                  'flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all group',
                  selectedKb?.id === kb.id
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'hover:bg-dark-800 text-dark-300'
                )}
              >
                <Database className="w-5 h-5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{kb.name}</p>
                  <p className="text-xs text-dark-500">
                    {kb.doc_count || 0} 个文档
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteKnowledgeBase(kb);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-dark-700 rounded text-dark-400 hover:text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {selectedKb ? (
          <>
            {/* Header */}
            <div className="h-16 flex items-center justify-between px-6 border-b border-dark-800">
              <div>
                <h1 className="text-xl font-semibold text-dark-100">{selectedKb.name}</h1>
                <p className="text-sm text-dark-500">{selectedKb.description || '暂无描述'}</p>
              </div>
              <button
                onClick={() => setShowUploadModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors"
              >
                <Upload className="w-4 h-4" />
                上传文档
              </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 p-6 border-b border-dark-800">
              <StatCard
                label="文档数量"
                value={documents.length}
                icon={<FileText className="w-5 h-5" />}
              />
              <StatCard
                label="总片段数"
                value={documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0)}
                icon={<Database className="w-5 h-5" />}
              />
              <StatCard
                label="分块大小"
                value={selectedKb.chunk_size}
                icon={<File className="w-5 h-5" />}
              />
              <StatCard
                label="状态"
                value={selectedKb.status === 1 ? '正常' : '禁用'}
                icon={<Check className="w-5 h-5" />}
                valueColor={selectedKb.status === 1 ? 'text-green-400' : 'text-red-400'}
              />
            </div>

            {/* Documents */}
            <div className="flex-1 overflow-y-auto p-6">
              <h3 className="text-sm font-medium text-dark-400 mb-4">文档列表</h3>

              {documents.length === 0 ? (
                <div className="text-center py-12">
                  <FolderOpen className="w-12 h-12 text-dark-600 mx-auto mb-4" />
                  <p className="text-dark-400">暂无文档</p>
                  <p className="text-sm text-dark-500 mt-1">点击上方按钮上传文档</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center gap-4 p-4 bg-dark-800/50 border border-dark-700 rounded-lg hover:border-dark-600 transition-all"
                    >
                      <div className="w-10 h-10 bg-primary-500/10 rounded-lg flex items-center justify-center">
                        <FileText className="w-5 h-5 text-primary-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-dark-100 truncate">{doc.title}</p>
                        <p className="text-sm text-dark-500">
                          {doc.chunk_count || 0} 个片段
                          {doc.file_size && ` · ${formatFileSize(doc.file_size)}`}
                        </p>
                      </div>
                      <StatusBadge status={doc.status} />
                      <button
                        onClick={() => deleteDocument(doc)}
                        className="p-2 hover:bg-dark-700 rounded-lg text-dark-400 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Database className="w-16 h-16 text-dark-600 mx-auto mb-4" />
              <p className="text-dark-400">选择一个知识库查看详情</p>
              <p className="text-sm text-dark-500 mt-1">或创建新的知识库开始使用</p>
            </div>
          </div>
        )}
      </div>

      {/* Create Knowledge Base Modal */}
      {showCreateModal && (
        <CreateKbModal
          onClose={() => setShowCreateModal(false)}
          onCreate={createKnowledgeBase}
        />
      )}

      {/* Upload Document Modal */}
      {showUploadModal && selectedKb && (
        <UploadModal
          onClose={() => setShowUploadModal(false)}
          onUpload={uploadDocument}
          uploading={uploading}
        />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  valueColor = 'text-dark-100',
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <div className="bg-dark-800/50 border border-dark-700 rounded-xl p-4">
      <div className="flex items-center gap-2 text-dark-400 mb-2">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <p className={clsx('text-2xl font-semibold', valueColor)}>{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    pending: { color: 'bg-yellow-500/10 text-yellow-400', text: '待处理' },
    processing: { color: 'bg-blue-500/10 text-blue-400', text: '处理中' },
    completed: { color: 'bg-green-500/10 text-green-400', text: '已完成' },
    failed: { color: 'bg-red-500/10 text-red-400', text: '失败' },
  }[status] || { color: 'bg-dark-600 text-dark-400', text: '未知' };

  return (
    <span className={clsx('px-2 py-1 text-xs rounded-full', config.color)}>
      {config.text}
    </span>
  );
}

function CreateKbModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, description: string) => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-dark-800 border border-dark-700 rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-dark-700">
          <h2 className="text-lg font-semibold text-dark-100">新建知识库</h2>
          <button onClick={onClose} className="p-2 hover:bg-dark-700 rounded-lg text-dark-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              知识库名称 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：产品文档"
              className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">描述</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述知识库的用途..."
              rows={3}
              className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-lg resize-none"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 bg-dark-700 text-dark-200 rounded-lg hover:bg-dark-600"
            >
              取消
            </button>
            <button
              onClick={() => onCreate(name, description)}
              disabled={!name.trim()}
              className="flex-1 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-400 disabled:opacity-50"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function UploadModal({
  onClose,
  onUpload,
  uploading,
}: {
  onClose: () => void;
  onUpload: (file: File, title: string) => void;
  uploading: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!title) {
        setTitle(f.name.replace(/\.[^.]+$/, ''));
      }
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) {
      setFile(f);
      if (!title) {
        setTitle(f.name.replace(/\.[^.]+$/, ''));
      }
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-dark-800 border border-dark-700 rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-dark-700">
          <h2 className="text-lg font-semibold text-dark-100">上传文档</h2>
          <button onClick={onClose} className="p-2 hover:bg-dark-700 rounded-lg text-dark-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileInputRef.current?.click()}
            className={clsx(
              'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors',
              file
                ? 'border-primary-500 bg-primary-500/5'
                : 'border-dark-600 hover:border-dark-500'
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.pdf,.doc,.docx"
              onChange={handleFileSelect}
              className="hidden"
            />
            {file ? (
              <div>
                <FileText className="w-10 h-10 text-primary-400 mx-auto mb-2" />
                <p className="text-dark-100 font-medium">{file.name}</p>
                <p className="text-sm text-dark-500">{formatFileSize(file.size)}</p>
              </div>
            ) : (
              <div>
                <Upload className="w-10 h-10 text-dark-500 mx-auto mb-2" />
                <p className="text-dark-300">点击或拖拽文件到此处</p>
                <p className="text-sm text-dark-500 mt-1">支持 TXT、MD、PDF、Word</p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              文档标题 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入文档标题"
              className="w-full px-4 py-2.5 bg-dark-900 border border-dark-600 rounded-lg"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              disabled={uploading}
              className="flex-1 py-2.5 bg-dark-700 text-dark-200 rounded-lg hover:bg-dark-600 disabled:opacity-50"
            >
              取消
            </button>
            <button
              onClick={() => file && onUpload(file, title)}
              disabled={!file || !title.trim() || uploading}
              className="flex-1 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-400 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  上传中...
                </>
              ) : (
                '上传'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
