package tech.nexus.agentconfig.service;

import tech.nexus.agentconfig.entity.ToolRegistry;

import java.util.List;

/**
 * 工具注册表服务接口。
 */
public interface ToolRegistryService {

    /** 列出所有工具 */
    List<ToolRegistry> listAll();

    /** 校验工具名列表中的所有工具是否已注册 */
    void validateToolNames(List<String> toolNames);
}
