"""
网格质量自查Agent (Week 5)
基于checkMesh结果进行网格质量评估和自动修复建议
"""

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

try:
    from ..core.openfoam_runner import OpenFOAMRunner
    from ..core.yplus_checker import YPlusChecker
except ImportError:
    # 作为脚本运行时
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
    from openfoam_runner import OpenFOAMRunner
    from yplus_checker import YPlusChecker


class MeshQualityLevel(Enum):
    """网格质量等级"""
    EXCELLENT = "excellent"      # 优秀，无需调整
    GOOD = "good"                # 良好，可以运行
    ACCEPTABLE = "acceptable"    # 可接受，建议优化
    POOR = "poor"                # 较差，需要修复
    CRITICAL = "critical"        # 严重问题，必须修复


@dataclass
class MeshQualityReport:
    """网格质量报告"""
    passed: bool
    quality_level: MeshQualityLevel
    
    # 质量指标
    non_orthogonality_max: float = 0.0
    non_orthogonality_avg: float = 0.0
    skewness_max: float = 0.0
    aspect_ratio_max: float = 0.0
    failed_checks: int = 0
    
    # 统计信息
    total_cells: int = 0
    boundary_faces: int = 0
    internal_faces: int = 0
    
    # 问题详情
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # 建议
    recommendations: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    fix_strategy: Optional[str] = None
    
    # y+相关检查 (新增)
    yplus_check: Optional[Dict] = None
    boundary_layer_advice: Optional[Dict] = None


class MeshQualityChecker:
    """
    网格质量检查器
    
    功能：
    1. 执行checkMesh并深度解析日志
    2. 评估网格质量等级
    3. 提供自动修复建议
    4. 集成自动/人工确认机制
    """
    
    # 质量阈值（根据AI约束宪法和CFD最佳实践）
    THRESHOLDS = {
        'non_orthogonality_warn': 70,
        'non_orthogonality_fail': 85,
        'skewness_warn': 4.0,
        'skewness_fail': 10.0,
        'aspect_ratio_warn': 100,
        'aspect_ratio_fail': 1000,
        'min_cells_2d': 400,      # 宪法要求
        'min_cells_3d': 8000,     # 宪法要求
    }
    
    def __init__(self, case_path: Path, constitution_path: Optional[Path] = None):
        """
        初始化网格质量检查器
        
        Args:
            case_path: 算例路径
            constitution_path: 宪法文件路径（可选）
        """
        self.case_path = Path(case_path)
        self.runner = OpenFOAMRunner(case_path)
        
        # 加载宪法规则
        self.constitution_rules = self._load_constitution(constitution_path)
        
        # 初始化y+检查器 (新增)
        self.yplus_checker = YPlusChecker()
    
    def _load_constitution(self, constitution_path: Optional[Path]) -> Dict:
        """加载宪法规则"""
        if constitution_path is None:
            constitution_path = Path(__file__).parent.parent / "config" / "system_constitution.yaml"
        
        try:
            import yaml
            with open(constitution_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[MeshQualityChecker] 无法加载宪法文件: {e}")
            return {}
    
    def check(self, auto_fix: bool = False) -> MeshQualityReport:
        """
        执行网格质量检查
        
        Args:
            auto_fix: 是否尝试自动修复
            
        Returns:
            MeshQualityReport质量报告
        """
        print(f"[MeshQualityChecker] 开始网格质量检查: {self.case_path}")
        
        # 执行checkMesh
        success, log, basic_metrics = self.runner.run_checkmesh()
        
        # 深度解析日志
        detailed_metrics = self._parse_detailed_log(log)
        detailed_metrics.update(basic_metrics)
        
        # 评估质量等级
        quality_level = self._assess_quality_level(detailed_metrics)
        
        # 生成问题列表
        warnings, errors = self._identify_issues(detailed_metrics)
        
        # 生成建议
        recommendations = self._generate_recommendations(
            detailed_metrics, warnings, errors
        )
        
        # 判断是否可以自动修复
        auto_fixable, fix_strategy = self._determine_fix_strategy(
            detailed_metrics, errors
        )
        
        # y+检查 (新增) - 如果是湍流问题
        yplus_check = None
        boundary_layer_advice = None
        if self._is_turbulent_case():
            yplus_check = self._check_yplus()
            if yplus_check:
                boundary_layer_advice = yplus_check.get('advice')
                # 将y+检查结果整合到warnings/errors中
                if yplus_check.get('compatibility', {}).get('severity') == 'error':
                    errors.append(f"y+检查: {yplus_check['compatibility']['recommendation']}")
                elif yplus_check.get('compatibility', {}).get('severity') == 'warning':
                    warnings.append(f"y+检查: {yplus_check['compatibility']['recommendation']}")
                if yplus_check.get('advice'):
                    recommendations.append(f"边界层建议: {yplus_check['advice']['explanation'][:100]}...")
        
        report = MeshQualityReport(
            passed=success and len(errors) == 0,
            quality_level=quality_level,
            non_orthogonality_max=detailed_metrics.get('non_orthogonality_max', 0),
            non_orthogonality_avg=detailed_metrics.get('non_orthogonality_avg', 0),
            skewness_max=detailed_metrics.get('skewness_max', 0),
            aspect_ratio_max=detailed_metrics.get('aspect_ratio_max', 0),
            failed_checks=detailed_metrics.get('failed_checks', 0),
            total_cells=detailed_metrics.get('total_cells', 0),
            boundary_faces=detailed_metrics.get('boundary_faces', 0),
            internal_faces=detailed_metrics.get('internal_faces', 0),
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            auto_fixable=auto_fixable,
            fix_strategy=fix_strategy,
            yplus_check=yplus_check,
            boundary_layer_advice=boundary_layer_advice
        )
        
        # 尝试自动修复
        if auto_fix and auto_fixable and fix_strategy:
            print(f"[MeshQualityChecker] 尝试自动修复: {fix_strategy}")
            fix_success = self._apply_fix(fix_strategy)
            if fix_success:
                # 重新检查
                print("[MeshQualityChecker] 修复成功，重新检查...")
                return self.check(auto_fix=False)  # 避免递归
            else:
                print("[MeshQualityChecker] 自动修复失败")
                report.recommendations.append("自动修复失败，建议人工检查")
        
        self._print_report(report)
        return report
    
    def _is_turbulent_case(self) -> bool:
        """检查是否为湍流算例
        
        通过检查turbulenceProperties文件或case_info.json判断
        """
        # 检查turbulenceProperties文件
        turb_props_path = self.case_path / "constant" / "turbulenceProperties"
        if turb_props_path.exists():
            content = turb_props_path.read_text(encoding='utf-8')
            if 'RAS' in content or 'LES' in content:
                return True
        
        # 检查case_info.json
        case_info_path = self.case_path / ".case_info.json"
        if case_info_path.exists():
            try:
                import json
                with open(case_info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                # 检查是否有湍流模型信息
                if info.get('turbulence_model') or info.get('physics', {}).get('turbulence'):
                    return True
                # 检查雷诺数
                Re = info.get('Re', 0)
                if Re > 4000:  # 雷诺数大于4000通常认为是湍流
                    return True
            except Exception:
                pass
        
        return False
    
    def _check_yplus(self) -> Optional[Dict]:
        """检查y+值和边界层网格质量
        
        Returns:
            Dict: y+检查结果，包含估算值、兼容性检查和建议
        """
        try:
            # 从case_info.json获取参数
            case_info_path = self.case_path / ".case_info.json"
            if not case_info_path.exists():
                return None
            
            import json
            with open(case_info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
            
            # 获取雷诺数和特征长度
            Re = info.get('Re', 0)
            if Re == 0:
                Re = info.get('physics', {}).get('Re', 0)
            
            if Re <= 0:
                return None
            
            # 获取特征长度
            L = info.get('L', 1.0)
            if 'geometry' in info:
                L = info['geometry'].get('L', L)
            
            # 获取湍流模型
            turbulence_model = info.get('turbulence_model', 'kOmegaSST')
            if 'physics' in info:
                turbulence_model = info['physics'].get('turbulence_model', turbulence_model)
            
            # 估算第一层网格高度（从blockMeshDict解析）
            first_cell_height = self._estimate_first_cell_height()
            
            # 执行y+检查
            result = self.yplus_checker.check_mesh_yplus_quality(
                Re=Re,
                L=L,
                first_cell_height=first_cell_height,
                turbulence_model=turbulence_model
            )
            
            return result
            
        except Exception as e:
            print(f"[MeshQualityChecker] y+检查失败: {e}")
            return None
    
    def _estimate_first_cell_height(self) -> float:
        """估算第一层网格高度
        
        从blockMeshDict解析网格参数估算
        """
        blockmesh_path = self.case_path / "system" / "blockMeshDict"
        if not blockmesh_path.exists():
            return 0.001  # 默认值
        
        try:
            content = blockmesh_path.read_text(encoding='utf-8')
            
            # 尝试解析simpleGrading或multiGrading
            # 查找hex块定义
            hex_pattern = r'hex\s*\([^)]+\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)'
            hex_match = re.search(hex_pattern, content)
            
            if not hex_match:
                return 0.001
            
            nx = int(hex_match.group(1))
            ny = int(hex_match.group(2))
            nz = int(hex_match.group(3))
            
            # 查找vertices获取域尺寸
            # 简化处理：假设标准cavity类型域
            # 实际应用中需要更复杂的解析
            
            # 查找simpleGrading
            grading_pattern = r'simpleGrading\s*\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)'
            grading_match = re.search(grading_pattern, content)
            
            if grading_match:
                # 有渐变网格，估算第一层高度
                # 假设y方向是壁面法向
                grading_y = float(grading_match.group(2))
                # 简化估算：假设域高为1，使用渐变比估算第一层高度
                # 这是一个粗略估算
                if grading_y != 1.0:
                    # 几何级数估算
                    # 总高度 = h1 * (r^n - 1) / (r - 1)
                    # 近似估算第一层高度
                    return 1.0 / ny / (grading_y ** 0.5) if grading_y > 1 else 1.0 / ny
            
            # 均匀网格
            return 1.0 / ny
            
        except Exception as e:
            print(f"[MeshQualityChecker] 估算第一层网格高度失败: {e}")
            return 0.001
    
    def _parse_detailed_log(self, log: str) -> Dict[str, Any]:
        """深度解析checkMesh日志"""
        metrics = {}
        
        # 提取网格统计
        cells_match = re.search(r'nCells:\s*(\d+)', log, re.IGNORECASE)
        if cells_match:
            metrics['total_cells'] = int(cells_match.group(1))
        
        faces_match = re.search(r'nFaces:\s*(\d+)', log, re.IGNORECASE)
        if faces_match:
            metrics['total_faces'] = int(faces_match.group(1))
        
        internal_match = re.search(r'nInternalFaces:\s*(\d+)', log, re.IGNORECASE)
        if internal_match:
            metrics['internal_faces'] = int(internal_match.group(1))
        
        boundary_match = re.search(r'nBoundaryFaces:\s*(\d+)', log, re.IGNORECASE)
        if boundary_match:
            metrics['boundary_faces'] = int(boundary_match.group(1))
        
        # 提取非正交性详细信息
        non_ortho_pattern = r'Non-orthogonality.*?Max\s*=\s*([\d.]+).*?average\s*=\s*([\d.]+)'
        non_ortho_match = re.search(non_ortho_pattern, log, re.DOTALL | re.IGNORECASE)
        if non_ortho_match:
            metrics['non_orthogonality_max'] = float(non_ortho_match.group(1))
            metrics['non_orthogonality_avg'] = float(non_ortho_match.group(2))
        
        # 提取偏斜度
        skewness_match = re.search(r'Max\s+skewness\s*=\s*([\d.]+)', log, re.IGNORECASE)
        if skewness_match:
            metrics['skewness_max'] = float(skewness_match.group(1))
        
        # 提取长宽比
        aspect_match = re.search(r'Max\s+aspect\s+ratio\s*=\s*([\d.]+)', log, re.IGNORECASE)
        if aspect_match:
            metrics['aspect_ratio_max'] = float(aspect_match.group(1))
        
        # 提取失败检查数
        failed_match = re.search(r'Failed\s+(\d+)\s+mesh', log, re.IGNORECASE)
        if failed_match:
            metrics['failed_checks'] = int(failed_match.group(1))
        
        # 提取具体失败项
        if metrics.get('failed_checks', 0) > 0:
            failed_items = re.findall(r'\*\*\*Error.*?in\s+(.+?)(?:\n|$)', log)
            metrics['failed_items'] = failed_items
        
        # 提取警告信息
        warnings = re.findall(r'\*\*\*Warning.*?(.+?)(?:\n|$)', log)
        metrics['warnings'] = warnings
        
        return metrics
    
    def _assess_quality_level(self, metrics: Dict[str, Any]) -> MeshQualityLevel:
        """评估网格质量等级"""
        non_ortho_max = metrics.get('non_orthogonality_max', 0)
        skewness_max = metrics.get('skewness_max', 0)
        aspect_ratio_max = metrics.get('aspect_ratio_max', 0)
        failed_checks = metrics.get('failed_checks', 0)
        
        # 严重问题
        if failed_checks > 0 or non_ortho_max > self.THRESHOLDS['non_orthogonality_fail']:
            return MeshQualityLevel.CRITICAL
        
        if skewness_max > self.THRESHOLDS['skewness_fail'] or \
           aspect_ratio_max > self.THRESHOLDS['aspect_ratio_fail']:
            return MeshQualityLevel.CRITICAL
        
        # 较差
        if non_ortho_max > self.THRESHOLDS['non_orthogonality_warn'] or \
           skewness_max > self.THRESHOLDS['skewness_warn']:
            return MeshQualityLevel.POOR
        
        if aspect_ratio_max > self.THRESHOLDS['aspect_ratio_warn']:
            return MeshQualityLevel.POOR
        
        # 可接受
        if non_ortho_max > 50 or skewness_max > 2:
            return MeshQualityLevel.ACCEPTABLE
        
        # 良好
        if non_ortho_max > 30 or skewness_max > 1:
            return MeshQualityLevel.GOOD
        
        # 优秀
        return MeshQualityLevel.EXCELLENT
    
    def _identify_issues(self, metrics: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """识别问题"""
        warnings = []
        errors = []
        
        non_ortho_max = metrics.get('non_orthogonality_max', 0)
        skewness_max = metrics.get('skewness_max', 0)
        aspect_ratio_max = metrics.get('aspect_ratio_max', 0)
        failed_checks = metrics.get('failed_checks', 0)
        
        # 检查失败项
        if failed_checks > 0:
            failed_items = metrics.get('failed_items', [])
            for item in failed_items:
                errors.append(f"网格检查失败: {item}")
        
        # 非正交性检查
        if non_ortho_max > self.THRESHOLDS['non_orthogonality_fail']:
            errors.append(f"非正交性过高({non_ortho_max:.1f}°)，可能导致数值不稳定")
        elif non_ortho_max > self.THRESHOLDS['non_orthogonality_warn']:
            warnings.append(f"非正交性偏高({non_ortho_max:.1f}°)，建议使用非正交修正器")
        
        # 偏斜度检查
        if skewness_max > self.THRESHOLDS['skewness_fail']:
            errors.append(f"偏斜度过高({skewness_max:.2f})")
        elif skewness_max > self.THRESHOLDS['skewness_warn']:
            warnings.append(f"偏斜度偏高({skewness_max:.2f})")
        
        # 长宽比检查
        if aspect_ratio_max > self.THRESHOLDS['aspect_ratio_fail']:
            errors.append(f"长宽比过高({aspect_ratio_max:.1f})")
        elif aspect_ratio_max > self.THRESHOLDS['aspect_ratio_warn']:
            warnings.append(f"长宽比偏高({aspect_ratio_max:.1f})")
        
        # 网格数量检查（宪法要求）
        total_cells = metrics.get('total_cells', 0)
        # 简单判断：如果total_cells为0，可能未正确解析
        if total_cells > 0:
            # 这里假设是2D还是3D需要其他信息，简化处理
            if total_cells < 100:
                warnings.append(f"网格数量({total_cells})可能不足")
        
        return warnings, errors
    
    def _generate_recommendations(self, metrics: Dict[str, Any], 
                                   warnings: List[str], 
                                   errors: List[str]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        non_ortho_max = metrics.get('non_orthogonality_max', 0)
        
        # 非正交性问题建议
        if non_ortho_max > self.THRESHOLDS['non_orthogonality_warn']:
            recommendations.append(
                "建议在fvSolution中添加非正交修正器: "
                "nNonOrthogonalCorrectors 1;"
            )
        
        if non_ortho_max > self.THRESHOLDS['non_orthogonality_fail']:
            recommendations.append(
                "非正交性严重超标，建议: 1) 重新划分网格 "
                "2) 使用更精细的网格 3) 考虑使用多面体网格"
            )
        
        # 偏斜度问题建议
        if metrics.get('skewness_max', 0) > self.THRESHOLDS['skewness_warn']:
            recommendations.append(
                "偏斜度偏高，建议检查网格生成参数，"
                "避免过度拉伸或扭曲的单元"
            )
        
        # 长宽比问题建议
        if metrics.get('aspect_ratio_max', 0) > self.THRESHOLDS['aspect_ratio_warn']:
            recommendations.append(
                "长宽比偏高，建议在边界层区域渐进式增加网格密度"
            )
        
        # 一般性建议
        if not recommendations and not warnings and not errors:
            recommendations.append("网格质量良好，可以开始计算")
        
        return recommendations
    
    def _determine_fix_strategy(self, metrics: Dict[str, Any], 
                                 errors: List[str]) -> Tuple[bool, Optional[str]]:
        """确定是否可以自动修复"""
        non_ortho_max = metrics.get('non_orthogonality_max', 0)
        
        # 如果只有非正交性问题，可以自动修复
        if non_ortho_max > self.THRESHOLDS['non_orthogonality_warn'] and \
           len(errors) == 0:
            return True, "add_nonorthogonal_correctors"
        
        # 如果有严重错误，无法自动修复
        if len(errors) > 0:
            return False, None
        
        return False, None
    
    def _apply_fix(self, strategy: str) -> bool:
        """应用自动修复策略"""
        if strategy == "add_nonorthogonal_correctors":
            return self._fix_add_nonorthogonal_correctors()
        
        return False
    
    def _fix_add_nonorthogonal_correctors(self) -> bool:
        """添加非正交修正器"""
        fv_solution_path = self.case_path / "system" / "fvSolution"
        
        if not fv_solution_path.exists():
            print(f"[MeshQualityChecker] 找不到fvSolution: {fv_solution_path}")
            return False
        
        try:
            content = fv_solution_path.read_text(encoding='utf-8')
            
            # 检查是否已有nNonOrthogonalCorrectors
            if 'nNonOrthogonalCorrectors' in content:
                # 增加修正器数量
                content = re.sub(
                    r'nNonOrthogonalCorrectors\s*\d+;',
                    'nNonOrthogonalCorrectors 2;',
                    content
                )
            else:
                # 在PIMPLE或SIMPLE字典中添加
                if 'PIMPLE' in content:
                    content = re.sub(
                        r'(PIMPLE\s*\{[^}]*)(\})',
                        r'\1    nNonOrthogonalCorrectors 1;\n}',
                        content
                    )
                elif 'SIMPLE' in content:
                    content = re.sub(
                        r'(SIMPLE\s*\{[^}]*)(\})',
                        r'\1    nNonOrthogonalCorrectors 1;\n}',
                        content
                    )
            
            fv_solution_path.write_text(content, encoding='utf-8')
            print("[MeshQualityChecker] 已添加非正交修正器")
            return True
            
        except Exception as e:
            print(f"[MeshQualityChecker] 修复失败: {e}")
            return False
    
    def _print_report(self, report: MeshQualityReport):
        """打印报告"""
        print("\n" + "=" * 60)
        print("网格质量检查报告")
        print("=" * 60)
        print(f"质量等级: {report.quality_level.value.upper()}")
        print(f"通过状态: {'✓ 通过' if report.passed else '✗ 未通过'}")
        print(f"\n网格统计:")
        print(f"  总单元数: {report.total_cells}")
        print(f"  边界 faces: {report.boundary_faces}")
        print(f"  内部 faces: {report.internal_faces}")
        print(f"\n质量指标:")
        print(f"  最大非正交性: {report.non_orthogonality_max:.2f}°")
        print(f"  平均非正交性: {report.non_orthogonality_avg:.2f}°")
        print(f"  最大偏斜度: {report.skewness_max:.2f}")
        print(f"  最大长宽比: {report.aspect_ratio_max:.2f}")
        print(f"  失败检查数: {report.failed_checks}")
        
        if report.errors:
            print(f"\n✗ 错误 ({len(report.errors)}项):")
            for error in report.errors:
                print(f"  - {error}")
        
        if report.warnings:
            print(f"\n⚠ 警告 ({len(report.warnings)}项):")
            for warning in report.warnings:
                print(f"  - {warning}")
        
        if report.recommendations:
            print(f"\n💡 建议:")
            for rec in report.recommendations:
                print(f"  - {rec}")
        
        if report.auto_fixable:
            print(f"\n🔧 可自动修复: 是")
            print(f"   修复策略: {report.fix_strategy}")
        
        print("=" * 60 + "\n")
    
    def generate_interactive_prompt(self, report: MeshQualityReport) -> str:
        """生成交互式提示"""
        if report.quality_level in [MeshQualityLevel.CRITICAL, MeshQualityLevel.POOR]:
            prompt = f"""检测到网格质量问题！

质量等级: {report.quality_level.value}
最大非正交性: {report.non_orthogonality_max:.1f}° (建议<70°)

问题:
"""
            for error in report.errors[:3]:  # 最多显示3个
                prompt += f"  - {error}\n"
            
            if report.auto_fixable:
                prompt += "\n我可以尝试自动修复这些问题（添加非正交修正器）。\n是否同意自动修复? (y/n)"
            else:
                prompt += "\n建议重新划分网格或调整网格参数。\n是否继续尝试计算? (y/n)"
            
            return prompt
        
        return "网格质量检查通过，可以开始计算。"


class MeshAutoFixer:
    """网格自动修复器"""
    
    def __init__(self, case_path: Path):
        self.case_path = Path(case_path)
    
    def fix_non_orthogonality(self, severity: str = "moderate") -> bool:
        """
        修复非正交性问题
        
        Args:
            severity: 严重程度 ("mild", "moderate", "severe")
        """
        fv_solution_path = self.case_path / "system" / "fvSolution"
        
        if not fv_solution_path.exists():
            return False
        
        try:
            content = fv_solution_path.read_text(encoding='utf-8')
            
            # 根据严重程度设置修正器数量
            num_correctors = {"mild": 1, "moderate": 2, "severe": 3}
            n_correctors = num_correctors.get(severity, 1)
            
            # 修改或添加nNonOrthogonalCorrectors
            if 'nNonOrthogonalCorrectors' in content:
                content = re.sub(
                    r'nNonOrthogonalCorrectors\s*\d+;',
                    f'nNonOrthogonalCorrectors {n_correctors};',
                    content
                )
            else:
                # 在PIMPLE字典中添加
                content = self._add_to_dict(content, 'PIMPLE', 
                    f'nNonOrthogonalCorrectors {n_correctors};')
            
            fv_solution_path.write_text(content, encoding='utf-8')
            return True
            
        except Exception as e:
            print(f"[MeshAutoFixer] 修复失败: {e}")
            return False
    
    def _add_to_dict(self, content: str, dict_name: str, entry: str) -> str:
        """向字典添加条目"""
        pattern = rf'({dict_name}\s*\{{[^}}]*)(\}})'
        replacement = rf'\1    {entry}\n}}'
        return re.sub(pattern, replacement, content, flags=re.DOTALL)


if __name__ == "__main__":
    # 测试
    print("MeshQualityChecker 模块测试")
    print("=" * 60)
    
    # 模拟测试
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test_case"
        case_path.mkdir()
        
        # 创建基本目录结构
        for d in ["0", "constant", "system", "logs"]:
            (case_path / d).mkdir(exist_ok=True)
        
        checker = MeshQualityChecker(case_path)
        print(f"初始化完成: {checker.case_path}")
        print(f"宪法规则: {list(checker.constitution_rules.keys())}")
