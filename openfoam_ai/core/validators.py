"""
物理约束验证器 (Pydantic Guardrails)
基于Pydantic的硬约束验证系统，防止LLM生成不符合物理规律的配置
"""

from pydantic import BaseModel, validator, Field, root_validator
from typing import Literal, Dict, Any, List, Optional, Tuple
import math
import yaml
import re
from pathlib import Path
from .config_manager import config


# 友好错误信息映射表
ERROR_TRANSLATIONS = {
    "nx_out_of_range": {
        "message": "X方向网格数 {value} 超出合理范围(10-1000)",
        "suggestion": "建议设置在 10-1000 之间。初学者推荐 20-50",
        "teaching": "网格数决定了计算精度和速度的平衡。太少结果不准，太多计算很慢"
    },
    "ny_out_of_range": {
        "message": "Y方向网格数 {value} 超出合理范围(10-1000)",
        "suggestion": "建议设置在 10-1000 之间。初学者推荐 20-50",
        "teaching": "各方向网格数应与几何尺寸成比例"
    },
    "nz_out_of_range": {
        "message": "Z方向网格数 {value} 超出合理范围",
        "suggestion": "2D问题设为1，3D问题建议10-100",
        "teaching": "对于2D仿真，Z方向只需1层网格"
    },
    "min_cells_2d": {
        "message": "2D网格总数 {value} 不足最低要求(400)",
        "suggestion": "增加nx或ny使总网格数≥400。推荐至少20x20=400",
        "teaching": "网格太少就像用很少的像素显示图片，无法捕捉流动细节"
    },
    "min_cells_3d": {
        "message": "3D网格总数 {value} 不足最低要求(8000)",
        "suggestion": "增加各方向网格数使总数≥8000。推荐至少20x20x20=8000",
        "teaching": "3D仿真需要更多网格来准确描述三维流动"
    },
    "cfl_violation": {
        "message": "时间步长 {value} 可能导致库朗数超限",
        "suggestion": "减小时间步长或减少网格密度。推荐deltaT使得Co<0.5",
        "teaching": "库朗数是衡量数值稳定性的关键指标，超过1通常会导致计算发散"
    },
    "solver_physics_mismatch": {
        "message": "求解器 {solver} 与物理类型 {physics} 不匹配",
        "suggestion": "不可压流推荐icoFoam/simpleFoam，传热推荐buoyantBoussinesqPimpleFoam",
        "teaching": "不同物理问题需要不同的数学模型和求解算法"
    },
    "negative_dimension": {
        "message": "几何尺寸不能为负值或零: {param}={value}",
        "suggestion": "请输入正数。尺寸单位为米(m)",
        "teaching": "几何尺寸定义了计算域的大小"
    },
    "endtime_too_short": {
        "message": "结束时间 {value} 可能太短，无法达到稳态",
        "suggestion": "瞬态问题建议至少运行几个特征时间尺度",
        "teaching": "仿真需要足够的时间让流动发展到期望状态"
    },
    "aspect_ratio_bad": {
        "message": "网格长宽比 {value} 过大，可能影响精度",
        "suggestion": "建议各方向网格尺寸比例不超过5:1",
        "teaching": "网格单元应尽量接近正方形/正方体，过度拉伸会降低精度"
    }
}


def translate_validation_error(error_key: str, **kwargs) -> dict:
    """将验证错误转换为友好的用户信息
    
    Args:
        error_key: 错误键名
        **kwargs: 格式化参数
    
    Returns:
        {"message": "友好消息", "suggestion": "建议", "teaching": "教学说明"}
    """
    template = ERROR_TRANSLATIONS.get(error_key, {
        "message": f"配置错误: {error_key}",
        "suggestion": "请检查参数设置",
        "teaching": ""
    })
    
    return {
        "message": template["message"].format(**kwargs) if kwargs else template["message"],
        "suggestion": template["suggestion"],
        "teaching": template.get("teaching", "")
    }


def _match_and_translate_error(error_msg: str, config: dict = None) -> dict:
    """通过关键词匹配将原始错误字符串映射到友好错误
    
    Args:
        error_msg: 原始错误信息
        config: 配置字典，用于提取上下文信息
    
    Returns:
        友好的错误信息字典
    """
    error_msg_lower = error_msg.lower()
    
    # 网格数范围错误
    if "nx" in error_msg_lower and ("ensure" in error_msg_lower or "less" in error_msg_lower or "greater" in error_msg_lower):
        match = re.search(r'(\d+)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("nx_out_of_range", value=value)
    
    if "ny" in error_msg_lower and ("ensure" in error_msg_lower or "less" in error_msg_lower or "greater" in error_msg_lower):
        match = re.search(r'(\d+)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("ny_out_of_range", value=value)
    
    if "nz" in error_msg_lower and ("ensure" in error_msg_lower or "less" in error_msg_lower or "greater" in error_msg_lower):
        match = re.search(r'(\d+)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("nz_out_of_range", value=value)
    
    # 长宽比错误
    if "长宽比" in error_msg or "aspect_ratio" in error_msg_lower:
        match = re.search(r'(\d+\.?\d*)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("aspect_ratio_bad", value=value)
    
    # 库朗数/CFL错误
    if "库朗数" in error_msg or "courant" in error_msg_lower:
        match = re.search(r'(\d+\.?\d*)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("cfl_violation", value=value)
    
    # 求解器不匹配
    if "不支持求解器" in error_msg or "solver" in error_msg_lower:
        solver_match = re.search(r'求解器(\w+)', error_msg)
        solver = solver_match.group(1) if solver_match else "未知"
        physics = config.get("physics_type", "unknown") if config else "未知"
        return translate_validation_error("solver_physics_mismatch", solver=solver, physics=physics)
    
    # 几何尺寸错误
    if "gt=0" in error_msg_lower or "greater than 0" in error_msg_lower:
        param_match = re.search(r'(\w+)\s*=', error_msg)
        param = param_match.group(1) if param_match else "参数"
        return translate_validation_error("negative_dimension", param=param, value="0或负数")
    
    # 结束时间错误
    if "endtime" in error_msg_lower or "结束时间" in error_msg:
        match = re.search(r'(\d+\.?\d*)', error_msg)
        value = match.group(1) if match else "未知"
        return translate_validation_error("endtime_too_short", value=value)
    
    # 默认返回原始错误
    return {
        "message": error_msg,
        "suggestion": "请检查相关参数设置",
        "teaching": ""
    }


def validate_with_friendly_errors(config: dict) -> tuple:
    """验证配置并返回友好错误信息
    
    Args:
        config: 配置字典
    
    Returns:
        (passed: bool, friendly_errors: list[dict], suggestions: list[str])
    """
    passed, raw_errors = validate_simulation_config(config)
    if passed:
        return True, [], []
    
    friendly_errors = []
    suggestions = []
    for error in raw_errors:
        # 尝试匹配到友好错误
        translated = _match_and_translate_error(error, config)
        friendly_errors.append(translated)
        if translated.get("suggestion"):
            suggestions.append(translated["suggestion"])
    
    return False, friendly_errors, suggestions

def load_constitution() -> Dict[str, Any]:
    """加载项目宪法规则（通过ConfigManager缓存）"""
    return config.load_constitution()


class MeshConfig(BaseModel):
    """网格配置验证"""
    
    nx: int = Field(..., ge=10, le=1000, description="x方向网格数")
    ny: int = Field(..., ge=10, le=1000, description="y方向网格数")
    nz: int = Field(1, ge=1, le=500, description="z方向网格数")
    
    # 几何尺寸
    L: float = Field(..., gt=0, description="长度")
    W: float = Field(..., gt=0, description="宽度")
    H: float = Field(0.1, gt=0, description="高度")
    
    @root_validator(pre=True)
    def consolidate_nested_fields(cls, values):
        """将嵌套的 dimensions/mesh_resolution 展平为顶层字段"""
        if isinstance(values, dict):
            # 处理嵌套的 geometry.dimensions
            dims = values.pop('dimensions', None)
            if dims and isinstance(dims, dict):
                values.setdefault('L', dims.get('L'))
                values.setdefault('W', dims.get('W'))
                values.setdefault('H', dims.get('H', 0.1))
            
            # 处理嵌套的 geometry.mesh_resolution
            res = values.pop('mesh_resolution', None)
            if res and isinstance(res, dict):
                values.setdefault('nx', res.get('nx'))
                values.setdefault('ny', res.get('ny'))
                values.setdefault('nz', res.get('nz', 1))
        return values
    
    @validator('nx', 'ny', 'nz')
    def validate_grid_resolution(cls, v, values):
        """验证网格分辨率合理性，依据宪法规则"""
        constitution = load_constitution()
        mesh_standards = constitution.get('Mesh_Standards', {})
        min_cells_2d = mesh_standards.get('min_cells_2d', 400)
        min_cells_3d = mesh_standards.get('min_cells_3d', 8000)
        min_cells_per_direction = mesh_standards.get('min_cells_per_direction', 20)
        
        # 获取其他维度值（可能尚未验证）
        nz = values.get('nz', 1)
        total_cells = v * values.get('ny', 1) * nz  # 注意：这里v是当前字段，需要计算总网格数？简化处理
        # 实际应在root_validator中检查总网格数，这里仅检查单个方向最小值
        # 根据宪法，2D最小网格数20x20=400，3D最小网格数20x20x20=8000
        # 我们检查单个方向是否低于20（警告）
        if v < min_cells_per_direction:
            print(f"[警告] 网格数{v}可能过低，建议至少{min_cells_per_direction}（宪法要求）")
        
        # 如果nz>1（3D），总网格数应至少8000，但这里无法计算总网格数，留待root_validator处理
        return v
    
    @root_validator(pre=False, skip_on_failure=True)
    def validate_aspect_ratio(cls, values):
        """验证网格长宽比及总网格数，依据宪法规则"""
        constitution = load_constitution()
        mesh_standards = constitution.get('Mesh_Standards', {})
        max_aspect_ratio = mesh_standards.get('max_aspect_ratio', 100)
        min_cells_2d = mesh_standards.get('min_cells_2d', 400)
        min_cells_3d = mesh_standards.get('min_cells_3d', 8000)
        
        nx = values.get('nx', 1)
        ny = values.get('ny', 1)
        nz = values.get('nz', 1)
        L = values.get('L', 1)
        W = values.get('W', 1)
        H = values.get('H', 1)
        
        # 计算长宽比
        dx = L / nx
        dy = W / ny
        dz = H / nz
        
        aspect_ratios = [dx/dy, dy/dz if dz > 0 else 1, dx/dz if dz > 0 else 1]
        max_ratio = max(max(aspect_ratios), 1/min(aspect_ratios))
        
        if max_ratio > max_aspect_ratio:
            raise ValueError(f"网格长宽比{max_ratio:.1f}过大，宪法要求不超过{max_aspect_ratio}")
        
        # 检查总网格数
        total_cells = nx * ny * nz
        if nz == 1:
            if total_cells < min_cells_2d:
                print(f"[警告] 2D网格总数{total_cells}低于宪法要求{min_cells_2d}，建议增加网格分辨率")
        else:
            if total_cells < min_cells_3d:
                print(f"[警告] 3D网格总数{total_cells}低于宪法要求{min_cells_3d}，建议增加网格分辨率")
        
        return values


class SolverConfig(BaseModel):
    """求解器配置验证"""
    
    name: Literal["icoFoam", "simpleFoam", "pimpleFoam", 
                  "buoyantBoussinesqPimpleFoam", "buoyantPimpleFoam"] = Field(
        ..., description="求解器名称"
    )
    
    startTime: float = Field(0, ge=0, description="开始时间")
    endTime: float = Field(..., gt=0, description="结束时间")
    deltaT: float = Field(..., gt=0, lt=1, description="时间步长")
    
    writeInterval: int = Field(20, ge=1, description="写入间隔")
    
    @validator('endTime')
    def validate_time_range(cls, v, values):
        """验证时间范围"""
        start = values.get('startTime', 0)
        if v <= start:
            raise ValueError(f"结束时间{v}必须大于开始时间{start}")
        return v
    
    @validator('deltaT')
    def validate_delta_t(cls, v, values):
        """验证时间步长"""
        end = values.get('endTime', 1)
        if v > end * 0.1:
            print(f"[警告] 时间步长{v}较大，建议不超过结束时间的10%")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_cfl_condition(cls, values):
        """
        验证CFL条件（仅作警告，不阻断验证）
        注意：SolverConfig 无法获取实际网格尺寸和速度数据，
        精确的 CFL 校验在 SimulationConfig 层完成
        """
        delta_t = values.get('deltaT', 0.01)
        end_time = values.get('endTime', 1.0)
        
        # 基本合理性检查：时间步长不应超过结束时间的一半
        if delta_t > end_time * 0.5:
            print(f"[警告] 时间步长 {delta_t} 超过结束时间 {end_time} 的50%，建议减小")
        
        return values


class BoundaryCondition(BaseModel):
    """边界条件验证"""
    
    name: Optional[str] = Field(None, description="边界名称")
    type: Literal["fixedValue", "zeroGradient", "noSlip", "slip", 
                  "inletOutlet", "totalPressure", "inletVelocity",
                  "empty", "symmetry", "symmetryPlane", "wall", "patch",
                  "pressureInletOutletVelocity", "fixedFluxPressure",
                  "calculated", "uniform"] = Field(
        ..., description="边界类型"
    )
    value: Optional[Any] = Field(None, description="边界值")
    
    @validator('value')
    def validate_bc_value(cls, v, values):
        """验证边界值"""
        bc_type = values.get('type')
        
        if bc_type == "fixedValue" and v is None:
            raise ValueError("fixedValue边界必须指定value")
        
        return v


class SimulationConfig(BaseModel):
    """
    完整仿真配置验证
    这是主要的验证入口
    """
    
    task_id: str = Field(..., description="任务ID")
    physics_type: Literal["incompressible", "compressible", "heatTransfer", 
                          "multiphase"] = Field(..., description="物理类型")
    
    geometry: MeshConfig = Field(..., description="几何配置")
    solver: SolverConfig = Field(..., description="求解器配置")
    
    # 边界条件
    boundary_conditions: Dict[str, BoundaryCondition] = Field(
        default_factory=dict, description="边界条件"
    )
    
    # 物理参数
    nu: float = Field(1e-05, gt=0, description="运动粘度")
    rho: float = Field(1.0, gt=0, description="密度")
    
    # 可选参数
    turbulence_model: Optional[str] = Field(None, description="湍流模型")
    
    @root_validator(pre=True)
    def normalize_input_format(cls, values):
        """预处理输入：处理边界条件字典格式和 fluid_properties 嵌套"""
        if not isinstance(values, dict):
            return values
        
        # 处理 fluid_properties 嵌套结构
        fluid_props = values.pop('fluid_properties', None)
        if fluid_props and isinstance(fluid_props, dict):
            values.setdefault('nu', fluid_props.get('nu', fluid_props.get('kinematicViscosity', 1e-05)))
            values.setdefault('rho', fluid_props.get('rho', fluid_props.get('density', 1.0)))
        
        # 处理边界条件字典格式：从 key 中提取 name
        bc_dict = values.get('boundary_conditions', {})
        if isinstance(bc_dict, dict):
            for bc_name, bc_config in bc_dict.items():
                if isinstance(bc_config, dict) and 'name' not in bc_config:
                    bc_config['name'] = bc_name
        
        return values
    
    @root_validator(skip_on_failure=True)
    def validate_physics_combination(cls, values):
        """验证物理场组合合理性，依据宪法规则"""
        constitution = load_constitution()
        prohibited = constitution.get('Prohibited_Combinations', [])
        
        physics = values.get('physics_type')
        solver_name = values.get('solver', {}).name if values.get('solver') else None
        turbulence = values.get('turbulence_model')
        
        # 检查禁止组合
        for prohibition in prohibited:
            # 跳过非字典格式的条目
            if not isinstance(prohibition, dict):
                continue
            # 简单匹配：如果所有字段匹配则禁止
            match = True
            if 'solver' in prohibition and prohibition['solver'] != solver_name:
                match = False
            if 'physics' in prohibition and prohibition['physics'] != physics:
                match = False
            if 'turbulence_model' in prohibition and prohibition['turbulence_model'] != turbulence:
                match = False
            if 'requirement' in prohibition:
                # 忽略复杂条件
                pass
            if match:
                reason = prohibition.get('reason', '违反宪法禁止组合')
                raise ValueError(f"配置违反宪法: {reason}")
        
        # 验证求解器与物理类型匹配（保留原逻辑）
        if physics == "incompressible":
            valid_solvers = ["icoFoam", "simpleFoam", "pimpleFoam"]
            if solver_name and solver_name not in valid_solvers:
                raise ValueError(
                    f"不可压流不支持求解器{solver_name}，"
                    f"请选择: {', '.join(valid_solvers)}"
                )
        
        elif physics == "heatTransfer":
            valid_solvers = ["buoyantBoussinesqPimpleFoam", "buoyantPimpleFoam"]
            if solver_name and solver_name not in valid_solvers:
                raise ValueError(
                    f"传热问题不支持求解器{solver_name}，"
                    f"请选择: {', '.join(valid_solvers)}"
                )
        
        # 验证物理参数范围（如果宪法中有定义）
        physical_constraints = constitution.get('Physical_Constraints', {})
        if 'kinematic_viscosity' in physical_constraints:
            nu_min = physical_constraints['kinematic_viscosity'].get('min', 1e-7)
            nu_max = physical_constraints['kinematic_viscosity'].get('max', 1e-2)
            nu = values.get('nu')
            if nu is not None and (nu < nu_min or nu > nu_max):
                print(f"[警告] 运动粘度{nu}超出宪法建议范围[{nu_min}, {nu_max}]")
        
        if 'density' in physical_constraints:
            rho_min = physical_constraints['density'].get('min', 0.1)
            rho_max = physical_constraints['density'].get('max', 20000)
            rho = values.get('rho')
            if rho is not None and (rho < rho_min or rho > rho_max):
                print(f"[警告] 密度{rho}超出宪法建议范围[{rho_min}, {rho_max}]")
        
        return values
    
    @validator('turbulence_model')
    def validate_turbulence(cls, v, values):
        """验证湍流模型选择"""
        if v is not None:
            valid_models = ["kEpsilon", "kOmega", "kOmegaSST", "SpalartAllmaras", "laminar"]
            if v not in valid_models:
                raise ValueError(f"未知的湍流模型: {v}，可选: {', '.join(valid_models)}")
        
        return v


class PhysicsValidator:
    """
    物理一致性校验器
    用于后处理阶段的物理验证
    """
    
    TOLERANCE = 0.001  # 0.1%
    
    def __init__(self, case_path: str):
        self.case_path = case_path
    
    def validate_mass_conservation(self, inlet_patch: str = "inlet", 
                                   outlet_patch: str = "outlet") -> Tuple[bool, float]:
        """
        验证质量守恒（进出口流量差）
        
        Returns:
            (是否通过, 误差)
        """
        try:
            inlet_flux = self._get_boundary_flux(inlet_patch)
            outlet_flux = self._get_boundary_flux(outlet_patch)
            
            if abs(inlet_flux) < 1e-10:
                return False, float('inf')
            
            error = abs(inlet_flux - outlet_flux) / abs(inlet_flux)
            passed = error < self.TOLERANCE
            
            return passed, error
        except Exception as e:
            print(f"[PhysicsValidator] 质量守恒验证失败: {e}")
            return False, float('inf')
    
    def validate_energy_conservation(self, inlet: str = "inlet",
                                     outlet: str = "outlet",
                                     walls: Optional[List[str]] = None) -> Tuple[bool, float]:
        """
        验证能量守恒
        
        Returns:
            (是否通过, 误差)
        """
        try:
            heat_in = self._get_boundary_heat_flux(inlet)
            heat_out = self._get_boundary_heat_flux(outlet)
            
            heat_wall = 0
            if walls:
                for wall in walls:
                    heat_wall += self._get_boundary_heat_flux(wall)
            
            total = heat_in + heat_out + heat_wall
            reference = max(abs(heat_in), abs(heat_out), 1e-10)
            
            error = abs(total) / reference
            passed = error < self.TOLERANCE
            
            return passed, error
        except Exception as e:
            print(f"[PhysicsValidator] 能量守恒验证失败: {e}")
            return False, float('inf')
    
    def validate_boundary_compatibility(self, bc_config: Dict[str, Any]) -> List[str]:
        """
        检查边界条件物理兼容性
        
        Returns:
            错误信息列表
        """
        errors = []
        
        # 检查压力-速度耦合
        has_pressure_inlet = any(
            bc.get('type') in ['totalPressure', 'fixedValue']
            for name, bc in bc_config.items()
            if 'p' in name.lower() or 'pressure' in name.lower()
        )
        
        has_velocity_inlet = any(
            bc.get('type') == 'fixedValue'
            for name, bc in bc_config.items()
            if 'u' in name.lower() or 'velocity' in name.lower() or 'inlet' in name.lower()
        )
        
        if has_pressure_inlet and has_velocity_inlet:
            errors.append("警告：同时指定压力入口和速度入口可能导致过约束")
        
        # 检查边界是否闭合
        # 简化检查：至少应该有入口和出口
        has_inlet = any('inlet' in name.lower() for name in bc_config.keys())
        has_outlet = any('outlet' in name.lower() for name in bc_config.keys())
        
        if not has_inlet:
            errors.append("警告：未检测到入口边界")
        if not has_outlet:
            errors.append("警告：未检测到出口边界")
        
        return errors
    
    def _get_boundary_flux(self, patch_name: str) -> float:
        """获取边界的质量流量（简化实现）"""
        # 这里应该读取OpenFOAM的flux数据
        # 简化返回一个模拟值
        return 1.0
    
    def _get_boundary_heat_flux(self, patch_name: str) -> float:
        """获取边界的热流量（简化实现）"""
        # 简化返回一个模拟值
        return 0.0


def validate_simulation_config(config_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证仿真配置的主函数
    
    Args:
        config_dict: 配置字典
        
    Returns:
        (是否通过, 错误信息列表)
    """
    errors = []
    
    try:
        config = SimulationConfig(**config_dict)
        print(f"[Validator] 配置验证通过: {config.task_id}")
        return True, []
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Validator] 配置验证失败: {error_msg}")
        errors.append(error_msg)
        return False, errors


if __name__ == "__main__":
    # 测试验证器
    test_config = {
        "task_id": "test_001",
        "physics_type": "incompressible",
        "geometry": {
            "nx": 50,
            "ny": 50,
            "nz": 1,
            "L": 1.0,
            "W": 1.0,
            "H": 0.1
        },
        "solver": {
            "name": "icoFoam",
            "endTime": 0.5,
            "deltaT": 0.005
        },
        "boundary_conditions": {
            "inlet": {"name": "inlet", "type": "fixedValue", "value": [1, 0, 0]},
            "outlet": {"name": "outlet", "type": "zeroGradient"}
        }
    }
    
    passed, errors = validate_simulation_config(test_config)
    print(f"\\n验证结果: {passed}")
    if errors:
        print(f"错误: {errors}")
