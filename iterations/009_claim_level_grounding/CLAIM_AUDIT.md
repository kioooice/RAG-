# 008 声明级离线审计

## 审计方法

1. 读取008保存的60条结果，不调用API。
2. 以 `parsed_output.used_facts` 为起点，并补充最终 `answer` 中没有出现在 `used_facts` 的事实声明。
3. 将故障表行、字段表行和编号维护步骤拆成最小声明。
4. Evidence匹配同时检查引用KnowledgeUnit的正文、标题和标题路径；不只做整句字符串匹配。
5. 只允许用户指定的七类classification和四级severity。

拒答回答中的“资料中未提供……”被保留为 `non_factual_language` 追踪记录，不作为产品事实计入事实声明分母；本轮共有21条此类记录。

## 统计结果

| 指标 | 结果 |
|---|---:|
| 008回答数 | 60 |
| 最小声明总数 | 117 |
| 事实声明数 | 96 |
| 旧评测器标记Unsupported的回答 | 26/60（43.33%） |
| 对应的被审计声明数 | 63 |
| 其中Evaluator False Positive | 63/63（100%） |
| Answer-level Unsupported Rate | 0% |
| Claim-level Unsupported Rate | 0% |
| Material Unsupported Rate | 0% |
| Claim Citation Coverage | 100% |
| Cited Claim Support | 100% |
| Contradicted Claim | 0 |

## 为什么008会出现“引用支持高、无依据声明高”

008的Citation Support主要检查引用ID是否来自相关Context；旧Unsupported检查则要求 `used_facts` 整句或整段文字能逐字出现在Evidence中。模型把“代码—现象—处理”表行改写成完整句、把字段名转换成中文，或从编号步骤作必要顺序推导时，引用仍然正确，但整句不再逐字相同。因此两个指标测量的层次不同：前者是“引用指向是否正确”，后者混入了“文字是否逐字复制”的要求。

典型例子：`E07表示温度过高` 与表格中的 `E07 | 温度过高 | 停止设备并检查散热` 语义一致；`维护流程的下一步是重启并记录结果` 可由编号步骤直接推导。它们被008旧评测器标记，但没有新增产品事实。

## 决策

Evaluator False Positive在旧标记声明中超过20%（实际100%），满足停止API复测条件。009没有发送Formal请求，没有修改模型Prompt，也没有把Claim-Level协议宣称为已验证默认协议。
