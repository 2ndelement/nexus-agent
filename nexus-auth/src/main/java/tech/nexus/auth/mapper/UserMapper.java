package tech.nexus.auth.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import tech.nexus.auth.entity.User;

/**
 * 用户 Mapper。
 * 通用 CRUD 由 MyBatis-Plus 的 BaseMapper 提供。
 * 自定义查询在 UserMapper.xml 中定义。
 */
public interface UserMapper extends BaseMapper<User> {

    /**
     * 按租户 ID + 用户名精确查询。
     */
    User findByTenantIdAndUsername(@Param("tenantId") Long tenantId,
                                   @Param("username") String username);
}
