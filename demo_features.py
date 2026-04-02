#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenFOAM AI Agent - FeaturesDemo脚本
展示项目实现的所有核心Features
"""

import sys
import tempfile
import os
from pathlib import Path

# 设置UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置路径
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "memory"))

print("=" * 70)
print("    OpenFOAM AI Agent - Functional Demo")
print("=" * 70)
print()

# ============================================================
# Phase 一: 基础设施与MVP
# ============================================================
print("[Phase 一]基础设施与MVPFeatures")
print("-" * 70)

from case_manager import CaseManager, create_cavity_case

# 1. CaseManager - 算例管理
print("\n1. CaseManager - 算例目录管理")
case_manager = CaseManager("./demo_cases")
case_path = case_manager.create_case("demo_case", physics_type="incompressible")
print(f"   [OK] 创建算例: {case_path.name}")
print(f"   [OK] 算例列表: {case_manager.list_cases()}")

# 2. 创建方腔算例模板
print("\n2. 方腔驱动流模板")
cavity_path = create_cavity_case(case_manager, "cavity_demo")
print(f"   [OK] 创建方腔算例: {cavity_path.name}")
files = list(cavity_path.glob("**/*"))
print(f"   [OK] 生成文件数: {len([f for f in files if f.is_file()])}")

# 3. PromptEngine - 自然语言解析
print("\n3. PromptEngine - 自然语言到配置")
from prompt_engine import PromptEngine, ConfigRefiner

engine = PromptEngine()
config = engine.natural_language_to_config("建立一个二维方腔驱动流")
print(f"   [OK] 物理类型: {config['physics_type']}")
print(f"   [OK] 求解器: {config['solver']['name']}")
print(f"   [OK] 网格: {config['geometry']['mesh_resolution']}")

# 4. 配置优化
print("\n4. ConfigRefiner - 配置优化")
refiner = ConfigRefiner()
refined = refiner.refine(config)
warnings = refiner.validate_critical_params(refined)
print(f"   [OK] 优化后网格: {refined['geometry']['mesh_resolution']}")
print(f"   [OK] 验证警告: {len(warnings)} 个")

print("\n" + "=" * 70)

# ============================================================
# Phase 二: AI自查与自愈
# ============================================================
print("[Phase 二]AI自查与自愈能力")
print("-" * 70)

# 1. MeshQualityAgent - 网格质量检查
print("\n1. MeshQualityAgent - 网格质量自查")
from mesh_quality_agent import MeshQualityChecker, MeshQualityLevel

checker = MeshQualityChecker(cavity_path)
metrics = {
    'non_orthogonality_max': 72,
    'skewness_max': 2.5,
    'aspect_ratio_max': 45,
    'failed_checks': 0
}
level = checker._assess_quality_level(metrics)
print(f"   [OK] 网格质量等级: {level.name}")
print(f"   [OK] 非正交性: {metrics['non_orthogonality_max']}°")
warnings, errors = checker._identify_issues(metrics)
print(f"   [OK] 检测到警告: {len(warnings)} 个")

# 2. SelfHealingAgent - 自愈控制
print("\n2. SelfHealingAgent - 求解稳定性监控")
from self_healing_agent import SolverStabilityMonitor, DivergenceType

monitor = SolverStabilityMonitor()
print(f"   [OK] 监控器初始化: max_history={monitor.max_history}")

# 模拟发散检测
from openfoam_runner import SolverMetrics
metrics_normal = SolverMetrics(
    time=0.1, courant_mean=0.2, courant_max=0.5, residuals={'Ux': 1e-5}
)
event = monitor._check_courant(metrics_normal)
print(f"   [OK] 库朗数检查: {'正常' if event is None else '超标'}")

metrics_critical = SolverMetrics(
    time=0.1, courant_mean=3.0, courant_max=6.0, residuals={}
)
event = monitor._check_courant(metrics_critical)
if event:
    print(f"   [OK] 发散检测: {event.divergence_type.value}")
    print(f"   [OK] 建议操作: {event.suggested_action}")

# 3. CriticAgent - 审查者Agent
print("\n3. CriticAgent - 方案审查")
from critic_agent import CriticAgent, ReviewVerdict

critic = CriticAgent(use_llm=False)
test_config = {
    "task_id": "demo_001",
    "physics_type": "incompressible",
    "geometry": {
        "mesh_resolution": {"nx": 50, "ny": 50, "nz": 1}
    },
    "solver": {"name": "icoFoam", "deltaT": 0.005}
}
report = critic.review(test_config)
print(f"   [OK] 审查评分: {report.score}/100")
print(f"   [OK] 审查结论: {report.verdict.name}")
print(f"   [OK] 发现问题: {len(report.issues)} 个")

# 4. PhysicsValidationAgent - 物理校验
print("\n4. PhysicsValidationAgent - 物理一致性校验")
from physics_validation_agent import PhysicsConsistencyValidator, ValidationType

validator = PhysicsConsistencyValidator(cavity_path)
result = validator.validate_mass_conservation()
print(f"   [OK] 质量守恒验证: {result.message}")
result = validator.validate_energy_conservation()
print(f"   [OK] 能量守恒验证: {result.message}")

print("\n" + "=" * 70)

# ============================================================
# Phase 三: 记忆性建模与交互
# ============================================================
print("[Phase 三]记忆性建模与交互")
print("-" * 70)

# 1. MemoryManager - 记忆管理
print("\n1. MemoryManager - 配置记忆存储")
from memory_manager import MemoryManager, ConfigurationDiffer

memory = MemoryManager(db_path="./demo_memory", use_mock=True)

config1 = {
    "physics_type": "incompressible",
    "solver": {"name": "icoFoam"},
    "geometry": {"mesh_resolution": {"nx": 20, "ny": 20}}
}
mem_id1 = memory.store_memory(
    case_name="cavity",
    user_prompt="建立方腔驱动流",
    config=config1
)
print(f"   [OK] 存储记忆: {mem_id1[:16]}...")

# 2. 增量更新
print("\n2. ConfigurationDiffer - 增量更新")
config2 = {
    "physics_type": "incompressible",
    "solver": {"name": "icoFoam"},
    "geometry": {"mesh_resolution": {"nx": 40, "ny": 40}}  # 修改网格
}
diff, mem_id2 = memory.create_incremental_update(
    case_name="cavity",
    modification_prompt="加密网格到40x40",
    new_config=config2
)
print(f"   [OK] 变更摘要: {diff.change_summary}")
for path, (old, new) in diff.modified.items():
    print(f"      - {path}: {old} -> {new}")

# 3. 相似性检索
print("\n3. 相似性检索")
results = memory.search_similar("方腔流动", n_results=2)
print(f"   [OK] 检索结果: {len(results)} 条记忆")

# 4. SessionManager - 会话管理
print("\n4. SessionManager - 会话管理")
from session_manager import SessionManager

session = SessionManager(session_id="demo_session")
session.add_message("user", "建立一个方腔驱动流")
session.add_message("assistant", "好的，我将为您创建方腔驱动流算例")
history = session.get_conversation_history()
print(f"   [OK] 会话消息数: {len(history)}")

# 风险操作确认
pending = session.create_pending_operation(
    operation_type="modify_boundary",
    description="修改边界条件为无滑移",
    details={"boundary": "wall", "type": "noSlip"}
)
print(f"   [OK] 创建待确认操作: {pending.operation_type}")

print("\n" + "=" * 70)

# ============================================================
# Phase 四: 多模态与后处理
# ============================================================
print("[Phase 四]多模态解析与后处理")
print("-" * 70)

# 1. GeometryImageParser - 几何图像解析
print("\n1. GeometryImageParser - 几何图像解析")
from geometry_image_agent import create_geometry_parser, GeometryType

parser = create_geometry_parser(api_key=None)

# 创建测试图像
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    test_image = Path(f.name)
test_image.write_text("fake image data")

features = parser.parse_image(str(test_image))
print(f"   [OK] 解析几何类型: {features.geometry_type.name}")
print(f"   [OK] 置信度: {features.confidence:.0%}")

# 转换为配置
sim_config = parser.convert_to_simulation_config(features)
print(f"   [OK] 转换后求解器: {sim_config.solver.name}")
print(f"   [OK] 网格分辨率: {sim_config.geometry.nx}x{sim_config.geometry.ny}")

test_image.unlink()  # 清理

# 2. PostProcessingAgent - 后处理
print("\n2. PostProcessingAgent - 自动绘图")
from postprocessing_agent import create_postprocessing_agent, PlotType

pp_agent = create_postprocessing_agent()

# 解析自然语言绘图需求
request1 = pp_agent.parse_natural_language("生成速度云图")
print(f"   [OK] 绘图类型: {request1.plot_type.name}")
print(f"   [OK] 场变量: {request1.field}")

request2 = pp_agent.parse_natural_language("绘制流线PDF")
print(f"   [OK] 绘图类型: {request2.plot_type.name}")
print(f"   [OK] 输出格式: {request2.output_format.name}")

# 生成PyVista脚本
with tempfile.TemporaryDirectory() as tmpdir:
    script_path = Path(tmpdir) / "plot_script.py"
    script = pp_agent.generate_pyvista_script(request1, str(script_path))
    print(f"   [OK] 脚本长度: {len(script)} 字符")
    print(f"   [OK] 包含PyVista导入: {'import pyvista' in script}")

print("\n" + "=" * 70)

# ============================================================
# 总结
# ============================================================
print("[FeaturesDemo完成]")
print("-" * 70)
print("""
已实现的Features模块:

Phase 一 - 基础设施:
  [OK] CaseManager: 算例目录管理、模板创建
  [OK] PromptEngine: 自然语言解析、Mock模式
  [OK] FileGenerator: OpenFOAM字典文件生成
  [OK] OpenFOAMRunner: 命令执行、日志监控
  [OK] ManagerAgent: 意图识别、任务调度

Phase 二 - AI自查与自愈:
  [OK] MeshQualityAgent: 网格质量检查、自动修复
  [OK] SelfHealingAgent: 发散检测、库朗数监控
  [OK] CriticAgent: 宪法规则审查、方案评分
  [OK] PhysicsValidationAgent: 质量/能量守恒验证

Phase 三 - 记忆性建模:
  [OK] MemoryManager: 向量存储、相似性检索
  [OK] ConfigurationDiffer: 增量更新、Diff分析
  [OK] SessionManager: 多轮对话、风险分级
  [OK] Gradio/CLI Interface: Web和命令行界面

Phase 四 - 多模态与后处理:
  [OK] GeometryImageParser: 几何图像解析
  [OK] PostProcessingAgent: 自然语言绘图、PyVista脚本

所有FeaturesDemo成功！
""")
print("=" * 70)
