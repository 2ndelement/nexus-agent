package tech.nexus.session.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.session.entity.BotBinding;
import tech.nexus.session.mapper.BotBindingMapper;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * BotBinding 服务
 *
 * 负责用户与 Bot 的绑定关系管理。
 * 核心功能是通过 puid（平台用户 ID）查找对应的 Nexus 用户。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class BotBindingService {

    private final BotBindingMapper botBindingMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 根据 Bot ID 和 puid 查找绑定
     *
     * @param botId Bot ID
     * @param puid 平台用户 ID
     * @return BotBinding 如果存在
     */
    public Optional<BotBinding> findByBotIdAndPuid(Long botId, String puid) {
        return botBindingMapper.findByBotIdAndPuid(botId, puid);
    }

    /**
     * 根据用户 ID 查找所有绑定
     */
    public List<BotBinding> findByUserId(Long userId) {
        return botBindingMapper.findByUserId(userId);
    }

    /**
     * 根据用户 ID 和 Bot ID 查找绑定
     */
    public Optional<BotBinding> findByUserIdAndBotId(Long userId, Long botId) {
        return botBindingMapper.findByUserIdAndBotId(userId, botId);
    }

    /**
     * 创建或更新绑定
     * 如果已存在则更新，不存在则创建
     */
    @Transactional
    public BotBinding createOrUpdateBinding(Long botId, Long userId, String puid, Map<String, Object> extraData) {
        Optional<BotBinding> existing = botBindingMapper.findByBotIdAndPuid(botId, puid);

        BotBinding binding;
        if (existing.isPresent()) {
            binding = existing.get();
            binding.setUserId(userId);
            binding.setExtraData(serializeExtraData(extraData));
            botBindingMapper.updateById(binding);
            log.info("[BotBinding] 更新绑定: botId={}, puid={}, userId={}", botId, puid, userId);
        } else {
            binding = new BotBinding();
            binding.setBotId(botId);
            binding.setUserId(userId);
            binding.setPuid(puid);
            binding.setExtraData(serializeExtraData(extraData));
            binding.setStatus(1);
            botBindingMapper.insert(binding);
            log.info("[BotBinding] 创建绑定: botId={}, puid={}, userId={}", botId, puid, userId);
        }
        return binding;
    }

    /**
     * 解绑
     */
    @Transactional
    public void unbind(Long bindingId) {
        BotBinding binding = new BotBinding();
        binding.setId(bindingId);
        binding.setStatus(0);
        botBindingMapper.updateById(binding);
        log.info("[BotBinding] 解绑: bindingId={}", bindingId);
    }

    /**
     * 解绑（通过 Bot ID 和 puid）
     */
    @Transactional
    public void unbindByBotIdAndPuid(Long botId, String puid) {
        botBindingMapper.findByBotIdAndPuid(botId, puid).ifPresent(binding -> {
            binding.setStatus(0);
            botBindingMapper.updateById(binding);
            log.info("[BotBinding] 解绑: botId={}, puid={}", botId, puid);
        });
    }

    private String serializeExtraData(Map<String, Object> extraData) {
        if (extraData == null || extraData.isEmpty()) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(extraData);
        } catch (JsonProcessingException e) {
            log.warn("[BotBinding] 序列化 extraData 失败", e);
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> deserializeExtraData(String json) {
        if (json == null || json.isEmpty()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(json, Map.class);
        } catch (JsonProcessingException e) {
            log.warn("[BotBinding] 反序列化 extraData 失败", e);
            return Map.of();
        }
    }
}
