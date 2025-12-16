package tech.nexus.agentconfig.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import tech.nexus.agentconfig.dto.AgentConfigRequest;
import tech.nexus.agentconfig.dto.AgentConfigVO;
import tech.nexus.agentconfig.entity.AgentConfigHistory;

import java.util.List;

/**
 * Agent 配置服务接口。
 */
public interface AgentConfigService {

    /** 创建 Agent（版本号初始为 1） */
    AgentConfigVO create(Long tenantId, AgentConfigRequest request);

    /** 分页查询 Agent 列表（仅当前租户） */
    Page<AgentConfigVO> list(Long tenantId, String name, int page, int size);

    /** 查询单个 Agent（必须属于当前租户） */
    AgentConfigVO getById(Long tenantId, Long id);

    /**
     * 更新 Agent：先写历史表，再更新主表，版本号 +1。
     * 顺序不可颠倒（Code Review 要求）。
     */
    AgentConfigVO update(Long tenantId, Long id, AgentConfigRequest request);

    /** 删除 Agent，同时失效缓存 */
    void delete(Long tenantId, Long id);

    /** 查询版本历史列表 */
    List<AgentConfigHistory> listHistory(Long tenantId, Long agentId);

    /** 回滚到指定版本（版本号继续 +1，不覆盖历史） */
    AgentConfigVO rollback(Long tenantId, Long agentId, int targetVersion);

    /** 获取平台公共模板列表 */
    List<AgentConfigVO> listTemplates();

    /** 从模板 fork 一个私有副本 */
    AgentConfigVO forkTemplate(Long tenantId, Long templateId);
}
