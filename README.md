# 医药知识图谱

面向临床决策辅助的本地医药知识图谱产品，基于 Neo4j 图数据库，提供 Web 界面与 REST API。

> **免责声明**：本系统数据仅供学习研究与临床决策辅助参考，不能替代执业医师的专业判断。

## 功能特性

| 模块 | 说明 |
|------|------|
| 疾病推荐 | 按疾病名/ICD 查询治疗方案，含证据等级、适用人群、用法用量 |
| 药品详情 | 适应症、不良反应、禁忌、ATC 分类、别名检索 |
| 相互作用 | 多药联用冲突检测 + 同类 ATC 重复用药识别 |
| 合并症分析 | 多种疾病方案合并 + 自动交叉冲突检测 |
| 关联图谱 | vis-network 可视化疾病-方案-药品-不良反应关系 |
| 智能问答 | 规则引擎支持联用、推荐、适应症、禁忌类自然语言提问 |
| 质量评估 | `scripts/eval.py` 自动回归测试推荐与相互作用 |

## 快速开始

```powershell
cd C:\Users\admin\Desktop\AI_Knowledeg

# 1. 启动 Neo4j（Docker 或 Neo4j Desktop）
docker compose up -d
# 或启动 Neo4j Desktop 实例，确保 .env 中密码正确

# 2. 安装依赖
pip install -r requirements.txt

# 3. 清洗并全量导入数据
python scripts/clean.py
python scripts/import_neo4j.py --full

# 4. 启动 Web 服务
.\scripts\start_web.ps1
```

## 访问地址

- 前端界面: http://127.0.0.1:8000
- API 文档: http://127.0.0.1:8000/docs
- 健康检查: http://127.0.0.1:8000/health

## 本体模型

```
Drug  -[TREATS]->              Disease
Drug  -[HAS_DOSAGE_FOR]->      Disease
Drug  -[INTERACTS_WITH]-       Drug
Drug  -[CONTRAINDICATED_FOR]-> Condition
Drug  -[CAUSES]->              AdverseEffect
Drug  -[HAS_ALIAS]->           Alias
Drug  -[BELONGS_TO_ATC]->      AtcClass
Plan  -[TARGETS]->             Disease
Plan  -[INCLUDES]->            Drug
Disease -[SUBCLASS_OF]->       Disease
AtcClass -[SUBCLASS_OF]->      AtcClass
```

详见 [docs/ONTOLOGY.md](docs/ONTOLOGY.md)

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/recommend` | GET | 疾病治疗方案推荐 |
| `/drug` | GET | 药品详情查询 |
| `/interactions` | GET | 相互作用检测（逗号分隔药名） |
| `/interactions/check` | POST | 相互作用检测（JSON） |
| `/contraindications` | GET | 禁忌查询 |
| `/comorbidity` | POST | 合并症方案分析 |
| `/graph` | GET | 关联子图数据 |
| `/qa` | POST | 智能问答 |
| `/stats` | GET | 图谱统计 |

## 项目结构

```
AI_Knowledeg/
├── api/                # FastAPI 后端
├── web/                # 前端 HTML/CSS/JS
├── data/raw/           # 原始 CSV 数据
├── data/clean/         # 清洗后数据
├── scripts/            # 清洗、导入、评估、启动
├── cypher/             # Neo4j schema 与查询
├── tests/              # 单元测试与评估用例
└── docs/               # 文档
```

## 测试

```powershell
# 单元测试（无需 Neo4j）
pytest tests/ -v

# 端到端评估（需 API 运行且已导入数据）
python scripts/eval.py
```

## 数据维护

1. 编辑 `data/raw/*.csv`
2. 运行 `python scripts/clean.py`
3. 运行 `python scripts/import_neo4j.py --full`（全量重建）或不带 `--full`（增量 MERGE）

## 当前数据规模（示例）

- 15 种药品，10 种疾病（含 3 个分类节点）
- 9 套治疗方案，10 组药物相互作用
- 15 条禁忌记录，25 条不良反应，14 条用法用量
