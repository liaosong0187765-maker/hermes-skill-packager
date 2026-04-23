# Skill Packager — AI Agent 工作流打包与迁移工厂

> 一个元 Skill（Meta-Skill），把你的散落的 AI 工具组装成标准化流水线，一键迁移到任意 Hermes 实例。

## 它能做什么？（5 个核心能力）

| 能力 | 命令 | 一句话解释 |
|------|------|-----------|
| 🔍 **盘点家底** | `discover.py` | 扫描系统里所有 skills，生成全景清单 |
| 🔗 **智能推荐** | `analyze.py` | 分析 skills 之间的关联，推荐可组合的工作流 |
| 🏥 **打包前体检** | `verify.py` | 核验每个 skill 的质量、安全性、完整性 |
| 📦 **打包工作流** | `packager.py` | 把一组 skills 打包成可迁移的工作流包 |
| 🚚 **异地安装** | `migrate.py` | 导出 tar / push GitHub / 对比两实例差异 |

## 快速上手

### 1. 发现现有 Skills
```bash
python3 scripts/discover.py --output /tmp/skills_inventory.json
```
输出包含：
- 242 个唯一 skills 的全景清单
- 105 个重复 skills 的冗余报告
- 各 Agent（CEO/Marketing/Video）的技能分布

### 2. 分析可组合的工作流
```bash
python3 scripts/analyze.py --inventory /tmp/skills_inventory.json --output /tmp/workflows.md
```
自动推荐 6 种现成的工作流模式，例如：
- 热点追踪 → 公众号爆款文章
- 竞品监控 → 差异化内容反击
- 英文教程 → 中文短视频
- 小红书爆款笔记工厂
- 多平台社媒同步发布
- 知识沉淀 → 复利资产

### 3. 前置核验（打包前体检）
```bash
python3 scripts/verify.py \
  --skills "blogwatcher,wechat-article-writer,wechat-title-generator" \
  --markdown /tmp/verify_report.md
```

核验项分级：
| 检查项 | 级别 | 是否阻塞打包 |
|--------|------|------------|
| Skill 不存在 | ❌ 错误 | ✅ 阻塞 |
| SKILL.md 无效 | ❌ 错误 | ✅ 阻塞 |
| 硬编码 API key | ❌ 错误 | ✅ 阻塞 |
| 缺 version/description | ⚠️ 警告 | ❌ 不阻塞 |
| 无 scripts/ 目录 | ⚠️ 警告 | ❌ 不阻塞 |
| 缺失 Python 包 | ⚠️ 警告 | ❌ 不阻塞 |
| 同名 skill 多副本 | ⚠️ 警告 | ❌ 不阻塞 |

### 4. 打包工作流（自动先 verify）
```bash
python3 scripts/packager.py \
  --name "hotspot-to-wechat" \
  --skills "blogwatcher,wechat-article-writer,wechat-title-generator,article-to-wechat-cover,feishu-doc-to-wechat-draft" \
  --description "热点追踪到公众号爆款文章的完整流水线" \
  --output ~/.hermes/skills/hotspot-to-wechat-workflow
```

打包出来的工作流包结构：
```
hotspot-to-wechat-workflow/
├── SKILL.md                    # 工作流定义 + 依赖清单
├── scripts/
│   ├── run.py                  # 一键执行工作流
│   ├── check_deps.py           # 检查依赖 skills 是否已安装
│   └── install_deps.py         # 自动安装缺失的依赖 skills
└── references/                 # 依赖 skills 的关键用法速查
```

跳过核验（不推荐）：`--skip-verify`  
严格模式（警告也阻塞）：`--verify-strict`

### 5. 迁移到目标机器

**方式一：GitHub 仓库（推荐）**
```bash
python3 scripts/migrate.py \
  --package ~/.hermes/skills/hotspot-to-wechat-workflow \
  --format git \
  --remote https://github.com/yourname/hotspot-to-wechat-workflow.git
```

**方式二：本地 tar 包**
```bash
python3 scripts/migrate.py \
  --package ~/.hermes/skills/hotspot-to-wechat-workflow \
  --format tar \
  --output /tmp/hotspot-to-wechat.tar.gz
```

**方式三：对比两实例差异**
```bash
python3 scripts/migrate.py --diff --target-home ~/.hermes_backup
```

## 设计哲学

1. **工作流即 Skill**：打包出来的不是配置文件，而是一个独立的 skill，能被 Hermes 自动发现
2. **自描述依赖**：SKILL.md 里明确列出依赖的 skills，安装时自动检查
3. **渐进式安装**：目标机器可以只装工作流包，缺失的依赖 skills 按需补装
4. **安全优先**：打包前强制核验，拒绝传播损坏的或带硬编码密钥的 skills

## 目录结构

```
skill-packager/
├── SKILL.md                  # 元 Skill 定义
├── README.md                 # 本文件
├── requirements.txt          # 无外部依赖（仅标准库）
└── scripts/
    ├── discover.py           # 扫描所有 skills
    ├── analyze.py            # 分析关联、推荐工作流
    ├── verify.py             # 前置核验器
    ├── packager.py           # 打包工作流
    └── migrate.py            # 迁移/导出/对比
```

## 与现有方案对比

| 方案 | 粒度 | 可迁移性 | 维护成本 | 安全核验 |
|------|------|---------|---------|---------|
| 复制整个 skills 目录 | 全量 | 差 | 高 | ❌ 无 |
| 软链接共享池 | 文件级 | 仅限同一机器 | 中 | ❌ 无 |
| **Skill Packager** | **工作流级** | **✅ 任意 Hermes** | **低** | **✅ 强制体检** |

## 未来扩展方向

- **Agent 原生编排**：当前 `run.py` 是 Python 脚本调用，未来可扩展为 Agent 级任务委派
- **LLM 智能推荐**：`analyze.py` 目前是关键词匹配，未来可用 LLM 分析 SKILL.md 内容做更智能的推荐
- **软链接去重**：当前 105 个重复 skills 占空间，可用 `discover` 结果指导批量转软链接
- **飞书中转**：内网环境可用飞书云盘做 skills 包中转站

## License

MIT
