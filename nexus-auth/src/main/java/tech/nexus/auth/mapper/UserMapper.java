package tech.nexus.auth.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Param;
import tech.nexus.auth.entity.User;

/**
 * 用户 Mapper。
 * 通用 CRUD 由 MyBatis-Plus 的 BaseMapper 提供。
 * 自定义查询在 UserMapper.xml 中定义。
 *
 * <p>V5 重构：移除 tenantId 相关查询，改为全局用户名/邮箱查询。
 */
public interface UserMapper extends BaseMapper<User> {

    /**
     * 按用户名精确查询（全局唯一）
     */
    User findByUsername(@Param("username") String username);

    /**
     * 按邮箱精确查询
     */
    User findByEmail(@Param("email") String email);

    /**
     * 按用户名或邮箱查询（用于登录）
     */
    User findByUsernameOrEmail(@Param("usernameOrEmail") String usernameOrEmail);
}
