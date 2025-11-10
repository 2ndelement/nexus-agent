package tech.nexus.common.result;

import lombok.Getter;
import lombok.ToString;

import java.io.Serializable;
import java.util.List;

/**
 * 分页响应结构
 *
 * @param <T> 列表元素类型
 */
@Getter
@ToString
public class PageResult<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 当前页数据 */
    private final List<T> records;

    /** 总记录数 */
    private final long total;

    /** 当前页码（从 1 开始） */
    private final int page;

    /** 每页大小 */
    private final int size;

    /** 总页数 */
    private final int pages;

    private PageResult(List<T> records, long total, int page, int size) {
        this.records = records;
        this.total = total;
        this.page = page;
        this.size = size;
        this.pages = size <= 0 ? 0 : (int) Math.ceil((double) total / size);
    }

    public static <T> PageResult<T> of(List<T> records, long total, int page, int size) {
        return new PageResult<>(records, total, page, size);
    }
}
