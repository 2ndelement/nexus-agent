package tech.nexus.common.context;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("TenantContext 单元测试")
class TenantContextTest {

    @AfterEach
    void tearDown() {
        // 每个测试结束后确保主线程清理干净
        TenantContext.clear();
    }

    // ── 基本 set / get / clear ────────────────────────────────

    @Test
    @DisplayName("setTenantId 后 getTenantId 应返回相同值")
    void set_and_get_tenant_id() {
        TenantContext.setTenantId("tenant-001");
        assertThat(TenantContext.getTenantId()).isEqualTo("tenant-001");
    }

    @Test
    @DisplayName("clear() 后 getTenantId 应返回 null")
    void clear_returns_null() {
        TenantContext.setTenantId("tenant-to-clear");
        TenantContext.clear();
        assertThat(TenantContext.getTenantId()).isNull();
    }

    @Test
    @DisplayName("未设置时 getTenantId 应返回 null")
    void initial_value_is_null() {
        // 确保主线程没有残留
        TenantContext.clear();
        assertThat(TenantContext.getTenantId()).isNull();
    }

    // ── 多线程隔离 ────────────────────────────────────────────

    /**
     * 核心场景：两个线程分别设置不同 tenantId，
     * 各自读取到自己设置的值，互不污染。
     */
    @Test
    @DisplayName("多线程场景：两个线程的 tenantId 互不污染")
    void multi_thread_isolation() throws InterruptedException {
        CountDownLatch startLatch = new CountDownLatch(1);  // 同时启动两个线程
        CountDownLatch doneLatch = new CountDownLatch(2);   // 等待两个线程完成

        AtomicReference<String> thread1Value = new AtomicReference<>();
        AtomicReference<String> thread2Value = new AtomicReference<>();

        Thread t1 = new Thread(() -> {
            try {
                startLatch.await();
                TenantContext.setTenantId("tenant-A");
                // 模拟业务处理耗时，让两个线程有交叉
                Thread.sleep(50);
                thread1Value.set(TenantContext.getTenantId());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                TenantContext.clear();
                doneLatch.countDown();
            }
        }, "thread-1");

        Thread t2 = new Thread(() -> {
            try {
                startLatch.await();
                TenantContext.setTenantId("tenant-B");
                Thread.sleep(50);
                thread2Value.set(TenantContext.getTenantId());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                TenantContext.clear();
                doneLatch.countDown();
            }
        }, "thread-2");

        t1.start();
        t2.start();
        startLatch.countDown();   // 两个线程同时开始
        doneLatch.await();        // 等待两个线程完成

        assertThat(thread1Value.get())
                .as("线程1应读到 tenant-A")
                .isEqualTo("tenant-A");
        assertThat(thread2Value.get())
                .as("线程2应读到 tenant-B")
                .isEqualTo("tenant-B");
    }

    /**
     * 子线程中未设置 tenantId，主线程的值不应泄漏到子线程
     * （普通 ThreadLocal，非 InheritableThreadLocal）。
     */
    @Test
    @DisplayName("多线程场景：主线程 tenantId 不泄漏到子线程")
    void parent_tenant_id_not_inherited_by_child_thread() throws InterruptedException {
        TenantContext.setTenantId("parent-tenant");

        AtomicReference<String> childValue = new AtomicReference<>("NOT_SET");
        CountDownLatch latch = new CountDownLatch(1);

        Thread child = new Thread(() -> {
            childValue.set(TenantContext.getTenantId());
            latch.countDown();
        }, "child-thread");

        child.start();
        latch.await();

        // 普通 ThreadLocal 不继承父线程的值
        assertThat(childValue.get())
                .as("子线程不应继承主线程的 tenantId（使用普通 ThreadLocal）")
                .isNull();
    }

    /**
     * 确保 clear() 后，同一线程再次 set 也能正常工作（无状态残留）。
     */
    @Test
    @DisplayName("clear() 后同一线程可以重新 set")
    void clear_then_reset_works() {
        TenantContext.setTenantId("first");
        TenantContext.clear();
        assertThat(TenantContext.getTenantId()).isNull();

        TenantContext.setTenantId("second");
        assertThat(TenantContext.getTenantId()).isEqualTo("second");
    }
}
