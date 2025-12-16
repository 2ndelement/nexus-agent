package tech.nexus.agentconfig.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import tech.nexus.agentconfig.entity.ToolRegistry;
import tech.nexus.agentconfig.mapper.ToolRegistryMapper;
import tech.nexus.agentconfig.service.ToolRegistryService;
import tech.nexus.common.exception.BizException;
import tech.nexus.common.result.ResultCode;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 工具注册表服务实现。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ToolRegistryServiceImpl implements ToolRegistryService {

    private final ToolRegistryMapper toolRegistryMapper;

    @Override
    public List<ToolRegistry> listAll() {
        return toolRegistryMapper.selectList(null);
    }

    @Override
    public void validateToolNames(List<String> toolNames) {
        if (toolNames == null || toolNames.isEmpty()) {
            return;
        }
        Set<String> registered = toolRegistryMapper
                .selectList(new LambdaQueryWrapper<ToolRegistry>().in(ToolRegistry::getName, toolNames))
                .stream()
                .map(ToolRegistry::getName)
                .collect(Collectors.toSet());

        List<String> unknown = toolNames.stream()
                .filter(t -> !registered.contains(t))
                .collect(Collectors.toList());

        if (!unknown.isEmpty()) {
            throw new BizException(ResultCode.PARAM_ERROR,
                    "以下工具未在注册表中：" + String.join(", ", unknown));
        }
    }
}
