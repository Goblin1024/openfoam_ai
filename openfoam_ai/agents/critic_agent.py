"""
Critic Agent - 审查者Agent (Week 8)
基于AI约束宪法要求，实现多智能体对抗框架中的审查者角色
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import yaml
import logging

# 导入 SchemeAdvisor 用于数值格式检查
from ..core.scheme_advisor import SchemeAdvisor

logger = logging.getLogger(__name__)

import sys
import os

# 添加项目根目录到路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.conservation_checker import ConservationChecker

try:
    from ..core.yplus_checker import YPlusChecker
except ImportError:
    from core.yplus_checker import YPlusChecker


class ReviewVerdict(Enum):
    """审查结论"""
    APPROVE = "APPROVE"      # 批准
    CONDITIONAL = "CONDITIONAL"  # 有条件批准
    REJECT = "REJECT"        # 拒绝


@dataclass
class ReviewIssue:
    """审查发现的问题"""
    severity: str  # "critical", "major", "minor"
    category: str  # "mesh", "solver", "physics", "boundary"
    description: str
    suggestion: str
    constitution_reference: Optional[str] = None  # 违反的宪法条款


@dataclass
class ReviewReport:
    """审查报告"""
    verdict: ReviewVerdict
    score: float  # 0-100分
    issues: List[ReviewIssue] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    reviewed_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%d %H:%M:%S'))
    
    def is_approved(self) -> bool:
        """是否通过审查"""
        return self.verdict in [ReviewVerdict.APPROVE, ReviewVerdict.CONDITIONAL]


class ConstitutionChecker:
    """
    宪法规则检查器
    基于system_constitution.yaml进行硬规则校验
    """
    
    def __init__(self, constitution_path: Optional[Path] = None):
        if constitution_path is None:
            constitution_path = Path(__file__).parent.parent / "config" / "system_constitution.yaml"
        
        self.constitution = self._load_constitution(constitution_path)
        self.rules = self._parse_rules()
    
    def _load_constitution(self, path: Path) -> Dict:
        """加载宪法文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ConstitutionChecker] 加载宪法失败: {e}")
            return {}
    
    def _parse_rules(self) -> List[Dict]:
        """解析宪法规则"""
        rules = []
        
        # 核心指令
        core_directives = self.constitution.get('Core_Directives', [])
        for directive in core_directives:
            rules.append({
                'type': 'core',
                'description': directive,
                'mandatory': True
            })
        
        # 网格标准
        mesh_standards = self.constitution.get('Mesh_Standards', {})
        for key, value in mesh_standards.items():
            rules.append({
                'type': 'mesh',
                'parameter': key,
                'threshold': value,
                'mandatory': True
            })
        
        # 求解器标准
        solver_standards = self.constitution.get('Solver_Standards', {})
        for key, value in solver_standards.items():
            rules.append({
                'type': 'solver',
                'parameter': key,
                'threshold': value,
                'mandatory': True
            })
        
        # 验证要求
        validation_reqs = self.constitution.get('Validation_Requirements', {})
        for key, value in validation_reqs.items():
            rules.append({
                'type': 'validation',
                'parameter': key,
                'threshold': value,
                'mandatory': True
            })
        
        return rules
    
    def check_config(self, config: Dict[str, Any]) -> List[ReviewIssue]:
        """检查配置是否违反宪法"""
        issues = []
        
        # 检查网格标准
        mesh_issues = self._check_mesh_standards(config)
        issues.extend(mesh_issues)
        
        # 检查求解器标准
        solver_issues = self._check_solver_standards(config)
        issues.extend(solver_issues)
        
        # 检查物理配置
        physics_issues = self._check_physics_config(config)
        issues.extend(physics_issues)
        
        # 检查数值格式配置
        scheme_issues = self._check_numerical_schemes(config)
        issues.extend(scheme_issues)
        
        return issues
    
    def _check_mesh_standards(self, config: Dict[str, Any]) -> List[ReviewIssue]:
        """检查网格标准"""
        issues = []
        
        geometry = config.get('geometry', {})
        resolution = geometry.get('mesh_resolution', {})
        
        nx = resolution.get('nx', 0)
        ny = resolution.get('ny', 0)
        nz = resolution.get('nz', 1)
        
        total_cells = nx * ny * nz
        
        # 检查最小网格数
        mesh_standards = self.constitution.get('Mesh_Standards', {})
        
        if nz == 1:  # 2D
            min_cells = mesh_standards.get('min_cells_2d', 400)
            if total_cells < min_cells:
                issues.append(ReviewIssue(
                    severity="critical",
                    category="mesh",
                    description=f"2D网格数量({total_cells})低于宪法要求({min_cells})",
                    suggestion="增加网格分辨率，建议至少20x20",
                    constitution_reference="Mesh_Standards.min_cells_2d"
                ))
        else:  # 3D
            min_cells = mesh_standards.get('min_cells_3d', 8000)
            if total_cells < min_cells:
                issues.append(ReviewIssue(
                    severity="critical",
                    category="mesh",
                    description=f"3D网格数量({total_cells})低于宪法要求({min_cells})",
                    suggestion="增加网格分辨率",
                    constitution_reference="Mesh_Standards.min_cells_3d"
                ))
        
        # 检查长宽比
        dims = geometry.get('dimensions', {})
        if dims and nx > 0 and ny > 0 and nz > 0:
            L = dims.get('L', 1.0)
            W = dims.get('W', 1.0)
            H = dims.get('H', 1.0)
            
            dx = L / nx
            dy = W / ny
            dz = H / nz if nz > 0 else 1
            
            aspect_ratios = [dx/dy, dy/dz if dz > 0 else 1, dx/dz if dz > 0 else 1]
            max_ratio = max(max(aspect_ratios), 1/min(aspect_ratios))
            
            max_allowed = mesh_standards.get('max_aspect_ratio', 100)
            if max_ratio > max_allowed:
                issues.append(ReviewIssue(
                    severity="major",
                    category="mesh",
                    description=f"网格长宽比({max_ratio:.1f})超过限制({max_allowed})",
                    suggestion="调整网格分布，避免过度拉伸",
                    constitution_reference="Mesh_Standards.max_aspect_ratio"
                ))
        
        return issues
    
    def _check_solver_standards(self, config: Dict[str, Any]) -> List[ReviewIssue]:
        """检查求解器标准"""
        issues = []
        
        solver = config.get('solver', {})
        solver_standards = self.constitution.get('Solver_Standards', {})
        
        # 检查收敛残差要求
        min_residual = solver_standards.get('min_convergence_residual', 1e-6)
        
        # 检查时间步长（库朗数）
        delta_t = solver.get('deltaT', 0.01)
        end_time = solver.get('endTime', 1.0)
        
        # 简化库朗数估计
        geometry = config.get('geometry', {})
        resolution = geometry.get('mesh_resolution', {})
        nx = resolution.get('nx', 20)
        
        dx = 1.0 / nx
        u_max = 10.0  # 假设最大速度
        courant = u_max * delta_t / dx
        
        max_courant = solver_standards.get('max_courant_explicit', 0.5)
        if courant > max_courant:
            issues.append(ReviewIssue(
                severity="major",
                category="solver",
                description=f"估计库朗数({courant:.2f})超过安全限制({max_courant})",
                suggestion=f"建议减小时间步长至{max_courant * dx / u_max:.5f}以下",
                constitution_reference="Solver_Standards.max_courant_explicit"
            ))
        
        return issues
    
    def _check_physics_config(self, config: Dict[str, Any]) -> List[ReviewIssue]:
        """检查物理配置"""
        issues = []
        
        physics_type = config.get('physics_type', '')
        solver_name = config.get('solver', {}).get('name', '')
        
        # 检查求解器与物理类型匹配
        if physics_type == 'incompressible':
            valid_solvers = ['icoFoam', 'simpleFoam', 'pimpleFoam', 'pisoFoam']
            if solver_name not in valid_solvers:
                issues.append(ReviewIssue(
                    severity="critical",
                    category="physics",
                    description=f"不可压流不支持求解器{solver_name}",
                    suggestion=f"请选择: {', '.join(valid_solvers)}",
                    constitution_reference="物理类型与求解器匹配"
                ))
        
        elif physics_type == 'heatTransfer':
            valid_solvers = ['buoyantBoussinesqPimpleFoam', 'buoyantPimpleFoam', 
                           'buoyantSimpleFoam', 'chtMultiRegionFoam']
            if solver_name not in valid_solvers:
                issues.append(ReviewIssue(
                    severity="critical",
                    category="physics",
                    description=f"传热问题不支持求解器{solver_name}",
                    suggestion=f"请选择: {', '.join(valid_solvers)}",
                    constitution_reference="物理类型与求解器匹配"
                ))
        
        # 检查边界条件
        bc_config = config.get('boundary_conditions', {})
        if bc_config:
            has_inlet = any('inlet' in name.lower() for name in bc_config.keys())
            has_outlet = any('outlet' in name.lower() for name in bc_config.keys())
            
            if not has_inlet:
                issues.append(ReviewIssue(
                    severity="major",
                    category="boundary",
                    description="未检测到入口边界",
                    suggestion="请添加inlet边界条件"
                ))
            
            if not has_outlet:
                issues.append(ReviewIssue(
                    severity="major",
                    category="boundary",
                    description="未检测到出口边界",
                    suggestion="请添加outlet边界条件"
                ))
        
        return issues
    
    def _check_numerical_schemes(self, config: Dict[str, Any]) -> List[ReviewIssue]:
        """检查数值格式配置是否合理
        
        使用 SchemeAdvisor 检查用户指定的格式是否适合当前场景：
        - LES 使用 upwind 格式会警告
        - 高雷诺数使用 center difference 会警告
        - 多相流 alpha 方程未使用限制器会警告
        
        Args:
            config: 配置字典，可能包含 fvSchemes 配置
        
        Returns:
            问题列表
        """
        issues = []
        
        # 如果配置中没有 fvSchemes 信息，跳过检查
        if "fvSchemes" not in config:
            return issues
        
        try:
            # 初始化 SchemeAdvisor
            scheme_advisor = SchemeAdvisor()
            
            fv_schemes = config.get("fvSchemes", {})
            solver_name = config.get("solver", {}).get("name", "")
            physics_type = config.get("physics_type", "")
            turbulence_model = config.get("turbulence_model", "laminar")
            
            div_schemes = fv_schemes.get("divSchemes", {})
            laplacian_schemes = fv_schemes.get("laplacianSchemes", {})
            sn_grad_schemes = fv_schemes.get("snGradSchemes", {})
            
            # 1. 检查 LES 模拟的格式选择
            if turbulence_model.lower() in ["les", "leskomega", "leskomegasst", "smagorinsky", "dynsmagorinsky"]:
                for key, value in div_schemes.items():
                    if "upwind" in value.lower() and "linearUpwind" not in value.lower():
                        issues.append(ReviewIssue(
                            severity="major",
                            category="solver",
                            description=f"LES模拟使用upwind格式({key}={value})会引入过多数值耗散",
                            suggestion="建议使用LUST或linear格式以保持LES的精度优势",
                            constitution_reference="数值格式与湍流模型匹配"
                        ))
                        break  # 只报告一次
            
            # 2. 检查多相流 alpha 方程的格式
            if "interFoam" in solver_name or physics_type == "multiphase":
                alpha_key = None
                for key in div_schemes.keys():
                    if "alpha" in key.lower():
                        alpha_key = key
                        break
                
                if alpha_key:
                    alpha_scheme = div_schemes[alpha_key]
                    if "vanLeer" not in alpha_scheme and "limitedLinear" not in alpha_scheme and "upwind" not in alpha_scheme:
                        issues.append(ReviewIssue(
                            severity="major",
                            category="solver",
                            description=f"多相流alpha方程格式({alpha_key}={alpha_scheme})可能导致界面模糊",
                            suggestion="建议使用vanLeer或limitedLinear格式保持界面锐利",
                            constitution_reference="数值格式与多相流匹配"
                        ))
            
            # 3. 检查高雷诺数流动的中心差分格式
            reynolds = config.get("Re", 0)
            if reynolds > 10000:
                for key, value in div_schemes.items():
                    if "U" in key and "linear" in value.lower() and "upwind" not in value.lower() and "limited" not in value.lower():
                        issues.append(ReviewIssue(
                            severity="major",
                            category="solver",
                            description=f"高雷诺数({reynolds})流动使用纯中心差分格式({key}={value})可能导致振荡",
                            suggestion="建议使用linearUpwind或limitedLinear格式提高稳定性",
                            constitution_reference="数值格式与雷诺数匹配"
                        ))
                        break
            
            # 4. 检查网格质量与拉普拉斯格式匹配
            mesh_quality = config.get("mesh_quality", {})
            non_orthogonality = mesh_quality.get("non_orthogonality", 0)
            
            if non_orthogonality > 70:
                laplacian_default = laplacian_schemes.get("default", "")
                if "corrected" in laplacian_default.lower() and "limited" not in laplacian_default.lower():
                    issues.append(ReviewIssue(
                        severity="major",
                        category="solver",
                        description=f"高非正交性({non_orthogonality}°)网格使用corrected拉普拉斯格式可能不稳定",
                        suggestion="建议使用'Gauss linear limited corrected 0.5'格式",
                        constitution_reference="数值格式与网格质量匹配"
                    ))
                
                sn_grad_default = sn_grad_schemes.get("default", "")
                if sn_grad_default.lower() == "corrected" and non_orthogonality > 80:
                    issues.append(ReviewIssue(
                        severity="minor",
                        category="solver",
                        description=f"高非正交性({non_orthogonality}°)建议调整snGradSchemes",
                        suggestion="建议使用'limited 0.5'或增加nNonOrthogonalCorrectors",
                        constitution_reference="数值格式与网格质量匹配"
                    ))
            
            # 5. 检查可压缩流的能量方程格式
            if physics_type == "compressible" or "rhoPimpleFoam" in solver_name or "rhoSimpleFoam" in solver_name:
                has_energy_scheme = any("h" in key or "T" in key for key in div_schemes.keys())
                if has_energy_scheme:
                    for key, value in div_schemes.items():
                        if ("h" in key or "T" in key) and "linear" in value.lower() and "upwind" not in value.lower():
                            issues.append(ReviewIssue(
                                severity="minor",
                                category="solver",
                                description="可压缩流能量方程使用纯中心差分可能在激波处产生振荡",
                                suggestion="建议使用linearUpwind格式",
                                constitution_reference="数值格式与可压缩流匹配"
                            ))
                            break
            
        except Exception as e:
            logger.warning(f"数值格式检查出错: {e}")
        
        return issues

    def _check_conservation(self, case_dir: str, log_file: str = None) -> Tuple[bool, List[ReviewIssue]]:
        """
        检查守恒性验证结果
        
        基于ConservationChecker的结果，检查质量守恒、能量守恒、
        连续性误差和残差收敛情况。
        
        Args:
            case_dir: 算例目录路径
            log_file: 日志文件路径（可选）
            
        Returns:
            (是否通过, 问题列表)
        """
        issues = []
        
        if not case_dir or not Path(case_dir).exists():
            return True, issues
        
        try:
            checker = ConservationChecker(case_dir)
            summary = checker.get_summary_dict(log_file=log_file)
            
            # 检查质量守恒
            mass_result = summary.get("mass_conservation", {})
            if not mass_result.get("passed", True):
                details = mass_result.get("details", {})
                error_pct = details.get("error_pct", 0)
                issues.append(ReviewIssue(
                    severity="major",
                    category="physics",
                    description=f"质量守恒验证未通过，误差: {error_pct:.4f}%（要求<0.1%）",
                    suggestion="检查边界条件设置、网格质量和求解器收敛性",
                    constitution_reference="Validation_Requirements.mass_conservation"
                ))
            
            # 检查能量守恒
            energy_result = summary.get("energy_conservation", {})
            if not energy_result.get("passed", True) and not energy_result.get("details", {}).get("skipped"):
                details = energy_result.get("details", {})
                error_pct = details.get("error_pct", 0)
                issues.append(ReviewIssue(
                    severity="major",
                    category="physics",
                    description=f"能量守恒验证未通过，误差: {error_pct:.4f}%（要求<0.1%）",
                    suggestion="检查热边界条件设置和能量方程求解",
                    constitution_reference="Validation_Requirements.energy_conservation"
                ))
            
            # 检查连续性误差
            continuity_result = summary.get("continuity_errors", {})
            if not continuity_result.get("passed", True):
                details = continuity_result.get("details", {})
                max_global = details.get("max_global", 0)
                trend = details.get("trend", "unknown")
                issues.append(ReviewIssue(
                    severity="minor" if trend == "converging" else "major",
                    category="solver",
                    description=f"连续性误差较高 (global={max_global:.2e}, 趋势={trend})",
                    suggestion="考虑减小时间步长或使用更保守的松弛因子",
                    constitution_reference="Solver_Standards.continuity_error"
                ))
            
            # 检查残差收敛
            residual_result = summary.get("residual_convergence", {})
            if not residual_result.get("passed", True):
                details = residual_result.get("details", {})
                non_converged = details.get("non_converged_fields", {})
                if non_converged:
                    field_str = ", ".join([f"{f}={v:.2e}" for f, v in list(non_converged.items())[:3]])
                    issues.append(ReviewIssue(
                        severity="minor",
                        category="solver",
                        description=f"部分字段残差未收敛: {field_str}",
                        suggestion="增加迭代次数或检查求解器设置",
                        constitution_reference="Solver_Standards.min_convergence_residual"
                    ))
            
            all_passed = summary.get("passed", True)
            return all_passed, issues
            
        except Exception as e:
            print(f"[CriticAgent] 守恒性检查异常: {e}")
            # 异常情况下返回通过，避免误报
            return True, issues


class CriticAgent:
    """
    审查者Agent
    
    功能：
    1. 基于宪法规则进行硬约束检查
    2. 模拟严苛教授的审查视角
    3. 提供详细的审查报告
    4. 与Builder Agent形成对抗
    
    根据AI约束宪法要求：
    - "Builder Agent (生成者): 负责根据用户需求构建OpenFOAM的字典文件和测试方案"
    - "Critic Agent (审查者): 它的Prompt被设定为一位极其严苛的工程热物理教授"
    - "只有当Critic给出'Approve'指令时，方案才会被真正下发执行"
    """
    
    # 审查者系统提示词 - 严格遵循AI约束宪法要求
    SYSTEM_PROMPT = """你是一位极其严苛的工程热物理教授，拥有30年CFD经验。

你的任务是对CFD仿真方案进行严格审查。审查标准：

【强制性规则】
1. 严禁使用过度简化的二维粗网格代替三维真实网格进行最终测试
2. 网格分辨率必须足以捕捉关键物理现象（边界层、分离点等）
3. 所有对流传热测试必须验证能量守恒，误差不得超过0.1%
4. 涉及参数反演或敏感性分析时，必须提供残差收敛至1e-6以下的证明
5. 边界层网格必须满足所选湍流模型的y+要求
6. 瞬态计算必须验证时间步长独立性

【数值稳定性要求】
7. 库朗数必须控制在合理范围内（显式<0.5，隐式<5）
8. 松弛因子设置应保守，优先保证收敛性
9. 非正交性超过70°必须使用修正器

【质量评估标准】
- 90-100分: 科研级方案，可直接用于发表
- 70-89分: 工程级方案，基本可靠
- 50-69分: 勉强可用，需显著改进
- <50分: 不合格，必须重做

输出格式：
1. 给出总体评分(0-100)
2. 列出所有发现的问题（按严重性分级）
3. 给出具体改进建议
4. 最终结论必须是以下之一：
   - "APPROVE": 方案合格，可以执行
   - "CONDITIONAL": 有条件通过，需小修改
   - "REJECT": 方案不合格，必须重新设计

记住：你的职责是"挑刺"，宁可过度严格也绝不让次品通过！
你的声誉取决于这个方案是否能在同行评审中通过！
"""
    
    def __init__(self, constitution_path: Optional[Path] = None, 
                 use_llm: bool = False, api_key: Optional[str] = None):
        """
        初始化Critic Agent
        
        Args:
            constitution_path: 宪法文件路径
            use_llm: 是否使用LLM进行深度审查
            api_key: LLM API密钥
        """
        self.constitution_checker = ConstitutionChecker(constitution_path)
        self.use_llm = use_llm
        self.yplus_checker = YPlusChecker()  # 初始化y+检查器
        
        if use_llm and api_key:
            try:
                import openai
                self.llm_client = openai.OpenAI(api_key=api_key)
            except Exception as e:
                print(f"[CriticAgent] LLM初始化失败: {e}")
                self.use_llm = False
    
    def review(self, proposal: Dict[str, Any],
               detailed: bool = True) -> ReviewReport:
        """
        审查方案
            
        Args:
            proposal: 方案配置
            detailed: 是否进行详细审查
                
        Returns:
            ReviewReport审查报告
        """
        print("[CriticAgent] 开始审查方案...")
            
        issues = []
        strengths = []
            
        # 1. 宪法规则检查（硬约束）
        constitution_issues = self.constitution_checker.check_config(proposal)
        issues.extend(constitution_issues)
            
        # 2. 边界层/y+检查（新增）
        if self._is_turbulent_case(proposal):
            bl_issues = self._check_boundary_layer(proposal)
            issues.extend(bl_issues)
            
        # 3. 分析方案优点
        strengths = self._identify_strengths(proposal)
            
        # 4. 守恒性检查（如果提供了case_dir）
        case_dir = proposal.get("case_dir") or proposal.get("case_path")
        if case_dir:
            conservation_passed, conservation_issues = self.constitution_checker._check_conservation(case_dir)
            issues.extend(conservation_issues)
            if conservation_passed and not conservation_issues:
                strengths.append("守恒性验证通过")
            
        # 5. 计算评分
        score = self._calculate_score(proposal, issues, strengths)
            
        # 6. 确定结论
        verdict = self._determine_verdict(score, issues)
            
        # 7. 生成建议
        recommendations = self._generate_recommendations(issues)
            
        # 8. LLM深度审查（如果启用）
        if self.use_llm and detailed:
            llm_review = self._llm_review(proposal)
            # 可以合并LLM的审查结果
            
        report = ReviewReport(
            verdict=verdict,
            score=score,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations
        )
            
        self._print_review(report)
        return report
    
    def _identify_strengths(self, proposal: Dict[str, Any]) -> List[str]:
        """识别方案优点"""
        strengths = []
        
        geometry = proposal.get('geometry', {})
        resolution = geometry.get('mesh_resolution', {})
        
        # 检查网格数量
        nx = resolution.get('nx', 0)
        ny = resolution.get('ny', 0)
        nz = resolution.get('nz', 1)
        
        if nx >= 50 and ny >= 50:
            strengths.append("网格分辨率充足")
        
        # 检查物理类型与求解器匹配
        physics = proposal.get('physics_type', '')
        solver = proposal.get('solver', {}).get('name', '')
        
        if physics == 'incompressible' and solver in ['icoFoam', 'simpleFoam', 'pimpleFoam']:
            strengths.append("物理类型与求解器匹配")
        
        if physics == 'heatTransfer' and 'buoyant' in solver:
            strengths.append("传热求解器选择正确")
        
        # 检查边界条件完整性
        bc = proposal.get('boundary_conditions', {})
        if bc:
            has_inlet = any('inlet' in name.lower() for name in bc.keys())
            has_outlet = any('outlet' in name.lower() for name in bc.keys())
            if has_inlet and has_outlet:
                strengths.append("边界条件设置完整")
        
        return strengths
    
    def _calculate_score(self, proposal: Dict[str, Any], 
                         issues: List[ReviewIssue],
                         strengths: List[str]) -> float:
        """计算方案评分"""
        base_score = 70.0  # 基础分
        
        # 加分项
        base_score += len(strengths) * 5
        
        # 减分项
        for issue in issues:
            if issue.severity == "critical":
                base_score -= 20
            elif issue.severity == "major":
                base_score -= 10
            elif issue.severity == "minor":
                base_score -= 3
        
        # 限制在0-100范围内
        return max(0.0, min(100.0, base_score))
    
    def _is_turbulent_case(self, proposal: Dict[str, Any]) -> bool:
        """检查是否为湍流算例
        
        Args:
            proposal: 方案配置
            
        Returns:
            bool: 是否为湍流算例
        """
        # 检查是否有湍流模型设置
        turbulence_model = proposal.get('turbulence_model', '')
        if not turbulence_model:
            solver = proposal.get('solver', {})
            turbulence_model = solver.get('turbulence_model', '')
        
        if turbulence_model and turbulence_model not in ['laminar', 'none', '']:
            return True
        
        # 检查雷诺数
        Re = proposal.get('Re', 0)
        if Re == 0:
            physics = proposal.get('physics', {})
            Re = physics.get('Re', 0)
        
        if Re > 4000:  # 雷诺数大于4000通常认为是湍流
            return True
        
        # 检查求解器类型
        solver_name = proposal.get('solver', {}).get('name', '')
        turbulent_solvers = ['simpleFoam', 'pimpleFoam', 'kEpsilon', 'kOmegaSST']
        if any(ts in solver_name for ts in turbulent_solvers):
            return True
        
        return False
    
    def _check_boundary_layer(self, proposal: Dict[str, Any]) -> List[ReviewIssue]:
        """检查边界层网格和y+设置
        
        Args:
            proposal: 方案配置
            
        Returns:
            List[ReviewIssue]: 发现的问题列表
        """
        issues = []
        
        try:
            # 获取必要参数
            Re = proposal.get('Re', 0)
            if Re == 0:
                physics = proposal.get('physics', {})
                Re = physics.get('Re', 0)
            
            if Re <= 0:
                return issues
            
            # 获取特征长度
            L = 1.0
            geometry = proposal.get('geometry', {})
            if geometry:
                L = geometry.get('L', 1.0)
            
            # 获取湍流模型
            turbulence_model = proposal.get('turbulence_model', 'kOmegaSST')
            if not turbulence_model:
                solver = proposal.get('solver', {})
                turbulence_model = solver.get('turbulence_model', 'kOmegaSST')
            
            # 标准化湍流模型名称
            model_map = {
                'k-omega SST': 'kOmegaSST',
                'k-epsilon': 'kEpsilon',
                'kEpsilon': 'kEpsilon',
                'kOmegaSST': 'kOmegaSST',
                'SpalartAllmaras': 'SpalartAllmaras',
                'realizableKE': 'realizableKE',
            }
            turbulence_model = model_map.get(turbulence_model, turbulence_model)
            
            # 估算第一层网格高度（从proposal或尝试解析blockMeshDict）
            first_cell_height = proposal.get('first_cell_height', 0.001)
            if first_cell_height <= 0:
                # 尝试从mesh_resolution估算
                resolution = geometry.get('mesh_resolution', {})
                ny = resolution.get('ny', 50)
                W = geometry.get('dimensions', {}).get('W', 1.0)
                first_cell_height = W / ny
            
            # 执行y+检查
            yplus_result = self.yplus_checker.check_mesh_yplus_quality(
                Re=Re,
                L=L,
                first_cell_height=first_cell_height,
                turbulence_model=turbulence_model
            )
            
            # 根据检查结果生成问题
            compatibility = yplus_result.get('compatibility', {})
            severity = compatibility.get('severity', 'ok')
            
            if severity == 'error':
                issues.append(ReviewIssue(
                    severity="critical",
                    category="mesh",
                    description=f"y+值不兼容: {compatibility.get('recommendation', '')}",
                    suggestion="重新划分网格，调整第一层网格高度以满足湍流模型要求",
                    constitution_reference="边界层网格必须满足所选湍流模型的y+要求"
                ))
            elif severity == 'warning':
                issues.append(ReviewIssue(
                    severity="major",
                    category="mesh",
                    description=f"y+值需要优化: {compatibility.get('recommendation', '')}",
                    suggestion="考虑调整网格以获得更好的边界层解析",
                    constitution_reference="边界层网格y+优化建议"
                ))
            
            # 检查边界层网格层数建议
            advice = yplus_result.get('advice', {})
            n_layers = advice.get('n_layers', 0)
            if n_layers < 5:
                issues.append(ReviewIssue(
                    severity="major",
                    category="mesh",
                    description=f"边界层网格层数可能不足（建议{n_layers}层）",
                    suggestion=f"建议增加边界层膨胀层数至至少10-15层，当前建议为{n_layers}层",
                    constitution_reference="边界层网格分辨率要求"
                ))
            
            # 记录检查结果到proposal（供后续使用）
            proposal['_yplus_check_result'] = yplus_result
            
        except Exception as e:
            print(f"[CriticAgent] 边界层检查失败: {e}")
        
        return issues
    
    def _determine_verdict(self, score: float, 
                           issues: List[ReviewIssue]) -> ReviewVerdict:
        """确定审查结论"""
        critical_count = sum(1 for i in issues if i.severity == "critical")
        major_count = sum(1 for i in issues if i.severity == "major")
        
        # 有关键问题直接拒绝
        if critical_count > 0 or score < 50:
            return ReviewVerdict.REJECT
        
        # 有重要问题但有条件通过
        if major_count > 0 or score < 70:
            return ReviewVerdict.CONDITIONAL
        
        return ReviewVerdict.APPROVE
    
    def _generate_recommendations(self, issues: List[ReviewIssue]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 按类别分组
        by_category = {}
        for issue in issues:
            cat = issue.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(issue)
        
        # 为每个类别生成建议
        for cat, cat_issues in by_category.items():
            critical = [i for i in cat_issues if i.severity == "critical"]
            if critical:
                recommendations.append(f"【{cat}】必须解决{critical[0].suggestion}")
            else:
                major = [i for i in cat_issues if i.severity == "major"]
                if major:
                    recommendations.append(f"【{cat}】建议改进: {major[0].suggestion}")
        
        return recommendations
    
    def _llm_review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM进行深度审查"""
        if not self.use_llm or not hasattr(self, 'llm_client'):
            return {}
        
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"请审查以下CFD方案：\n{json.dumps(proposal, indent=2, ensure_ascii=False)}"}
                ],
                temperature=0.3
            )
            
            review_text = response.choices[0].message.content
            
            return {
                "llm_review": review_text,
                "approved": "APPROVE" in review_text.upper()
            }
            
        except Exception as e:
            print(f"[CriticAgent] LLM审查失败: {e}")
            return {}
    
    def _print_review(self, report: ReviewReport):
        """Print review report"""
        print("\n" + "=" * 70)
        print("Critic Agent Review Report")
        print("=" * 70)
        print(f"Review Time: {report.reviewed_at}")
        print(f"Overall Score: {report.score:.1f}/100")
        print(f"Verdict: {report.verdict.value}")
        print("-" * 70)
        
        if report.strengths:
            print(f"\n[Strengths] ({len(report.strengths)} items):")
            for s in report.strengths:
                print(f"  * {s}")
        
        if report.issues:
            print(f"\n[Issues Found] ({len(report.issues)} items):")
            for issue in report.issues:
                icon = "[C]" if issue.severity == "critical" else "[M]" if issue.severity == "major" else "[m]"
                print(f"  {icon} [{issue.category}] {issue.description}")
                print(f"     Suggestion: {issue.suggestion}")
        
        if report.recommendations:
            print(f"\n[Recommendations]:")
            for rec in report.recommendations:
                print(f"  * {rec}")
        
        print("=" * 70 + "\n")
    
    def interactive_review(self, proposal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        交互式审查
        
        Returns:
            (是否通过, 交互提示)
        """
        report = self.review(proposal)
        
        if report.verdict == ReviewVerdict.APPROVE:
            return True, "方案审查通过！"
        
        elif report.verdict == ReviewVerdict.CONDITIONAL:
            prompt = f"""方案审查结果：有条件通过（评分: {report.score:.1f}/100）

发现{len([i for i in report.issues if i.severity in ['major', 'critical']])}个重要问题需要关注：
"""
            for issue in report.issues[:3]:
                prompt += f"\n• [{issue.severity}] {issue.description}"
            
            prompt += "\n\n建议先修复上述问题，是否继续执行当前方案? (y/n/modify)"
            return False, prompt
        
        else:  # REJECT
            prompt = f"""方案审查结果：不通过（评分: {report.score:.1f}/100）

发现{len(report.issues)}个问题必须解决：
"""
            for issue in report.issues[:5]:
                prompt += f"\n• [{issue.severity}] {issue.description}"
            
            prompt += "\n\n请先修改方案，是否查看详细建议? (y/n)"
            return False, prompt


if __name__ == "__main__":
    # 模块测试
    print("CriticAgent 模块测试")
    print("=" * 70)
    
    # 创建Critic Agent
    critic = CriticAgent(use_llm=False)
    
    # 测试配置
    test_proposal = {
        "task_id": "test_case_001",
        "physics_type": "incompressible",
        "geometry": {
            "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
            "mesh_resolution": {"nx": 10, "ny": 10, "nz": 1}  # 故意设置低分辨率测试
        },
        "solver": {
            "name": "icoFoam",
            "endTime": 0.5,
            "deltaT": 0.01
        },
        "boundary_conditions": {
            "movingWall": {"type": "fixedValue", "value": [1, 0, 0]},
            "fixedWalls": {"type": "noSlip"}
        }
    }
    
    # 执行审查
    report = critic.review(test_proposal)
    
    print(f"\n测试结果:")
    print(f"  通过: {report.is_approved()}")
    print(f"  评分: {report.score:.1f}")
    print(f"  问题数: {len(report.issues)}")
