import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  Bot,
  Sparkles,
  Wrench,
  MessageSquare,
  Settings2,
  AlertCircle,
  Database,
  Star,
  Zap,
  Gauge,
  Code,
  Globe,
  ChevronDown,
  ChevronRight,
  Eye,
  Loader2,
} from 'lucide-react';
import { useAuthStore, useAgentStore, useToolsStore } from '../stores';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import api, { botApi } from '../services/api';
import type { ModelInfo, ModelCategoryGroup } from '../types';

const API_BASE = '';
const TOOLS_API = '/tools-api';

// 本地存储 key (与 KnowledgePage 共享)
const KB_STORAGE_KEY = 'nexus_knowledge_bases';

// 分类图标映射
const CATEGORY_ICONS: Record<string, React.ElementType> = {
  recommended: Star,
  powerful: Zap,
  lightweight: Gauge,
  coding: Code,
  chinese: Globe,
  other: Sparkles,
};

// 降级模型列表（API 不可用时使用）
const FALLBACK_CATEGORIES: ModelCategoryGroup[] = [
  {
    id: 'lightweight',
    name: '轻量快速',
    description: '低延迟场景',
    models: [
      { id: 'gpt-5-mini', name: 'GPT-5 mini', vendor: 'OpenAI', category: 'lightweight', description: '快速响应，性价比高' },
      { id: 'MiniMax-M2.7-highspeed', name: 'MiniMax M2.7', vendor: 'MiniMax', category: 'lightweight', description: '极速响应' },
    ],
  },
  {
    id: 'chinese',
    name: '国产模型',
    description: '中文优化',
    models: [
      { id: 'qwen3.5-plus', name: '通义千问 3.5 Plus', vendor: '阿里云', category: 'chinese', description: '1M 上下文，深度思考' },
      { id: 'kimi-k2.5', name: 'Kimi K2.5', vendor: '月之暗面', category: 'chinese', description: '262K 上下文' },
      { id: 'glm-5', name: 'GLM-5', vendor: '智谱AI', category: 'chinese', description: '深度思考模型' },
    ],
  },
];

export default function AgentEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, currentContext } = useAuthStore();
  const { addAgent, updateAgent } = useAgentStore();
  const { tools, setTools } = useToolsStore();

  const isNew = !id || id === 'new';

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'basic' | 'prompt' | 'tools' | 'knowledge' | 'bots'>('basic');

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [model, setModel] = useState('gpt-5-mini');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [enabledTools, setEnabledTools] = useState<string[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<any[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);

  // 模型列表状态
  const [modelCategories, setModelCategories] = useState<ModelCategoryGroup[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);

  // Load models
  useEffect(() => {
    loadModels();
  }, []);

  async function loadModels() {
    setModelsLoading(true);
    try {
      const response = await api.get('/api/v1/models?grouped=true');
      if (response.data.code === 200 && response.data.data?.categories) {
        setModelCategories(response.data.data.categories);
      } else {
        throw new Error('API 返回失败');
      }
    } catch (error) {
      console.error('Failed to load models:', error);
      // 降级使用静态列表
      setModelCategories(FALLBACK_CATEGORIES);
    } finally {
      setModelsLoading(false);
    }
  }

  // Load agent data, tools, and knowledge bases
  useEffect(() => {
    loadTools();
    loadKnowledgeBases();
    if (!isNew && id) {
      loadAgent(Number(id));
    }
  }, [id]);

  async function loadAgent(agentId: number) {
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/agents/${agentId}`);
      const agent = response.data.data || response.data;

      setName(agent.name || '');
      setDescription(agent.description || '');
      setModel(agent.model || 'gpt-5-mini');
      setTemperature(agent.temperature || 0.7);
      setMaxTokens(agent.max_tokens || 4096);
      setSystemPrompt(agent.system_prompt || '');

      try {
        const toolsEnabled = typeof agent.tools_enabled === 'string'
          ? JSON.parse(agent.tools_enabled)
          : agent.tools_enabled || [];
        setEnabledTools(toolsEnabled);
      } catch {
        setEnabledTools([]);
      }

      try {
        const kbIds = typeof agent.knowledge_base_ids === 'string'
          ? JSON.parse(agent.knowledge_base_ids)
          : agent.knowledge_base_ids || [];
        setSelectedKbIds(kbIds);
      } catch {
        setSelectedKbIds([]);
      }
    } catch (error) {
      console.error('Failed to load agent:', error);
      toast.error('加载 Agent 失败');
      navigate('/agents');
    } finally {
      setLoading(false);
    }
  }

  async function loadTools() {
    try {
      // X-Context header is automatically added by api interceptor
      const response = await api.get(`${TOOLS_API}/tools`);
      const data = response.data.data || [];
      setTools(data);
    } catch (error) {
      console.error('Failed to load tools:', error);
    }
  }

  function loadKnowledgeBases() {
    try {
      // Use user id or context for storage key
      const storageKey = currentContext?.type === 'organization'
        ? `${KB_STORAGE_KEY}_org_${currentContext.orgCode}`
        : `${KB_STORAGE_KEY}_user_${user?.id}`;
      const data = localStorage.getItem(storageKey);
      const kbs = data ? JSON.parse(data) : [];
      setKnowledgeBases(kbs);
    } catch {
      setKnowledgeBases([]);
    }
  }

  function toggleKnowledgeBase(kbId: string) {
    setSelectedKbIds((prev) =>
      prev.includes(kbId)
        ? prev.filter((id) => id !== kbId)
        : [...prev, kbId]
    );
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error('请输入 Agent 名称');
      return;
    }

    setSaving(true);
    try {
      const data = {
        // owner_type and owner_id are set by backend based on X-Context header
        name: name.trim(),
        description: description.trim(),
        model,
        temperature,
        max_tokens: maxTokens,
        system_prompt: systemPrompt,
        tools_enabled: JSON.stringify(enabledTools),
        knowledge_base_ids: JSON.stringify(selectedKbIds),
        status: 1,
      };

      if (isNew) {
        const response = await api.post(`/api/v1/agents`, data);
        const newAgent = response.data.data || response.data;
        addAgent(newAgent);
        toast.success('Agent 创建成功');
        navigate('/agents');
      } else {
        await api.put(`/api/v1/agents/${id}`, data);
        updateAgent(Number(id), data);
        toast.success('Agent 保存成功');
        navigate('/agents');
      }
    } catch (error: any) {
      console.error('Failed to save agent:', error);
      toast.error(error.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  function toggleTool(toolName: string) {
    setEnabledTools((prev) =>
      prev.includes(toolName)
        ? prev.filter((t) => t !== toolName)
        : [...prev, toolName]
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-6 border-b border-dark-800 bg-dark-900/50">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/agents')}
            className="p-2 hover:bg-dark-800 rounded-lg text-dark-400 hover:text-dark-200 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-semibold text-dark-100">
              {isNew ? '创建 Agent' : '编辑 Agent'}
            </h1>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-400 transition-colors disabled:opacity-50"
        >
          {saving ? (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          保存
        </button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar tabs */}
        <div className="w-48 border-r border-dark-800 bg-dark-900/30 p-4">
          <nav className="space-y-1">
            {[
              { id: 'basic', label: '基本信息', icon: Settings2 },
              { id: 'prompt', label: '系统提示词', icon: MessageSquare },
              { id: 'tools', label: '工具配置', icon: Wrench },
              { id: 'knowledge', label: '知识库', icon: Database },
              { id: 'bots', label: 'Bot 绑定', icon: Bot },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={clsx(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-primary-500/10 text-primary-400'
                    : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'
                )}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl">
            {activeTab === 'basic' && (
              <BasicInfoTab
                name={name}
                setName={setName}
                description={description}
                setDescription={setDescription}
                model={model}
                setModel={setModel}
                temperature={temperature}
                setTemperature={setTemperature}
                maxTokens={maxTokens}
                setMaxTokens={setMaxTokens}
                modelCategories={modelCategories}
                modelsLoading={modelsLoading}
              />
            )}

            {activeTab === 'prompt' && (
              <PromptTab
                systemPrompt={systemPrompt}
                setSystemPrompt={setSystemPrompt}
              />
            )}

            {activeTab === 'tools' && (
              <ToolsTab
                tools={tools}
                enabledTools={enabledTools}
                toggleTool={toggleTool}
              />
            )}

            {activeTab === 'knowledge' && (
              <KnowledgeTab
                knowledgeBases={knowledgeBases}
                selectedKbIds={selectedKbIds}
                toggleKnowledgeBase={toggleKnowledgeBase}
              />
            )}

            {activeTab === 'bots' && (
              <BotsTab agentId={isNew ? null : Number(id)} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Basic Info Tab
function BasicInfoTab({
  name,
  setName,
  description,
  setDescription,
  model,
  setModel,
  temperature,
  setTemperature,
  maxTokens,
  setMaxTokens,
  modelCategories,
  modelsLoading,
}: {
  name: string;
  setName: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
  temperature: number;
  setTemperature: (v: number) => void;
  maxTokens: number;
  setMaxTokens: (v: number) => void;
  modelCategories: import('../types').ModelCategoryGroup[];
  modelsLoading: boolean;
}) {
  // 展开/折叠状态（默认展开推荐和轻量快速）
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    recommended: true,
    lightweight: true,
  });

  const toggleCategory = (catId: string) => {
    setExpandedCategories(prev => ({
      ...prev,
      [catId]: !prev[catId],
    }));
  };

  // 找到当前选中模型所属分类并确保展开
  useEffect(() => {
    for (const cat of modelCategories) {
      if (cat.models.some(m => m.id === model)) {
        if (!expandedCategories[cat.id]) {
          setExpandedCategories(prev => ({ ...prev, [cat.id]: true }));
        }
        break;
      }
    }
  }, [model, modelCategories]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-4">基本信息</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Agent 名称 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：智能客服助手"
              className="w-full px-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-dark-100"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              描述
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述这个 Agent 的用途..."
              rows={3}
              className="w-full px-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-dark-100 resize-none"
            />
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-4">模型配置</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              模型
            </label>

            {modelsLoading ? (
              <div className="flex items-center justify-center py-8 bg-dark-800 rounded-lg border border-dark-700">
                <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
                <span className="ml-2 text-dark-400">加载模型列表...</span>
              </div>
            ) : (
              <div className="space-y-3">
                {modelCategories.map((category) => {
                  const CategoryIcon = CATEGORY_ICONS[category.id] || Sparkles;
                  const isExpanded = expandedCategories[category.id] ?? false;
                  const hasSelectedModel = category.models.some(m => m.id === model);

                  return (
                    <div
                      key={category.id}
                      className={clsx(
                        'rounded-lg border overflow-hidden',
                        hasSelectedModel ? 'border-primary-500/50' : 'border-dark-700'
                      )}
                    >
                      {/* Category Header */}
                      <button
                        type="button"
                        onClick={() => toggleCategory(category.id)}
                        className={clsx(
                          'w-full flex items-center justify-between p-3 text-left transition-colors',
                          hasSelectedModel ? 'bg-primary-500/5' : 'bg-dark-850 hover:bg-dark-800'
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <CategoryIcon className={clsx(
                            'w-4 h-4',
                            hasSelectedModel ? 'text-primary-400' : 'text-dark-400'
                          )} />
                          <span className={clsx(
                            'font-medium text-sm',
                            hasSelectedModel ? 'text-primary-300' : 'text-dark-200'
                          )}>
                            {category.name}
                          </span>
                          <span className="text-xs text-dark-500">
                            ({category.models.length})
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {hasSelectedModel && (
                            <span className="text-xs text-primary-400">已选择</span>
                          )}
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-dark-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-dark-400" />
                          )}
                        </div>
                      </button>

                      {/* Models List */}
                      {isExpanded && (
                        <div className="p-2 space-y-1 bg-dark-900 max-h-64 overflow-y-auto">
                          {category.models.map((m) => (
                            <label
                              key={m.id}
                              className={clsx(
                                'flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-all',
                                model === m.id
                                  ? 'bg-primary-500/15 border border-primary-500/50'
                                  : 'bg-dark-800/50 border border-transparent hover:bg-dark-800 hover:border-dark-600'
                              )}
                            >
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                <input
                                  type="radio"
                                  name="model"
                                  value={m.id}
                                  checked={model === m.id}
                                  onChange={(e) => setModel(e.target.value)}
                                  className="sr-only"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <p className={clsx(
                                      'font-medium text-sm truncate',
                                      model === m.id ? 'text-primary-200' : 'text-dark-100'
                                    )}>
                                      {m.name}
                                    </p>
                                    {m.preview && (
                                      <span className="px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-400 rounded">
                                        预览
                                      </span>
                                    )}
                                    {m.supportsVision && (
                                      <span title="支持视觉">
                                        <Eye className="w-3 h-3 text-blue-400" />
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-xs text-dark-500 truncate">
                                    {m.vendor}{m.description ? ` · ${m.description}` : ''}
                                  </p>
                                </div>
                              </div>
                              {model === m.id && (
                                <div className="w-2 h-2 bg-primary-400 rounded-full flex-shrink-0 ml-2" />
                              )}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              温度 (Temperature): {temperature}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className="w-full accent-primary-500"
            />
            <div className="flex justify-between text-xs text-dark-500 mt-1">
              <span>更确定</span>
              <span>更随机</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              最大 Token 数
            </label>
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(Number(e.target.value))}
              min={100}
              max={128000}
              className="w-full px-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-dark-100"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// Prompt Tab
function PromptTab({ systemPrompt, setSystemPrompt }: any) {
  const presets = [
    {
      name: '通用助手',
      prompt:
        '你是一个有帮助的AI助手。请用中文回答用户的问题，保持专业、友好的态度。',
    },
    {
      name: '代码专家',
      prompt:
        '你是一个专业的编程助手。擅长多种编程语言，能够帮助用户编写、调试和优化代码。请提供清晰的代码示例和解释。',
    },
    {
      name: '文案写手',
      prompt:
        '你是一个专业的文案撰写专家。擅长各类文案创作，包括营销文案、社交媒体内容、产品描述等。请根据用户需求提供创意且引人入胜的内容。',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-2">系统提示词</h2>
        <p className="text-sm text-dark-400 mb-4">
          系统提示词定义了 Agent 的角色、能力和行为方式
        </p>

        <div className="mb-4">
          <label className="block text-sm font-medium text-dark-300 mb-2">
            快速模板
          </label>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.name}
                onClick={() => setSystemPrompt(preset.prompt)}
                className="px-3 py-1.5 text-sm bg-dark-800 hover:bg-dark-700 border border-dark-700 rounded-lg text-dark-300 transition-colors"
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        <textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="输入系统提示词..."
          rows={12}
          className="w-full px-4 py-3 bg-dark-800 border border-dark-700 rounded-lg text-dark-100 resize-none font-mono text-sm"
        />

        <div className="mt-2 flex items-center gap-2 text-xs text-dark-500">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>好的提示词可以显著提升 Agent 的表现</span>
        </div>
      </div>
    </div>
  );
}

// Tools Tab
function ToolsTab({ tools, enabledTools, toggleTool }: any) {
  const builtinTools = tools.filter((t: any) => t.scope === 'BUILTIN');
  const customTools = tools.filter((t: any) => t.scope === 'TENANT');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-2">工具配置</h2>
        <p className="text-sm text-dark-400 mb-4">
          选择 Agent 可以使用的工具，工具让 Agent 能够执行实际操作
        </p>
      </div>

      {/* Built-in tools */}
      <div>
        <h3 className="text-sm font-medium text-dark-300 mb-3">内置工具</h3>
        <div className="space-y-2">
          {builtinTools.map((tool: any) => (
            <ToolItem
              key={tool.name}
              tool={tool}
              enabled={enabledTools.includes(tool.name)}
              onToggle={() => toggleTool(tool.name)}
            />
          ))}
        </div>
      </div>

      {/* Custom tools */}
      {customTools.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-dark-300 mb-3">自定义工具</h3>
          <div className="space-y-2">
            {customTools.map((tool: any) => (
              <ToolItem
                key={tool.name}
                tool={tool}
                enabled={enabledTools.includes(tool.name)}
                onToggle={() => toggleTool(tool.name)}
              />
            ))}
          </div>
        </div>
      )}

      {tools.length === 0 && (
        <div className="text-center py-8 text-dark-500">
          暂无可用工具
        </div>
      )}
    </div>
  );
}

function ToolItem({
  tool,
  enabled,
  onToggle,
}: {
  tool: any;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label
      className={clsx(
        'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all',
        enabled
          ? 'bg-primary-500/10 border-primary-500/50'
          : 'bg-dark-800/50 border-dark-700 hover:border-dark-600'
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={clsx(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            enabled ? 'bg-primary-500/20' : 'bg-dark-700'
          )}
        >
          <Wrench
            className={clsx(
              'w-5 h-5',
              enabled ? 'text-primary-400' : 'text-dark-400'
            )}
          />
        </div>
        <div>
          <p
            className={clsx(
              'font-medium',
              enabled ? 'text-primary-300' : 'text-dark-200'
            )}
          >
            {tool.name}
          </p>
          <p className="text-sm text-dark-500 line-clamp-1">
            {tool.description}
          </p>
        </div>
      </div>

      <input
        type="checkbox"
        checked={enabled}
        onChange={onToggle}
        className="w-5 h-5 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500 focus:ring-offset-0"
      />
    </label>
  );
}

// Knowledge Tab
function KnowledgeTab({
  knowledgeBases,
  selectedKbIds,
  toggleKnowledgeBase,
}: {
  knowledgeBases: any[];
  selectedKbIds: string[];
  toggleKnowledgeBase: (id: string) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-2">知识库配置</h2>
        <p className="text-sm text-dark-400 mb-4">
          选择要绑定到此 Agent 的知识库，Agent 将能够从中检索信息来回答问题
        </p>
      </div>

      {knowledgeBases.length === 0 ? (
        <div className="text-center py-12 bg-dark-800/30 border border-dark-700 rounded-xl">
          <Database className="w-12 h-12 text-dark-600 mx-auto mb-4" />
          <p className="text-dark-400">暂无知识库</p>
          <p className="text-sm text-dark-500 mt-1">请先在知识库页面创建知识库</p>
        </div>
      ) : (
        <div className="space-y-2">
          {knowledgeBases.map((kb: any) => (
            <label
              key={kb.id}
              className={clsx(
                'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all',
                selectedKbIds.includes(kb.id)
                  ? 'bg-primary-500/10 border-primary-500/50'
                  : 'bg-dark-800/50 border-dark-700 hover:border-dark-600'
              )}
            >
              <div className="flex items-center gap-3">
                <div
                  className={clsx(
                    'w-10 h-10 rounded-lg flex items-center justify-center',
                    selectedKbIds.includes(kb.id) ? 'bg-primary-500/20' : 'bg-dark-700'
                  )}
                >
                  <Database
                    className={clsx(
                      'w-5 h-5',
                      selectedKbIds.includes(kb.id) ? 'text-primary-400' : 'text-dark-400'
                    )}
                  />
                </div>
                <div>
                  <p
                    className={clsx(
                      'font-medium',
                      selectedKbIds.includes(kb.id) ? 'text-primary-300' : 'text-dark-200'
                    )}
                  >
                    {kb.name}
                  </p>
                  <p className="text-sm text-dark-500 line-clamp-1">
                    {kb.description || `${kb.doc_count || 0} 个文档`}
                  </p>
                </div>
              </div>

              <input
                type="checkbox"
                checked={selectedKbIds.includes(kb.id)}
                onChange={() => toggleKnowledgeBase(kb.id)}
                className="w-5 h-5 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500 focus:ring-offset-0"
              />
            </label>
          ))}
        </div>
      )}

      {selectedKbIds.length > 0 && (
        <div className="p-4 bg-primary-500/10 border border-primary-500/30 rounded-lg">
          <p className="text-sm text-primary-300">
            <span className="font-medium">已选择 {selectedKbIds.length} 个知识库</span>
            <br />
            <span className="text-primary-400/80">
              Agent 对话时将自动使用 knowledge_search 工具查询这些知识库
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

// Bots Tab - Bot 绑定配置
function BotsTab({ agentId }: { agentId: number | null }) {
  const { user, currentContext } = useAuthStore();
  const [bots, setBots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBotIds, setSelectedBotIds] = useState<number[]>([]);

  // 加载可用的 Bot 列表
  useEffect(() => {
    loadBots();
  }, []);

  async function loadBots() {
    setLoading(true);
    try {
      // 根据当前上下文获取 Bot 列表
      const ownerType = currentContext?.type === 'organization' ? 'ORGANIZATION' : 'PERSONAL';
      const ownerId = currentContext?.type === 'organization'
        ? currentContext.orgId
        : user?.id;

      const result = await botApi.list({
        ownerType,
        ownerId,
        status: 1,
      });

      setBots(result.records || []);
    } catch (error) {
      console.error('Failed to load bots:', error);
      toast.error('加载 Bot 列表失败');
    } finally {
      setLoading(false);
    }
  }

  function toggleBot(botId: number) {
    setSelectedBotIds(prev =>
      prev.includes(botId)
        ? prev.filter(id => id !== botId)
        : [...prev, botId]
    );
  }

  // 平台图标映射
  const platformLabels: Record<string, string> = {
    WEB: 'Web',
    QQ: 'QQ',
    QQ_GUILD: 'QQ 频道',
    QQ_GROUP: 'QQ 群聊',
    FEISHU: '飞书',
    WECHAT: '微信',
    TELEGRAM: 'Telegram',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
        <span className="ml-2 text-dark-400">加载 Bot 列表...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-dark-100 mb-2">Bot 绑定</h2>
        <p className="text-sm text-dark-400 mb-4">
          选择要绑定到此 Agent 的 Bot。Bot 是 Agent 的接入点，可以让 Agent 通过不同平台与用户交互。
        </p>
      </div>

      {bots.length === 0 ? (
        <div className="text-center py-12 bg-dark-800/30 border border-dark-700 rounded-xl">
          <Bot className="w-12 h-12 text-dark-600 mx-auto mb-4" />
          <p className="text-dark-400">暂无可用的 Bot</p>
          <p className="text-sm text-dark-500 mt-1">
            请先在「我的 Bot」页面创建 Bot
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {bots.map((bot) => (
            <label
              key={bot.id}
              className={clsx(
                'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all',
                selectedBotIds.includes(bot.id)
                  ? 'bg-primary-500/10 border-primary-500/50'
                  : 'bg-dark-800/50 border-dark-700 hover:border-dark-600'
              )}
            >
              <div className="flex items-center gap-3">
                <div
                  className={clsx(
                    'w-10 h-10 rounded-lg flex items-center justify-center',
                    selectedBotIds.includes(bot.id) ? 'bg-primary-500/20' : 'bg-dark-700'
                  )}
                >
                  <Bot
                    className={clsx(
                      'w-5 h-5',
                      selectedBotIds.includes(bot.id) ? 'text-primary-400' : 'text-dark-400'
                    )}
                  />
                </div>
                <div>
                  <p
                    className={clsx(
                      'font-medium',
                      selectedBotIds.includes(bot.id) ? 'text-primary-300' : 'text-dark-200'
                    )}
                  >
                    {bot.botName}
                  </p>
                  <p className="text-sm text-dark-500">
                    {platformLabels[bot.platform] || bot.platform} {bot.appId ? `· ${bot.appId}` : ''}
                  </p>
                </div>
              </div>

              <input
                type="checkbox"
                checked={selectedBotIds.includes(bot.id)}
                onChange={() => toggleBot(bot.id)}
                className="w-5 h-5 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500 focus:ring-offset-0"
              />
            </label>
          ))}
        </div>
      )}

      {selectedBotIds.length > 0 && (
        <div className="p-4 bg-primary-500/10 border border-primary-500/30 rounded-lg">
          <p className="text-sm text-primary-300">
            <span className="font-medium">已选择 {selectedBotIds.length} 个 Bot</span>
            <br />
            <span className="text-primary-400/80">
              这些 Bot 将作为此 Agent 的接入点。用户可以通过这些平台与 Agent 对话。
            </span>
          </p>
        </div>
      )}

      {bots.length > 0 && (
        <div className="p-4 bg-dark-800/50 border border-dark-700 rounded-lg">
          <p className="text-sm text-dark-400">
            <span className="font-medium text-dark-300">提示：</span>
            Bot 绑定配置需要保存后生效。绑定 Bot 后，用户可以在「我的 Bot」页面管理平台账号绑定。
          </p>
        </div>
      )}
    </div>
  );
}
