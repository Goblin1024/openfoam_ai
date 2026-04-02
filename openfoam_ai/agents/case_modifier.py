"""
Case Modifier Module
参数解析与修改处理模块

负责：
1. 从自然语言中解析参数修改意图
2. 应用修改到配置
3. 生成变更摘要
"""

import re
import copy
from typing import Dict, Any, List, Tuple, Optional


class CaseModifier:
    """
    算例修改器
    
    职责：
    1. 解析用户的修改意图
    2. 应用修改到配置
    3. 生成变更对比
    """
    
    # 网格修改正则模式
    MESH_PATTERNS: List[Tuple[str, List[str]]] = [
        (r"网格.*?改.*?成.*?(\d+)\s*x\s*(\d+)", ["nx", "ny"]),
        (r"网格.*?设.*?为.*?(\d+)\s*x\s*(\d+)", ["nx", "ny"]),
        (r"网格.*?([\d\.]+)\s*x\s*([\d\.]+)", ["nx", "ny"]),
        (r"分辨率.*?改.*?成.*?(\d+)\s*x\s*(\d+)", ["nx", "ny"]),
        (r"nx.*?[=:]?\s*(\d+)", ["nx"]),
        (r"ny.*?[=:]?\s*(\d+)", ["ny"]),
        (r"nz.*?[=:]?\s*(\d+)", ["nz"]),
    ]
    
    # 时间步长修改正则模式
    DT_PATTERNS: List[str] = [
        r"时间步长.*?改.*?成.*?([\d.eE-]+)",
        r"时间步.*?设.*?为.*?([\d.eE-]+)",
        r"dt.*?[=:]?\s*([\d.eE-]+)",
        r"deltaT.*?[=:]?\s*([\d.eE-]+)",
    ]
    
    # 结束时间修改正则模式
    ENDTIME_PATTERNS: List[str] = [
        r"结束时间.*?改.*?成.*?([\d.eE-]+)",
        r"运行到.*?([\d.eE-]+)",
        r"endTime.*?[=:]?\s*([\d.eE-]+)",
    ]
    
    # 运动粘度修改正则模式
    NU_PATTERNS: List[str] = [
        r"粘度.*?改.*?成.*?([\d.eE-]+)",
        r"粘度.*?设.*?为.*?([\d.eE-]+)",
        r"nu.*?[=:]?\s*([\d.eE-]+)",
        r"运动粘度.*?([\d.eE-]+)",
    ]
    
    # 求解器关键词映射
    SOLVER_KEYWORDS: Dict[str, str] = {
        "icofoam": "icoFoam",
        "simplefoam": "simpleFoam",
        "pimplefoam": "pimpleFoam",
        "buoyantboussinesqpimplefoam": "buoyantBoussinesqPimpleFoam",
    }
    
    def __init__(self):
        """初始化CaseModifier"""
        pass
    
    def parse_modifications(self, user_input: str) -> Dict[str, Any]:
        """从自然语言中提取参数名和目标值
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            修改参数字典，如 {"nx": 40, "ny": 40, "deltaT": 0.001}
        """
        modifications = {}
        input_lower = user_input.lower()
        
        # 网格修改模式
        for pattern, keys in self.MESH_PATTERNS:
            match = re.search(pattern, input_lower)
            if match:
                for i, key in enumerate(keys):
                    try:
                        modifications[key] = int(match.group(i + 1))
                    except (ValueError, IndexError):
                        pass
        
        # 时间步长修改
        for pattern in self.DT_PATTERNS:
            match = re.search(pattern, input_lower)
            if match:
                try:
                    modifications["deltaT"] = float(match.group(1))
                except ValueError:
                    pass
                break
        
        # 结束时间修改
        for pattern in self.ENDTIME_PATTERNS:
            match = re.search(pattern, input_lower)
            if match:
                try:
                    modifications["endTime"] = float(match.group(1))
                except ValueError:
                    pass
                break
        
        # 运动粘度修改
        for pattern in self.NU_PATTERNS:
            match = re.search(pattern, input_lower)
            if match:
                try:
                    modifications["nu"] = float(match.group(1))
                except ValueError:
                    pass
                break
        
        # 求解器修改
        for keyword, solver_name in self.SOLVER_KEYWORDS.items():
            if keyword in input_lower or solver_name.lower() in input_lower:
                modifications["solver_name"] = solver_name
                break
        
        return modifications
    
    def apply_modifications(self, config: Dict[str, Any], modifications: Dict[str, Any]) -> Dict[str, Any]:
        """将修改应用到配置副本
        
        Args:
            config: 原始配置
            modifications: 修改参数
            
        Returns:
            修改后的配置副本
        """
        new_config = copy.deepcopy(config)
        
        # 应用网格修改
        if "nx" in modifications or "ny" in modifications or "nz" in modifications:
            geom = new_config.get("geometry", {})
            res = geom.get("mesh_resolution", {})
            if "nx" in modifications:
                res["nx"] = modifications["nx"]
            if "ny" in modifications:
                res["ny"] = modifications["ny"]
            if "nz" in modifications:
                res["nz"] = modifications["nz"]
            geom["mesh_resolution"] = res
            new_config["geometry"] = geom
        
        # 应用求解器参数修改
        if "deltaT" in modifications or "endTime" in modifications or "solver_name" in modifications:
            solver = new_config.get("solver", {})
            if "deltaT" in modifications:
                solver["deltaT"] = modifications["deltaT"]
            if "endTime" in modifications:
                solver["endTime"] = modifications["endTime"]
            if "solver_name" in modifications:
                solver["name"] = modifications["solver_name"]
            new_config["solver"] = solver
        
        # 应用物理参数修改
        if "nu" in modifications:
            new_config["nu"] = modifications["nu"]
        
        return new_config
    
    def generate_change_summary(self, old: Dict[str, Any], new: Dict[str, Any]) -> str:
        """生成变更对比摘要
        
        Args:
            old: 旧配置
            new: 新配置
            
        Returns:
            变更摘要文本
        """
        changes = []
        
        # 检查网格变化
        old_res = old.get("geometry", {}).get("mesh_resolution", {})
        new_res = new.get("geometry", {}).get("mesh_resolution", {})
        for key in ["nx", "ny", "nz"]:
            if old_res.get(key) != new_res.get(key):
                changes.append(f"  {key}: {old_res.get(key)} → {new_res.get(key)}")
        
        # 检查求解器参数变化
        old_solver = old.get("solver", {})
        new_solver = new.get("solver", {})
        for key in ["deltaT", "endTime", "name"]:
            if old_solver.get(key) != new_solver.get(key):
                changes.append(f"  {key}: {old_solver.get(key)} → {new_solver.get(key)}")
        
        # 检查物理参数变化
        if old.get("nu") != new.get("nu"):
            changes.append(f"  nu (运动粘度): {old.get('nu')} → {new.get('nu')}")
        
        return "\n".join(changes) if changes else "  (无可见变更)"
    
    def get_modification_hints(self) -> str:
        """获取修改提示文本"""
        return (
            "请具体说明要修改什么参数。例如：\n"
            "• \"把网格改成40x40\"\n"
            "• \"时间步长改为0.001\"\n"
            "• \"运动粘度设为1e-6\""
        )
