package tech.nexus.common.entity;

import jakarta.persistence.Column;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.MappedSuperclass;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 通用实体基类。
 *
 * <p>所有业务实体继承本类，获得 id、tenantId、createTime、updateTime 四个公共字段。
 */
@MappedSuperclass
@Getter
@Setter
@ToString
public abstract class BaseEntity implements Serializable {

    private static final long serialVersionUID = 1L;

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 租户 ID，多租户隔离核心字段，不允许为空 */
    @Column(nullable = false)
    private String tenantId;

    /** 创建时间 */
    @Column(updatable = false)
    private LocalDateTime createTime;

    /** 最后更新时间 */
    private LocalDateTime updateTime;
}
