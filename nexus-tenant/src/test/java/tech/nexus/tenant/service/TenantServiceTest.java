package tech.nexus.tenant.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import tech.nexus.common.exception.BizException;
import tech.nexus.tenant.dto.*;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("TenantService 单元测试")
class TenantServiceTest {

    @Autowired
    private TenantService tenantService;

    @Test
    @DisplayName("创建租户 - 基本字段正确")
    void createTenant_success() {
        CreateTenantRequest req = new CreateTenantRequest();
        req.setName("TestCorp");
        req.setPlan("FREE");

        TenantVO vo = tenantService.createTenant(req);

        assertThat(vo).isNotNull();
        assertThat(vo.getId()).isNotNull();
        assertThat(vo.getName()).isEqualTo("TestCorp");
        assertThat(vo.getPlan()).isEqualTo("FREE");
    }

    @Test
    @DisplayName("查询不存在的租户 - 抛出 BizException")
    void getTenant_notFound() {
        assertThatThrownBy(() -> tenantService.getTenant(999999L))
            .isInstanceOf(BizException.class);
    }

    @Test
    @DisplayName("更新租户 - 名称和套餐可修改")
    void updateTenant_success() {
        CreateTenantRequest create = new CreateTenantRequest();
        create.setName("OldName");
        TenantVO created = tenantService.createTenant(create);

        UpdateTenantRequest update = new UpdateTenantRequest();
        update.setName("NewName");
        update.setPlan("PRO");
        TenantVO updated = tenantService.updateTenant(created.getId(), update);

        assertThat(updated.getName()).isEqualTo("NewName");
        assertThat(updated.getPlan()).isEqualTo("PRO");
    }

    @Test
    @DisplayName("添加成员 - 成功")
    void addMember_success() {
        CreateTenantRequest create = new CreateTenantRequest();
        create.setName("MemberTestCorp");
        TenantVO tenant = tenantService.createTenant(create);

        AddMemberRequest req = new AddMemberRequest();
        req.setUserId(100L);
        req.setRole("MEMBER");
        MemberVO member = tenantService.addMember(tenant.getId(), req);

        assertThat(member).isNotNull();
        assertThat(member.getUserId()).isEqualTo(100L);
        assertThat(member.getRole()).isEqualTo("MEMBER");
    }

    @Test
    @DisplayName("重复添加同一成员 - 幂等更新（不抛异常）")
    void addMember_idempotent() {
        CreateTenantRequest create = new CreateTenantRequest();
        create.setName("DupTestCorp");
        TenantVO tenant = tenantService.createTenant(create);

        AddMemberRequest req = new AddMemberRequest();
        req.setUserId(200L);
        req.setRole("MEMBER");
        tenantService.addMember(tenant.getId(), req);

        // 幂等：再次添加相同成员，更新role为ADMIN
        req.setRole("ADMIN");
        MemberVO updated = tenantService.addMember(tenant.getId(), req);
        assertThat(updated.getRole()).isEqualTo("ADMIN");
    }

    @Test
    @DisplayName("移除不存在的成员 - 抛出 BizException")
    void removeMember_notFound() {
        CreateTenantRequest create = new CreateTenantRequest();
        create.setName("RemoveTestCorp");
        TenantVO tenant = tenantService.createTenant(create);

        assertThatThrownBy(() -> tenantService.removeMember(tenant.getId(), 999L))
            .isInstanceOf(BizException.class);
    }

    @Test
    @DisplayName("成员列表 - 多租户隔离验证")
    void listMembers_tenantIsolation() {
        CreateTenantRequest create1 = new CreateTenantRequest();
        create1.setName("Tenant-A");
        TenantVO tenantA = tenantService.createTenant(create1);

        CreateTenantRequest create2 = new CreateTenantRequest();
        create2.setName("Tenant-B");
        TenantVO tenantB = tenantService.createTenant(create2);

        AddMemberRequest memberA = new AddMemberRequest();
        memberA.setUserId(301L);
        memberA.setRole("ADMIN");
        tenantService.addMember(tenantA.getId(), memberA);

        AddMemberRequest memberB = new AddMemberRequest();
        memberB.setUserId(302L);
        memberB.setRole("MEMBER");
        tenantService.addMember(tenantB.getId(), memberB);

        List<MemberVO> membersA = tenantService.listMembers(tenantA.getId());
        List<MemberVO> membersB = tenantService.listMembers(tenantB.getId());

        assertThat(membersA).hasSize(1);
        assertThat(membersA.get(0).getUserId()).isEqualTo(301L);
        assertThat(membersB).hasSize(1);
        assertThat(membersB.get(0).getUserId()).isEqualTo(302L);
    }
}
