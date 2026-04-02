"""
求解稳定性监控与自愈Agent (Week 6-7)
实现求解器实时监控、发散检测和自动修复
"""

import re
import time
import signal
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
from abc import ABC, abstractmethod
import json
import logging

try:
    from ..core.openfoam_runner import OpenFOAMRunner, SolverMetrics, SolverState
    from ..core.scheme_advisor import SchemeAdvisor
except ImportError:
    # 作为脚本运行时
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
    from openfoam_runner import OpenFOAMRunner, SolverMetrics, SolverState
    from scheme_advisor import SchemeAdvisor

logger = logging.getLogger(__name__)


# ==================== 策略模式自愈系统 ====================

class HealingStrategy(ABC):
    """自愈策略基类
    
    定义自愈策略的通用接口，所有具体策略必须继承此类
    """
    name: str = "base"
    priority: int = 0  # 数字越小优先级越高
    
    @abstractmethod
    def can_apply(self, event: DivergenceEvent, context: dict = None) -> bool:
        """判断此策略是否适用于当前事件
        
        Args:
            event: 发散事件
            context: 额外上下文信息
            
        Returns:
            是否适用
        """
        return False
    
    @abstractmethod
    def apply(self, case_path: Path, event: DivergenceEvent, context: dict = None) -> tuple:
        """执行修复
        
        Args:
            case_path: 算例路径
            event: 发散事件
            context: 额外上下文信息
            
        Returns:
            (success: bool, message: str, changes: dict)
        """
        return False, "未实现", {}


class BoundaryConditionStrategy(HealingStrategy):
    """边界条件调整策略 - 检测到不合理边界值时自动修正"""
    name = "boundary_adjustment"
    priority = 2
    
    # 物理合理范围
    PHYSICAL_LIMITS = {
        "velocity": {"min": 0, "max": 1000, "unit": "m/s"},  # 速度
        "pressure": {"min": -1e6, "max": 1e9, "unit": "Pa"},  # 压力
        "temperature": {"min": 0, "max": 5000, "unit": "K"},  # 温度
    }
    
    def can_apply(self, event: DivergenceEvent, context: dict = None) -> bool:
        """检查是否是边界条件相关的发散"""
        # 残差爆炸或物理量不现实时可能适用
        return event.divergence_type in [
            DivergenceType.RESIDUAL_EXPLOSION,
            DivergenceType.PHYSICAL_UNREALISTIC
        ]
    
    def apply(self, case_path: Path, event: DivergenceEvent, context: dict = None) -> tuple:
        """尝试调整边界条件到合理范围"""
        changes = {}
        
        try:
            # 读取0目录下的边界条件文件
            zero_dir = case_path / "0"
            if not zero_dir.exists():
                return False, "找不到边界条件目录", {}
            
            modified_files = []
            
            for bc_file in zero_dir.glob("*"):
                if bc_file.is_file():
                    content = bc_file.read_text(encoding='utf-8')
                    original_content = content
                    
                    # 检查并修正不合理的速度值
                    # 匹配 uniform (value) 格式的值
                    velocity_pattern = r'(uniform\s*\(\s*)([\d.-]+)(\s+)([\d.-]+)(\s+)([\d.-]+)(\s*\))'
                    
                    def fix_velocity(match):
                        prefix = match.group(1)
                        u = float(match.group(2))
                        sep1 = match.group(3)
                        v = float(match.group(4))
                        sep2 = match.group(5)
                        w = float(match.group(6))
                        suffix = match.group(7)
                        
                        # 限制速度在合理范围内
                        max_vel = self.PHYSICAL_LIMITS["velocity"]["max"]
                        u = max(-max_vel, min(max_vel, u))
                        v = max(-max_vel, min(max_vel, v))
                        w = max(-max_vel, min(max_vel, w))
                        
                        return f"{prefix}{u}{sep1}{v}{sep2}{w}{suffix}"
                    
                    content = re.sub(velocity_pattern, fix_velocity, content)
                    
                    if content != original_content:
                        bc_file.write_text(content, encoding='utf-8')
                        modified_files.append(bc_file.name)
                        changes[bc_file.name] = "调整边界值到物理合理范围"
            
            if modified_files:
                return True, f"已调整边界条件文件: {', '.join(modified_files)}", changes
            else:
                return False, "未发现需要调整的边界条件", {}
                
        except Exception as e:
            return False, f"边界条件调整失败: {e}", {}


class NumericalSchemeDowngradeStrategy(HealingStrategy):
    """数值格式降级策略 - 从高阶格式降到一阶格式提高稳定性"""
    name = "scheme_downgrade"
    priority = 3
    
    # 高阶格式到低阶格式的映射
    SCHEME_DOWNGRADE_MAP = {
        "linearUpwind": "upwind",  # 二阶迎风格式 -> 一阶迎风格式
        "LUST": "upwind",  # 混合格式 -> 一阶迎风格式
        "cubic": "linear",  # 三阶 -> 线性
        "QUICK": "upwind",  # QUICK -> 一阶迎风格式
        "MUSCL": "upwind",  # MUSCL -> 一阶迎风格式
    }
    
    def can_apply(self, event: DivergenceEvent, context: dict = None) -> bool:
        """残差爆炸或停滞时适用"""
        return event.divergence_type in [
            DivergenceType.RESIDUAL_EXPLOSION,
            DivergenceType.RESIDUAL_STALL
        ]
    
    def apply(self, case_path: Path, event: DivergenceEvent, context: dict = None) -> tuple:
        """将高阶格式降级为一阶格式"""
        changes = {}
        
        try:
            fv_schemes_path = case_path / "system" / "fvSchemes"
            if not fv_schemes_path.exists():
                return False, "找不到fvSchemes文件", {}
            
            content = fv_schemes_path.read_text(encoding='utf-8')
            original_content = content
            
            # 替换高阶格式为低阶格式
            for high_order, low_order in self.SCHEME_DOWNGRADE_MAP.items():
                pattern = rf'\b{re.escape(high_order)}\b'
                if re.search(pattern, content):
                    content = re.sub(pattern, low_order, content)
                    changes[high_order] = low_order
            
            if content != original_content:
                fv_schemes_path.write_text(content, encoding='utf-8')
                change_desc = ", ".join([f"{k}->{v}" for k, v in changes.items()])
                return True, f"数值格式降级: {change_desc}", changes
            else:
                return False, "未发现需要降级的高阶格式", {}
                
        except Exception as e:
            return False, f"格式降级失败: {e}", {}


class IntelligentSchemeDowngradeStrategy(HealingStrategy):
    """智能数值格式降级策略 - 使用 SchemeAdvisor 进行智能诊断和降级
    
    与 NumericalSchemeDowngradeStrategy 相比，此策略：
    1. 使用 SchemeAdvisor 进行智能发散诊断
    2. 针对特定发散字段进行定向降级
    3. 提供专业的教学级解释
    """
    name = "intelligent_scheme_downgrade"
    priority = 2  # 比普通降级策略优先级更高
    
    def __init__(self):
        self.scheme_advisor = SchemeAdvisor()
    
    def can_apply(self, event: DivergenceEvent, context: dict = None) -> bool:
        """残差爆炸、振荡或停滞时适用
        
        适用场景：
        - 残差持续上升（格式不稳定）
        - 残差振荡（可能是中心差分导致）
        - 残差停滞（可能需要调整格式）
        """
        return event.divergence_type in [
            DivergenceType.RESIDUAL_EXPLOSION,
            DivergenceType.RESIDUAL_STALL,
        ]
    
    def apply(self, case_path: Path, event: DivergenceEvent, context: dict = None) -> tuple:
        """使用 SchemeAdvisor 进行智能诊断和格式调整
        
        流程：
        1. 读取当前 fvSchemes 文件
        2. 读取求解器日志
        3. 调用 SchemeAdvisor.diagnose_divergence 进行诊断
        4. 根据诊断结果修改 fvSchemes
        """
        changes = {}
        
        try:
            fv_schemes_path = case_path / "system" / "fvSchemes"
            if not fv_schemes_path.exists():
                return False, "找不到 fvSchemes 文件", {}
            
            # 读取当前格式配置
            current_schemes = self._parse_fvschemes(fv_schemes_path)
            
            # 获取日志内容（从 context 或从日志文件）
            log_content = ""
            if context and "log_content" in context:
                log_content = context["log_content"]
            else:
                # 尝试读取日志文件
                log_path = case_path / "logs" / "solver.log"
                if not log_path.exists():
                    log_path = case_path / "log"
                if log_path.exists():
                    log_content = log_path.read_text(encoding='utf-8')
            
            # 使用 SchemeAdvisor 进行诊断
            diagnosis = self.scheme_advisor.diagnose_divergence(log_content, current_schemes)
            
            logger.info(f"发散诊断结果: {diagnosis.diagnosis}")
            logger.info(f"问题字段: {diagnosis.problematic_fields}")
            
            # 根据诊断结果修改格式
            content = fv_schemes_path.read_text(encoding='utf-8')
            original_content = content
            
            if diagnosis.recommended_changes:
                for key, recommendation in diagnosis.recommended_changes.items():
                    if isinstance(recommendation, dict) and "recommended" in recommendation:
                        # 获取旧格式和新格式
                        old_scheme = recommendation.get("current", "")
                        new_scheme = recommendation.get("recommended", "")
                        
                        if old_scheme and new_scheme:
                            # 在内容中替换
                            # 处理特殊的键名格式
                            pattern = rf'({re.escape(key)}\s+)({re.escape(old_scheme)})'
                            if re.search(pattern, content):
                                content = re.sub(pattern, rf'\1{new_scheme}', content)
                                changes[key] = {
                                    "old": old_scheme,
                                    "new": new_scheme,
                                    "reason": recommendation.get("reason", "")
                                }
            
            # 如果没有找到具体的修改，执行通用降级
            if not changes and diagnosis.problematic_fields:
                for field in diagnosis.problematic_fields:
                    if field.startswith("Co="):  # 库朗数问题
                        continue
                    
                    # 对流格式降级
                    div_key = f"div(phi,{field})"
                    if div_key in current_schemes.get("divSchemes", {}):
                        current = current_schemes["divSchemes"][div_key]
                        downgrade = self.scheme_advisor.get_downgrade_recommendation(current, field)
                        
                        if downgrade:
                            new_scheme = downgrade["recommended"]
                            pattern = rf'({re.escape(div_key)}\s+)({re.escape(current)})'
                            if re.search(pattern, content):
                                content = re.sub(pattern, rf'\1{new_scheme}', content)
                                changes[div_key] = {
                                    "old": current,
                                    "new": new_scheme,
                                    "reason": downgrade["reason"]
                                }
            
            if content != original_content:
                fv_schemes_path.write_text(content, encoding='utf-8')
                
                change_desc = "; ".join([
                    f"{k}: {v['old']} -> {v['new']}" 
                    for k, v in changes.items()
                ])
                
                message = f"智能格式降级: {change_desc}"
                if diagnosis.explanation:
                    message += f"\n诊断说明: {diagnosis.explanation}"
                
                return True, message, {
                    "changes": changes,
                    "diagnosis": diagnosis.diagnosis,
                    "problematic_fields": diagnosis.problematic_fields
                }
            else:
                return False, "无需修改格式配置", {}
                
        except Exception as e:
            logger.error(f"智能格式降级失败: {e}")
            return False, f"智能格式降级失败: {e}", {}
    
    def _parse_fvschemes(self, fv_schemes_path: Path) -> Dict[str, Any]:
        """解析 fvSchemes 文件
        
        Args:
            fv_schemes_path: fvSchemes 文件路径
        
        Returns:
            格式配置字典
        """
        schemes = {
            "divSchemes": {},
            "gradSchemes": {},
            "laplacianSchemes": {},
            "interpolationSchemes": {},
            "snGradSchemes": {},
            "ddtSchemes": {}
        }
        
        try:
            content = fv_schemes_path.read_text(encoding='utf-8')
            
            # 简单解析各部分
            for section in ["divSchemes", "gradSchemes", "laplacianSchemes", 
                           "interpolationSchemes", "snGradSchemes", "ddtSchemes"]:
                # 匹配 { ... } 块
                pattern = rf'{section}\s*\{{([^}}]+)\}}'
                match = re.search(pattern, content, re.DOTALL)
                
                if match:
                    section_content = match.group(1)
                    # 解析键值对
                    for line in section_content.strip().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('//') and ';' in line:
                            parts = line.rsplit(';', 1)
                            if len(parts) >= 1:
                                key_val = parts[0].strip().split(None, 1)
                                if len(key_val) == 2:
                                    schemes[section][key_val[0].strip()] = key_val[1].strip()
        
        except Exception as e:
            logger.warning(f"解析 fvSchemes 失败: {e}")
        
        return schemes


class HealingHistory:
    """修复历史记录 - 跟踪修复效果，避免重复无效修复"""
    
    def __init__(self):
        self.records: List[Tuple[str, str, bool, float]] = []  # (event_type, strategy_name, success, timestamp)
    
    def record(self, event_type: str, strategy_name: str, success: bool):
        """记录一次修复尝试
        
        Args:
            event_type: 事件类型
            strategy_name: 策略名称
            success: 是否成功
        """
        timestamp = time.time()
        self.records.append((event_type, strategy_name, success, timestamp))
    
    def get_success_rate(self, event_type: str, strategy_name: str) -> float:
        """获取特定策略对特定事件的成功率
        
        Args:
            event_type: 事件类型
            strategy_name: 策略名称
            
        Returns:
            成功率 (0.0 - 1.0)
        """
        relevant = [r for r in self.records 
                   if r[0] == event_type and r[1] == strategy_name]
        if not relevant:
            return 0.5  # 默认50%，表示未知
        
        successes = sum(1 for r in relevant if r[2])
        return successes / len(relevant)
    
    def get_recommended_strategy(self, event_type: str, available_strategies: List[str]) -> str:
        """基于历史记录推荐最优策略
        
        Args:
            event_type: 事件类型
            available_strategies: 可用策略列表
            
        Returns:
            推荐的策略名称
        """
        if not available_strategies:
            return None
        
        # 按成功率排序
        rates = [(s, self.get_success_rate(event_type, s)) for s in available_strategies]
        rates.sort(key=lambda x: x[1], reverse=True)
        
        return rates[0][0]
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self.records:
            return {"total": 0, "success_rate": 0}
        
        total = len(self.records)
        successes = sum(1 for r in self.records if r[2])
        
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total
        }


class StrategyBasedHealer:
    """基于策略模式的增强自愈控制器
    
    使用策略模式实现更灵活、可扩展的自愈系统
    """
    
    def __init__(self, max_attempts: int = 5):
        self.strategies = self._register_strategies()
        self.history = HealingHistory()
        self.max_attempts = max_attempts
        self.attempt_count = 0
    
    def _register_strategies(self) -> List[HealingStrategy]:
        """注册所有可用策略，按优先级排序
        
        Returns:
            排序后的策略列表
        """
        strategies = [
            BoundaryConditionStrategy(),
            IntelligentSchemeDowngradeStrategy(),  # 智能格式降级策略（优先级更高）
            NumericalSchemeDowngradeStrategy(),     # 传统格式降级策略（备用）
        ]
        # 按优先级排序（数字越小优先级越高）
        strategies.sort(key=lambda s: s.priority)
        return strategies
    
    def heal(self, case_path: Path, event: DivergenceEvent, context: dict = None) -> tuple:
        """使用策略模式进行修复
        
        流程：
        1. 获取所有适用于当前事件的策略
        2. 按历史成功率排序
        3. 依次尝试直到成功或用尽
        
        Args:
            case_path: 算例路径
            event: 发散事件
            context: 额外上下文
            
        Returns:
            (success: bool, message: str, report: dict)
        """
        if self.attempt_count >= self.max_attempts:
            return False, f"已达到最大尝试次数({self.max_attempts})", {}
        
        self.attempt_count += 1
        
        # 1. 获取适用策略
        applicable = [s for s in self.strategies if s.can_apply(event, context)]
        if not applicable:
            return False, "没有适用的修复策略", {}
        
        # 2. 按历史成功率排序
        strategy_names = [s.name for s in applicable]
        recommended = self.history.get_recommended_strategy(
            event.divergence_type.value, strategy_names
        )
        
        # 将推荐策略排在最前
        if recommended:
            applicable.sort(key=lambda s: (s.name != recommended, s.priority))
        
        # 3. 依次尝试
        for strategy in applicable:
            success, message, changes = strategy.apply(case_path, event, context)
            
            # 记录结果
            self.history.record(event.divergence_type.value, strategy.name, success)
            
            if success:
                return True, message, {
                    "strategy": strategy.name,
                    "changes": changes,
                    "attempt": self.attempt_count
                }
        
        return False, "所有策略均失败", {
            "attempted": [s.name for s in applicable],
            "attempt": self.attempt_count
        }
    
    def get_healing_report(self) -> dict:
        """返回修复历史报告
        
        Returns:
            包含统计信息和历史记录的报告
        """
        return {
            "max_attempts": self.max_attempts,
            "attempt_count": self.attempt_count,
            "history_stats": self.history.get_stats(),
            "registered_strategies": [s.name for s in self.strategies]
        }


class DivergenceType(Enum):
    """发散类型"""
    NONE = "none"
    COURANT_EXCEEDED = "courant_exceeded"      # 库朗数超标
    RESIDUAL_EXPLOSION = "residual_explosion"   # 残差爆炸
    RESIDUAL_STALL = "residual_stall"           # 残差停滞
    PHYSICAL_UNREALISTIC = "physical_unrealistic"  # 物理量不现实


@dataclass
class DivergenceEvent:
    """发散事件"""
    timestamp: str
    divergence_type: DivergenceType
    severity: str  # "warning", "critical"
    description: str
    metrics_snapshot: Dict[str, Any]
    suggested_action: str


@dataclass
class HealingAction:
    """自愈动作"""
    action_type: str
    description: str
    target_file: str
    old_value: Any
    new_value: Any
    reason: str


class SolverStabilityMonitor:
    """
    求解器稳定性监控器
    
    功能：
    1. 实时解析求解器日志
    2. 检测各种发散模式
    3. 记录指标历史
    4. 触发告警
    """
    
    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.divergence_events: List[DivergenceEvent] = []
        
        # 阈值配置
        self.courant_critical = 5.0
        self.courant_warning = 1.0
        self.residual_explosion_threshold = 1.0
        self.residual_stall_threshold = 100  # 步数
        self.residual_stall_ratio = 1.1      # 残差下降比例阈值
        
        # 状态
        self.current_time = 0.0
        self.consecutive_divergence_steps = 0
        self.stagnant_steps = 0
    
    def process_metrics(self, metrics: SolverMetrics) -> Tuple[SolverState, Optional[DivergenceEvent]]:
        """
        处理新指标，检测异常
        
        Returns:
            (求解器状态, 发散事件)
        """
        self.metrics_history.append(metrics)
        
        # 检查库朗数
        courant_event = self._check_courant(metrics)
        if courant_event:
            return SolverState.DIVERGING, courant_event
        
        # 检查残差
        residual_event = self._check_residuals(metrics)
        if residual_event:
            if residual_event.severity == "critical":
                return SolverState.DIVERGING, residual_event
            else:
                return SolverState.STALLED, residual_event
        
        # 检查收敛
        if self._check_convergence(metrics):
            return SolverState.CONVERGED, None
        
        return SolverState.RUNNING, None
    
    def _check_courant(self, metrics: SolverMetrics) -> Optional[DivergenceEvent]:
        """检查库朗数"""
        if metrics.courant_max > self.courant_critical:
            return DivergenceEvent(
                timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                divergence_type=DivergenceType.COURANT_EXCEEDED,
                severity="critical",
                description=f"库朗数严重超标: {metrics.courant_max:.2f} (限制: {self.courant_critical})",
                metrics_snapshot=metrics.to_dict(),
                suggested_action="减小时间步长至50%"
            )
        elif metrics.courant_max > self.courant_warning:
            # 连续超标计数
            self.consecutive_divergence_steps += 1
            if self.consecutive_divergence_steps >= 3:
                return DivergenceEvent(
                    timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                    divergence_type=DivergenceType.COURANT_EXCEEDED,
                    severity="warning",
                    description=f"库朗数持续偏高: {metrics.courant_max:.2f}",
                    metrics_snapshot=metrics.to_dict(),
                    suggested_action="建议减小时间步长或调整网格"
                )
        else:
            self.consecutive_divergence_steps = 0
        
        return None
    
    def _check_residuals(self, metrics: SolverMetrics) -> Optional[DivergenceEvent]:
        """检查残差"""
        # 检查残差爆炸
        for var, res in metrics.residuals.items():
            if res > self.residual_explosion_threshold:
                return DivergenceEvent(
                    timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                    divergence_type=DivergenceType.RESIDUAL_EXPLOSION,
                    severity="critical",
                    description=f"{var}残差爆炸: {res:.2e}",
                    metrics_snapshot=metrics.to_dict(),
                    suggested_action="减小松弛因子至80%"
                )
        
        # 检查残差停滞
        if len(self.metrics_history) >= self.residual_stall_threshold:
            return self._check_stagnation()
        
        return None
    
    def _check_stagnation(self) -> Optional[DivergenceEvent]:
        """检查残差停滞"""
        recent = list(self.metrics_history)[-self.residual_stall_threshold:]
        
        for var in ['Ux', 'Uy', 'Uz', 'p', 'T', 'k', 'epsilon']:
            values = [m.residuals.get(var, 0) for m in recent if var in m.residuals]
            
            if len(values) >= self.residual_stall_threshold:
                # 检查是否停滞（残差不再明显下降）
                first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
                second_half_avg = sum(values[len(values)//2:]) / (len(values)//2)
                
                if second_half_avg > first_half_avg / self.residual_stall_ratio:
                    return DivergenceEvent(
                        timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                        divergence_type=DivergenceType.RESIDUAL_STALL,
                        severity="warning",
                        description=f"{var}残差停滞: {values[0]:.2e} -> {values[-1]:.2e}",
                        metrics_snapshot={"variable": var, "values": values},
                        suggested_action="调整求解器参数或网格"
                    )
        
        return None
    
    def _check_convergence(self, metrics: SolverMetrics) -> bool:
        """检查是否收敛"""
        # 简化：所有残差都低于1e-6认为收敛
        if not metrics.residuals:
            return False
        
        for var, res in metrics.residuals.items():
            if res > 1e-6:
                return False
        
        return True
    
    def get_trend_analysis(self) -> Dict[str, Any]:
        """获取趋势分析"""
        if len(self.metrics_history) < 10:
            return {"status": "insufficient_data"}
        
        recent = list(self.metrics_history)[-50:]  # 最近50步
        
        analysis = {
            "courant_trend": "stable",
            "residual_trends": {},
            "recommendations": []
        }
        
        # 库朗数趋势
        courant_values = [m.courant_max for m in recent]
        if courant_values[-1] > courant_values[0] * 2:
            analysis["courant_trend"] = "increasing"
            analysis["recommendations"].append("库朗数上升趋势，建议减小时间步长")
        
        # 残差趋势
        for var in ['Ux', 'Uy', 'p']:
            values = [m.residuals.get(var, 0) for m in recent if var in m.residuals]
            if len(values) >= 10:
                if values[-1] < values[0] * 0.1:
                    analysis["residual_trends"][var] = "decreasing"
                elif values[-1] > values[0]:
                    analysis["residual_trends"][var] = "increasing"
                    analysis["recommendations"].append(f"{var}残差上升，可能需要调整松弛因子")
                else:
                    analysis["residual_trends"][var] = "stable"
        
        return analysis


class SelfHealingController:
    """
    自愈控制器
    
    功能：
    1. 根据发散类型选择修复策略
    2. 自动调整求解器参数
    3. 从上次保存点重启
    4. 限制最大尝试次数
    """
    
    def __init__(self, case_path: Path, max_attempts: int = 3):
        self.case_path = Path(case_path)
        self.max_attempts = max_attempts
        self.healing_attempts = 0
        self.healing_history: List[HealingAction] = []
        
        # 备份原配置
        self._backup_original_config()
    
    def _backup_original_config(self):
        """备份原始配置"""
        system_dir = self.case_path / "system"
        backup_dir = self.case_path / "system" / ".backup"
        
        backup_dir.mkdir(exist_ok=True)
        
        for file in ["controlDict", "fvSolution", "fvSchemes"]:
            src = system_dir / file
            if src.exists():
                shutil.copy2(src, backup_dir / file)
    
    def can_heal(self, event: DivergenceEvent) -> bool:
        """判断是否可以自愈"""
        if self.healing_attempts >= self.max_attempts:
            print(f"[SelfHealing] 已达到最大自愈尝试次数({self.max_attempts})")
            return False
        
        # 某些发散类型无法自动修复
        if event.divergence_type == DivergenceType.PHYSICAL_UNREALISTIC:
            print("[SelfHealing] 物理量不现实，无法自动修复")
            return False
        
        return True
    
    def heal(self, event: DivergenceEvent) -> Tuple[bool, str]:
        """
        执行自愈
        
        Returns:
            (是否成功, 消息)
        """
        if not self.can_heal(event):
            return False, "无法自愈"
        
        self.healing_attempts += 1
        print(f"[SelfHealing] 第{self.healing_attempts}次自愈尝试")
        
        # 根据发散类型选择策略
        if event.divergence_type == DivergenceType.COURANT_EXCEEDED:
            return self._heal_courant_issue(event)
        
        elif event.divergence_type == DivergenceType.RESIDUAL_EXPLOSION:
            return self._heal_residual_explosion(event)
        
        elif event.divergence_type == DivergenceType.RESIDUAL_STALL:
            return self._heal_residual_stall(event)
        
        return False, "未知的发散类型"
    
    def _heal_courant_issue(self, event: DivergenceEvent) -> Tuple[bool, str]:
        """修复库朗数问题"""
        print("[SelfHealing] 修复库朗数问题...")
        
        # 策略：减小时间步长
        control_dict_path = self.case_path / "system" / "controlDict"
        
        try:
            content = control_dict_path.read_text(encoding='utf-8')
            
            # 提取当前deltaT
            delta_t_match = re.search(r'deltaT\s+([\d.e+-]+);', content)
            if delta_t_match:
                current_delta_t = float(delta_t_match.group(1))
                new_delta_t = current_delta_t * 0.5
                
                # 修改deltaT
                content = re.sub(
                    r'deltaT\s+[\d.e+-]+;',
                    f'deltaT {new_delta_t};',
                    content
                )
                
                # 设置从最新时间步重启
                content = re.sub(
                    r'startFrom\s+\w+;',
                    'startFrom latestTime;',
                    content
                )
                
                control_dict_path.write_text(content, encoding='utf-8')
                
                action = HealingAction(
                    action_type="reduce_deltaT",
                    description=f"减小时间步长: {current_delta_t} -> {new_delta_t}",
                    target_file="controlDict",
                    old_value=current_delta_t,
                    new_value=new_delta_t,
                    reason="库朗数超标"
                )
                self.healing_history.append(action)
                
                return True, f"已减小时间步长至{new_delta_t}，将从最新时间步重启"
            
            return False, "无法解析deltaT"
            
        except Exception as e:
            return False, f"修复失败: {e}"
    
    def _heal_residual_explosion(self, event: DivergenceEvent) -> Tuple[bool, str]:
        """修复残差爆炸"""
        print("[SelfHealing] 修复残差爆炸...")
        
        # 策略：减小松弛因子
        fv_solution_path = self.case_path / "system" / "fvSolution"
        
        try:
            content = fv_solution_path.read_text(encoding='utf-8')
            
            # 修改松弛因子
            modifications = []
            
            # 匹配relaxationFactors字段
            rf_pattern = r'(relaxationFactors\s*\{[^}]*)(\})'
            rf_match = re.search(rf_pattern, content, re.DOTALL)
            
            if rf_match:
                rf_section = rf_match.group(1)
                
                # 修改各字段的松弛因子
                for field in ['U', 'p', 'k', 'epsilon', 'omega']:
                    pattern = rf'{field}\s+([\d.]+);'
                    match = re.search(pattern, rf_section)
                    if match:
                        old_val = float(match.group(1))
                        new_val = min(old_val * 0.8, 0.7)  # 减小20%，不超过0.7
                        rf_section = re.sub(pattern, f'{field} {new_val:.2f};', rf_section)
                        modifications.append(f"{field}: {old_val} -> {new_val:.2f}")
                
                # 更新内容
                content = content[:rf_match.start()] + rf_section + content[rf_match.end():]
                fv_solution_path.write_text(content, encoding='utf-8')
            
            if modifications:
                action = HealingAction(
                    action_type="reduce_relaxation",
                    description=f"减小松弛因子: {', '.join(modifications)}",
                    target_file="fvSolution",
                    old_value="参见history",
                    new_value="参见history",
                    reason="残差爆炸"
                )
                self.healing_history.append(action)
                
                return True, f"已减小松弛因子: {', '.join(modifications)}"
            
            return False, "未找到可修改的松弛因子"
            
        except Exception as e:
            return False, f"修复失败: {e}"
    
    def _heal_residual_stall(self, event: DivergenceEvent) -> Tuple[bool, str]:
        """修复残差停滞"""
        print("[SelfHealing] 修复残差停滞...")
        
        # 策略1：尝试增加非正交修正器
        fv_solution_path = self.case_path / "system" / "fvSolution"
        
        try:
            content = fv_solution_path.read_text(encoding='utf-8')
            
            # 检查是否有nNonOrthogonalCorrectors
            if 'nNonOrthogonalCorrectors' in content:
                # 增加数量
                content = re.sub(
                    r'nNonOrthogonalCorrectors\s*(\d+);',
                    lambda m: f"nNonOrthogonalCorrectors {int(m.group(1)) + 1};",
                    content
                )
            else:
                # 添加非正交修正器
                content = self._add_to_dict(content, 'PIMPLE', 
                    'nNonOrthogonalCorrectors 1;')
            
            fv_solution_path.write_text(content, encoding='utf-8')
            
            action = HealingAction(
                action_type="add_nonorthogonal_correctors",
                description="增加非正交修正器",
                target_file="fvSolution",
                old_value=0,
                new_value=1,
                reason="残差停滞"
            )
            self.healing_history.append(action)
            
            return True, "已增加非正交修正器"
            
        except Exception as e:
            return False, f"修复失败: {e}"
    
    def _add_to_dict(self, content: str, dict_name: str, entry: str) -> str:
        """向字典添加条目"""
        pattern = rf'({dict_name}\s*\{{[^}}]*)(\}})'
        replacement = rf'\1    {entry}\n}}'
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    def reset_config(self):
        """重置配置到原始状态"""
        backup_dir = self.case_path / "system" / ".backup"
        system_dir = self.case_path / "system"
        
        if backup_dir.exists():
            for file in ["controlDict", "fvSolution", "fvSchemes"]:
                backup_file = backup_dir / file
                if backup_file.exists():
                    shutil.copy2(backup_file, system_dir / file)
            
            print("[SelfHealing] 配置已重置到原始状态")
    
    def get_healing_report(self) -> Dict[str, Any]:
        """获取自愈报告"""
        return {
            "total_attempts": self.healing_attempts,
            "max_attempts": self.max_attempts,
            "actions": [
                {
                    "type": a.action_type,
                    "description": a.description,
                    "target": a.target_file,
                    "reason": a.reason
                }
                for a in self.healing_history
            ]
        }


class SmartSolverRunner:
    """
    智能求解器运行器
    集成监控和自愈功能
    """
    
    def __init__(self, case_path: Path, enable_healing: bool = True):
        self.case_path = Path(case_path)
        self.runner = OpenFOAMRunner(case_path)
        self.monitor = SolverStabilityMonitor()
        self.healer = SelfHealingController(case_path) if enable_healing else None
        self.enable_healing = enable_healing
        
        self.interrupted = False
    
    def run(self, solver_name: str, 
            progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        运行求解器，带自愈功能
        
        Args:
            solver_name: 求解器名称
            progress_callback: 进度回调函数
            
        Returns:
            运行结果报告
        """
        print(f"[SmartSolverRunner] 启动求解器: {solver_name}")
        
        results = {
            "solver": solver_name,
            "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": None,
            "status": "running",
            "restart_count": 0,
            "divergence_events": [],
            "final_metrics": None
        }
        
        max_restarts = self.healer.max_attempts if self.healer else 0
        restart_count = 0
        
        while restart_count <= max_restarts:
            if restart_count > 0:
                print(f"[SmartSolverRunner] 第{restart_count}次重启...")
                results["restart_count"] = restart_count
            
            # 运行求解器
            final_metrics = self._run_single_attempt(
                solver_name, progress_callback, results
            )
            
            if self.interrupted:
                results["status"] = "interrupted"
                break
            
            # 检查是否发散
            if results["status"] == "diverging" and self.healer:
                # 获取最后一个发散事件
                if results["divergence_events"]:
                    last_event = DivergenceEvent(**results["divergence_events"][-1])
                    
                    # 尝试自愈
                    healed, message = self.healer.heal(last_event)
                    
                    if healed:
                        print(f"[SmartSolverRunner] 自愈成功: {message}")
                        restart_count += 1
                        results["status"] = "running"
                        continue
                    else:
                        print(f"[SmartSolverRunner] 自愈失败: {message}")
                        results["status"] = "failed"
                        break
            
            # 正常结束或收敛
            if results["status"] in ["completed", "converged"]:
                break
            
            # 其他错误
            if results["status"] == "error":
                break
            
            restart_count += 1
        
        results["end_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
        results["final_metrics"] = final_metrics.to_dict() if final_metrics else None
        results["healing_report"] = self.healer.get_healing_report() if self.healer else None
        
        return results
    
    def _run_single_attempt(self, solver_name: str,
                           progress_callback: Optional[Callable[[str], None]],
                           results: Dict[str, Any]) -> Optional[SolverMetrics]:
        """单次运行尝试"""
        final_metrics = None
        
        for metrics in self.runner.run_solver(solver_name, callback=progress_callback):
            final_metrics = metrics
            
            # 监控
            state, event = self.monitor.process_metrics(metrics)
            
            # 处理发散
            if state == SolverState.DIVERGING and event:
                print(f"[SmartSolverRunner] 检测到发散: {event.description}")
                results["divergence_events"].append({
                    "timestamp": event.timestamp,
                    "type": event.divergence_type.value,
                    "severity": event.severity,
                    "description": event.description
                })
                results["status"] = "diverging"
                
                # 停止求解器
                self.runner.stop_solver()
                return final_metrics
            
            # 检测收敛
            if state == SolverState.CONVERGED:
                print("[SmartSolverRunner] 求解器收敛")
                results["status"] = "converged"
                return final_metrics
        
        # 运行结束
        if self.runner.state == SolverState.COMPLETED:
            results["status"] = "completed"
        elif self.runner.state == SolverState.ERROR:
            results["status"] = "error"
        
        return final_metrics
    
    def stop(self):
        """停止运行"""
        self.interrupted = True
        self.runner.stop_solver()


if __name__ == "__main__":
    # 模块测试
    print("SelfHealingAgent 模块测试")
    print("=" * 60)
    
    # 测试监控器
    monitor = SolverStabilityMonitor()
    print(f"监控器初始化: max_history={monitor.max_history}")
    
    # 测试自愈控制器
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test"
        case_path.mkdir()
        (case_path / "system").mkdir()
        
        # 创建模拟controlDict
        control_dict = case_path / "system" / "controlDict"
        control_dict.write_text("""
deltaT 0.01;
startFrom startTime;
""")
        
        healer = SelfHealingController(case_path)
        print(f"自愈控制器初始化: max_attempts={healer.max_attempts}")
