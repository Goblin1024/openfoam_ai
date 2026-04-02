#!/usr/bin/env python3
"""
Mock 模式演示 - 无需 API Key 体验完整功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

from prompt_engine import PromptEngine, ConfigRefiner
from critic_agent import CriticAgent
from case_manager import CaseManager, create_cavity_case
from mesh_quality_agent import MeshQualityChecker

print("=" * 70)
print("OpenFOAM AI Agent - Mock 模式演示")
print("=" * 70)
print("\n注意: 当前使用 Mock 模式（预定义模板），非真实 LLM")
print()

# 1. 初始化组件
engine = PromptEngine(mock_mode=True)
case_manager = CaseManager("./demo_cases")
config_refiner = ConfigRefiner()
critic = CriticAgent(use_llm=False)

# 2. 用户输入
user_input = "创建一个二维方腔驱动流，顶部速度1m/s"
print(f"[用户输入] {user_input}")
print()

# 3. LLM 解析配置
print("[步骤1] AI 解析自然语言...")
config = engine.natural_language_to_config(user_input)
config = config_refiner.refine(config)
print(f"  [OK] 物理类型: {config['physics_type']}")
print(f"  [OK] 求解器: {config['solver']['name']}")
print(f"  [OK] 网格: {config['geometry']['mesh_resolution']}")
print()

# 4. Critic 审查
print("[步骤2] Critic Agent 方案审查...")
report = critic.review(config)
print(f"  [OK] 评分: {report.score}/100")
print(f"  [OK] 结论: {report.verdict.name}")
if report.issues:
    print(f"  [WARN] 发现 {len(report.issues)} 个问题")
print()

# 5. 创建算例
print("[步骤3] 生成 OpenFOAM 算例...")
case_name = config.get('task_id', 'cavity_demo')
case_path = create_cavity_case(case_manager, case_name)
print(f"  [OK] 算例创建: {case_path}")

files = list(case_path.glob("**/*"))
file_count = len([f for f in files if f.is_file()])
print(f"  [OK] 生成文件: {file_count} 个")
print()

# 6. 显示文件
print("[步骤4] 生成的配置文件:")
for f in sorted(case_path.rglob("*")):
    if f.is_file() and not f.name.startswith("."):
        rel_path = f.relative_to(case_path)
        print(f"    [FILE] {rel_path}")
print()

# 7. 网格质量检查
print("[步骤5] 网格质量检查...")
checker = MeshQualityChecker(case_path)
metrics = {
    'non_orthogonality_max': 45,
    'skewness_max': 1.5,
    'aspect_ratio_max': 25,
    'failed_checks': 0
}
level = checker._assess_quality_level(metrics)
print(f"  [OK] 质量等级: {level.name}")
print(f"  [OK] 非正交性: {metrics['non_orthogonality_max']}°")
print()

# 8. 配置说明
print("[步骤6] 配置说明...")
explanation = engine.explain_config(config)
print(explanation[:500])
print()

# 9. 汇总
print("=" * 70)
print("演示完成！")
print("=" * 70)
print("""
[功能汇总]
  [OK] 自然语言解析 (Mock模式)
  [OK] Critic Agent 方案审查
  [OK] OpenFOAM 算例生成 (8个文件)
  [OK] 网格质量检查
  [OK] 配置说明生成

[要启用真实 LLM]
  1. 确认 API Key 正确且已激活
  2. 确保账户有余额
  3. 运行: python start_with_llm.py

[算例位置]
  ./demo_cases/{case_name}/
""")
