# 医药知识图谱本体说明

## 节点类型

| 标签 | 主键 | 主要属性 | 说明 |
|------|------|----------|------|
| Drug | id | generic_name, brand_name, atc, dosage_form, manufacturer | 药品 |
| Disease | id | name, icd, category, description | 疾病（category=分类 表示分类节点） |
| Plan | id | name, line, source, evidence_level, population, description | 治疗方案 |
| Condition | name | — | 禁忌/慎用条件 |
| AdverseEffect | name | — | 不良反应 |
| Alias | name | — | 药品别名 |
| AtcClass | code | name, level | ATC 分类 |

## 关系类型

| 关系 | 方向 | 属性 | 说明 |
|------|------|------|------|
| TREATS | Drug → Disease | source, line, relation_type | 药品治疗疾病 |
| HAS_DOSAGE_FOR | Drug → Disease | dose, frequency, route, notes | 用法用量 |
| INTERACTS_WITH | Drug ↔ Drug | severity, description, recommendation | 药物相互作用 |
| CONTRAINDICATED_FOR | Drug → Condition | condition_type, severity, description | 禁忌/慎用 |
| CAUSES | Drug → AdverseEffect | frequency, severity | 不良反应 |
| HAS_ALIAS | Drug → Alias | — | 别名 |
| BELONGS_TO_ATC | Drug → AtcClass | — | ATC 归属 |
| TARGETS | Plan → Disease | — | 方案目标疾病 |
| INCLUDES | Plan → Drug | — | 方案包含药品 |
| SUBCLASS_OF | Disease/AtcClass → 父节点 | — | 层级关系 |

## 严重程度枚举

- **interactions.severity**: major / moderate / minor
- **contraindications.severity**: major / moderate
- **adverse_effects.severity**: major / moderate / mild
- **adverse_effects.frequency**: common / uncommon / rare

## 方案排序规则

推荐 API 按以下优先级排序：
1. 治疗线别（first → second）
2. 证据等级（A → B → 其他）
3. 方案名称

## 数据来源

当前数据基于中国临床指南共识手工整理，包括：
- 中国高血压防治指南
- 中国2型糖尿病防治指南
- 中国血脂异常防治指南
- 冠心病二级预防指南
- 胃食管反流病诊疗共识

## 扩展建议

- 接入 RxNorm / SNOMED CT 标准编码
- 增加 Symptom、PatientPopulation 节点
- 引入 LLM + GraphRAG 增强问答能力
