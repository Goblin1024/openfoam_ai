"""
Error Recovery Module
错误恢复模块

负责：
1. 尝试自动修复配置错误
2. 生成修复选项供用户选择
3. 执行失败后的恢复尝试
"""

from typing import Dict, Any, List, Tuple, Optional


class ErrorRecovery:
    """
    错误恢复器
    
    职责：
    1. 自动修复配置错误
    2. 生成修复选项
    3. 执行失败后的恢复
    """
    
    # 最小网格数
    MIN_MESH_2D = 20
    MIN_MESH_3D = 20
    MIN_MESH_FALLBACK = 10
    
    # 时间步长调整因子
    TIMESTEP_REDUCTION_FACTOR = 0.5
    
    def __init__(self, current_config: Optional[Dict[str, Any]] = None):
        """
        初始化ErrorRecovery
        
        Args:
            current_config: 当前配置
        """
        self.current_config = current_config
    
    def set_config(self, config: Dict[str, Any]) -> None:
        """设置当前配置"""
        self.current_config = config
    
    def try_auto_fix(self, config: Dict[str, Any], errors: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """尝试自动修复配置错误
        
        Args:
            config: 原始配置
            errors: 友好错误信息列表
            
        Returns:
            (fixed_config or None, fix_log: list[str])
        """
        from ..core.validators import validate_simulation_config
        
        fix_log = []
        fixed_config = config.copy()
        
        # 深拷贝几何和求解器配置
        if "geometry" in fixed_config:
            fixed_config["geometry"] = fixed_config["geometry"].copy()
        if "solver" in fixed_config:
            fixed_config["solver"] = fixed_config["solver"].copy()
        
        can_fix = False
        
        for error in errors:
            error_msg = error.get("message", "")
            
            # 网格数不足 -> 自动增加到最小值
            if "网格数" in error_msg and "不足" in error_msg:
                geom = fixed_config.get("geometry", {})
                if "nx" in geom and "ny" in geom:
                    nz = geom.get("nz", 1)
                    if nz == 1:  # 2D问题
                        # 确保至少20x20
                        if geom.get("nx", 0) < self.MIN_MESH_2D:
                            geom["nx"] = self.MIN_MESH_2D
                            fix_log.append(f"nx自动调整为{self.MIN_MESH_2D}")
                            can_fix = True
                        if geom.get("ny", 0) < self.MIN_MESH_2D:
                            geom["ny"] = self.MIN_MESH_2D
                            fix_log.append(f"ny自动调整为{self.MIN_MESH_2D}")
                            can_fix = True
                    else:  # 3D问题
                        if geom.get("nx", 0) < self.MIN_MESH_3D:
                            geom["nx"] = self.MIN_MESH_3D
                            fix_log.append(f"nx自动调整为{self.MIN_MESH_3D}")
                            can_fix = True
                        if geom.get("ny", 0) < self.MIN_MESH_3D:
                            geom["ny"] = self.MIN_MESH_3D
                            fix_log.append(f"ny自动调整为{self.MIN_MESH_3D}")
                            can_fix = True
                        if geom.get("nz", 0) < self.MIN_MESH_3D:
                            geom["nz"] = self.MIN_MESH_3D
                            fix_log.append(f"nz自动调整为{self.MIN_MESH_3D}")
                            can_fix = True
            
            # CFL超限 -> 自动减小时间步长
            if "库朗数" in error_msg or "时间步长" in error_msg:
                solver = fixed_config.get("solver", {})
                if "deltaT" in solver:
                    old_dt = solver["deltaT"]
                    new_dt = old_dt * self.TIMESTEP_REDUCTION_FACTOR  # 减半
                    solver["deltaT"] = new_dt
                    fix_log.append(f"时间步长从{old_dt}自动减小到{new_dt}")
                    can_fix = True
            
            # 求解器不匹配 -> 自动选择匹配的求解器
            if "求解器" in error_msg and "不匹配" in error_msg:
                physics = fixed_config.get("physics_type", "incompressible")
                solver = fixed_config.get("solver", {})
                
                if physics == "incompressible":
                    solver["name"] = "icoFoam"
                    fix_log.append(f"求解器自动设置为icoFoam（不可压流）")
                    can_fix = True
                elif physics == "heatTransfer":
                    solver["name"] = "buoyantBoussinesqPimpleFoam"
                    fix_log.append(f"求解器自动设置为buoyantBoussinesqPimpleFoam（传热问题）")
                    can_fix = True
        
        if can_fix:
            # 验证修复后的配置
            passed, _ = validate_simulation_config(fixed_config)
            if passed:
                return fixed_config, fix_log
            else:
                return None, ["自动修复后配置仍不合法"]
        
        return None, []
    
    def generate_fix_options(self, config: Dict[str, Any], errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为每个错误生成修复选项供用户选择
        
        Args:
            config: 当前配置
            errors: 错误列表
            
        Returns:
            [{"error": "...", "options": [{"label": "自动修复(推荐)", "action": "auto"}, ...]}]
        """
        options_list = []
        
        for error in errors:
            error_msg = error.get("message", "")
            options = []
            
            # 网格相关错误
            if "网格数" in error_msg:
                options.append({
                    "label": "自动调整网格数(推荐)",
                    "action": "auto_fix_mesh",
                    "description": "自动设置到推荐值"
                })
                options.append({
                    "label": "手动输入网格数",
                    "action": "manual_mesh",
                    "description": "自定义网格分辨率"
                })
            
            # 时间步长相关错误
            if "时间步长" in error_msg or "库朗数" in error_msg:
                options.append({
                    "label": "自动减小时间步长",
                    "action": "auto_fix_timestep",
                    "description": "将时间步长减半"
                })
                options.append({
                    "label": "使用隐式格式",
                    "action": "use_implicit",
                    "description": "切换到更稳定的隐式格式"
                })
            
            # 求解器不匹配
            if "求解器" in error_msg:
                physics = config.get("physics_type", "incompressible")
                if physics == "incompressible":
                    recommended = "icoFoam/simpleFoam"
                elif physics == "heatTransfer":
                    recommended = "buoyantBoussinesqPimpleFoam"
                else:
                    recommended = "合适的求解器"
                
                options.append({
                    "label": f"使用推荐求解器({recommended})",
                    "action": "auto_fix_solver",
                    "description": "自动选择匹配的求解器"
                })
            
            # 默认选项
            if not options:
                options.append({
                    "label": "查看详细说明",
                    "action": "show_help",
                    "description": error.get("teaching", "")
                })
            
            options_list.append({
                "error": error_msg,
                "suggestion": error.get("suggestion", ""),
                "options": options
            })
        
        return options_list
    
    def attempt_recovery(self, failed_result: Any, logs: List[str]) -> bool:
        """尝试从失败中恢复
        
        分析失败日志，尝试自动修复配置
        
        Args:
            failed_result: 失败的执行结果（用于获取日志）
            logs: 日志列表
            
        Returns:
            是否成功恢复
        """
        if self.current_config is None:
            return False
        
        # 分析失败原因
        for log in logs:
            log_lower = log.lower()
            
            # 网格生成失败
            if "blockmesh" in log_lower and "失败" in log:
                # 可能是网格定义问题，尝试调整
                if "geometry" in self.current_config:
                    geom = self.current_config["geometry"]
                    # 检查并修正不合理的网格数
                    modified = False
                    if geom.get("nx", 0) < self.MIN_MESH_FALLBACK:
                        geom["nx"] = self.MIN_MESH_FALLBACK
                        modified = True
                    if geom.get("ny", 0) < self.MIN_MESH_FALLBACK:
                        geom["ny"] = self.MIN_MESH_FALLBACK
                        modified = True
                    if modified:
                        print(f"[ErrorRecovery] 自动调整网格数后重试")
                        return True
            
            # checkMesh失败
            if "checkmesh" in log_lower:
                # 可能是网格质量问题，尝试增加网格数
                if "geometry" in self.current_config:
                    geom = self.current_config["geometry"]
                    # 增加网格数以改善质量
                    geom["nx"] = geom.get("nx", 20) + 5
                    geom["ny"] = geom.get("ny", 20) + 5
                    print(f"[ErrorRecovery] 增加网格数以改善质量后重试")
                    return True
        
        return False
