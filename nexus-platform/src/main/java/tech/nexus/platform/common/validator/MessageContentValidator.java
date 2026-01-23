package tech.nexus.platform.common.validator;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import tech.nexus.platform.common.validator.ValidMessageContent;

/**
 * 消息内容验证器
 */
public class MessageContentValidator implements ConstraintValidator<ValidMessageContent, String> {

    private int maxLength;

    @Override
    public void initialize(ValidMessageContent constraintAnnotation) {
        this.maxLength = constraintAnnotation.maxLength();
    }

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true; // 使用 @NotNull 单独验证
        }
        
        // 长度检查
        if (value.length() > maxLength) {
            return false;
        }
        
        // 空白字符检查
        if (value.trim().isEmpty()) {
            return false;
        }
        
        return true;
    }
}
