# -*- coding: utf-8 -*-
"""
TeachingEngine - 渐进式教学引导系统

为OpenFOAM CFD仿真系统提供上下文相关的CFD知识解释，
帮助零基础用户理解仿真流程中的各个概念。
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


class TeachingEngine:
    """CFD教学引导引擎，提供参数解释、步骤说明、错误诊断等功能"""

    def __init__(self):
        self.user_level = "beginner"  # beginner/intermediate/advanced
        self.knowledge_base = self._load_knowledge_base()

    def _load_knowledge_base(self) -> Dict[str, Any]:
        """从YAML文件加载知识库"""
        knowledge_dir = Path(__file__).parent.parent / "config" / "knowledge"

        knowledge_base = {
            "parameters": {},
            "steps": {},
            "errors": {},
            "scenarios": {},
            "glossary": {}
        }

        file_mapping = {
            "parameters": "parameters.yaml",
            "steps": "steps.yaml",
            "errors": "errors.yaml",
            "scenarios": "scenarios.yaml",
            "glossary": "glossary.yaml"
        }

        for key, filename in file_mapping.items():
            filepath = knowledge_dir / filename
            try:
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data:
                            if key == "scenarios":
                                # scenarios.yaml 包含两部分：cenarios_knowledge 和 scenario_templates
                                knowledge_base[key] = data.get("cenarios_knowledge", {})
                                knowledge_base["scenario_templates"] = data.get("scenario_templates", {})
                            else:
                                knowledge_base[key] = data
                        else:
                            logger.warning(f"知识库文件为空: {filepath}")
                else:
                    logger.warning(f"知识库文件不存在: {filepath}")
            except Exception as e:
                logger.error(f"加载知识库文件失败 {filepath}: {e}")

        return knowledge_base

    # ============ 公共接口方法 ============

    def explain_parameter(self, param_name: str, current_value=None, context: dict = None) -> str:
        """
        解释某个参数的含义、为什么选这个值、取值范围

        Args:
            param_name: 参数名称
            current_value: 当前值（可选）
            context: 上下文信息（可选）

        Returns:
            格式化的参数解释字符串
        """
        param = self.knowledge_base["parameters"].get(param_name)
        if not param:
            return f"【{param_name}】\n暂无可用的详细解释。请检查参数名称是否正确。"

        # 根据用户水平选择提示
        tips = param["tips"].get(self.user_level, param["tips"]["beginner"])

        # 构建输出
        lines = [
            f"【{param['name']} ({param['symbol']})】",
            f"英文：{param['name_en']}",
            f"单位：{param['unit']}",
            "",
            f"📖 含义：{param['description']}",
            "",
            f"📊 典型取值范围："
        ]

        for key, value in param["typical_range"].items():
            lines.append(f"  • {key}: {value}")

        if current_value is not None:
            lines.extend(["", f"✅ 当前值：{current_value}"])

        lines.extend([
            "",
            f"💡 通俗理解：{param['analogy']}",
            "",
            f"⚠️ 为什么重要：{param['why_matters']}",
            "",
            f"💬 建议（{self._level_name(self.user_level)}）：{tips}"
        ])

        return "\n".join(lines)

    def explain_step(self, step_name: str, config: dict = None) -> str:
        """
        解释当前步骤在整个仿真流程中的作用

        Args:
            step_name: 步骤名称 (scenario/geometry/mesh/boundary/solver/review)
            config: 配置信息（可选）

        Returns:
            格式化的步骤解释字符串
        """
        step = self.knowledge_base["steps"].get(step_name)
        if not step:
            return f"【{step_name}】\n暂无可用的详细解释。可用步骤：scenario, geometry, mesh, boundary, solver, review"

        details = step["details"].get(self.user_level, step["details"]["beginner"])

        lines = [
            f"【步骤：{step['name']}】",
            "",
            f"🎯 目的：{step['purpose']}",
            "",
            f"📋 说明：{step['description']}",
            "",
            f"📚 详细内容（{self._level_name(self.user_level)}）：",
            details
        ]

        return "\n".join(lines)

    def explain_error(self, error_type: str, error_detail: str = "", config: dict = None) -> str:
        """
        用通俗语言解释错误原因和修复建议

        Args:
            error_type: 错误类型
            error_detail: 错误详情（可选）
            config: 配置信息（可选）

        Returns:
            格式化的错误解释和修复建议
        """
        error = self.knowledge_base["errors"].get(error_type)
        if not error:
            return f"【{error_type}】\n暂无可用的详细解释。常见错误类型：mesh_too_coarse, cfl_violation, divergence_residual, boundary_mismatch, solver_incompatible, physical_unrealistic"

        lines = [
            f"【错误：{error['name']}】",
            "",
            f"🔍 症状：{error['symptom']}"
        ]

        if error_detail:
            lines.extend([f"📄 详细信息：{error_detail}", ""])

        lines.extend([
            f"💡 原因解释：{error['explanation']}",
            "",
            f"🔧 修复建议：{error['solution']}"
        ])

        return "\n".join(lines)

    def get_best_practice(self, scenario: str, param_name: str = None) -> str:
        """
        给出特定场景下的最佳实践建议

        Args:
            scenario: 场景名称
            param_name: 特定参数（可选）

        Returns:
            最佳实践建议字符串
        """
        scenario_info = self.knowledge_base["scenarios"].get(scenario)
        if not scenario_info:
            scenarios = ", ".join(self.knowledge_base["scenarios"].keys())
            return f"场景 '{scenario}' 未找到。可用场景：{scenarios}"

        lines = [
            f"【{scenario_info['name']} - 最佳实践】",
            "",
            f"📖 场景描述：{scenario_info['description']}",
            "",
            f"🔬 物理背景：{scenario_info['physics']}",
            "",
            f"⚙️ 设置建议：{scenario_info['setup']}",
            "",
            f"💡 特别提示：{scenario_info['tips']}"
        ]

        return "\n".join(lines)

    def adjust_detail_level(self, user_level: str):
        """
        根据用户水平调整解释详细程度

        Args:
            user_level: 用户水平 (beginner/intermediate/advanced)
        """
        valid_levels = ["beginner", "intermediate", "advanced"]
        if user_level not in valid_levels:
            raise ValueError(f"无效的用户水平：{user_level}。可选值：{valid_levels}")

        self.user_level = user_level

    def get_glossary(self) -> dict:
        """
        返回CFD术语表，用于学习中心

        Returns:
            术语表字典
        """
        return self.knowledge_base["glossary"]

    def get_scenario_explanation(self, scenario_id: str) -> str:
        """
        返回某个仿真场景的详细图文说明

        Args:
            scenario_id: 场景ID

        Returns:
            场景详细说明字符串
        """
        return self.get_best_practice(scenario_id)

    def get_scenario_template(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        获取场景模板（用于wizard_engine共享数据）

        Args:
            scenario_id: 场景ID

        Returns:
            场景模板字典
        """
        return self.knowledge_base.get("scenario_templates", {}).get(scenario_id)

    def _level_name(self, level: str) -> str:
        """将用户水平代码转换为中文名称"""
        mapping = {
            "beginner": "初学者",
            "intermediate": "进阶用户",
            "advanced": "高级用户"
        }
        return mapping.get(level, level)

    def list_parameters(self) -> List[str]:
        """返回所有可用参数列表"""
        return list(self.knowledge_base["parameters"].keys())

    def list_scenarios(self) -> List[str]:
        """返回所有可用场景列表"""
        return list(self.knowledge_base["scenarios"].keys())

    def list_error_types(self) -> List[str]:
        """返回所有可用错误类型列表"""
        return list(self.knowledge_base["errors"].keys())

    def search_glossary(self, keyword: str) -> Dict[str, Dict]:
        """
        搜索术语表

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的术语字典
        """
        results = {}
        keyword_lower = keyword.lower()

        for term, info in self.knowledge_base["glossary"].items():
            if (keyword_lower in term.lower() or
                keyword_lower in info.get("cn", "").lower() or
                keyword_lower in info.get("desc", "").lower()):
                results[term] = info

        return results


# 便捷函数：创建默认教学引擎实例
def create_teaching_engine(user_level: str = "beginner") -> TeachingEngine:
    """
    创建并配置TeachingEngine实例

    Args:
        user_level: 用户水平 (beginner/intermediate/advanced)

    Returns:
        配置好的TeachingEngine实例
    """
    engine = TeachingEngine()
    engine.adjust_detail_level(user_level)
    return engine


# 测试代码
if __name__ == "__main__":
    # 创建教学引擎
    engine = create_teaching_engine("beginner")

    print("=" * 60)
    print("TeachingEngine 测试")
    print("=" * 60)

    # 测试参数解释
    print("\n【测试1：参数解释 - nu】")
    print(engine.explain_parameter("nu", current_value=1e-6))

    # 测试步骤解释
    print("\n" + "=" * 60)
    print("\n【测试2：步骤解释 - mesh】")
    print(engine.explain_step("mesh"))

    # 测试错误解释
    print("\n" + "=" * 60)
    print("\n【测试3：错误解释 - cfl_violation】")
    print(engine.explain_error("cfl_violation"))

    # 测试最佳实践
    print("\n" + "=" * 60)
    print("\n【测试4：最佳实践 - cylinder】")
    print(engine.get_best_practice("cylinder"))

    # 测试术语表
    print("\n" + "=" * 60)
    print("\n【测试5：术语表搜索 - '雷诺'】")
    results = engine.search_glossary("雷诺")
    for term, info in results.items():
        print(f"  {term}: {info}")

    # 测试不同用户水平
    print("\n" + "=" * 60)
    print("\n【测试6：不同用户水平对比】")
    for level in ["beginner", "intermediate", "advanced"]:
        engine.adjust_detail_level(level)
        tip = engine.knowledge_base["parameters"]["nu"]["tips"][level]
        print(f"\n{engine._level_name(level)}: {tip[:50]}...")

    print("\n" + "=" * 60)
    print("测试完成！")
