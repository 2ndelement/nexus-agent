-- 预置内置工具
INSERT INTO `tool_registry` (`name`, `display_name`, `description`, `is_builtin`) VALUES
  ('web_search',           '网页搜索',   '实时互联网搜索',           1),
  ('calculator',           '数学计算',   '四则运算及科学计算',        1),
  ('knowledge_retrieval',  '知识库检索', '检索 Agent 绑定的知识库',   1),
  ('code_interpreter',     '代码执行',   '执行 Python 代码（规划中）', 1);
