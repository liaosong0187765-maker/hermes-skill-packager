---
name: skill-packager
description: "元技能：发现系统中的所有 skills，分析它们的关联，打包成可迁移的工作流包，并在其他 Hermes 实例上安装使用。像一个 Skill 工厂，把散落的工具组装成标准化流水线。"
version: 1.1.1
author: OPC Team
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [skill-management, workflow-packaging, migration, meta-skill, agent-orchestration]
    related_skills: [hermes-multi-instance, profile-skill-migration]
---

# Skill Packager — 工作流打包与迁移工厂

当你想要：
- 发现系统里有哪些 skills，它们能组成什么工作流
- 把一组 skills 打包成一个可迁移的工作流包
- 把这个工作流包安装到另一台机器的 Hermes 上
- 管理不同 Agent（CEO/Marketing/Video）的技能清单

就用这个 skill。

## 核心能力

| 命令 | 功能 |
|------|------|
| `discover` | 扫描所有 skills（主目录 + 各 profile），生成全景清单 |
| `analyze` | 分析 skills 之间的关联，推荐可组合的工作流 |
| `verify` | **前置核验**：检查 skill 存在性、SKILL.md 有效性、安全扫描 |
| `pack` | 选择 skills 组合，打包成可迁移的工作流包（自动先 verify） |
| `migrate` | 在目标 Hermes 实例上安装工作流包 |
| `diff` | 对比两个 Hermes 实例的 skills 差异 |

## 打包出来的工作流包结构

```
my-workflow-package/           ← 一个独立 skill
├── SKILL.md                   ← 工作流定义（触发词、步骤、依赖清单）
├── scripts/
│   ├── run.py                 ← 一键执行工作流
│   ├── check_deps.py          ← 检查依赖 skills 是否已安装
│   └── install_deps.py        ← 自动安装缺失的依赖 skills
├── references/
│   └── skill-guides/          ← 依赖 skills 的关键用法速查
└── requirements.txt           ← Python 依赖
```

## 跨 Hermes 迁移方式

**方式一：GitHub 仓库（推荐）**
```bash
# 源机器：打包并 push
cd ~/.hermes/skills/my-workflow-package
git init && git add . && git commit -m "v1.0"
git push origin main

# 目标机器：安装
hermes skills install https://github.com/user/my-workflow-package.git
```

**方式二：本地 tar 包**
```bash
# 源机器
cd ~/.hermes/skills && tar czf my-workflow-package.tar.gz my-workflow-package

# 目标机器
cd ~/.hermes/skills && tar xzf my-workflow-package.tar.gz
```

**方式三：飞书文档附件（内网环境）**
```bash
# 源机器：打包上传到飞书云盘
# 目标机器：从飞书下载解压到 ~/.hermes/skills/
```

## 使用流程

### 1. 发现现有 Skills
```bash
python3 scripts/discover.py --output /tmp/skills_inventory.json
```
输出包含：
- 每个 skill 的名称、描述、tags、所在位置（主目录 / profile）
- 各 profile 独有的 skills
- 各 profile 之间重复的 skills

### 2. 分析可组合的工作流
```bash
python3 scripts/analyze.py --inventory /tmp/skills_inventory.json --output /tmp/workflow_suggestions.md
```
基于 skills 的 tags 和描述，分析出可能的工作流组合：
- "热点追踪 → 公众号文章"（需要 blogwatcher + wechat-article-writer + ...）
- "竞品监控 → 反击内容"（需要 competitive-ads-extractor + content-marketer + ...）
- "英文教程 → 中文短视频"（需要 article-translator + video-outline-generation + ...）

### 3. 前置核验（打包前体检）

**packager.py 默认会自动核验**，但也可以单独运行：

```bash
python3 scripts/verify.py \
  --skills "blogwatcher,wechat-article-writer,wechat-title-generator,article-to-wechat-cover,feishu-doc-to-wechat-draft" \
  --markdown /tmp/verify_report.md
```

核验项：
| 检查项 | 严重级别 | 说明 |
|--------|---------|------|
| Skill 存在性 | ❌ 错误 | skill 是否在系统中 |
| SKILL.md 有效性 | ❌ 错误 | 是否有 name 字段 |
| 缺少 version/description | ⚠️ 警告 | 不影响打包，但建议补全 |
| 无 scripts/ 目录 | ⚠️ 警告 | 纯文档型 skill 正常 |
| 缺失 Python 包 | ⚠️ 警告 | 运行时依赖，不影响打包 |
| 同名 skill 多副本 | ⚠️ 警告 | 提示重复，不阻塞 |
| 硬编码密钥扫描 | ❌ 错误 | 发现 API key/token |

**核验结果决定打包行为：**
- ✅ 无错误 → 自动继续打包
- ❌ 有错误 → **终止打包**（可用 `--skip-verify` 强制跳过，不推荐）
- ⚠️ 有警告无错误 → 提示警告，但继续打包（加 `--verify-strict` 可让警告也阻塞）

### 4. 打包工作流

```bash
python3 scripts/packager.py \
  --name "hotspot-to-wechat" \
  --skills "blogwatcher,wechat-article-writer,wechat-title-generator,article-to-wechat-cover,feishu-doc-to-wechat-draft" \
  --description "热点追踪到公众号爆款文章的完整流水线" \
  --output ~/.hermes/skills/hotspot-to-wechat-workflow
```

打包时会自动先 `verify`，核验通过才会生成工作流包。

跳过核验（不推荐）：
```bash
python3 scripts/packager.py ... --skip-verify
```

严格模式（警告也视为失败）：
```bash
python3 scripts/packager.py ... --verify-strict
```

### 5. 迁移到目标机器
```bash
python3 scripts/migrate.py \
  --package ~/.hermes/skills/hotspot-to-wechat-workflow \
  --target-host user@new-server \
  --target-path ~/.hermes/skills/
```

## 与现有方案对比

| 方案 | 粒度 | 可迁移性 | 维护成本 | 适用场景 |
|------|------|---------|---------|---------|
| 复制整个 skills 目录 | 全量 | 差（大量无用 skills） | 高 | 备份 |
| 软链接共享池 | 文件级 | 仅限同一机器 | 中 | 单机多 Agent |
| **Skill Packager** | **工作流级** | **✅ 任意 Hermes** | **低** | **标准化流水线** |

## 关键设计原则

1. **工作流是技能**：打包出来的不是配置文件，而是一个独立的 skill，能被 Hermes 自动发现
2. **自描述依赖**：SKILL.md 里明确列出依赖的 skills，安装时自动检查
3. **渐进式安装**：目标机器可以只装工作流包，缺失的依赖 skills 按需补装
4. **版本兼容**：工作流包声明兼容的 Hermes 版本和 skill 版本

## Pitfalls & Lessons Learned

### Pitfall 1: Python 模板生成 Python 代码时不能用 `.format()`
**问题**：`packager.py` 需要生成一个 `run.py` 文件，模板内含有 Python f-string 语法（如 `{'='*60}`）。直接用 `.format()` 会被 Python 当成格式字符串解析，导致 `KeyError`。

**解决**：使用独特的占位符（如 `__WORKFLOW_NAME__`）+ `.replace()` 而非 `.format()`。

```python
# ❌ 错误
template.format(name=skill_name)  # KeyError: "'='*60"

# ✅ 正确
run_py = (
    RUN_PY_TEMPLATE
    .replace("__WORKFLOW_NAME__", args.name)
    .replace("__WORKFLOW_DESCRIPTION__", args.description)
    .replace("__STEPS_JSON__", steps_json)
)
```

### Pitfall 2: `check_dependencies()` 返回值不一致
**问题**：`check_deps.py` 中的 `check_dependencies()` 返回 3 个值 `(ok, missing, found)`，但 `run.py` 模板最初只解包 2 个，导致 `ValueError: too many values to unpack`。

**解决**：模板中必须写 `deps_ok, missing, _found = check_dependencies()`。

### Pitfall 3: lark-cli 的 markdown 文件路径限制
**问题**：`lark-cli docs +create --markdown @/tmp/report.md` 报错 "--file must be a relative path within the current directory"。

**解决**：必须 `cd` 到文件所在目录，使用相对路径 `./report.md`。

### Pitfall 4: verify.py 的返回值结构必须和 packager.py 解包一致
**问题**：`verify.py` 的 `check_dependencies()` 最初返回 3 个值 `(ok, missing, found)`，但 `packager.py` 里的 `run.py` 模板只解包 2 个，导致运行时 `ValueError`。

**解决**：模板代码中必须匹配 verify.py 的返回值数量。如果 verify.py 改了返回结构，模板必须同步更新。

### Pitfall 5: GitHub PAT 推送的安全做法
**问题**：`git push` 需要认证，但当前环境没有全局配置 GitHub 凭证。

**解决**：临时将 PAT 写入 remote URL 完成 push，成功后立即恢复为干净 URL：
```bash
# 临时写入 PAT
git remote set-url origin https://用户名:TOKEN@github.com/用户/仓库.git
git push -u origin main
# 成功后立即恢复（token 不会留在本地配置）
git remote set-url origin https://github.com/用户/仓库.git
```

### Pitfall 6: 软链接 vs 物理拷贝的权衡
当前系统可能有大量重复 skills（同一 skill 出现在 main + 多个 profile）。物理拷贝占用空间但 profile 隔离性好；软链接省空间但修改会全局影响。建议：
- 先用 `discover.py` 扫描出重复列表
- 对纯只读的 skills（无本地状态）转软链接
- 对有本地配置/状态的 skills 保留物理拷贝

## 当前局限

- 依赖 skills 的自动安装目前通过 git clone 实现，需要目标机器有网络
- 内网环境需手动下载依赖 skills 或使用飞书/云盘中转
- 工作流包的 `run.py` 目前用 Python 直接调用，未来可扩展为 Agent 原生编排
- analyze.py 目前是关键词匹配，未来可用 LLM 分析 SKILL.md 内容做更智能的工作流推荐
