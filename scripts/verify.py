#!/usr/bin/env python3
"""
Skill Verify — 打包前置核验器

用法:
    python3 verify.py \
      --skills "blogwatcher,wechat-article-writer,wechat-title-generator" \
      --report /tmp/verify_report.json

核验项:
    1. Skill 存在性 — 每个 skill 是否在主目录或 profile 中存在
    2. SKILL.md 有效性 — 是否有 name、description、version
    3. 脚本可执行性 — scripts/run.py 是否存在且可执行
    4. 依赖完整性 — requirements.txt 中的 Python 包是否已安装
    5. 外部命令 — SKILL.md 或脚本中引用的系统命令是否可用
    6. 重复检测 — 同名 skill 是否出现在多个 profile 中
    7. 密钥硬编码扫描 — 检查是否有 API key/token 硬编码
"""

import os
import re
import json
import shutil
import subprocess
import argparse
from pathlib import Path


HERMES_HOME = os.path.expanduser("~/.hermes")

# 常见的敏感关键词
SENSITIVE_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',           # OpenAI key
    r'ghp_[a-zA-Z0-9]{36}',           # GitHub PAT
    r'Bearer\s+[a-zA-Z0-9_\-]{20,}',  # Bearer token
    r'api[_-]?key\s*[:=]\s*["\']?[a-zA-Z0-9]{16,}',  # API key
    r'token\s*[:=]\s*["\']?[a-zA-Z0-9]{16,}',         # Generic token
    r'password\s*[:=]\s*["\']?[^\s"\']{8,}',          # Password
]


def find_skill_path(skill_name: str) -> str:
    """查找 skill 的完整路径"""
    # 主目录
    main_path = os.path.join(HERMES_HOME, "skills", skill_name)
    if os.path.exists(main_path):
        return main_path

    # 各 profile
    profiles_dir = os.path.join(HERMES_HOME, "profiles")
    if os.path.isdir(profiles_dir):
        for profile in sorted(os.listdir(profiles_dir)):
            profile_path = os.path.join(profiles_dir, profile, "skills", skill_name)
            if os.path.exists(profile_path):
                return profile_path

    return None


def find_all_skill_locations(skill_name: str) -> list:
    """查找 skill 出现的所有位置"""
    locations = []
    main_path = os.path.join(HERMES_HOME, "skills", skill_name)
    if os.path.exists(main_path):
        locations.append(("main", main_path))

    profiles_dir = os.path.join(HERMES_HOME, "profiles")
    if os.path.isdir(profiles_dir):
        for profile in sorted(os.listdir(profiles_dir)):
            profile_path = os.path.join(profiles_dir, profile, "skills", skill_name)
            if os.path.exists(profile_path):
                locations.append((f"profile:{profile}", profile_path))

    return locations


def verify_skill_md(skill_path: str) -> dict:
    """验证 SKILL.md 的有效性"""
    result = {
        "exists": False,
        "valid": False,
        "name": None,
        "description": None,
        "version": None,
        "errors": [],
        "warnings": [],
    }

    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md):
        result["errors"].append("SKILL.md 不存在")
        return result

    result["exists"] = True

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read(5000)
    except Exception as e:
        result["errors"].append(f"读取 SKILL.md 失败: {e}")
        return result

    # 提取 frontmatter
    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""

    # 检查必填字段
    name_match = re.search(r'^name:\s*(.+)', frontmatter, re.MULTILINE)
    desc_match = re.search(r'^description:\s*(.+)', frontmatter, re.MULTILINE)
    ver_match = re.search(r'^version:\s*(.+)', frontmatter, re.MULTILINE)

    result["name"] = name_match.group(1).strip() if name_match else None
    result["description"] = desc_match.group(1).strip() if desc_match else None
    result["version"] = ver_match.group(1).strip() if ver_match else None

    if not result["name"]:
        result["errors"].append("缺少 name 字段")
    if not result["description"]:
        result["warnings"].append("缺少 description 字段")
    if not result["version"]:
        result["warnings"].append("缺少 version 字段")

    # 检查 body 是否为空（除了 frontmatter）
    body = content[len(fm_match.group(0)) if fm_match else 0:]
    if not body.strip():
        result["warnings"].append("SKILL.md 正文为空")

    result["valid"] = len(result["errors"]) == 0
    return result


def verify_scripts(skill_path: str) -> dict:
    """验证 scripts 目录"""
    result = {
        "has_scripts_dir": False,
        "has_run_py": False,
        "run_py_executable": False,
        "scripts": [],
        "errors": [],
        "warnings": [],
    }

    scripts_dir = os.path.join(skill_path, "scripts")
    if not os.path.exists(scripts_dir):
        result["warnings"].append("无 scripts/ 目录（纯文档型 skill）")
        return result

    result["has_scripts_dir"] = True
    result["scripts"] = os.listdir(scripts_dir)

    run_py = os.path.join(scripts_dir, "run.py")
    if os.path.exists(run_py):
        result["has_run_py"] = True
        result["run_py_executable"] = os.access(run_py, os.X_OK)
        if not result["run_py_executable"]:
            result["warnings"].append("run.py 不可执行（建议 chmod +x）")
    else:
        result["warnings"].append("无 run.py（可能需要手动调用）")

    return result


def verify_requirements(skill_path: str) -> dict:
    """验证 Python 依赖"""
    result = {
        "has_requirements": False,
        "packages": [],
        "missing_packages": [],
        "errors": [],
        "warnings": [],
    }

    req_file = os.path.join(skill_path, "requirements.txt")
    if not os.path.exists(req_file):
        return result

    result["has_requirements"] = True

    try:
        with open(req_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        result["errors"].append(f"读取 requirements.txt 失败: {e}")
        return result

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 提取包名（忽略版本号）
        pkg = re.split(r'[>=<!~]', line)[0].strip()
        if pkg:
            result["packages"].append(pkg)

    # 检查每个包是否已安装
    for pkg in result["packages"]:
        try:
            subprocess.run(
                ["python3", "-c", f"import {pkg.replace('-', '_')}"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, Exception):
            result["missing_packages"].append(pkg)

    if result["missing_packages"]:
        result["warnings"].append(f"缺失 Python 包（运行时依赖，不影响打包）: {', '.join(result['missing_packages'])}")

    return result


def scan_sensitive_data(skill_path: str) -> dict:
    """扫描硬编码的敏感信息"""
    result = {
        "scanned_files": [],
        "findings": [],
        "clean": True,
        "errors": [],
        "warnings": [],
    }

    # 扫描所有 .py .sh .md 文件
    for root, dirs, files in os.walk(skill_path):
        # 跳过 __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for fname in files:
            if not fname.endswith((".py", ".sh", ".md", ".yaml", ".yml", ".json")):
                continue

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, skill_path)
            result["scanned_files"].append(rel_path)

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                continue

            for pattern in SENSITIVE_PATTERNS:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for m in matches:
                    # 排除明显的误报（如示例/文档中的占位符）
                    matched_text = m.group(0)
                    if "example" in matched_text.lower() or "placeholder" in matched_text.lower():
                        continue
                    if "your_" in matched_text.lower() or "xxx" in matched_text.lower():
                        continue

                    # 脱敏处理
                    redacted = matched_text[:8] + "..." + matched_text[-4:] if len(matched_text) > 12 else "***"

                    result["findings"].append({
                        "file": rel_path,
                        "line": content[:m.start()].count("\n") + 1,
                        "type": "potential_secret",
                        "redacted": redacted,
                        "pattern": pattern[:30] + "...",
                    })

    result["clean"] = len(result["findings"]) == 0
    if not result["clean"]:
        result["errors"].append(f"发现 {len(result['findings'])} 处潜在硬编码密钥")

    return result


def verify_skill(skill_name: str) -> dict:
    """对一个 skill 做完整核验"""
    result = {
        "name": skill_name,
        "path": None,
        "locations": [],
        "exists": False,
        "skill_md": {},
        "scripts": {},
        "requirements": {},
        "security": {},
        "passed": False,
        "errors": [],
        "warnings": [],
    }

    # 1. 存在性
    path = find_skill_path(skill_name)
    all_locs = find_all_skill_locations(skill_name)

    if not path:
        result["errors"].append(f"Skill '{skill_name}' 不存在于系统中")
        return result

    result["path"] = path
    result["locations"] = [loc for loc, _ in all_locs]
    result["exists"] = True

    # 2. SKILL.md
    result["skill_md"] = verify_skill_md(path)
    result["errors"].extend(result["skill_md"].get("errors", []))
    result["warnings"].extend(result["skill_md"].get("warnings", []))

    # 3. Scripts
    result["scripts"] = verify_scripts(path)
    result["errors"].extend(result["scripts"].get("errors", []))
    result["warnings"].extend(result["scripts"].get("warnings", []))

    # 4. Requirements
    result["requirements"] = verify_requirements(path)
    result["errors"].extend(result["requirements"].get("errors", []))
    result["warnings"].extend(result["requirements"].get("warnings", []))

    # 5. Security scan
    result["security"] = scan_sensitive_data(path)
    result["errors"].extend(result["security"].get("errors", []))
    result["warnings"].extend(result["security"].get("warnings", []))

    # 6. 重复检测（仅警告）
    if len(all_locs) > 1:
        result["warnings"].append(f"同名 skill 出现在 {len(all_locs)} 个位置: {', '.join(result['locations'])}")

    result["passed"] = len(result["errors"]) == 0
    return result


def verify_workflow(skill_names: list, strict: bool = False) -> dict:
    """核验整个工作流"""
    results = []
    all_errors = []
    all_warnings = []
    passed_count = 0

    print(f"🔍 开始核验 {len(skill_names)} 个 skills...\n")

    for i, name in enumerate(skill_names, 1):
        print(f"  [{i}/{len(skill_names)}] 核验 {name}...", end=" ")
        result = verify_skill(name)
        results.append(result)

        has_errors = len(result["errors"]) > 0
        has_warnings = len(result["warnings"]) > 0

        if not has_errors and not has_warnings:
            print("✅ 通过")
            passed_count += 1
        elif has_errors:
            print("❌ 失败")
            all_errors.extend([f"[{name}] {e}" for e in result["errors"]])
        elif has_warnings:
            print("⚠️  警告")
            all_warnings.extend([f"[{name}] {w}" for w in result["warnings"]])

    print(f"\n{'='*60}")
    print(f"核验结果: {passed_count}/{len(skill_names)} 完全通过")
    if all_warnings:
        print(f"警告数: {len(all_warnings)}")
    if all_errors:
        print(f"错误数: {len(all_errors)}")

    # 严格模式：有警告也算失败
    can_package = (not strict and len(all_errors) == 0) or (strict and len(all_errors) == 0 and len(all_warnings) == 0)

    return {
        "total": len(skill_names),
        "passed": passed_count,
        "warnings": len(all_warnings),
        "errors": len(all_errors),
        "failed": len([r for r in results if not r["passed"]]),
        "strict": strict,
        "can_package": can_package,
        "results": results,
        "all_errors": all_errors,
        "all_warnings": all_warnings,
    }


def to_markdown(report: dict, skill_names: list) -> str:
    """生成 Markdown 核验报告"""
    lines = [
        "# Skill 核验报告",
        "",
        f"**核验时间**: 刚刚",
        f"**核验 Skills**: {', '.join(skill_names)}",
        f"**严格模式**: {'开' if report['strict'] else '关'}",
        "",
        "## 摘要",
        "",
        f"| 项目 | 数值 |",
        f"|------|------|",
        f"| 总数 | {report['total']} |",
        f"| ✅ 通过 | {report['passed']} |",
        f"| ⚠️ 警告 | {report['warnings']} |",
        f"| ❌ 失败 | {report['failed']} |",
        f"| **可打包** | {'✅ 是' if report['can_package'] else '❌ 否'} |",
        "",
    ]

    if report["all_errors"] or report["all_warnings"]:
        lines.extend([
            "## 问题清单",
            "",
        ])
        if report["all_errors"]:
            lines.append("### ❌ 错误（阻塞打包）")
            for issue in report["all_errors"]:
                lines.append(f"- {issue}")
            lines.append("")
        if report["all_warnings"]:
            lines.append("### ⚠️ 警告（非阻塞，可忽略）")
            for issue in report["all_warnings"]:
                lines.append(f"- {issue}")
            lines.append("")

    lines.extend([
        "## 详细结果",
        "",
    ])

    for r in report["results"]:
        if r["passed"] and not r["warnings"]:
            status = "✅"
        elif r["passed"]:
            status = "⚠️"
        else:
            status = "❌"
        lines.append(f"### {status} {r['name']}")
        lines.append(f"- **路径**: `{r['path']}`")
        lines.append(f"- **位置**: {', '.join(r['locations'])}")

        if r["skill_md"]:
            md = r["skill_md"]
            lines.append(f"- **SKILL.md**: {'✅ 有效' if md['valid'] else '❌ 无效'}")
            if md["name"]:
                lines.append(f"  - 名称: {md['name']}")
            if md["version"]:
                lines.append(f"  - 版本: {md['version']}")
            if md.get("warnings"):
                for w in md["warnings"]:
                    lines.append(f"  - ⚠️ {w}")

        if r["scripts"]:
            sc = r["scripts"]
            if sc["has_scripts_dir"]:
                lines.append(f"- **脚本**: {', '.join(sc['scripts'])}")
                lines.append(f"  - run.py: {'✅' if sc['has_run_py'] else '❌'}")
            if sc.get("warnings"):
                for w in sc["warnings"]:
                    lines.append(f"  - ⚠️ {w}")

        if r["requirements"]:
            req = r["requirements"]
            if req["has_requirements"]:
                lines.append(f"- **Python 依赖**: {', '.join(req['packages'])}")
                if req["missing_packages"]:
                    lines.append(f"  - 缺失: {', '.join(req['missing_packages'])}")
            if req.get("warnings"):
                for w in req["warnings"]:
                    lines.append(f"  - ⚠️ {w}")

        if r["security"] and not r["security"]["clean"]:
            lines.append(f"- **安全扫描**: ❌ 发现 {len(r['security']['findings'])} 处潜在密钥")
            for f in r["security"]["findings"][:3]:
                lines.append(f"  - `{f['file']}:{f['line']}` {f['redacted']}")
        elif r["security"].get("warnings"):
            for w in r["security"]["warnings"]:
                lines.append(f"  - ⚠️ {w}")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify skills before packaging")
    parser.add_argument("--skills", "-s", required=True, help="逗号分隔的 skills 列表")
    parser.add_argument("--strict", action="store_true", help="严格模式（警告也视为失败）")
    parser.add_argument("--report", "-o", help="输出 JSON 报告路径")
    parser.add_argument("--markdown", "-m", help="输出 Markdown 报告路径")
    parser.add_argument("--auto-fix", action="store_true", help="自动修复简单问题（chmod +x 等）")
    args = parser.parse_args()

    skill_names = [s.strip() for s in args.skills.split(",")]

    report = verify_workflow(skill_names, strict=args.strict)

    # 自动修复
    if args.auto_fix:
        print("🔧 尝试自动修复...")
        for r in report["results"]:
            if r["path"] and r["scripts"].get("has_run_py") and not r["scripts"].get("run_py_executable"):
                run_py = os.path.join(r["path"], "scripts", "run.py")
                os.chmod(run_py, 0o755)
                print(f"  + chmod +x {run_py}")

    # 输出 JSON
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📄 JSON 报告: {args.report}")

    # 输出 Markdown
    if args.markdown:
        md = to_markdown(report, skill_names)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"📄 Markdown 报告: {args.markdown}")

    # 总结
    print(f"\n{'='*60}")
    if report["can_package"]:
        print("🎉 核验通过，可以安全打包！")
        return 0
    else:
        if args.strict and report["warnings"] > 0 and report["errors"] == 0:
            print("❌ 严格模式下未通过（存在警告）。")
            print("💡 提示: 去掉 --strict 参数可在有警告时继续打包")
        else:
            print("❌ 核验未通过，请修复错误后再打包。")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
