import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, Home, Building2, Plus, Link as LinkIcon, Check, Settings } from 'lucide-react';
import { useAuthStore } from '../stores';

export default function ContextSwitcher() {
  const navigate = useNavigate();
  const { currentContext, organizations, switchContext, user } = useAuthStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 获取当前显示名称
  const currentOrg = currentContext?.type === 'organization'
    ? organizations.find(o => o.code === currentContext?.orgCode)
    : null;

  const currentLabel = currentContext?.type === 'personal'
    ? '个人空间'
    : currentOrg?.name || '未知组织';

  const currentIcon = currentContext?.type === 'personal'
    ? <Home className="w-4 h-4" />
    : <Building2 className="w-4 h-4" />;

  // 计算已创建的组织数量
  const ownedOrgCount = organizations.filter(o => o.role === 'OWNER').length;
  const canCreateOrg = user ? ownedOrgCount < user.orgCreateLimit : false;

  // 计算已加入的组织数量
  const joinedOrgCount = organizations.length;
  const canJoinOrg = user ? joinedOrgCount < user.orgJoinLimit : false;

  return (
    <div ref={ref} className="relative">
      {/* 触发按钮 */}
      <button
        onClick={() => setOpen(!open)}
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg
          bg-dark-800 hover:bg-dark-700
          border border-dark-700 hover:border-dark-600
          transition-all duration-200
          ${open ? 'ring-1 ring-primary-500/50 border-primary-500/50' : ''}
        `}
      >
        <span className="text-primary-400">
          {currentIcon}
        </span>
        <span className="text-sm font-medium text-dark-100 max-w-[140px] truncate">
          {currentLabel}
        </span>
        <ChevronDown className={`
          w-4 h-4 text-dark-400 transition-transform duration-200
          ${open ? 'rotate-180' : ''}
        `} />
      </button>

      {/* 下拉菜单 */}
      {open && (
        <div className="absolute top-full left-0 mt-2 w-72 bg-dark-800 border border-dark-700 rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {/* 个人空间 */}
          <div className="p-2">
            <button
              onClick={() => {
                switchContext({ type: 'personal' });
                setOpen(false);
              }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                hover:bg-dark-700 transition-colors
                ${currentContext?.type === 'personal' ? 'bg-primary-500/10 ring-1 ring-primary-500/30' : ''}
              `}
            >
              <div className="w-9 h-9 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
                <Home className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm font-medium text-dark-100">个人空间</p>
                <p className="text-xs text-dark-500">个人 Agent 和会话</p>
              </div>
              {currentContext?.type === 'personal' && (
                <Check className="w-4 h-4 text-primary-400" />
              )}
            </button>
          </div>

          {/* 分隔线 */}
          {organizations.length > 0 && (
            <>
              <div className="border-t border-dark-700" />
              <div className="px-3 py-2">
                <p className="text-xs font-medium text-dark-500 uppercase tracking-wider">
                  我的组织
                </p>
              </div>
            </>
          )}

          {/* 组织列表 */}
          <div className="p-2 pt-0 max-h-64 overflow-y-auto">
            {organizations.map(org => (
              <button
                key={org.id}
                onClick={() => {
                  switchContext({ type: 'organization', orgCode: org.code, orgId: org.id });
                  setOpen(false);
                }}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                  hover:bg-dark-700 transition-colors
                  ${currentContext?.type === 'organization' && currentContext.orgCode === org.code
                    ? 'bg-primary-500/10 ring-1 ring-primary-500/30'
                    : ''
                  }
                `}
              >
                <div className="w-9 h-9 bg-dark-600 rounded-lg flex items-center justify-center text-dark-300 overflow-hidden">
                  {org.avatar ? (
                    <img src={org.avatar} alt="" className="w-9 h-9 object-cover" />
                  ) : (
                    <Building2 className="w-4 h-4" />
                  )}
                </div>
                <div className="flex-1 text-left min-w-0">
                  <p className="text-sm font-medium text-dark-100 truncate">{org.name}</p>
                  <p className="text-xs text-dark-500">{getRoleLabel(org.role)}</p>
                </div>
                {currentContext?.type === 'organization' && currentContext.orgCode === org.code && (
                  <Check className="w-4 h-4 text-primary-400 flex-shrink-0" />
                )}
              </button>
            ))}
          </div>

          {/* 分隔线 */}
          <div className="border-t border-dark-700" />

          {/* 操作按钮 */}
          <div className="p-2">
            <button
              onClick={() => {
                setOpen(false);
                navigate('/org/new');
              }}
              disabled={!canCreateOrg}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                transition-colors text-dark-300
                ${canCreateOrg
                  ? 'hover:bg-dark-700 hover:text-dark-100'
                  : 'opacity-50 cursor-not-allowed'
                }
              `}
            >
              <div className="w-9 h-9 border border-dashed border-dark-600 rounded-lg flex items-center justify-center">
                <Plus className="w-4 h-4" />
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm">创建组织</p>
              </div>
              {!canCreateOrg && (
                <span className="text-xs text-dark-500">已达上限</span>
              )}
            </button>

            <button
              onClick={() => {
                setOpen(false);
                navigate('/join-org');
              }}
              disabled={!canJoinOrg}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                transition-colors text-dark-300
                ${canJoinOrg
                  ? 'hover:bg-dark-700 hover:text-dark-100'
                  : 'opacity-50 cursor-not-allowed'
                }
              `}
            >
              <div className="w-9 h-9 border border-dashed border-dark-600 rounded-lg flex items-center justify-center">
                <LinkIcon className="w-4 h-4" />
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm">加入组织</p>
              </div>
              {!canJoinOrg && (
                <span className="text-xs text-dark-500">已达上限</span>
              )}
            </button>
          </div>

          {/* 当前组织设置入口 */}
          {currentContext?.type === 'organization' && currentOrg && (
            <>
              <div className="border-t border-dark-700" />
              <div className="p-2">
                <button
                  onClick={() => {
                    setOpen(false);
                    navigate(`/org/${currentOrg.code}/settings`);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-dark-700 transition-colors text-dark-400 hover:text-dark-200"
                >
                  <Settings className="w-4 h-4" />
                  <span className="text-sm">组织设置</span>
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function getRoleLabel(role: string): string {
  switch (role) {
    case 'OWNER': return '所有者';
    case 'ADMIN': return '管理员';
    case 'MEMBER': return '成员';
    default: return role;
  }
}
