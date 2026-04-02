"""
OpenFOAM字典文件生成器
负责将结构化配置转换为OpenFOAM字典文件
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from jinja2 import Template
import logging
import math
import yaml

# 导入 SchemeAdvisor 用于智能格式推荐
from .scheme_advisor import SchemeAdvisor

logger = logging.getLogger(__name__)


# ============================================================================
# 湍流参数估算辅助函数
# ============================================================================

def estimate_turbulence_initial_values(
    U_mag: float,
    turbulence_intensity: float = 0.05,
    length_scale: float = 0.1,
    C_mu: float = 0.09
) -> Dict[str, float]:
    """
    估算湍流初始值
    
    根据入口速度、湍流强度和特征长度估算湍流参数的初始值。
    使用标准湍流模型公式：
        k = 1.5 * (U * I)^2
        epsilon = C_mu^0.75 * k^1.5 / l
        omega = k^0.5 / (C_mu^0.25 * l)
        nut = C_mu * k^2 / epsilon
    
    Args:
        U_mag: 入口速度大小 (m/s)
        turbulence_intensity: 湍流强度 I = u'/U，默认0.05 (5%)
        length_scale: 湍流特征长度 (m)，默认0.1
        C_mu: k-ε模型常数，默认0.09
    
    Returns:
        包含 k, epsilon, omega, nut 估算值的字典
    """
    # 湍动能 k = 1.5 * (U * I)^2
    k = 1.5 * (U_mag * turbulence_intensity) ** 2
    
    # 耗散率 epsilon = C_mu^0.75 * k^1.5 / l
    epsilon = (C_mu ** 0.75) * (k ** 1.5) / length_scale
    
    # 比耗散率 omega = k^0.5 / (C_mu^0.25 * l)
    omega = (k ** 0.5) / ((C_mu ** 0.25) * length_scale)
    
    # 湍流粘度 nut = C_mu * k^2 / epsilon
    nut = C_mu * (k ** 2) / epsilon if epsilon > 0 else 0.0
    
    # 湍流热扩散率 alphat (Pr_t ≈ 0.85)
    Pr_t = 0.85
    alphat = nut / Pr_t if nut > 0 else 0.0
    
    return {
        "k": round(k, 6),
        "epsilon": round(epsilon, 6),
        "omega": round(omega, 6),
        "nut": round(nut, 8),
        "alphat": round(alphat, 8),
        "turbulence_intensity": turbulence_intensity,
        "length_scale": length_scale
    }


def load_solver_requirements() -> Dict[str, Any]:
    """
    加载求解器需求配置
    
    Returns:
        求解器需求配置字典
    """
    config_path = Path(__file__).parent.parent / "config" / "knowledge" / "solver_requirements.yaml"
    
    if not config_path.exists():
        logger.warning(f"求解器需求配置文件不存在: {config_path}")
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class FoamFileGenerator:
    """OpenFOAM文件生成器基类"""
    
    @staticmethod
    def get_foam_header(object_name: str, foam_class: str = "dictionary") -> str:
        """获取OpenFOAM文件头"""
        return f'''/*--------------------------------*- C++ -*----------------------------------*\\\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       {foam_class};
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

'''


class BlockMeshDictGenerator(FoamFileGenerator):
    """blockMeshDict生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.geometry = config.get("geometry", {})
    
    def generate(self) -> str:
        """生成blockMeshDict内容"""
        
        dims = self.geometry.get("dimensions", {})
        res = self.geometry.get("mesh_resolution", {})
        
        L = dims.get("L", 1.0)
        W = dims.get("W", 1.0)
        H = dims.get("H", 0.1)
        nx = res.get("nx", 20)
        ny = res.get("ny", 20)
        nz = res.get("nz", 1)
        
        # 生成简单的blockMeshDict
        content = self.get_foam_header("blockMeshDict")
        content += f'''scale   1;

vertices
(
    (0 0 0)
    ({L} 0 0)
    ({L} {W} 0)
    (0 {W} 0)
    (0 0 {H})
    ({L} 0 {H})
    ({L} {W} {H})
    (0 {W} {H})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);
'''
        
        # 添加边界
        bcs = self.config.get("boundary_conditions", {})
        content += self._generate_boundary_section(bcs)
        
        content += "\n// ************************************************************************* //\n"
        
        return content
    
    def _generate_boundary_section(self, bcs: Dict[str, Any]) -> str:
        """生成边界部分"""
        
        # 默认边界定义
        default_boundaries = {
            "movingWall": {
                "type": "wall",
                "faces": "(3 7 6 2)"
            },
            "fixedWalls": {
                "type": "wall", 
                "faces": "(0 4 7 3)(2 6 5 1)(1 5 4 0)"
            },
            "frontAndBack": {
                "type": "empty",
                "faces": "(0 3 2 1)(4 5 6 7)"
            }
        }
        
        # 使用用户定义的边界或默认边界
        boundaries_to_use = default_boundaries
        if bcs:
            # 这里可以添加自定义边界逻辑
            pass
        
        content = "boundary\n(\n"
        
        for name, bc in boundaries_to_use.items():
            content += f'''    {name}
    {{
        type {bc["type"]};
        faces
        (
            {bc["faces"]}
        );
    }}
'''
        
        content += ");\n"
        
        return content
    
    def write(self, case_path: Path) -> None:
        """写入system/blockMeshDict"""
        system_dir = case_path / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        
        (system_dir / "blockMeshDict").write_text(self.generate())


class ControlDictGenerator(FoamFileGenerator):
    """controlDict生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.solver_config = config.get("solver", {})
    
    def generate(self) -> str:
        """生成controlDict内容"""
        
        solver_name = self.solver_config.get("name", "icoFoam")
        start_time = self.solver_config.get("startTime", 0)
        end_time = self.solver_config.get("endTime", 0.5)
        delta_t = self.solver_config.get("deltaT", 0.005)
        write_interval = self.solver_config.get("writeInterval", 20)
        
        content = self.get_foam_header("controlDict")
        content += f'''application     {solver_name};

startFrom       startTime;

startTime       {start_time};

stopAt          endTime;

endTime         {end_time};

deltaT          {delta_t};

writeControl    timeStep;

writeInterval   {write_interval};

purgeWrite      0;

writeFormat     ascii;

writePrecision  6;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

// ************************************************************************* //
'''
        return content
    
    def write(self, case_path: Path) -> None:
        """写入system/controlDict"""
        system_dir = case_path / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        
        (system_dir / "controlDict").write_text(self.generate())


class FvSchemesGenerator(FoamFileGenerator):
    """fvSchemes生成器
    
    使用 SchemeAdvisor 进行智能格式推荐
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.physics_type = config.get("physics_type", "incompressible")
        self.solver_name = config.get("solver", {}).get("name", "icoFoam")
        self.turbulence_model = config.get("turbulence_model", "laminar")
        self.mesh_quality = config.get("mesh_quality", {})
        
        # 初始化 SchemeAdvisor
        self.scheme_advisor = SchemeAdvisor()
    
    def generate(self) -> str:
        """生成fvSchemes内容
        
        使用 SchemeAdvisor 智能推荐格式配置
        """
        
        content = self.get_foam_header("fvSchemes")
        
        # 使用 SchemeAdvisor 获取智能推荐
        try:
            recommendation = self.scheme_advisor.recommend_schemes(
                solver=self.solver_name,
                turbulence_model=self.turbulence_model,
                mesh_quality=self.mesh_quality,
                is_initial=False,
                physics_type=self.physics_type
            )
            
            # 使用推荐结果生成内容
            content += self._generate_schemes_from_recommendation(recommendation)
            logger.info(f"使用智能推荐格式: {recommendation.reasoning}")
            
        except Exception as e:
            logger.warning(f"智能格式推荐失败，回退到默认配置: {e}")
            # 回退到传统方式
            if self.physics_type == "incompressible":
                content += self._incompressible_schemes()
            elif self.physics_type == "heatTransfer":
                content += self._heat_transfer_schemes()
            else:
                content += self._default_schemes()
        
        content += "\n// ************************************************************************* //\n"
        return content
    
    def _generate_schemes_from_recommendation(self, recommendation) -> str:
        """根据 SchemeRecommendation 生成格式内容
        
        Args:
            recommendation: SchemeRecommendation 对象
        
        Returns:
            fvSchemes 文件内容字符串
        """
        content = ""
        
        # ddtSchemes
        content += "ddtSchemes\n{\n"
        for key, value in recommendation.ddtSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # gradSchemes
        content += "gradSchemes\n{\n"
        for key, value in recommendation.gradSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # divSchemes
        content += "divSchemes\n{\n"
        content += "    default             none;\n"
        for key, value in recommendation.divSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # laplacianSchemes
        content += "laplacianSchemes\n{\n"
        for key, value in recommendation.laplacianSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # interpolationSchemes
        content += "interpolationSchemes\n{\n"
        for key, value in recommendation.interpolationSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n\n"
        
        # snGradSchemes
        content += "snGradSchemes\n{\n"
        for key, value in recommendation.snGradSchemes.items():
            content += f"    {key:<20} {value};\n"
        content += "}\n"
        
        return content
    
    def _incompressible_schemes(self) -> str:
        """不可压流格式"""
        return '''ddtSchemes
{
    default         Euler;
}

gradSchemes
{
    default         Gauss linear;
    grad(p)         Gauss linear;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear orthogonal;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         orthogonal;
}
'''
    
    def _heat_transfer_schemes(self) -> str:
        """传热问题格式"""
        return '''ddtSchemes
{
    default         Euler;
}

gradSchemes
{
    default         Gauss linear;
    grad(p)         Gauss linear;
    grad(T)         Gauss linear;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linear;
    div(phi,T)      Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear orthogonal;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         orthogonal;
}
'''
    
    def _default_schemes(self) -> str:
        """默认格式"""
        return self._incompressible_schemes()
    
    def write(self, case_path: Path) -> None:
        """写入system/fvSchemes"""
        system_dir = case_path / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        
        (system_dir / "fvSchemes").write_text(self.generate())


class FvSolutionGenerator(FoamFileGenerator):
    """fvSolution生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.physics_type = config.get("physics_type", "incompressible")
        self.solver_name = config.get("solver", {}).get("name", "icoFoam")
    
    def generate(self) -> str:
        """生成fvSolution内容"""
        
        content = self.get_foam_header("fvSolution")
        
        # 求解器设置
        content += "solvers\n{\n"
        content += self._pressure_solver()
        content += self._velocity_solver()
        
        if self.physics_type == "heatTransfer":
            content += self._temperature_solver()
        
        content += "}\n\n"
        
        # 算法设置
        content += self._algorithm_settings()
        
        content += "\n// ************************************************************************* //\n"
        return content
    
    def _pressure_solver(self) -> str:
        """压力求解器设置"""
        return '''    p
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-06;
        relTol          0.05;
    }

    pFinal
    {
        $p;
        relTol          0;
    }
'''
    
    def _velocity_solver(self) -> str:
        """速度求解器设置"""
        return '''
    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0;
    }
'''
    
    def _temperature_solver(self) -> str:
        """温度求解器设置"""
        return '''
    T
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-07;
        relTol          0;
    }
'''
    
    def _algorithm_settings(self) -> str:
        """算法设置"""
        if "icoFoam" in self.solver_name:
            return '''PISO
{
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;
}'''
        elif "simpleFoam" in self.solver_name:
            return '''SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      yes;

    residualControl
    {
        p               1e-2;
        U               1e-3;
        \"(k|epsilon|omega)\" 1e-3;
    }
}'''
        else:
            return '''PIMPLE
{
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
}'''
    
    def write(self, case_path: Path) -> None:
        """写入system/fvSolution"""
        system_dir = case_path / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        
        (system_dir / "fvSolution").write_text(self.generate())


class FieldGenerator(FoamFileGenerator):
    """
    场文件生成器（U, p, T, k, epsilon, omega, nut等）
    
    支持生成各种初始场文件，包括：
    - 标量场：p, p_rgh, T, k, epsilon, omega, nut, alphat
    - 矢量场：U
    - 相分数场：alpha.water
    """
    
    def __init__(self, field_name: str, field_type: str, dimensions: List[int],
                 internal_value: Any, boundary_conditions: Dict[str, Any]):
        self.field_name = field_name
        self.field_type = field_type  # volScalarField, volVectorField
        self.dimensions = dimensions
        self.internal_value = internal_value
        self.boundary_conditions = boundary_conditions
    
    def generate(self) -> str:
        """生成场文件内容"""
        
        content = self.get_foam_header(self.field_name, self.field_type)
        
        # 维度
        dims_str = " ".join(str(d) for d in self.dimensions)
        content += f"dimensions      [{dims_str}];\n\n"
        
        # 内部场
        if isinstance(self.internal_value, list):
            val_str = " ".join(str(v) for v in self.internal_value)
            content += f"internalField   uniform ({val_str});\n\n"
        else:
            content += f"internalField   uniform {self.internal_value};\n\n"
        
        # 边界条件
        content += "boundaryField\n{\n"
        
        for bc_name, bc_def in self.boundary_conditions.items():
            content += self._format_boundary_condition(bc_name, bc_def)
        
        content += "}\n\n"
        content += "// ************************************************************************* //\n"
        
        return content
    
    def _format_boundary_condition(self, name: str, bc_def: Dict[str, Any]) -> str:
        """格式化边界条件"""
        bc_type = bc_def.get("type", "zeroGradient")
        
        content = f'''    {name}
    {{
        type            {bc_type};'''
        
        # 添加value（如果有）
        if "value" in bc_def:
            value = bc_def["value"]
            if isinstance(value, list):
                val_str = " ".join(str(v) for v in value)
                content += f'''\n        value           uniform ({val_str});'''
            else:
                content += f'''\n        value           uniform {value};'''
        
        # 添加其他参数（如inletValue等）
        for key, value in bc_def.items():
            if key in ["type", "value"]:
                continue
            if isinstance(value, list):
                val_str = " ".join(str(v) for v in value)
                content += f'''\n        {key:<15} uniform ({val_str});'''
            else:
                content += f'''\n        {key:<15} {value};'''
        
        content += "\n    }\n"
        
        return content
    
    def write(self, case_path: Path) -> None:
        """写入0/field_name"""
        zero_dir = case_path / "0"
        zero_dir.mkdir(parents=True, exist_ok=True)
        
        (zero_dir / self.field_name).write_text(self.generate())


class InitialFieldFactory:
    """
    初始场工厂类
    
    用于根据场名称自动生成对应的初始场文件
    """
    
    # 场维度定义
    FIELD_DIMENSIONS = {
        "p": [0, 2, -2, 0, 0, 0, 0],
        "p_rgh": [1, -1, -2, 0, 0, 0, 0],
        "U": [0, 1, -1, 0, 0, 0, 0],
        "T": [0, 0, 0, 1, 0, 0, 0],
        "k": [0, 2, -2, 0, 0, 0, 0],
        "epsilon": [0, 2, -3, 0, 0, 0, 0],
        "omega": [0, 0, -1, 0, 0, 0, 0],
        "nut": [0, 2, -1, 0, 0, 0, 0],
        "alphat": [0, 2, -1, 0, 0, 0, 0],
        "nuTilda": [0, 2, -1, 0, 0, 0, 0],
        "alpha.water": [0, 0, 0, 0, 0, 0, 0],
    }
    
    # 场类型定义
    FIELD_TYPES = {
        "p": "volScalarField",
        "p_rgh": "volScalarField",
        "U": "volVectorField",
        "T": "volScalarField",
        "k": "volScalarField",
        "epsilon": "volScalarField",
        "omega": "volScalarField",
        "nut": "volScalarField",
        "alphat": "volScalarField",
        "nuTilda": "volScalarField",
        "alpha.water": "volScalarField",
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化初始场工厂
        
        Args:
            config: 配置字典，包含边界条件、湍流参数等
        """
        self.config = config
        self.bcs = config.get("boundary_conditions", {})
        self.turbulence_model = config.get("turbulence_model", "laminar")
        self.solver_name = config.get("solver", {}).get("name", "icoFoam")
        
        # 估算湍流参数
        inlet_velocity = self._get_inlet_velocity()
        self.turb_values = estimate_turbulence_initial_values(inlet_velocity)
    
    def _get_inlet_velocity(self) -> float:
        """获取入口速度大小"""
        bcs = self.config.get("boundary_conditions", {})
        for name, bc in bcs.items():
            if "U" in bc and "inlet" in name.lower():
                value = bc["U"].get("value", [1, 0, 0])
                if isinstance(value, list) and len(value) >= 3:
                    return math.sqrt(sum(v**2 for v in value))
        return 1.0
    
    def create_field(self, field_name: str) -> Optional[FieldGenerator]:
        """
        创建场文件生成器
        
        Args:
            field_name: 场名称
        
        Returns:
            FieldGenerator实例，如果场名不支持则返回None
        """
        dimensions = self.FIELD_DIMENSIONS.get(field_name)
        field_type = self.FIELD_TYPES.get(field_name)
        
        if dimensions is None or field_type is None:
            logger.warning(f"未知场类型: {field_name}")
            return None
        
        # 获取边界条件
        bc = self._get_boundary_conditions_for_field(field_name)
        
        # 获取内部场值
        internal_value = self._get_internal_value(field_name)
        
        return FieldGenerator(field_name, field_type, dimensions, internal_value, bc)
    
    def _get_internal_value(self, field_name: str) -> Any:
        """获取场内部值"""
        # 检查配置中是否有自定义值
        custom_values = self.config.get("initial_values", {})
        if field_name in custom_values:
            return custom_values[field_name]
        
        # 默认值
        defaults = {
            "p": 0,
            "p_rgh": 0,
            "U": [0, 0, 0],
            "T": 300,
            "k": self.turb_values["k"],
            "epsilon": self.turb_values["epsilon"],
            "omega": self.turb_values["omega"],
            "nut": 0,
            "alphat": 0,
            "nuTilda": self.turb_values["nut"],
            "alpha.water": 0,
        }
        return defaults.get(field_name, 0)
    
    def _get_boundary_conditions_for_field(self, field_name: str) -> Dict[str, Any]:
        """获取场的边界条件"""
        bc_templates = self._get_bc_templates(field_name)
        result = {}
        
        # 从配置中获取边界名称
        boundary_names = self._get_boundary_names()
        
        for name in boundary_names:
            bc_type = self._classify_boundary(name)
            
            # 检查配置中是否有自定义边界条件
            if name in self.bcs and field_name in self.bcs[name]:
                result[name] = self.bcs[name][field_name]
            else:
                # 使用模板
                template_key = f"{field_name}_{bc_type}"
                if template_key in bc_templates:
                    result[name] = bc_templates[template_key]
                else:
                    result[name] = {"type": "zeroGradient"}
        
        return result
    
    def _get_boundary_names(self) -> List[str]:
        """获取边界名称列表"""
        if self.bcs:
            return list(self.bcs.keys())
        
        # 默认边界
        solver = self.solver_name
        if solver in ["interFoam", "multiphaseInterFoam"]:
            return ["inlet", "outlet", "walls", "atmosphere"]
        else:
            return ["movingWall", "fixedWalls", "frontAndBack"]
    
    def _classify_boundary(self, name: str) -> str:
        """分类边界类型"""
        name_lower = name.lower()
        
        if "inlet" in name_lower:
            return "inlet"
        elif "outlet" in name_lower:
            return "outlet"
        elif "wall" in name_lower:
            return "wall"
        elif "symmetry" in name_lower:
            return "symmetry"
        elif "front" in name_lower or "back" in name_lower:
            return "empty"
        elif "atmosphere" in name_lower:
            return "atmosphere"
        else:
            return "wall"
    
    def _get_bc_templates(self, field_name: str) -> Dict[str, Dict[str, Any]]:
        """获取边界条件模板"""
        # 基础模板
        templates = {
            # 速度场
            "U_inlet": {"type": "fixedValue", "value": [1, 0, 0]},
            "U_outlet": {"type": "zeroGradient"},
            "U_wall": {"type": "noSlip"},
            "U_symmetry": {"type": "symmetry"},
            "U_empty": {"type": "empty"},
            
            # 压力场
            "p_inlet": {"type": "zeroGradient"},
            "p_outlet": {"type": "fixedValue", "value": 0},
            "p_wall": {"type": "zeroGradient"},
            "p_symmetry": {"type": "symmetry"},
            "p_empty": {"type": "empty"},
            
            # 相对压力场
            "p_rgh_inlet": {"type": "zeroGradient"},
            "p_rgh_outlet": {"type": "fixedValue", "value": 0},
            "p_rgh_wall": {"type": "fixedFluxPressure"},
            "p_rgh_atmosphere": {"type": "totalPressure", "p0": "uniform 0"},
            
            # 温度场
            "T_inlet": {"type": "fixedValue", "value": 300},
            "T_outlet": {"type": "zeroGradient"},
            "T_wall": {"type": "fixedValue", "value": 350},
            
            # 湍动能
            "k_inlet": {"type": "fixedValue", "value": self.turb_values["k"]},
            "k_wall": {"type": "kqRWallFunction", "value": self.turb_values["k"]},
            
            # 耗散率
            "epsilon_inlet": {"type": "fixedValue", "value": self.turb_values["epsilon"]},
            "epsilon_wall": {"type": "epsilonWallFunction", "value": self.turb_values["epsilon"]},
            
            # 比耗散率
            "omega_inlet": {"type": "fixedValue", "value": self.turb_values["omega"]},
            "omega_wall": {"type": "omegaWallFunction", "value": self.turb_values["omega"]},
            
            # 湍流粘度
            "nut_inlet": {"type": "calculated", "value": 0},
            "nut_wall": {"type": "nutkWallFunction", "value": 0},
            
            # 湍流热扩散率
            "alphat_inlet": {"type": "calculated", "value": 0},
            "alphat_wall": {"type": "alphatWallFunction", "value": 0},
            
            # 相分数
            "alpha.water_inlet": {"type": "fixedValue", "value": 0},
            "alpha.water_outlet": {"type": "inletOutlet", "inletValue": 0, "value": 0},
            "alpha.water_wall": {"type": "zeroGradient"},
            "alpha.water_atmosphere": {"type": "inletOutlet", "inletValue": 0, "value": 0},
        }
        
        return templates


class TransportPropertiesGenerator(FoamFileGenerator):
    """transportProperties生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.nu = config.get("nu", 0.01)
        self.solver_name = config.get("solver", {}).get("name", "icoFoam")
        self.physics_type = config.get("physics_type", "incompressible")
    
    def generate(self) -> str:
        """生成transportProperties内容"""
        
        content = self.get_foam_header("transportProperties")
        
        # 多相流求解器需要更复杂的transportProperties
        if self.solver_name in ["interFoam", "interIsoFoam", "multiphaseInterFoam"]:
            content += self._generate_multiphase_properties()
        else:
            content += f'''nu              {self.nu};

// ************************************************************************* //
'''
        return content
    
    def _generate_multiphase_properties(self) -> str:
        """生成多相流transportProperties"""
        phases = self.config.get("phases", ["water", "air"])
        
        content = f'''phases          ({" ".join(phases)});

water
{{
    transportModel  Newtonian;
    nu              1e-06;
    rho             1000;
}}

air
{{
    transportModel  Newtonian;
    nu              1.48e-05;
    rho             1;
}}

sigma           0.07;

// ************************************************************************* //
'''
        return content
    
    def write(self, case_path: Path) -> None:
        """写入constant/transportProperties"""
        constant_dir = case_path / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)
        
        (constant_dir / "transportProperties").write_text(self.generate())


class TurbulencePropertiesGenerator(FoamFileGenerator):
    """
    turbulenceProperties生成器
    
    生成湍流属性文件，支持：
    - laminar: 层流
    - RAS: 雷诺平均（kEpsilon, kOmegaSST, realizableKE等）
    - LES: 大涡模拟（Smagorinsky, WALE, kEqn）
    """
    
    # 支持的湍流模型
    RAS_MODELS = ["kEpsilon", "kOmegaSST", "realizableKE", "kOmega", "SpalartAllmaras"]
    LES_MODELS = ["Smagorinsky", "WALE", "kEqn", "dynamicKEqn"]
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.turbulence_model = config.get("turbulence_model", "laminar")
        self.simulation_type = self._determine_simulation_type()
    
    def _determine_simulation_type(self) -> str:
        """确定模拟类型"""
        if self.turbulence_model == "laminar":
            return "laminar"
        elif self.turbulence_model in self.LES_MODELS:
            return "LES"
        else:
            return "RAS"
    
    def generate(self) -> str:
        """生成turbulenceProperties内容"""
        
        content = self.get_foam_header("turbulenceProperties")
        
        if self.simulation_type == "laminar":
            content += '''simulationType  laminar;

// ************************************************************************* //
'''
        elif self.simulation_type == "RAS":
            content += self._generate_ras_config()
        elif self.simulation_type == "LES":
            content += self._generate_les_config()
        
        return content
    
    def _generate_ras_config(self) -> str:
        """生成RAS湍流配置"""
        model = self.turbulence_model
        
        # 特殊处理 SpalartAllmaras
        if model == "SpalartAllmaras":
            return f'''simulationType  RAS;

RAS
{{
    model           {model};
    turbulence      on;
    printCoeffs     on;
}}

// ************************************************************************* //
'''
        
        # 标准 RAS 模型
        return f'''simulationType  RAS;

RAS
{{
    model           {model};
    turbulence      on;
    printCoeffs     on;
}}

// ************************************************************************* //
'''
    
    def _generate_les_config(self) -> str:
        """生成LES湍流配置"""
        model = self.turbulence_model
        
        return f'''simulationType  LES;

LES
{{
    LESModel        {model};
    delta           cubeRootVol;
    printCoeffs     on;
}}

// ************************************************************************* //
'''
    
    def write(self, case_path: Path) -> None:
        """写入constant/turbulenceProperties"""
        constant_dir = case_path / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)
        
        (constant_dir / "turbulenceProperties").write_text(self.generate())


class ThermophysicalPropertiesGenerator(FoamFileGenerator):
    """
    thermophysicalProperties生成器
    
    生成热物性属性文件，支持：
    - heRhoThermo: 不可压缩传热（浮力驱动流）
    - hePsiThermo: 可压缩流动
    """
    
    # 默认物性参数
    AIR_20C = {
        "rho": 1.204,
        "mu": 1.825e-5,
        "Cp": 1005,
        "Pr": 0.729,
        "k": 0.0257
    }
    
    WATER_20C = {
        "rho": 998.2,
        "mu": 1.002e-3,
        "Cp": 4182,
        "Pr": 7.01,
        "k": 0.598
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.solver_name = config.get("solver", {}).get("name", "buoyantSimpleFoam")
        self.fluid = config.get("fluid", "air")
        self.thermo_type = self._determine_thermo_type()
        
        # 获取物性参数
        props = config.get("thermophysical", {})
        self.T_ref = props.get("T_ref", 293.15)
        self.p_ref = props.get("p_ref", 101325)
    
    def _determine_thermo_type(self) -> str:
        """确定热物性类型"""
        if self.solver_name in ["rhoSimpleFoam", "rhoPimpleFoam", "rhoCentralFoam", "sonicFoam"]:
            return "hePsiThermo"
        else:
            return "heRhoThermo"
    
    def generate(self) -> str:
        """生成thermophysicalProperties内容"""
        
        content = self.get_foam_header("thermophysicalProperties")
        
        if self.thermo_type == "hePsiThermo":
            content += self._generate_compressible_config()
        else:
            content += self._generate_incompressible_heat_config()
        
        return content
    
    def _generate_incompressible_heat_config(self) -> str:
        """生成不可压缩传热配置（浮力驱动流）"""
        fluid = self.fluid
        
        if fluid.lower() == "air":
            return f'''thermoType
{{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState rhoConst;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie
    {{
        molWeight   28.96;
    }}
    equationOfState
    {{
        rho         1.204;
    }}
    thermodynamics
    {{
        Cp          1005;
        Hf          0;
    }}
    transport
    {{
        mu          1.825e-05;
        Pr          0.729;
    }}
}}

// ************************************************************************* //
'''
        elif fluid.lower() == "water":
            return f'''thermoType
{{
    type            heRhoThermo;
    mixture         pureMixture;
    transport       const;
    thermo          hConst;
    equationOfState rhoConst;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie
    {{
        molWeight   18.0153;
    }}
    equationOfState
    {{
        rho         998.2;
    }}
    thermodynamics
    {{
        Cp          4182;
        Hf          0;
    }}
    transport
    {{
        mu          1.002e-03;
        Pr          7.01;
    }}
}}

// ************************************************************************* //
'''
        else:
            # 默认空气
            return self._generate_incompressible_heat_config()
    
    def _generate_compressible_config(self) -> str:
        """生成可压缩流动配置"""
        return f'''thermoType
{{
    type            hePsiThermo;
    mixture         pureMixture;
    transport       sutherland;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleEnthalpy;
}}

mixture
{{
    specie
    {{
        molWeight       28.96;
    }}
    thermodynamics
    {{
        Cp              1005;
        Hf              0;
    }}
    transport
    {{
        As              1.4792e-06;
        Ts              116;
    }}
}}

// ************************************************************************* //
'''
    
    def write(self, case_path: Path) -> None:
        """写入constant/thermophysicalProperties"""
        constant_dir = case_path / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)
        
        (constant_dir / "thermophysicalProperties").write_text(self.generate())


class GFieldGenerator(FoamFileGenerator):
    """
    重力场文件生成器
    
    生成constant/g文件
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        gravity = config.get("gravity", {})
        self.gx = gravity.get("gx", 0)
        self.gy = gravity.get("gy", -9.81)
        self.gz = gravity.get("gz", 0)
    
    def generate(self) -> str:
        """生成g文件内容"""
        
        content = self.get_foam_header("g")
        content += f'''dimensions      [0 1 -2 0 0 0 0];
value           uniform ({self.gx} {self.gy} {self.gz});

// ************************************************************************* //
'''
        return content
    
    def write(self, case_path: Path) -> None:
        """写入constant/g"""
        constant_dir = case_path / "constant"
        constant_dir.mkdir(parents=True, exist_ok=True)
        
        (constant_dir / "g").write_text(self.generate())


class CaseGenerator:
    """
    完整算例生成器
    整合所有生成器，一键生成完整算例
    
    支持多种物理场：
    - 不可压缩流（icoFoam, simpleFoam, pimpleFoam）
    - 传热问题（buoyantSimpleFoam, buoyantPimpleFoam）
    - 多相流（interFoam）
    - 可压缩流（rhoSimpleFoam, rhoPimpleFoam）
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.solver_name = config.get("solver", {}).get("name", "icoFoam")
        self.turbulence_model = config.get("turbulence_model", "laminar")
        self.physics_type = config.get("physics_type", "incompressible")
        
        # 加载求解器需求配置
        self.solver_requirements = load_solver_requirements()
    
    def generate_all(self, case_path: Path) -> None:
        """
        生成完整算例的所有文件
        
        Args:
            case_path: 算例目录路径
        """
        
        print(f"[CaseGenerator] 生成算例文件到: {case_path}")
        print(f"[CaseGenerator] 求解器: {self.solver_name}, 湍流模型: {self.turbulence_model}")
        
        # 生成system目录文件
        BlockMeshDictGenerator(self.config).write(case_path)
        ControlDictGenerator(self.config).write(case_path)
        FvSchemesGenerator(self.config).write(case_path)
        FvSolutionGenerator(self.config).write(case_path)
        
        # 根据求解器类型生成constant目录文件
        self._generate_constant_files(case_path)
        
        # 生成初始条件
        self._generate_initial_fields(case_path)
        
        print(f"[CaseGenerator] 算例文件生成完成")
    
    def _generate_constant_files(self, case_path: Path) -> None:
        """生成constant目录下的字典文件"""
        
        solver_info = self.solver_requirements.get(self.solver_name, {})
        required_dicts = solver_info.get("required_dicts", [])
        
        # 如果没有配置，使用默认
        if not required_dicts:
            required_dicts = self._get_default_required_dicts()
        
        for dict_name in required_dicts:
            self._generate_dict(dict_name, case_path)
    
    def _get_default_required_dicts(self) -> List[str]:
        """获取默认的必需字典列表"""
        defaults = {
            "icoFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "transportProperties"],
            "simpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "transportProperties", "turbulenceProperties"],
            "pimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "transportProperties", "turbulenceProperties"],
            "buoyantSimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "thermophysicalProperties", "turbulenceProperties", "g"],
            "buoyantPimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "thermophysicalProperties", "turbulenceProperties", "g"],
            "interFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "transportProperties", "turbulenceProperties", "g"],
            "rhoSimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "thermophysicalProperties", "turbulenceProperties"],
            "rhoPimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "thermophysicalProperties", "turbulenceProperties"],
        }
        return defaults.get(self.solver_name, ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", "transportProperties"])
    
    def _generate_dict(self, dict_name: str, case_path: Path) -> None:
        """生成指定的字典文件"""
        
        if dict_name == "blockMeshDict":
            pass  # 已在generate_all中生成
        elif dict_name == "controlDict":
            pass  # 已在generate_all中生成
        elif dict_name == "fvSchemes":
            pass  # 已在generate_all中生成
        elif dict_name == "fvSolution":
            pass  # 已在generate_all中生成
        elif dict_name == "transportProperties":
            TransportPropertiesGenerator(self.config).write(case_path)
        elif dict_name == "turbulenceProperties":
            TurbulencePropertiesGenerator(self.config).write(case_path)
        elif dict_name == "thermophysicalProperties":
            ThermophysicalPropertiesGenerator(self.config).write(case_path)
        elif dict_name == "g":
            GFieldGenerator(self.config).write(case_path)
        else:
            logger.warning(f"未知的字典类型: {dict_name}")
    
    def _generate_initial_fields(self, case_path: Path) -> None:
        """生成初始场文件"""
        
        # 获取求解器所需的初始场
        solver_info = self.solver_requirements.get(self.solver_name, {})
        initial_fields = solver_info.get("initial_fields", [])
        
        # 如果没有配置，使用默认场
        if not initial_fields:
            initial_fields = self._get_default_initial_fields()
        
        # 创建初始场工厂
        field_factory = InitialFieldFactory(self.config)
        
        # 生成每个场
        for field_info in initial_fields:
            if isinstance(field_info, dict):
                field_name = field_info.get("name")
            else:
                field_name = field_info
            
            # 特殊处理：根据湍流模型选择epsilon或omega
            if field_name == "epsilon" and self.turbulence_model in ["kOmegaSST", "kOmega"]:
                continue
            if field_name == "omega" and self.turbulence_model not in ["kOmegaSST", "kOmega"]:
                continue
            
            field_gen = field_factory.create_field(field_name)
            if field_gen:
                field_gen.write(case_path)
                print(f"[CaseGenerator] 生成场文件: {field_name}")
    
    def _get_default_initial_fields(self) -> List[Dict[str, Any]]:
        """获取默认的初始场列表"""
        defaults = {
            "icoFoam": [{"name": "p"}, {"name": "U"}],
            "simpleFoam": [{"name": "p"}, {"name": "U"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}],
            "pimpleFoam": [{"name": "p"}, {"name": "U"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}],
            "buoyantSimpleFoam": [{"name": "p_rgh"}, {"name": "p"}, {"name": "U"}, {"name": "T"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}, {"name": "alphat"}],
            "buoyantPimpleFoam": [{"name": "p_rgh"}, {"name": "p"}, {"name": "U"}, {"name": "T"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}, {"name": "alphat"}],
            "interFoam": [{"name": "alpha.water"}, {"name": "p_rgh"}, {"name": "U"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}],
            "rhoSimpleFoam": [{"name": "p"}, {"name": "U"}, {"name": "T"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}, {"name": "alphat"}],
            "rhoPimpleFoam": [{"name": "p"}, {"name": "U"}, {"name": "T"}, {"name": "k"}, {"name": "epsilon"}, {"name": "omega"}, {"name": "nut"}, {"name": "alphat"}],
        }
        return defaults.get(self.solver_name, [{"name": "p"}, {"name": "U"}])
    
    def generate_all_to_dict(self) -> Dict[str, str]:
        """
        生成所有文件内容到字典（不写入磁盘）
        
        Returns:
            字典，键为文件路径，值为文件内容
        """
        result = {}
        
        # 获取求解器需求
        solver_info = self.solver_requirements.get(self.solver_name, {})
        required_dicts = solver_info.get("required_dicts", self._get_default_required_dicts())
        initial_fields = solver_info.get("initial_fields", self._get_default_initial_fields())
        
        # 生成system文件
        result["system/blockMeshDict"] = BlockMeshDictGenerator(self.config).generate()
        result["system/controlDict"] = ControlDictGenerator(self.config).generate()
        result["system/fvSchemes"] = FvSchemesGenerator(self.config).generate()
        result["system/fvSolution"] = FvSolutionGenerator(self.config).generate()
        
        # 生成constant文件
        for dict_name in required_dicts:
            if dict_name == "transportProperties":
                result["constant/transportProperties"] = TransportPropertiesGenerator(self.config).generate()
            elif dict_name == "turbulenceProperties":
                result["constant/turbulenceProperties"] = TurbulencePropertiesGenerator(self.config).generate()
            elif dict_name == "thermophysicalProperties":
                result["constant/thermophysicalProperties"] = ThermophysicalPropertiesGenerator(self.config).generate()
            elif dict_name == "g":
                result["constant/g"] = GFieldGenerator(self.config).generate()
        
        # 生成初始场
        field_factory = InitialFieldFactory(self.config)
        for field_info in initial_fields:
            if isinstance(field_info, dict):
                field_name = field_info.get("name")
            else:
                field_name = field_info
            
            # 根据湍流模型选择epsilon或omega
            if field_name == "epsilon" and self.turbulence_model in ["kOmegaSST", "kOmega"]:
                continue
            if field_name == "omega" and self.turbulence_model not in ["kOmegaSST", "kOmega"]:
                continue
            
            field_gen = field_factory.create_field(field_name)
            if field_gen:
                result[f"0/{field_name}"] = field_gen.generate()
        
        return result


if __name__ == "__main__":
    # 测试
    test_config = {
        "task_id": "test_cavity",
        "physics_type": "incompressible",
        "geometry": {
            "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
            "mesh_resolution": {"nx": 20, "ny": 20, "nz": 1}
        },
        "solver": {
            "name": "icoFoam",
            "endTime": 0.5,
            "deltaT": 0.005
        },
        "nu": 0.01
    }
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test_case"
        case_path.mkdir()
        
        generator = CaseGenerator(test_config)
        generator.generate_all(case_path)
        
        # 列出生成的文件
        print("\\n生成的文件:")
        for f in case_path.rglob("*"):
            if f.is_file():
                print(f"  {f.relative_to(case_path)}")
