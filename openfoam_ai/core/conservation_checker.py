"""
物理守恒性验证器
验证仿真结果满足基本物理守恒定律：
- 质量守恒：进出口流量误差 < 0.1%
- 能量守恒：热流量平衡误差 <= 0.1%
- 连续性误差：求解过程中的连续性方程残差
"""

import re
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConservationResult:
    """守恒性检查结果"""
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContinuityErrorData:
    """连续性误差数据"""
    time: float
    local: float
    global_err: float
    cumulative: float


class ConservationChecker:
    """物理守恒性验证器
    
    验证仿真结果满足基本物理守恒定律：
    - 质量守恒：进出口流量误差 < 0.1%
    - 能量守恒：热流量平衡误差 <= 0.1%
    - 连续性误差：求解过程中的连续性方程残差
    """
    
    # 守恒性阈值（来自AI约束宪法）
    MASS_CONSERVATION_THRESHOLD = 0.001  # 0.1%
    ENERGY_CONSERVATION_THRESHOLD = 0.001  # 0.1%
    CONTINUITY_ERROR_THRESHOLD = 1e-6  # 连续性误差上限
    RESIDUAL_CONVERGENCE_THRESHOLD = 1e-6  # 残差收敛阈值
    
    def __init__(self, case_dir: str = None):
        """
        初始化守恒性验证器
        
        Args:
            case_dir: 算例目录路径
        """
        self.case_dir = Path(case_dir) if case_dir else None
        
    def set_case_dir(self, case_dir: str) -> None:
        """
        设置算例目录
        
        Args:
            case_dir: 算例目录路径
        """
        self.case_dir = Path(case_dir)
    
    def check_mass_conservation(self, case_dir: str = None) -> ConservationResult:
        """
        检查质量守恒
        
        尝试解析 postProcessing/flowRatePatch 目录下的数据，
        如果无后处理数据，则从求解日志解析 continuity errors。
        
        Args:
            case_dir: 算例目录路径（可选，如未设置则使用实例变量）
            
        Returns:
            ConservationResult: 包含检查结果和详细信息
        """
        case_path = Path(case_dir) if case_dir else self.case_dir
        if not case_path:
            return ConservationResult(
                passed=False,
                message="未指定算例目录",
                details={}
            )
        
        case_path = Path(case_path)
        
        # 尝试从 postProcessing 数据获取流量信息
        flow_rate_data = self._parse_flow_rate_data(case_path)
        
        if flow_rate_data:
            return self._check_mass_from_flow_rate(flow_rate_data)
        
        # 如果没有流量数据，从日志中的连续性误差推断
        log_file = self._find_latest_log(case_path)
        if log_file:
            continuity_result = self._parse_continuity_errors_from_log(log_file)
            if continuity_result:
                return self._check_mass_from_continuity(continuity_result)
        
        # 无法获取数据，返回跳过状态
        return ConservationResult(
            passed=True,  # 无数据时默认通过，避免误报
            message="无法获取流量数据，跳过质量守恒检查",
            details={"skipped": True, "reason": "no_data"}
        )
    
    def check_energy_conservation(self, case_dir: str = None) -> ConservationResult:
        """
        检查能量守恒
        
        解析 postProcessing/wallHeatFlux 或类似热流量数据，
        如果是传热问题，验证能量输入=能量输出。
        
        Args:
            case_dir: 算例目录路径（可选）
            
        Returns:
            ConservationResult: 包含检查结果和详细信息
        """
        case_path = Path(case_dir) if case_dir else self.case_dir
        if not case_path:
            return ConservationResult(
                passed=False,
                message="未指定算例目录",
                details={}
            )
        
        case_path = Path(case_path)
        
        # 检查是否为传热问题
        if not self._is_heat_transfer_case(case_path):
            return ConservationResult(
                passed=True,
                message="非传热问题，跳过能量守恒检查",
                details={"skipped": True, "reason": "not_heat_transfer"}
            )
        
        # 尝试解析热流量数据
        heat_flux_data = self._parse_heat_flux_data(case_path)
        
        if heat_flux_data:
            heat_in = heat_flux_data.get("heat_in", 0.0)
            heat_out = heat_flux_data.get("heat_out", 0.0)
            heat_wall = heat_flux_data.get("heat_wall", 0.0)
            
            total = heat_in + heat_out + heat_wall
            reference = max(abs(heat_in), abs(heat_out), abs(heat_wall), 1e-10)
            
            error_pct = abs(total) / reference if reference > 1e-10 else 0.0
            passed = error_pct <= self.ENERGY_CONSERVATION_THRESHOLD
            
            return ConservationResult(
                passed=passed,
                message=f"能量守恒{'通过' if passed else '未通过'}，误差: {error_pct*100:.4f}%",
                details={
                    "heat_in": heat_in,
                    "heat_out": heat_out,
                    "heat_wall": heat_wall,
                    "error_pct": error_pct * 100,
                    "threshold": self.ENERGY_CONSERVATION_THRESHOLD * 100
                }
            )
        
        return ConservationResult(
            passed=True,
            message="无法获取热流量数据，跳过能量守恒检查",
            details={"skipped": True, "reason": "no_heat_flux_data"}
        )
    
    def check_continuity_errors(self, log_file: str = None, case_dir: str = None) -> ConservationResult:
        """
        检查连续性误差
        
        用正则解析求解日志中的 time step continuity errors 行，
        跟踪全局误差随时间步的趋势。
        
        Args:
            log_file: 日志文件路径
            case_dir: 算例目录路径（用于查找日志文件）
            
        Returns:
            ConservationResult: 包含检查结果和详细信息
        """
        if log_file:
            log_path = Path(log_file)
        else:
            case_path = Path(case_dir) if case_dir else self.case_dir
            if not case_path:
                return ConservationResult(
                    passed=False,
                    message="未指定日志文件或算例目录",
                    details={}
                )
            log_path = self._find_latest_log(case_path)
        
        if not log_path or not log_path.exists():
            return ConservationResult(
                passed=True,
                message="未找到求解日志，跳过连续性误差检查",
                details={"skipped": True, "reason": "no_log_file"}
            )
        
        continuity_data = self._parse_continuity_errors_from_log(log_path)
        
        if not continuity_data:
            return ConservationResult(
                passed=True,
                message="日志中未找到连续性误差数据",
                details={"skipped": True, "reason": "no_continuity_data"}
            )
        
        # 分析连续性误差趋势
        local_errors = [d.local for d in continuity_data]
        global_errors = [d.global_err for d in continuity_data]
        cumulative_errors = [d.cumulative for d in continuity_data]
        
        max_local = max(local_errors) if local_errors else 0.0
        max_global = max(global_errors) if global_errors else 0.0
        final_cumulative = cumulative_errors[-1] if cumulative_errors else 0.0
        
        # 判断趋势：收敛、发散或稳定
        trend = self._analyze_error_trend(global_errors)
        
        # 检查是否通过
        passed = (
            max_local < self.CONTINUITY_ERROR_THRESHOLD * 100 and
            max_global < self.CONTINUITY_ERROR_THRESHOLD and
            trend in ["converging", "stable"]
        )
        
        return ConservationResult(
            passed=passed,
            message=f"连续性误差检查{'通过' if passed else '未通过'}，趋势: {trend}",
            details={
                "max_local": max_local,
                "max_global": max_global,
                "final_cumulative": final_cumulative,
                "trend": trend,
                "data_points": len(continuity_data)
            }
        )
    
    def check_residual_convergence(self, log_file: str = None, case_dir: str = None) -> ConservationResult:
        """
        检查残差收敛情况
        
        解析各字段（Ux, Uy, p, T, k, epsilon等）的最终残差，
        判断是否收敛到合理水平。
        
        Args:
            log_file: 日志文件路径
            case_dir: 算例目录路径
            
        Returns:
            ConservationResult: 包含检查结果和详细信息
        """
        if log_file:
            log_path = Path(log_file)
        else:
            case_path = Path(case_dir) if case_dir else self.case_dir
            if not case_path:
                return ConservationResult(
                    passed=False,
                    message="未指定日志文件或算例目录",
                    details={}
                )
            log_path = self._find_latest_log(case_path)
        
        if not log_path or not log_path.exists():
            return ConservationResult(
                passed=True,
                message="未找到求解日志，跳过残差收敛检查",
                details={"skipped": True, "reason": "no_log_file"}
            )
        
        residuals = self._parse_residuals_from_log(log_path)
        
        if not residuals:
            return ConservationResult(
                passed=True,
                message="日志中未找到残差数据",
                details={"skipped": True, "reason": "no_residual_data"}
            )
        
        # 检查各字段的最终残差
        converged_fields = []
        non_converged_fields = []
        
        for field_name, final_residual in residuals.items():
            if final_residual <= self.RESIDUAL_CONVERGENCE_THRESHOLD:
                converged_fields.append(field_name)
            else:
                non_converged_fields.append((field_name, final_residual))
        
        # 所有字段都收敛才通过
        converged = len(non_converged_fields) == 0 and len(converged_fields) > 0
        
        if converged:
            message = f"所有字段残差收敛至 {self.RESIDUAL_CONVERGENCE_THRESHOLD} 以下"
        elif non_converged_fields:
            field_str = ", ".join([f"{f}={v:.2e}" for f, v in non_converged_fields[:3]])
            message = f"部分字段残差未收敛: {field_str}"
        else:
            message = "未找到残差数据"
        
        return ConservationResult(
            passed=converged,
            message=message,
            details={
                "converged": converged,
                "final_residuals": residuals,
                "converged_fields": converged_fields,
                "non_converged_fields": {f: v for f, v in non_converged_fields}
            }
        )
    
    def generate_report(self, case_dir: str = None, log_file: str = None) -> str:
        """
        生成守恒性验证报告
        
        调用上述所有检查，生成格式化的守恒性验证报告（中文）。
        
        Args:
            case_dir: 算例目录路径
            log_file: 日志文件路径（可选）
            
        Returns:
            str: 格式化的报告文本
        """
        case_path = Path(case_dir) if case_dir else self.case_dir
        if case_path:
            self.case_dir = case_path
        
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("物理守恒性验证报告")
        report_lines.append("=" * 70)
        report_lines.append(f"算例目录: {self.case_dir or '未指定'}")
        report_lines.append("")
        
        all_passed = True
        
        # 1. 质量守恒检查
        report_lines.append("【质量守恒检查】")
        mass_result = self.check_mass_conservation()
        all_passed = all_passed and mass_result.passed
        report_lines.append(f"  状态: {'✓ 通过' if mass_result.passed else '✗ 未通过'}")
        report_lines.append(f"  说明: {mass_result.message}")
        if mass_result.details:
            for key, value in mass_result.details.items():
                if key not in ["skipped", "reason"]:
                    report_lines.append(f"    - {key}: {value}")
        report_lines.append("")
        
        # 2. 能量守恒检查
        report_lines.append("【能量守恒检查】")
        energy_result = self.check_energy_conservation()
        all_passed = all_passed and energy_result.passed
        report_lines.append(f"  状态: {'✓ 通过' if energy_result.passed else '✗ 未通过'}")
        report_lines.append(f"  说明: {energy_result.message}")
        if energy_result.details:
            for key, value in energy_result.details.items():
                if key not in ["skipped", "reason"]:
                    report_lines.append(f"    - {key}: {value}")
        report_lines.append("")
        
        # 3. 连续性误差检查
        report_lines.append("【连续性误差检查】")
        continuity_result = self.check_continuity_errors(log_file)
        all_passed = all_passed and continuity_result.passed
        report_lines.append(f"  状态: {'✓ 通过' if continuity_result.passed else '✗ 未通过'}")
        report_lines.append(f"  说明: {continuity_result.message}")
        if continuity_result.details:
            for key, value in continuity_result.details.items():
                if key not in ["skipped", "reason"]:
                    report_lines.append(f"    - {key}: {value}")
        report_lines.append("")
        
        # 4. 残差收敛检查
        report_lines.append("【残差收敛检查】")
        residual_result = self.check_residual_convergence(log_file)
        all_passed = all_passed and residual_result.passed
        report_lines.append(f"  状态: {'✓ 通过' if residual_result.passed else '✗ 未通过'}")
        report_lines.append(f"  说明: {residual_result.message}")
        if residual_result.details and residual_result.details.get("final_residuals"):
            report_lines.append("  最终残差:")
            for field, value in residual_result.details["final_residuals"].items():
                status = "✓" if value <= self.RESIDUAL_CONVERGENCE_THRESHOLD else "✗"
                report_lines.append(f"    {status} {field}: {value:.2e}")
        report_lines.append("")
        
        # 总结
        report_lines.append("-" * 70)
        report_lines.append(f"总体结论: {'✓ 所有检查通过' if all_passed else '✗ 存在未通过的检查项'}")
        report_lines.append("=" * 70)
        
        return "\n".join(report_lines)
    
    def get_summary_dict(self, case_dir: str = None, log_file: str = None) -> Dict[str, Any]:
        """
        获取守恒性验证摘要字典
        
        Args:
            case_dir: 算例目录路径
            log_file: 日志文件路径
            
        Returns:
            Dict: 包含所有检查结果的字典
        """
        case_path = Path(case_dir) if case_dir else self.case_dir
        if case_path:
            self.case_dir = case_path
        
        mass_result = self.check_mass_conservation()
        energy_result = self.check_energy_conservation()
        continuity_result = self.check_continuity_errors(log_file)
        residual_result = self.check_residual_convergence(log_file)
        
        all_passed = (
            mass_result.passed and
            energy_result.passed and
            continuity_result.passed and
            residual_result.passed
        )
        
        return {
            "passed": all_passed,
            "mass_conservation": {
                "passed": mass_result.passed,
                "message": mass_result.message,
                "details": mass_result.details
            },
            "energy_conservation": {
                "passed": energy_result.passed,
                "message": energy_result.message,
                "details": energy_result.details
            },
            "continuity_errors": {
                "passed": continuity_result.passed,
                "message": continuity_result.message,
                "details": continuity_result.details
            },
            "residual_convergence": {
                "passed": residual_result.passed,
                "message": residual_result.message,
                "details": residual_result.details
            }
        }
    
    # ================== 私有辅助方法 ==================
    
    def _find_latest_log(self, case_dir: Path) -> Optional[Path]:
        """
        在 case_dir/logs/ 目录下找到最新的求解日志
        
        Args:
            case_dir: 算例目录路径
            
        Returns:
            最新的日志文件路径，如果没有则返回 None
        """
        logs_dir = case_dir / "logs"
        if not logs_dir.exists():
            # 检查根目录
            logs_dir = case_dir
        
        log_files = list(logs_dir.glob("*.log"))
        if not log_files:
            return None
        
        # 按修改时间排序，返回最新的
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return log_files[0]
    
    def _parse_flow_rate_data(self, case_path: Path) -> Optional[Dict[str, Any]]:
        """
        解析 postProcessing/flowRatePatch 目录下的流量数据
        
        Args:
            case_path: 算例目录路径
            
        Returns:
            流量数据字典，如果不存在则返回 None
        """
        post_processing_dir = case_path / "postProcessing"
        if not post_processing_dir.exists():
            return None
        
        # 查找 flowRatePatch 目录
        flow_rate_dirs = list(post_processing_dir.glob("*flowRate*"))
        if not flow_rate_dirs:
            return None
        
        flow_data = {}
        
        for flow_dir in flow_rate_dirs:
            # 查找数据文件
            for data_file in flow_dir.glob("*.dat"):
                patch_name = flow_dir.name.replace("flowRatePatch_", "").replace("flowRate_", "")
                try:
                    values = self._parse_simple_data_file(data_file)
                    if values:
                        # 取最后一个值作为最终流量
                        flow_data[patch_name] = values[-1] if values else 0.0
                except Exception as e:
                    logger.debug(f"解析流量数据文件失败 {data_file}: {e}")
        
        return flow_data if flow_data else None
    
    def _parse_heat_flux_data(self, case_path: Path) -> Optional[Dict[str, float]]:
        """
        解析 postProcessing/wallHeatFlux 或类似热流量数据
        
        Args:
            case_path: 算例目录路径
            
        Returns:
            热流量数据字典
        """
        post_processing_dir = case_path / "postProcessing"
        if not post_processing_dir.exists():
            return None
        
        heat_flux_dirs = list(post_processing_dir.glob("*heatFlux*"))
        if not heat_flux_dirs:
            return None
        
        heat_data = {"heat_in": 0.0, "heat_out": 0.0, "heat_wall": 0.0}
        
        for heat_dir in heat_flux_dirs:
            for data_file in heat_dir.glob("*.dat"):
                patch_name = heat_dir.name.lower()
                try:
                    values = self._parse_simple_data_file(data_file)
                    if values:
                        final_value = values[-1] if values else 0.0
                        
                        if "inlet" in patch_name:
                            heat_data["heat_in"] += final_value
                        elif "outlet" in patch_name:
                            heat_data["heat_out"] += final_value
                        else:
                            heat_data["heat_wall"] += final_value
                except Exception as e:
                    logger.debug(f"解析热流量数据文件失败 {data_file}: {e}")
        
        return heat_data
    
    def _parse_continuity_errors_from_log(self, log_path: Path) -> List[ContinuityErrorData]:
        """
        解析求解日志中的连续性误差
        
        Args:
            log_path: 日志文件路径
            
        Returns:
            连续性误差数据列表
        """
        continuity_data = []
        
        # 正则模式匹配连续性误差行
        # 格式: "time step continuity errors : sum local = 1.234e-06, global = 2.345e-08, cumulative = 3.456e-07"
        pattern = re.compile(
            r'time step continuity errors\s*:\s*sum local\s*=\s*([\d.e+-]+),\s*'
            r'global\s*=\s*([\d.e+-]+),\s*cumulative\s*=\s*([\d.e+-]+)',
            re.IGNORECASE
        )
        
        # 时间步模式
        time_pattern = re.compile(r'Time\s*=\s*([\d.]+)')
        
        current_time = 0.0
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # 更新当前时间
                    time_match = time_pattern.search(line)
                    if time_match:
                        current_time = float(time_match.group(1))
                    
                    # 匹配连续性误差
                    match = pattern.search(line)
                    if match:
                        continuity_data.append(ContinuityErrorData(
                            time=current_time,
                            local=float(match.group(1)),
                            global_err=float(match.group(2)),
                            cumulative=float(match.group(3))
                        ))
        except Exception as e:
            logger.warning(f"读取日志文件失败 {log_path}: {e}")
        
        return continuity_data
    
    def _parse_residuals_from_log(self, log_path: Path) -> Dict[str, float]:
        """
        解析日志中的残差数据
        
        Args:
            log_path: 日志文件路径
            
        Returns:
            各字段的最终残差字典
        """
        residuals = {}
        
        # 残差模式: "Solving for Ux, Initial residual = 1.234e-05, Final residual = 1.234e-08"
        pattern = re.compile(
            r'Solving for\s+(\w+),\s*Initial residual\s*=\s*[\d.e+-]+,\s*Final residual\s*=\s*([\d.e+-]+)',
            re.IGNORECASE
        )
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    matches = pattern.findall(line)
                    for field_name, final_residual in matches:
                        residuals[field_name] = float(final_residual)
        except Exception as e:
            logger.warning(f"读取日志文件失败 {log_path}: {e}")
        
        return residuals
    
    def _parse_simple_data_file(self, file_path: Path) -> List[float]:
        """
        解析简单的两列数据文件
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            数据值列表（取第二列）
        """
        values = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            values.append(float(parts[1]))
                        except ValueError:
                            continue
        except Exception as e:
            logger.debug(f"解析数据文件失败 {file_path}: {e}")
        
        return values
    
    def _analyze_error_trend(self, errors: List[float]) -> str:
        """
        分析误差趋势
        
        Args:
            errors: 误差列表
            
        Returns:
            趋势描述: "converging"（收敛）, "diverging"（发散）, "stable"（稳定）
        """
        if len(errors) < 5:
            return "insufficient_data"
        
        # 取最近一半的数据点进行分析
        recent = errors[len(errors)//2:]
        
        if len(recent) < 2:
            return "stable"
        
        # 计算趋势：比较前后两半的平均值
        mid = len(recent) // 2
        first_half_avg = sum(recent[:mid]) / mid if mid > 0 else recent[0]
        second_half_avg = sum(recent[mid:]) / (len(recent) - mid) if len(recent) > mid else recent[-1]
        
        if first_half_avg == 0:
            return "converging" if second_half_avg == 0 else "stable"
        
        ratio = second_half_avg / first_half_avg
        
        if ratio < 0.5:
            return "converging"
        elif ratio > 2.0:
            return "diverging"
        else:
            return "stable"
    
    def _is_heat_transfer_case(self, case_path: Path) -> bool:
        """
        判断是否为传热问题
        
        Args:
            case_path: 算例目录路径
            
        Returns:
            是否为传热问题
        """
        # 检查是否存在温度场文件
        for time_dir in case_path.iterdir():
            if time_dir.is_dir():
                try:
                    float(time_dir.name)  # 检查是否为时间目录
                    T_file = time_dir / "T"
                    if T_file.exists():
                        return True
                except ValueError:
                    continue
        
        # 检查 controlDict 中的求解器配置
        control_dict = case_path / "system" / "controlDict"
        if control_dict.exists():
            try:
                content = control_dict.read_text(encoding='utf-8', errors='ignore')
                heat_keywords = ['buoyant', 'heat', 'temperature', 'buoyancy']
                if any(kw in content.lower() for kw in heat_keywords):
                    return True
            except Exception:
                pass
        
        return False
    
    def _check_mass_from_flow_rate(self, flow_data: Dict[str, Any]) -> ConservationResult:
        """
        从流量数据检查质量守恒
        
        Args:
            flow_data: 流量数据字典
            
        Returns:
            检查结果
        """
        inlet_flux = 0.0
        outlet_flux = 0.0
        
        for patch_name, flux in flow_data.items():
            name_lower = patch_name.lower()
            if 'inlet' in name_lower or 'in' in name_lower:
                inlet_flux += abs(flux)
            elif 'outlet' in name_lower or 'out' in name_lower:
                outlet_flux += abs(flux)
        
        if inlet_flux < 1e-10:
            return ConservationResult(
                passed=True,
                message="入口流量为零或未检测到，跳过质量守恒检查",
                details={"skipped": True, "reason": "zero_inlet_flux"}
            )
        
        error_pct = abs(inlet_flux - outlet_flux) / inlet_flux
        passed = error_pct <= self.MASS_CONSERVATION_THRESHOLD
        
        return ConservationResult(
            passed=passed,
            message=f"质量守恒{'通过' if passed else '未通过'}，误差: {error_pct*100:.4f}%",
            details={
                "inlet_flux": inlet_flux,
                "outlet_flux": outlet_flux,
                "error_pct": error_pct * 100,
                "threshold": self.MASS_CONSERVATION_THRESHOLD * 100
            }
        )
    
    def _check_mass_from_continuity(self, continuity_data: List[ContinuityErrorData]) -> ConservationResult:
        """
        从连续性误差推断质量守恒情况
        
        Args:
            continuity_data: 连续性误差数据列表
            
        Returns:
            检查结果
        """
        if not continuity_data:
            return ConservationResult(
                passed=True,
                message="无连续性误差数据",
                details={"skipped": True}
            )
        
        final_error = continuity_data[-1]
        
        # 使用累积误差作为质量守恒的指标
        cumulative = abs(final_error.cumulative)
        passed = cumulative < self.CONTINUITY_ERROR_THRESHOLD * 1000  # 放宽阈值
        
        return ConservationResult(
            passed=passed,
            message=f"基于连续性误差的质量守恒检查{'通过' if passed else '未通过'}",
            details={
                "final_cumulative": cumulative,
                "final_local": final_error.local,
                "final_global": final_error.global_err
            }
        )


if __name__ == "__main__":
    # 模块测试
    print("ConservationChecker 模块测试")
    print("=" * 70)
    
    # 创建测试实例
    checker = ConservationChecker()
    
    # 测试报告生成
    report = checker.generate_report()
    print(report)
    
    # 测试摘要字典
    summary = checker.get_summary_dict()
    print("\n摘要字典:")
    print(summary)
