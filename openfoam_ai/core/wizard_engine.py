"""
向导引擎模块 (WizardEngine)
为零基础用户提供分步向导式仿真配置界面
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import uuid
import yaml
import logging

from .validators import validate_simulation_config
from .config_manager import config

logger = logging.getLogger(__name__)


class WizardStep(Enum):
    """向导步骤枚举"""
    SCENARIO = 0      # 场景选择
    GEOMETRY = 1      # 几何参数
    MESH = 2          # 网格设置
    BOUNDARY = 3      # 边界条件
    SOLVER = 4        # 求解器配置
    REVIEW_RUN = 5    # 审查与运行


@dataclass
class StepInfo:
    """步骤信息数据类"""
    step: WizardStep
    title: str
    description: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)
    teaching_notes: Dict[str, str] = field(default_factory=dict)
    is_first: bool = False
    is_last: bool = False


def _load_scenario_templates() -> Dict[str, Dict[str, Any]]:
    """从YAML文件加载场景模板"""
    knowledge_dir = Path(__file__).parent.parent / "config" / "knowledge"
    filepath = knowledge_dir / "scenarios.yaml"

    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and "scenario_templates" in data:
                    return data["scenario_templates"]
                else:
                    logger.warning(f"场景模板数据为空或格式错误: {filepath}")
        else:
            logger.warning(f"场景模板文件不存在: {filepath}")
    except Exception as e:
        logger.error(f"加载场景模板失败: {e}")

    return {}


# 场景模板库（从YAML加载）
SCENARIO_TEMPLATES: Dict[str, Dict[str, Any]] = _load_scenario_templates()


# 求解器映射表
SOLVER_MAP: Dict[str, List[Dict[str, Any]]] = {
    "incompressible": [
        {"name": "icoFoam", "description": "瞬态不可压层流求解器", "transient": True},
        {"name": "simpleFoam", "description": "稳态不可压求解器", "transient": False},
        {"name": "pimpleFoam", "description": "瞬态不可压求解器（支持大时间步）", "transient": True}
    ],
    "compressible": [
        {"name": "rhoSimpleFoam", "description": "稳态可压求解器", "transient": False},
        {"name": "rhoPimpleFoam", "description": "瞬态可压求解器", "transient": True}
    ],
    "heatTransfer": [
        {"name": "buoyantBoussinesqPimpleFoam", "description": "瞬态浮力驱动流（Boussinesq近似）", "transient": True},
        {"name": "buoyantPimpleFoam", "description": "瞬态浮力驱动流（完全可压）", "transient": True}
    ],
    "multiphase": [
        {"name": "interFoam", "description": "VOF多相流求解器", "transient": True},
        {"name": "multiphaseInterFoam", "description": "多相VOF求解器", "transient": True}
    ]
}


class WizardEngine:
    """向导引擎主类"""
    
    def __init__(self):
        """初始化向导引擎"""
        self._current_step = WizardStep.SCENARIO
        self._collected_params: Dict[str, Any] = {}
        self._step_history: List[WizardStep] = []
        self._wizard_id = f"wizard_{uuid.uuid4().hex[:8]}"
        self._selected_scenario: Optional[str] = None
        
        # 加载宪法配置
        self._constitution = config.load_constitution()
        self._mesh_standards = self._constitution.get('Mesh_Standards', {})
        self._solver_standards = self._constitution.get('Solver_Standards', {})
    
    def get_step_info(self, step: Optional[WizardStep] = None) -> StepInfo:
        """获取指定步骤的完整信息"""
        if step is None:
            step = self._current_step
        
        step_methods = {
            WizardStep.SCENARIO: self._get_scenario_step_info,
            WizardStep.GEOMETRY: self._get_geometry_step_info,
            WizardStep.MESH: self._get_mesh_step_info,
            WizardStep.BOUNDARY: self._get_boundary_step_info,
            WizardStep.SOLVER: self._get_solver_step_info,
            WizardStep.REVIEW_RUN: self._get_review_step_info
        }
        return step_methods[step]()
    
    def _get_scenario_step_info(self) -> StepInfo:
        """获取场景选择步骤信息"""
        scenarios = [
            {
                "id": key,
                "name": template["name"],
                "name_en": template["name_en"],
                "description": template["description"],
                "icon": template["icon"],
                "difficulty": template["difficulty"]
            }
            for key, template in (SCENARIO_TEMPLATES if SCENARIO_TEMPLATES else _load_scenario_templates()).items()
        ]
        
        return StepInfo(
            step=WizardStep.SCENARIO,
            title="选择仿真场景",
            description="请选择一个预设场景或自定义配置。每个场景都包含推荐的默认参数。",
            fields=[{
                "name": "scenario_id",
                "type": "select",
                "label": "仿真场景",
                "options": scenarios,
                "required": True
            }],
            teaching_notes={
                "what": "场景模板包含了特定类型仿真的推荐配置。",
                "why": "使用模板可以避免从零开始的困难，确保配置的合理性。",
                "tips": "初学者建议从'方腔驱动流'或'管道流'开始。"
            },
            is_first=True,
            is_last=False
        )
    
    def _get_geometry_step_info(self) -> StepInfo:
        """获取几何参数步骤信息"""
        defaults = {"L": 1.0, "W": 1.0, "H": 0.1}
        if self._selected_scenario:
            template = self._get_scenario_template(self._selected_scenario)
            if template:
                defaults.update(template.get("default_geometry", {}))
        defaults.update(self._collected_params.get("geometry", {}))
        
        return StepInfo(
            step=WizardStep.GEOMETRY,
            title="设置几何参数",
            description="定义计算域的尺寸。对于2D问题，H表示厚度方向，通常设为0.1。",
            fields=[
                {"name": "L", "type": "number", "label": "长度 (L)", "unit": "m", "min": 0.001, "max": 1000, "required": True, "help": "计算域在x方向的长度"},
                {"name": "W", "type": "number", "label": "宽度 (W)", "unit": "m", "min": 0.001, "max": 1000, "required": True, "help": "计算域在y方向的宽度"},
                {"name": "H", "type": "number", "label": "高度 (H)", "unit": "m", "min": 0.0001, "max": 1000, "required": True, "help": "计算域在z方向的高度。对于2D问题，设为0.1并在前后边界使用empty类型"}
            ],
            defaults=defaults,
            teaching_notes={
                "what": "几何参数定义了计算域的物理尺寸。",
                "why": "正确的几何尺寸是获得有意义结果的基础。",
                "tips": "2D问题的H可以设为任意小值（如0.1），但必须在边界条件中将前后设为empty类型。"
            },
            is_first=False,
            is_last=False
        )
    
    def _get_mesh_step_info(self) -> StepInfo:
        """获取网格设置步骤信息"""
        defaults = {"nx": 40, "ny": 40, "nz": 1}
        if self._selected_scenario:
            template = self._get_scenario_template(self._selected_scenario)
            if template:
                defaults.update(template.get("default_mesh", {}))
        defaults.update(self._collected_params.get("mesh", {}))
        
        recommendations = self._calculate_mesh_recommendations()
        total_cells = defaults.get("nx", 40) * defaults.get("ny", 40) * defaults.get("nz", 1)
        
        return StepInfo(
            step=WizardStep.MESH,
            title="设置网格分辨率",
            description=f"定义计算网格。当前总网格数约 {total_cells}。",
            fields=[
                {"name": "nx", "type": "integer", "label": "X方向网格数", "min": 10, "max": 1000, "required": True, "help": f"推荐值: {recommendations.get('nx', 40)}"},
                {"name": "ny", "type": "integer", "label": "Y方向网格数", "min": 10, "max": 1000, "required": True, "help": f"推荐值: {recommendations.get('ny', 40)}"},
                {"name": "nz", "type": "integer", "label": "Z方向网格数", "min": 1, "max": 500, "required": True, "help": "2D问题设为1，3D问题至少设为20"}
            ],
            defaults=defaults,
            teaching_notes={
                "what": "网格将计算域离散为有限个小单元，是CFD计算的基础。",
                "why": "网格数量影响计算精度和时间。过粗影响精度，过细增加计算成本。",
                "tips": f"根据宪法规则，2D最少400单元，3D最少8000单元。当前推荐: nx={recommendations.get('nx', 40)}, ny={recommendations.get('ny', 40)}"
            },
            is_first=False,
            is_last=False
        )
    
    def _get_boundary_step_info(self) -> StepInfo:
        """获取边界条件步骤信息"""
        defaults = {}
        if self._selected_scenario:
            template = self._get_scenario_template(self._selected_scenario)
            if template:
                defaults = template.get("default_boundary", {}).copy()
        defaults.update(self._collected_params.get("boundary", {}))
        
        fields = []
        for boundary_name, boundary_def in defaults.items():
            fields.append({
                "name": boundary_name,
                "type": "boundary_condition",
                "label": boundary_def.get("description", boundary_name),
                "default_type": boundary_def.get("type", "noSlip"),
                "default_value": boundary_def.get("value"),
                "field": boundary_def.get("field", "U"),
                "help": f"边界类型: {boundary_def.get('type', 'noSlip')}"
            })
        
        return StepInfo(
            step=WizardStep.BOUNDARY,
            title="设置边界条件",
            description="定义计算域边界上的物理条件。边界条件必须与物理问题相匹配。",
            fields=fields,
            defaults=defaults,
            teaching_notes={
                "what": "边界条件指定了边界上的物理量（速度、压力、温度等）。",
                "why": "边界条件决定了流动的特性，错误的边界条件会导致错误的结果。",
                "tips": "确保至少有一个入口和一个出口；壁面通常使用noSlip；2D的前后边界必须使用empty。"
            },
            is_first=False,
            is_last=False
        )
    
    def _get_solver_step_info(self) -> StepInfo:
        """获取求解器配置步骤信息"""
        physics_type = self._collected_params.get("physics_type", "incompressible")
        scenario_template = None
        if self._selected_scenario:
            scenario_template = self._get_scenario_template(self._selected_scenario)
            if scenario_template:
                physics_type = scenario_template.get("physics_type", physics_type)

        available_solvers = SOLVER_MAP.get(physics_type, SOLVER_MAP["incompressible"])
        recommendations = self._calculate_time_step_recommendations()

        defaults = {
            "solver_name": recommendations.get("recommended_solver", "icoFoam"),
            "endTime": 0.5,
            "deltaT": recommendations.get("recommended_deltaT", 0.005),
            "writeInterval": 100
        }
        if scenario_template:
            defaults["solver_name"] = scenario_template.get("recommended_solver", defaults.get("solver_name", "icoFoam"))
            defaults["endTime"] = scenario_template.get("default_endTime", defaults.get("endTime", 0.5))
            defaults["deltaT"] = scenario_template.get("default_deltaT", defaults.get("deltaT", 0.005))
        defaults.update(self._collected_params.get("solver", {}))
        
        return StepInfo(
            step=WizardStep.SOLVER,
            title="配置求解器",
            description="选择求解器并设置时间参数。",
            fields=[
                {"name": "solver_name", "type": "select", "label": "求解器", "options": [{"value": s["name"], "label": f"{s['name']} - {s['description']}"} for s in available_solvers], "required": True, "help": "根据物理类型选择合适的求解器"},
                {"name": "endTime", "type": "number", "label": "结束时间", "unit": "s", "min": 0.001, "max": 100000, "required": True, "help": "瞬态计算的终止时间，稳态计算设为1000左右"},
                {"name": "deltaT", "type": "number", "label": "时间步长", "unit": "s", "min": 1e-8, "max": 10, "required": True, "help": f"推荐值: {recommendations.get('recommended_deltaT', 0.005)}（满足CFL条件）"},
                {"name": "writeInterval", "type": "integer", "label": "写入间隔", "min": 1, "max": 10000, "required": True, "help": "每多少步保存一次结果，默认100"},
                {"name": "nu", "type": "number", "label": "运动粘度", "unit": "m²/s", "min": 1e-7, "max": 1e-2, "required": True, "help": "水的运动粘度约1e-6，空气约1.5e-5"}
            ],
            defaults=defaults,
            teaching_notes={
                "what": "求解器配置控制数值计算的进程。",
                "why": "正确的时间步长保证计算稳定性，结束时间决定计算覆盖的物理时间。",
                "tips": f"推荐时间步长 {recommendations.get('recommended_deltaT', 0.005)} 基于CFL条件估算。稳态计算可将endTime设为1000，deltaT设为1。"
            },
            is_first=False,
            is_last=False
        )
    
    def _get_review_step_info(self) -> StepInfo:
        """获取审查步骤信息"""
        config_preview = self.build_config()
        
        return StepInfo(
            step=WizardStep.REVIEW_RUN,
            title="审查与运行",
            description="请检查以下配置，确认无误后点击运行。",
            fields=[
                {"name": "config_preview", "type": "json_preview", "label": "配置预览", "value": config_preview},
                {"name": "case_name", "type": "text", "label": "算例名称", "default": f"wizard_case_{self._wizard_id[-6:]}", "required": True}
            ],
            defaults={"case_name": f"wizard_case_{self._wizard_id[-6:]}"},
            teaching_notes={
                "what": "最后检查所有配置是否正确。",
                "why": "预防性检查可以避免计算失败和时间浪费。",
                "tips": "特别注意网格总数、时间步长和边界条件设置。"
            },
            is_first=False,
            is_last=True
        )
    
    def _get_scenario_template(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景模板，优先从已加载的全局变量获取"""
        if SCENARIO_TEMPLATES:
            return SCENARIO_TEMPLATES.get(scenario_id)
        # 如果全局变量为空，尝试重新加载
        return _load_scenario_templates().get(scenario_id)

    def _calculate_mesh_recommendations(self) -> Dict[str, int]:
        """计算网格推荐值"""
        geometry = self._collected_params.get("geometry", {})
        L = geometry.get("L", 1.0)
        W = geometry.get("W", 1.0)

        defaults = self._get_scenario_template(self._selected_scenario) or {}
        default_mesh = defaults.get("default_mesh", {"nx": 40, "ny": 40, "nz": 1})
        nx, ny, nz = default_mesh["nx"], default_mesh["ny"], default_mesh["nz"]
        
        aspect_ratio = L / W if W > 0 else 1.0
        if aspect_ratio > 2:
            nx = int(nx * aspect_ratio / 2)
        elif aspect_ratio < 0.5:
            ny = int(ny / aspect_ratio / 2)
        
        return {"nx": max(20, min(1000, nx)), "ny": max(20, min(1000, ny)), "nz": nz}
    
    def _calculate_time_step_recommendations(self) -> Dict[str, Any]:
        """计算时间步长推荐值"""
        geometry = self._collected_params.get("geometry", {})
        mesh = self._collected_params.get("mesh", {})
        L = geometry.get("L", 1.0)
        nx = mesh.get("nx", 40)
        dx = L / nx if nx > 0 else 0.025
        u_max = 1.0
        
        max_courant_explicit = self._solver_standards.get('max_courant_explicit', 0.5)
        max_courant_implicit = self._solver_standards.get('max_courant_implicit', 5.0)
        
        dt_explicit = max_courant_explicit * dx / u_max if u_max > 0 else 0.001
        dt_implicit = max_courant_implicit * dx / u_max if u_max > 0 else 0.01
        
        scenario_template = self._get_scenario_template(self._selected_scenario) or {}
        physics_type = scenario_template.get("physics_type", "incompressible")
        solver_map = {"incompressible": "icoFoam", "heatTransfer": "buoyantBoussinesqPimpleFoam", "multiphase": "interFoam"}
        recommended_solver = solver_map.get(physics_type, "icoFoam")
        
        is_explicit = recommended_solver in ["icoFoam"]
        recommended_deltaT = round(dt_explicit if is_explicit else min(dt_implicit, 0.01), 6)
        
        return {
            "recommended_solver": recommended_solver,
            "recommended_deltaT": recommended_deltaT,
            "alternative_deltaT": dt_implicit,
            "estimated_courant": u_max * recommended_deltaT / dx if dx > 0 else 0
        }
    
    def validate_step(self, step: WizardStep, params: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """验证当前步骤参数"""
        errors = []
        suggestions = []
        
        if step == WizardStep.SCENARIO:
            scenario_id = params.get("scenario_id")
            if not scenario_id:
                errors.append("请选择一个仿真场景")
            elif not self._get_scenario_template(scenario_id):
                errors.append(f"未知的场景: {scenario_id}")
        
        elif step == WizardStep.GEOMETRY:
            for name in ["L", "W", "H"]:
                val = params.get(name)
                if val is None or val <= 0:
                    errors.append(f"{name}必须大于0")
            
            L, W = params.get("L"), params.get("W")
            if L and W and (L / W > 100 or W / L > 100):
                suggestions.append("长宽比过大，可能需要调整网格分布")
        
        elif step == WizardStep.MESH:
            nx, ny, nz = params.get("nx"), params.get("ny"), params.get("nz", 1)
            min_cells_2d = self._mesh_standards.get('min_cells_2d', 400)
            min_cells_3d = self._mesh_standards.get('min_cells_3d', 8000)
            max_aspect_ratio = self._mesh_standards.get('max_aspect_ratio', 100)
            
            for name, val, min_v, max_v in [("nx", nx, 10, 1000), ("ny", ny, 10, 1000), ("nz", nz, 1, 500)]:
                if val is None or val < min_v or val > max_v:
                    errors.append(f"{name}必须在{min_v}-{max_v}之间")
            
            if nx and ny and nz:
                total_cells = nx * ny * nz
                if nz == 1 and total_cells < min_cells_2d:
                    suggestions.append(f"2D网格总数{total_cells}低于宪法要求{min_cells_2d}")
                elif nz > 1 and total_cells < min_cells_3d:
                    suggestions.append(f"3D网格总数{total_cells}低于宪法要求{min_cells_3d}")
                
                geometry = self._collected_params.get("geometry", {})
                L, W, H = geometry.get("L", 1.0), geometry.get("W", 1.0), geometry.get("H", 0.1)
                dx, dy, dz = L / nx, W / ny, H / nz if nz > 0 else 1
                ratios = [dx/dy, dy/dz if dz > 0 else 1, dx/dz if dz > 0 else 1]
                max_ratio = max(max(ratios), 1/min(ratios) if min(ratios) > 0 else 1)
                if max_ratio > max_aspect_ratio:
                    suggestions.append(f"网格长宽比{max_ratio:.1f}较大，建议调整网格分布")
        
        elif step == WizardStep.BOUNDARY:
            if not params:
                errors.append("请至少设置一个边界条件")
            has_inlet = any("inlet" in k.lower() for k in params.keys())
            has_outlet = any("outlet" in k.lower() for k in params.keys())
            if not has_inlet:
                suggestions.append("未检测到入口边界，请确认设置是否正确")
            if not has_outlet:
                suggestions.append("未检测到出口边界，请确认设置是否正确")
        
        elif step == WizardStep.SOLVER:
            solver_name = params.get("solver_name")
            end_time, delta_t, nu = params.get("endTime"), params.get("deltaT"), params.get("nu")
            
            if not solver_name:
                errors.append("请选择求解器")
            if end_time is None or end_time <= 0:
                errors.append("结束时间必须大于0")
            if delta_t is None or delta_t <= 0:
                errors.append("时间步长必须大于0")
            if nu is None or nu <= 0:
                errors.append("运动粘度必须大于0")
            
            if end_time and delta_t:
                if delta_t > end_time * 0.1:
                    suggestions.append(f"时间步长{delta_t}较大，建议不超过结束时间的10%")
                
                mesh = self._collected_params.get("mesh", {})
                geometry = self._collected_params.get("geometry", {})
                nx, L = mesh.get("nx", 40), geometry.get("L", 1.0)
                dx = L / nx if nx > 0 else 0.025
                u_max = 1.0
                courant = u_max * delta_t / dx if dx > 0 else 0
                
                max_courant_explicit = self._solver_standards.get('max_courant_explicit', 0.5)
                max_courant_implicit = self._solver_standards.get('max_courant_implicit', 5.0)
                is_explicit = solver_name in ["icoFoam", "pisoFoam"] if solver_name else True
                max_allowed = max_courant_explicit if is_explicit else max_courant_implicit
                
                if courant > max_allowed:
                    recommended_dt = max_allowed * dx / u_max
                    errors.append(f"估计库朗数{courant:.2f}过大，建议减小时间步长至{recommended_dt:.6f}以下")
                elif courant > max_courant_explicit:
                    suggestions.append(f"估计库朗数{courant:.2f}超过显式格式安全限制{max_courant_explicit}")
            
            if nu:
                physical_constraints = self._constitution.get('Physical_Constraints', {})
                nu_min = physical_constraints.get('kinematic_viscosity', {}).get('min', 1e-7)
                nu_max = physical_constraints.get('kinematic_viscosity', {}).get('max', 1e-2)
                if nu < nu_min or nu > nu_max:
                    suggestions.append(f"运动粘度{nu}超出宪法建议范围[{nu_min}, {nu_max}]")
        
        return len(errors) == 0, errors, suggestions
    
    def advance(self, params: Dict[str, Any]) -> StepInfo:
        """保存当前步骤参数并前进到下一步"""
        self._save_step_params(self._current_step, params)
        self._step_history.append(self._current_step)
        current_value = self._current_step.value
        if current_value < WizardStep.REVIEW_RUN.value:
            self._current_step = WizardStep(current_value + 1)
        return self.get_step_info()
    
    def _save_step_params(self, step: WizardStep, params: Dict[str, Any]):
        """保存步骤参数"""
        if step == WizardStep.SCENARIO:
            self._selected_scenario = params.get("scenario_id")
            scenario_template = self._get_scenario_template(self._selected_scenario)
            if scenario_template:
                self._collected_params["physics_type"] = scenario_template.get("physics_type", "incompressible")
        elif step == WizardStep.GEOMETRY:
            self._collected_params["geometry"] = {k: params.get(k) for k in ["L", "W", "H"]}
        elif step == WizardStep.MESH:
            self._collected_params["mesh"] = {"nx": params.get("nx"), "ny": params.get("ny"), "nz": params.get("nz", 1)}
        elif step == WizardStep.BOUNDARY:
            self._collected_params["boundary"] = params
        elif step == WizardStep.SOLVER:
            self._collected_params["solver"] = {
                "name": params.get("solver_name"),
                "endTime": params.get("endTime"),
                "deltaT": params.get("deltaT"),
                "writeInterval": params.get("writeInterval", 100)
            }
            self._collected_params["nu"] = params.get("nu")
    
    def go_back(self) -> StepInfo:
        """返回上一步"""
        if self._step_history:
            self._current_step = self._step_history.pop()
        return self.get_step_info()
    
    def build_config(self) -> Dict[str, Any]:
        """将所有步骤收集的参数组装为完整的仿真配置字典"""
        geometry = self._collected_params.get("geometry", {})
        mesh = self._collected_params.get("mesh", {})
        boundary = self._collected_params.get("boundary", {})
        solver = self._collected_params.get("solver", {})
        
        # 构建与validators.py兼容的边界条件格式
        boundary_conditions = {}
        for name, bc in boundary.items():
            if isinstance(bc, dict):
                # 跳过描述字段，只保留必要的字段
                bc_data = {"name": name, "type": bc.get("type", "noSlip")}
                if "value" in bc and bc["value"] is not None:
                    bc_data["value"] = bc["value"]
                boundary_conditions[name] = bc_data
        
        # 构建与validators.py兼容的几何配置（展开格式）
        config_dict = {
            "task_id": self._wizard_id,
            "physics_type": self._collected_params.get("physics_type", "incompressible"),
            "geometry": {
                "L": geometry.get("L", 1.0),
                "W": geometry.get("W", 1.0),
                "H": geometry.get("H", 0.1),
                "nx": mesh.get("nx", 40),
                "ny": mesh.get("ny", 40),
                "nz": mesh.get("nz", 1)
            },
            "solver": {
                "name": solver.get("name", "icoFoam"),
                "endTime": solver.get("endTime", 0.5),
                "deltaT": solver.get("deltaT", 0.005),
                "writeInterval": solver.get("writeInterval", 100)
            },
            "boundary_conditions": boundary_conditions,
            "nu": self._collected_params.get("nu", 0.01)
        }
        
        if self._selected_scenario:
            config_dict["scenario"] = self._selected_scenario
            scenario_template = self._get_scenario_template(self._selected_scenario) or {}
            config_dict["scenario_name"] = scenario_template.get("name", "")
        
        return config_dict
    
    def reset(self):
        """重置向导到初始状态"""
        self._current_step = WizardStep.SCENARIO
        self._collected_params = {}
        self._step_history = []
        self._wizard_id = f"wizard_{uuid.uuid4().hex[:8]}"
        self._selected_scenario = None
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度信息"""
        total_steps = len(WizardStep)
        current_index = self._current_step.value
        
        step_status = {step.name: ("completed" if step.value < current_index else ("current" if step.value == current_index else "pending")) for step in WizardStep}
        
        return {
            "current_step": self._current_step.name,
            "current_step_index": current_index,
            "total_steps": total_steps,
            "progress_percentage": int((current_index / (total_steps - 1)) * 100) if total_steps > 1 else 0,
            "step_status": step_status,
            "can_go_back": len(self._step_history) > 0,
            "is_complete": self._current_step == WizardStep.REVIEW_RUN,
            "wizard_id": self._wizard_id,
            "selected_scenario": self._selected_scenario
        }
    
    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """获取所有可用场景列表"""
        templates = SCENARIO_TEMPLATES if SCENARIO_TEMPLATES else _load_scenario_templates()
        return [
            {"id": key, "name": template["name"], "name_en": template["name_en"],
             "description": template["description"], "icon": template["icon"],
             "difficulty": template["difficulty"], "physics_type": template["physics_type"]}
            for key, template in templates.items()
        ]


def create_wizard() -> WizardEngine:
    """创建新的向导引擎实例"""
    return WizardEngine()


def get_scenario_template(scenario_id: str) -> Optional[Dict[str, Any]]:
    """获取指定场景的模板"""
    if SCENARIO_TEMPLATES:
        return SCENARIO_TEMPLATES.get(scenario_id)
    return _load_scenario_templates().get(scenario_id)


if __name__ == "__main__":
    print("=" * 60)
    print("WizardEngine 模块测试")
    print("=" * 60)
    
    wizard = create_wizard()
    
    print("\n【可用场景】")
    for s in wizard.get_available_scenarios():
        print(f"  {s['icon']} {s['name']} ({s['difficulty']})")
    
    print("\n【步骤 1: 场景选择】")
    step_info = wizard.get_step_info()
    print(f"标题: {step_info.title}")
    
    is_valid, errors, suggestions = wizard.validate_step(WizardStep.SCENARIO, {"scenario_id": "cavity"})
    print(f"验证结果: {'通过' if is_valid else '失败'}")
    
    wizard.advance({"scenario_id": "cavity"})
    
    print("\n【步骤 2: 几何参数】")
    step_info = wizard.get_step_info()
    print(f"标题: {step_info.title}")
    print(f"默认值: {step_info.defaults}")
    
    wizard.advance({"L": 1.0, "W": 1.0, "H": 0.1})
    
    print("\n【步骤 3: 网格设置】")
    step_info = wizard.get_step_info()
    print(f"标题: {step_info.title}")
    
    is_valid, errors, suggestions = wizard.validate_step(WizardStep.MESH, {"nx": 10, "ny": 10, "nz": 1})
    print(f"验证结果(10x10): {'通过' if is_valid else '失败'}")
    if suggestions:
        print(f"建议: {suggestions}")
    
    wizard.advance({"nx": 40, "ny": 40, "nz": 1})
    wizard.advance({})  # 跳过边界
    wizard.advance({})  # 进入求解器
    
    print("\n【步骤 5: 求解器配置】")
    step_info = wizard.get_step_info()
    print(f"标题: {step_info.title}")
    print(f"默认值: {step_info.defaults}")
    
    print("\n【当前进度】")
    progress = wizard.get_progress()
    print(f"当前步骤: {progress['current_step']}")
    print(f"完成度: {progress['progress_percentage']}%")
    
    print("\n【生成的配置】")
    wizard._collected_params["solver"] = {"name": "icoFoam", "endTime": 0.5, "deltaT": 0.005, "writeInterval": 100}
    wizard._collected_params["nu"] = 0.01
    # 使用与validators.py兼容的边界类型（注意：empty类型在OpenFOAM 2D中是必需的，但验证器需要扩展支持）
    wizard._collected_params["boundary"] = {
        "movingWall": {"type": "fixedValue", "value": [1, 0, 0], "description": "顶部运动壁面"},
        "fixedWalls": {"type": "noSlip", "description": "固定壁面"},
        "frontAndBack": {"type": "slip", "description": "前后边界（2D近似）"}
    }
    
    config_dict = wizard.build_config()
    import json
    print(json.dumps(config_dict, indent=2, ensure_ascii=False))
    
    print("\n【配置验证】")
    passed, errors = validate_simulation_config(config_dict)
    print(f"验证结果: {'通过' if passed else '失败'}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
