"""
数值离散格式智能推荐引擎 (Scheme Advisor)
提供数值格式智能推荐、发散诊断和教学解释功能

功能：
1. 根据求解器/湍流模型/网格质量推荐完整的 fvSchemes 配置
2. 诊断发散原因并推荐格式调整
3. 提供格式的教学解释
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

import yaml

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class SchemeRecommendation:
    """格式推荐结果"""
    divSchemes: Dict[str, str] = field(default_factory=dict)
    gradSchemes: Dict[str, str] = field(default_factory=dict)
    laplacianSchemes: Dict[str, str] = field(default_factory=dict)
    interpolationSchemes: Dict[str, str] = field(default_factory=dict)
    snGradSchemes: Dict[str, str] = field(default_factory=dict)
    ddtSchemes: Dict[str, str] = field(default_factory=lambda: {"default": "Euler"})
    reasoning: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class DivergenceDiagnosis:
    """发散诊断结果"""
    diagnosis: str
    problematic_fields: List[str] = field(default_factory=list)
    divergence_type: str = "unknown"
    recommended_changes: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    severity: str = "warning"  # "warning", "critical"


class SchemeAdvisor:
    """数值离散格式智能推荐引擎
    
    功能：
    1. 根据求解器/湍流模型/网格质量推荐完整的 fvSchemes 配置
    2. 诊断发散原因并推荐格式调整
    3. 提供格式的教学解释
    
    Usage:
        advisor = SchemeAdvisor()
        
        # 获取推荐格式
        recommendation = advisor.recommend_schemes(
            solver="pimpleFoam",
            turbulence_model="kOmegaSST",
            mesh_quality={"non_orthogonality": 65}
        )
        
        # 诊断发散
        diagnosis = advisor.diagnose_divergence(log_content, current_schemes)
        
        # 获取格式解释
        explanation = advisor.get_scheme_explanation("linearUpwind")
    """
    
    def __init__(self, knowledge_path: Optional[Path] = None):
        """初始化，从 schemes.yaml 加载格式知识库
        
        Args:
            knowledge_path: 知识库文件路径，默认为 config/knowledge/schemes.yaml
        """
        if knowledge_path is None:
            knowledge_path = Path(__file__).parent.parent / "config" / "knowledge" / "schemes.yaml"
        
        self.knowledge_path = Path(knowledge_path)
        self.knowledge = self._load_knowledge()
        
        logger.info(f"SchemeAdvisor 初始化完成，知识库路径: {self.knowledge_path}")
    
    def _load_knowledge(self) -> Dict[str, Any]:
        """加载格式知识库
        
        Returns:
            知识库字典
        """
        try:
            with open(self.knowledge_path, 'r', encoding='utf-8') as f:
                knowledge = yaml.safe_load(f) or {}
            logger.debug(f"成功加载格式知识库，包含 {len(knowledge)} 个顶级分类")
            return knowledge
        except Exception as e:
            logger.error(f"加载格式知识库失败: {e}")
            return self._get_default_knowledge()
    
    def _get_default_knowledge(self) -> Dict[str, Any]:
        """获取默认知识库（当文件加载失败时使用）"""
        return {
            "convection_schemes": {
                "upwind": {"order": 1, "stability": "high", "accuracy": "low", "bounded": True},
                "linearUpwind": {"order": 2, "stability": "medium", "accuracy": "medium", "bounded": False},
                "linear": {"order": 2, "stability": "low", "accuracy": "high", "bounded": False},
            },
            "gradient_schemes": {
                "Gauss_linear": {"accuracy": "high", "stability": "medium"},
            },
            "laplacian_schemes": {
                "corrected": {"accuracy": "high", "stability": "medium"},
            },
            "solver_scheme_defaults": {
                "icoFoam": {
                    "divSchemes": {"div(phi,U)": "Gauss linearUpwind grad(U)"},
                    "gradSchemes": {"default": "Gauss linear"},
                    "laplacianSchemes": {"default": "Gauss linear corrected"},
                }
            }
        }
    
    def recommend_schemes(
        self,
        solver: str,
        turbulence_model: str = "laminar",
        mesh_quality: Optional[Dict[str, Any]] = None,
        is_initial: bool = False,
        physics_type: str = "incompressible"
    ) -> SchemeRecommendation:
        """根据求解器/湍流模型/网格质量推荐完整的 fvSchemes 配置
        
        Args:
            solver: 求解器名称（如 icoFoam, simpleFoam, pimpleFoam）
            turbulence_model: 湍流模型名称（如 laminar, kEpsilon, kOmegaSST）
            mesh_quality: 网格质量指标，包含：
                - non_orthogonality: 非正交性角度（度）
                - aspect_ratio: 长宽比
                - skewness: 倾斜率
            is_initial: 是否为初始化阶段（True时使用更稳定的格式）
            physics_type: 物理类型（incompressible, heatTransfer, compressible）
        
        Returns:
            SchemeRecommendation 包含推荐格式和理由
        """
        logger.info(f"推荐格式: solver={solver}, turbulence={turbulence_model}, is_initial={is_initial}")
        
        mesh_quality = mesh_quality or {}
        recommendation = SchemeRecommendation()
        
        # 1. 从 solver_scheme_defaults 获取基础配置
        solver_defaults = self._get_solver_defaults(solver)
        
        # 2. 复制基础配置
        recommendation.divSchemes = solver_defaults.get("divSchemes", {}).copy()
        recommendation.gradSchemes = solver_defaults.get("gradSchemes", {}).copy()
        recommendation.laplacianSchemes = solver_defaults.get("laplacianSchemes", {}).copy()
        recommendation.interpolationSchemes = solver_defaults.get("interpolationSchemes", {"default": "linear"}).copy()
        recommendation.snGradSchemes = solver_defaults.get("snGradSchemes", {"default": "corrected"}).copy()
        
        reasoning_parts = []
        reasoning_parts.append(f"基于求解器 {solver} 的默认配置")
        
        # 3. 根据网格质量调整
        non_orthogonality = mesh_quality.get("non_orthogonality", 50)
        mesh_adjustments = self._get_mesh_quality_adjustments(non_orthogonality)
        
        if mesh_adjustments:
            recommendation.laplacianSchemes["default"] = f"Gauss linear {mesh_adjustments['laplacian']}"
            recommendation.snGradSchemes["default"] = mesh_adjustments["snGrad"]
            reasoning_parts.append(f"网格非正交性 {non_orthogonality}° 调整: {mesh_adjustments['note']}")
        
        # 处理长宽比
        aspect_ratio = mesh_quality.get("aspect_ratio", 1)
        if aspect_ratio > 50:
            recommendation.gradSchemes["default"] = "Gauss cellLimited 1"
            reasoning_parts.append(f"高长宽比 {aspect_ratio}，使用 cellLimited 梯度格式")
            recommendation.warnings.append(f"网格长宽比 {aspect_ratio} 较高，可能影响收敛性")
        
        # 4. 如果是初始化阶段，降级到更稳定的格式
        if is_initial:
            recommendation = self._downgrade_for_initial(recommendation)
            reasoning_parts.append("初始化阶段使用更稳定的格式（upwind）")
        
        # 5. 根据湍流模型调整
        if turbulence_model != "laminar":
            self._adjust_for_turbulence(recommendation, turbulence_model)
            reasoning_parts.append(f"湍流模型 {turbulence_model} 的特定调整")
        
        # 6. 根据物理类型调整
        if physics_type == "heatTransfer":
            self._adjust_for_heat_transfer(recommendation)
            reasoning_parts.append("传热问题的特定调整")
        elif physics_type == "compressible":
            self._adjust_for_compressible(recommendation)
            reasoning_parts.append("可压缩流的特定调整")
        
        recommendation.reasoning = "；".join(reasoning_parts)
        
        logger.debug(f"推荐结果: {recommendation.reasoning}")
        return recommendation
    
    def _get_solver_defaults(self, solver: str) -> Dict[str, Any]:
        """获取求解器的默认格式配置
        
        Args:
            solver: 求解器名称
        
        Returns:
            默认格式配置字典
        """
        solver_defaults = self.knowledge.get("solver_scheme_defaults", {})
        
        # 精确匹配
        if solver in solver_defaults:
            return solver_defaults[solver]
        
        # 模糊匹配（如 pimpleDyMFoam -> pimpleFoam）
        for base_solver in ["pimpleFoam", "simpleFoam", "icoFoam", "interFoam", "buoyantPimpleFoam"]:
            if base_solver.lower() in solver.lower():
                logger.debug(f"求解器 {solver} 使用 {base_solver} 的默认配置")
                return solver_defaults.get(base_solver, {})
        
        # 返回通用默认配置
        return {
            "divSchemes": {"div(phi,U)": "Gauss linearUpwind grad(U)"},
            "gradSchemes": {"default": "Gauss linear"},
            "laplacianSchemes": {"default": "Gauss linear corrected"},
            "interpolationSchemes": {"default": "linear"},
            "snGradSchemes": {"default": "corrected"},
        }
    
    def _get_mesh_quality_adjustments(self, non_orthogonality: float) -> Optional[Dict[str, str]]:
        """根据非正交性获取格式调整建议
        
        Args:
            non_orthogonality: 非正交性角度（度）
        
        Returns:
            调整建议字典，包含 laplacian, snGrad, note
        """
        mesh_adj = self.knowledge.get("mesh_quality_adjustments", {}).get("non_orthogonality", {})
        
        if non_orthogonality >= mesh_adj.get("extreme", {}).get("threshold", 90):
            return mesh_adj.get("extreme", {})
        elif non_orthogonality >= mesh_adj.get("high", {}).get("threshold", 80):
            return mesh_adj.get("high", {})
        elif non_orthogonality >= mesh_adj.get("medium", {}).get("threshold", 70):
            return mesh_adj.get("medium", {})
        elif non_orthogonality >= mesh_adj.get("low", {}).get("threshold", 50):
            return mesh_adj.get("low", {})
        
        return None
    
    def _downgrade_for_initial(self, recommendation: SchemeRecommendation) -> SchemeRecommendation:
        """为初始化阶段降级格式
        
        Args:
            recommendation: 当前推荐
        
        Returns:
            降级后的推荐
        """
        # 对流项降级为 upwind
        for key, value in recommendation.divSchemes.items():
            if "linear" in value.lower() and "upwind" not in value.lower():
                recommendation.divSchemes[key] = "Gauss upwind"
        
        return recommendation
    
    def _adjust_for_turbulence(self, recommendation: SchemeRecommendation, turbulence_model: str) -> None:
        """根据湍流模型调整格式
        
        Args:
            recommendation: 推荐对象（会被修改）
            turbulence_model: 湍流模型名称
        """
        # k-epsilon 和 k-omega 系列的湍流输运方程推荐 upwind
        if "k" in turbulence_model.lower() or "epsilon" in turbulence_model.lower() or "omega" in turbulence_model.lower():
            if "div(phi,k)" not in recommendation.divSchemes:
                recommendation.divSchemes["div(phi,k)"] = "Gauss upwind"
            if "div(phi,epsilon)" not in recommendation.divSchemes and "epsilon" in turbulence_model.lower():
                recommendation.divSchemes["div(phi,epsilon)"] = "Gauss upwind"
            if "div(phi,omega)" not in recommendation.divSchemes and "omega" in turbulence_model.lower():
                recommendation.divSchemes["div(phi,omega)"] = "Gauss upwind"
    
    def _adjust_for_heat_transfer(self, recommendation: SchemeRecommendation) -> None:
        """传热问题的格式调整"""
        if "div(phi,T)" not in recommendation.divSchemes:
            recommendation.divSchemes["div(phi,T)"] = "Gauss linearUpwind grad(T)"
    
    def _adjust_for_compressible(self, recommendation: SchemeRecommendation) -> None:
        """可压缩流的格式调整"""
        if "div(phi,h)" not in recommendation.divSchemes:
            recommendation.divSchemes["div(phi,h)"] = "Gauss linearUpwind grad(h)"
    
    def diagnose_divergence(
        self,
        log_content: str,
        current_schemes: Optional[Dict[str, Any]] = None
    ) -> DivergenceDiagnosis:
        """诊断发散原因并推荐格式调整
        
        解析求解器日志，识别发散模式：
        - 残差持续上升 -> 格式不稳定
        - 残差振荡 -> 可能是中心差分导致
        - 特定字段发散 -> 针对该字段调整
        
        Args:
            log_content: 求解器日志内容
            current_schemes: 当前使用的格式配置（可选）
        
        Returns:
            DivergenceDiagnosis 包含诊断结果和建议
        """
        diagnosis = DivergenceDiagnosis()
        current_schemes = current_schemes or {}
        
        # 1. 解析残差历史
        residual_history = self._parse_residual_history(log_content)
        
        # 2. 检测发散模式
        divergence_type = self._detect_divergence_type(residual_history, log_content)
        diagnosis.divergence_type = divergence_type
        
        # 3. 根据发散类型给出诊断
        if divergence_type == "residual_explosion":
            diagnosis = self._diagnose_explosion(diagnosis, residual_history, current_schemes)
        elif divergence_type == "residual_oscillation":
            diagnosis = self._diagnose_oscillation(diagnosis, residual_history, current_schemes)
        elif divergence_type == "residual_stagnation":
            diagnosis = self._diagnose_stagnation(diagnosis, residual_history, current_schemes)
        elif divergence_type == "courant_exceeded":
            diagnosis = self._diagnose_courant(diagnosis, log_content)
        else:
            diagnosis.diagnosis = "无法确定具体发散原因"
            diagnosis.explanation = "日志信息不足以诊断发散原因，建议检查网格质量和边界条件"
        
        return diagnosis
    
    def _parse_residual_history(self, log_content: str) -> Dict[str, List[float]]:
        """解析日志中的残差历史
        
        Args:
            log_content: 日志内容
        
        Returns:
            字段名到残差列表的映射
        """
        residual_history: Dict[str, List[float]] = {}
        
        # 匹配 GAMG: Solving for p, ... residual = 0.01 等格式
        pattern = r'(?:GAMG|PCG|PBiCG|PBiCGStab|smoothSolver|DIC|DILU):\s+Solving for\s+(\w+).*?residual\s*=\s*([0-9.eE+-]+)'
        
        for match in re.finditer(pattern, log_content):
            field = match.group(1)
            residual = float(match.group(2))
            
            if field not in residual_history:
                residual_history[field] = []
            residual_history[field].append(residual)
        
        return residual_history
    
    def _detect_divergence_type(self, residual_history: Dict[str, List[float]], log_content: str) -> str:
        """检测发散类型
        
        Args:
            residual_history: 残差历史
            log_content: 日志内容
        
        Returns:
            发散类型字符串
        """
        # 检查 Courant 数超标
        if re.search(r'Maximum Courant number.*exceeds', log_content, re.IGNORECASE):
            return "courant_exceeded"
        
        # 检查 NaN/Inf
        if re.search(r'NaN|inf|INFINITY', log_content, re.IGNORECASE):
            return "residual_explosion"
        
        # 检查残差历史
        for field, residuals in residual_history.items():
            if len(residuals) < 3:
                continue
            
            # 检查残差爆炸（连续增大）
            recent = residuals[-10:] if len(residuals) >= 10 else residuals
            if all(recent[i] < recent[i+1] * 0.9 for i in range(len(recent)-1)):
                return "residual_explosion"
            
            # 检查残差振荡
            if len(recent) >= 5:
                changes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
                sign_changes = sum(1 for i in range(len(changes)-1) if changes[i] * changes[i+1] < 0)
                if sign_changes > len(changes) * 0.4:  # 40% 以上符号变化
                    return "residual_oscillation"
            
            # 检查残差停滞
            if len(residuals) >= 20:
                first_avg = sum(residuals[:10]) / 10
                last_avg = sum(residuals[-10:]) / 10
                if last_avg > first_avg * 0.5:  # 残差下降不超过50%
                    return "residual_stagnation"
        
        return "unknown"
    
    def _diagnose_explosion(
        self,
        diagnosis: DivergenceDiagnosis,
        residual_history: Dict[str, List[float]],
        current_schemes: Dict[str, Any]
    ) -> DivergenceDiagnosis:
        """诊断残差爆炸"""
        diagnosis.diagnosis = "检测到残差爆炸（残差持续增大）"
        diagnosis.severity = "critical"
        
        # 找出发散的字段
        for field, residuals in residual_history.items():
            if len(residuals) >= 3:
                recent = residuals[-5:]
                if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                    diagnosis.problematic_fields.append(field)
        
        diagnosis.explanation = "残差持续增大通常表明数值格式过于激进或不稳定。"
        
        # 给出降级建议
        diagnosis.recommended_changes = self._get_downgrade_recommendations(
            diagnosis.problematic_fields,
            current_schemes
        )
        
        if diagnosis.recommended_changes:
            diagnosis.explanation += f" 建议将相关对流格式降级：{diagnosis.recommended_changes}"
        
        return diagnosis
    
    def _diagnose_oscillation(
        self,
        diagnosis: DivergenceDiagnosis,
        residual_history: Dict[str, List[float]],
        current_schemes: Dict[str, Any]
    ) -> DivergenceDiagnosis:
        """诊断残差振荡"""
        diagnosis.diagnosis = "检测到残差振荡（残差上下波动无法收敛）"
        diagnosis.severity = "warning"
        
        # 找出振荡的字段
        for field, residuals in residual_history.items():
            if len(residuals) >= 5:
                recent = residuals[-10:]
                changes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
                sign_changes = sum(1 for i in range(len(changes)-1) if changes[i] * changes[i+1] < 0)
                if sign_changes > len(changes) * 0.3:
                    diagnosis.problematic_fields.append(field)
        
        diagnosis.explanation = "残差振荡通常由中心差分格式导致，高雷诺数时会产生非物理振荡。"
        
        diagnosis.recommended_changes = {
            "action": "改用迎风格式或限制器格式",
            "schemes": {
                field: f"Gauss limitedLinear 1" for field in diagnosis.problematic_fields
            }
        }
        
        return diagnosis
    
    def _diagnose_stagnation(
        self,
        diagnosis: DivergenceDiagnosis,
        residual_history: Dict[str, List[float]],
        current_schemes: Dict[str, Any]
    ) -> DivergenceDiagnosis:
        """诊断残差停滞"""
        diagnosis.diagnosis = "检测到残差停滞（残差长时间不下降）"
        diagnosis.severity = "warning"
        
        diagnosis.explanation = "残差停滞可能由松弛因子过小、网格质量问题或求解器参数不佳导致。"
        
        diagnosis.recommended_changes = {
            "relaxation_factors": "增大松弛因子至 0.5-0.7",
            "nNonOrthogonalCorrectors": "增加非正交修正器迭代次数至 1-2",
            "gradSchemes": "考虑使用 Gauss cellLimited 1 提高稳定性"
        }
        
        return diagnosis
    
    def _diagnose_courant(self, diagnosis: DivergenceDiagnosis, log_content: str) -> DivergenceDiagnosis:
        """诊断库朗数超标"""
        diagnosis.diagnosis = "检测到库朗数超标"
        diagnosis.severity = "critical"
        
        # 提取库朗数
        match = re.search(r'Maximum Courant number[:\s]+([0-9.eE+-]+)', log_content)
        if match:
            courant = float(match.group(1))
            diagnosis.problematic_fields.append(f"Co={courant:.2f}")
        
        diagnosis.explanation = "库朗数超标表明时间步长过大，需要减小时间步长或调整网格。"
        
        diagnosis.recommended_changes = {
            "deltaT": "减小时间步长至当前值的 50%",
            "maxCo": "限制最大库朗数至 0.5-1.0（隐式）或 0.3（显式）"
        }
        
        return diagnosis
    
    def _get_downgrade_recommendations(
        self,
        problematic_fields: List[str],
        current_schemes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取格式降级建议
        
        Args:
            problematic_fields: 有问题的字段列表
            current_schemes: 当前格式配置
        
        Returns:
            降级建议字典
        """
        recommendations = {}
        
        downgrade_path = self.knowledge.get("scheme_downgrade_paths", {}).get("convection", {}).get("path", [])
        
        for field in problematic_fields:
            # 确定对流格式键名
            div_key = f"div(phi,{field})"
            if div_key in current_schemes.get("divSchemes", {}):
                current = current_schemes["divSchemes"][div_key]
                downgrade = self.get_downgrade_recommendation(current, field)
                if downgrade:
                    recommendations[div_key] = downgrade
        
        return recommendations
    
    def get_downgrade_recommendation(self, current_scheme: str, field: str = "U") -> Optional[Dict[str, str]]:
        """给出降级建议
        
        降级路径：linear -> limitedLinear -> linearUpwind -> upwind
        
        Args:
            current_scheme: 当前格式名称
            field: 字段名称
        
        Returns:
            降级建议字典，包含 current, recommended, reason
        """
        # 获取降级路径
        downgrade_path = self.knowledge.get("scheme_downgrade_paths", {}).get("convection", {}).get("path", [])
        
        if not downgrade_path:
            downgrade_path = ["cubic", "linear", "limitedLinear", "linearUpwind", "upwind"]
        
        # 识别当前格式在路径中的位置
        current_scheme_lower = current_scheme.lower()
        
        for i, scheme in enumerate(downgrade_path):
            if scheme.lower() in current_scheme_lower:
                # 找到下一个更稳定的格式
                if i < len(downgrade_path) - 1:
                    recommended = downgrade_path[i + 1]
                    
                    # 构建完整格式字符串
                    if recommended == "upwind":
                        recommended_full = "Gauss upwind"
                    elif recommended == "linearUpwind":
                        recommended_full = f"Gauss linearUpwind grad({field})"
                    elif recommended == "limitedLinear":
                        recommended_full = "Gauss limitedLinear 1"
                    else:
                        recommended_full = f"Gauss {recommended}"
                    
                    return {
                        "current": current_scheme,
                        "recommended": recommended_full,
                        "reason": f"从 {scheme}({i+1}阶) 降级到 {recommended} 以提高稳定性"
                    }
        
        # 如果当前格式不在路径中，默认推荐 upwind
        return {
            "current": current_scheme,
            "recommended": "Gauss upwind",
            "reason": "使用一阶迎风格式保证最大稳定性"
        }
    
    def get_scheme_explanation(self, scheme_name: str) -> str:
        """从知识库返回格式的教学级解释
        
        Args:
            scheme_name: 格式名称
        
        Returns:
            教学级解释字符串
        """
        # 在各格式类别中查找
        for category in ["convection_schemes", "gradient_schemes", "laplacian_schemes", 
                         "interpolation_schemes", "sngrad_schemes", "time_schemes"]:
            schemes = self.knowledge.get(category, {})
            
            # 尝试精确匹配或部分匹配
            for name, info in schemes.items():
                if name.lower() == scheme_name.lower() or scheme_name.lower() in name.lower():
                    teaching_note = info.get("teaching_note", "")
                    use_case = info.get("use_case", "")
                    order = info.get("order", "")
                    stability = info.get("stability", "")
                    accuracy = info.get("accuracy", "")
                    
                    explanation_parts = []
                    
                    if teaching_note:
                        explanation_parts.append(teaching_note)
                    
                    if order:
                        explanation_parts.append(f"精度阶数: {order}阶")
                    
                    if stability:
                        explanation_parts.append(f"稳定性: {stability}")
                    
                    if accuracy:
                        explanation_parts.append(f"精度: {accuracy}")
                    
                    if use_case:
                        explanation_parts.append(f"适用场景: {use_case}")
                    
                    return "\n".join(explanation_parts)
        
        return f"未找到格式 '{scheme_name}' 的详细解释，请参考 OpenFOAM 官方文档。"
    
    def generate_fvschemes_content(self, schemes: SchemeRecommendation) -> str:
        """将推荐结果转为 OpenFOAM fvSchemes 文件内容字符串
        
        Args:
            schemes: SchemeRecommendation 对象
        
        Returns:
            OpenFOAM fvSchemes 文件内容字符串
        """
        content = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

'''
        
        # ddtSchemes
        content += "ddtSchemes\n{\n"
        for key, value in schemes.ddtSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # gradSchemes
        content += "gradSchemes\n{\n"
        for key, value in schemes.gradSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # divSchemes
        content += "divSchemes\n{\n"
        content += "    default             none;\n"
        for key, value in schemes.divSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # laplacianSchemes
        content += "laplacianSchemes\n{\n"
        for key, value in schemes.laplacianSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # interpolationSchemes
        content += "interpolationSchemes\n{\n"
        for key, value in schemes.interpolationSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # snGradSchemes
        content += "snGradSchemes\n{\n"
        for key, value in schemes.snGradSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        content += "// ************************************************************************* //\n"
        
        return content
    
    def get_recommended_nNonOrthogonalCorrectors(self, non_orthogonality: float) -> int:
        """根据非正交性推荐非正交修正器次数
        
        Args:
            non_orthogonality: 非正交性角度（度）
        
        Returns:
            推荐的非正交修正器次数
        """
        if non_orthogonality >= 80:
            return 2
        elif non_orthogonality >= 70:
            return 1
        return 0


# 模块测试
if __name__ == "__main__":
    print("SchemeAdvisor 模块测试")
    print("=" * 70)
    
    # 创建 Advisor
    advisor = SchemeAdvisor()
    
    # 测试1: 推荐 pimpleFoam 格式
    print("\n[测试1] 推荐 pimpleFoam 格式")
    rec = advisor.recommend_schemes("pimpleFoam", "kOmegaSST")
    print(f"理由: {rec.reasoning}")
    print(f"divSchemes: {rec.divSchemes}")
    
    # 测试2: 推荐高非正交性格式
    print("\n[测试2] 推荐高非正交性格式")
    rec2 = advisor.recommend_schemes("simpleFoam", mesh_quality={"non_orthogonality": 78})
    print(f"理由: {rec2.reasoning}")
    print(f"laplacianSchemes: {rec2.laplacianSchemes}")
    
    # 测试3: 获取格式解释
    print("\n[测试3] linearUpwind 格式解释")
    explanation = advisor.get_scheme_explanation("linearUpwind")
    print(explanation)
    
    # 测试4: 降级建议
    print("\n[测试4] linear 格式降级建议")
    downgrade = advisor.get_downgrade_recommendation("Gauss linear")
    print(downgrade)
    
    print("\n测试完成")
