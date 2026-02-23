import React from 'react';
import { Settings, User, Building2, Bell, Shield, Database, UserCircle } from 'lucide-react';
import { useAuthStore } from '../stores';

export default function SettingsPage() {
  const { user, currentContext, organizations } = useAuthStore();

  // 获取当前组织信息（如果在组织空间）
  const currentOrg = currentContext?.type === 'organization'
    ? organizations.find(org => org.code === currentContext.orgCode)
    : null;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-100">设置</h1>
        <p className="text-dark-400 mt-1">管理您的账户和系统设置</p>
      </div>

      <div className="space-y-6">
        {/* Current Context Section */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <UserCircle className="w-5 h-5 text-primary-400" />
            当前空间
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">空间类型</label>
              <p className="text-dark-100">
                {currentContext?.type === 'personal' ? '个人空间' : '组织空间'}
              </p>
            </div>
            {currentContext?.type === 'organization' && currentOrg && (
              <>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">组织名称</label>
                  <p className="text-dark-100">{currentOrg.name}</p>
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">组织代码</label>
                  <p className="text-dark-100">{currentOrg.code}</p>
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">我的角色</label>
                  <p className="text-dark-100">
                    {currentOrg.role === 'OWNER' ? '所有者' : currentOrg.role === 'ADMIN' ? '管理员' : '成员'}
                  </p>
                </div>
              </>
            )}
          </div>
        </section>

        {/* Profile Section */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <User className="w-5 h-5 text-primary-400" />
            个人信息
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">用户名</label>
              <p className="text-dark-100">{user?.username || '-'}</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">昵称</label>
              <p className="text-dark-100">{user?.nickname || '-'}</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">邮箱</label>
              <p className="text-dark-100">{user?.email || '未设置'}</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">用户 ID</label>
              <p className="text-dark-100">{user?.id || '-'}</p>
            </div>
          </div>
        </section>

        {/* Organizations Section */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <Building2 className="w-5 h-5 text-primary-400" />
            我的组织
          </h2>
          {organizations.length === 0 ? (
            <p className="text-dark-400">暂未加入任何组织</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {organizations.map((org) => (
                <div
                  key={org.id}
                  className="flex items-center justify-between p-3 bg-dark-900/50 rounded-lg"
                >
                  <div>
                    <p className="text-dark-200 font-medium">{org.name}</p>
                    <p className="text-xs text-dark-500">{org.code}</p>
                  </div>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    org.role === 'OWNER' ? 'bg-primary-500/20 text-primary-400' :
                    org.role === 'ADMIN' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-dark-600 text-dark-400'
                  }`}>
                    {org.role === 'OWNER' ? '所有者' : org.role === 'ADMIN' ? '管理员' : '成员'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Quota Section */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <Bell className="w-5 h-5 text-primary-400" />
            配额信息
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">个人 Agent 数量限制</label>
              <p className="text-dark-100">{user?.personalAgentLimit || 1}</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">可创建组织数量</label>
              <p className="text-dark-100">{user?.orgCreateLimit || 3}</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">可加入组织数量</label>
              <p className="text-dark-100">{user?.orgJoinLimit || 10}</p>
            </div>
          </div>
        </section>

        {/* System Info */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-primary-400" />
            系统信息
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">版本</label>
              <p className="text-dark-100">NexusAgent v5.0.0</p>
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">API 端点</label>
              <p className="text-dark-100 text-sm font-mono">
                /api
              </p>
            </div>
          </div>
        </section>

        {/* Service Status */}
        <section className="bg-dark-800/50 border border-dark-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-dark-100 flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-primary-400" />
            服务状态
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { name: 'Agent Engine', port: 8011 },
              { name: 'Auth Service', port: 8002 },
              { name: 'RAG Service', port: 8013 },
              { name: 'Tool Registry', port: 8012 },
              { name: 'Memory Service', port: 8012 },
              { name: 'Sandbox Service', port: 8020 },
            ].map((service) => (
              <div
                key={service.name}
                className="flex items-center gap-2 p-3 bg-dark-900/50 rounded-lg"
              >
                <div className="w-2 h-2 bg-green-400 rounded-full" />
                <div>
                  <p className="text-sm text-dark-200">{service.name}</p>
                  <p className="text-xs text-dark-500">:{service.port}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
