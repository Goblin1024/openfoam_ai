"""
OpenFOAM Case Manager
算例目录管理器 - 负责创建、管理和清理OpenFOAM算例
"""

import os
import shutil
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class CaseInfo:
    """算例信息数据类"""
    name: str
    path: str
    created_at: str
    modified_at: str
    physics_type: str
    solver: str
    status: str  # init, meshed, solving, converged, diverged


class CaseManager:
    """
    OpenFOAM算例目录管理器
    
    负责：
    - 创建标准OpenFOAM算例目录结构
    - 复制模板算例
    - 清理算例文件
    - 管理算例元数据
    """
    
    def __init__(self, base_path: str = "./cases"):
        """
        初始化CaseManager
        
        Args:
            base_path: 算例根目录路径
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 标准OpenFOAM目录结构
        self.standard_dirs = ["0", "constant", "system", "logs"]
    
    def create_case(self, case_name: str, physics_type: str = "incompressible") -> Path:
        """
        创建标准OpenFOAM算例目录结构
        
        Args:
            case_name: 算例名称
            physics_type: 物理类型
            
        Returns:
            创建的算例路径
        """
        case_path = self.base_path / case_name
        
        # 如果已存在，先删除
        if case_path.exists():
            shutil.rmtree(case_path)
        
        # 创建标准目录
        for dir_name in self.standard_dirs:
            (case_path / dir_name).mkdir(parents=True, exist_ok=True)
        
        # 创建算例信息文件
        case_info = CaseInfo(
            name=case_name,
            path=str(case_path.absolute()),
            created_at=time.strftime('%Y-%m-%d %H:%M:%S'),
            modified_at=time.strftime('%Y-%m-%d %H:%M:%S'),
            physics_type=physics_type,
            solver="",
            status="init"
        )
        
        self._save_case_info(case_path, case_info)
        
        print(f"[CaseManager] 创建算例: {case_name} at {case_path}")
        return case_path
    
    def copy_template(self, template_path: str, case_name: str) -> Path:
        """
        从模板复制算例
        
        Args:
            template_path: 模板路径
            case_name: 新算例名称
            
        Returns:
            新算例路径
        """
        src = Path(template_path)
        dst = self.base_path / case_name
        
        if not src.exists():
            raise FileNotFoundError(f"模板不存在: {template_path}")
        
        if dst.exists():
            shutil.rmtree(dst)
        
        shutil.copytree(src, dst)
        
        # 更新算例信息
        case_info = self._load_case_info(dst)
        if case_info:
            case_info.name = case_name
            case_info.modified_at = time.strftime('%Y-%m-%d %H:%M:%S')
            self._save_case_info(dst, case_info)
        
        print(f"[CaseManager] 复制模板: {template_path} -> {case_name}")
        return dst
    
    def get_case(self, case_name: str) -> Optional[Path]:
        """
        获取算例路径
        
        Args:
            case_name: 算例名称
            
        Returns:
            算例路径，不存在则返回None
        """
        case_path = self.base_path / case_name
        return case_path if case_path.exists() else None
    
    def list_cases(self) -> List[str]:
        """
        列出所有算例
        
        Returns:
            算例名称列表
        """
        cases = []
        for item in self.base_path.iterdir():
            if item.is_dir():
                # 验证是否为有效的OpenFOAM算例
                if all((item / d).exists() for d in ["system", "constant"]):
                    cases.append(item.name)
        return cases
    
    def cleanup(self, case_name: str, keep_results: bool = False) -> None:
        """
        清理算例文件
        
        Args:
            case_name: 算例名称
            keep_results: 是否保留计算结果
        """
        case_path = self.base_path / case_name
        
        if not case_path.exists():
            print(f"[CaseManager] 警告: 算例不存在 {case_name}")
            return
        
        if not keep_results:
            # 删除时间步目录（以数字开头的目录）
            for item in case_path.iterdir():
                if item.is_dir():
                    try:
                        float(item.name)  # 尝试转换为数字
                        shutil.rmtree(item)
                        print(f"[CaseManager] 删除时间步: {item.name}")
                    except ValueError:
                        pass
        
        # 清理处理器目录
        for proc_dir in case_path.glob("processor*"):
            if proc_dir.is_dir():
                shutil.rmtree(proc_dir)
                print(f"[CaseManager] 删除并行目录: {proc_dir.name}")
        
        # 清理日志（可选保留最近的几条）
        log_dir = case_path / "logs"
        if log_dir.exists():
            logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
            # 保留最近3个日志
            for log in logs[:-3]:
                log.unlink()
                print(f"[CaseManager] 清理旧日志: {log.name}")
        
        # 更新算例信息
        case_info = self._load_case_info(case_path)
        if case_info:
            case_info.modified_at = time.strftime('%Y-%m-%d %H:%M:%S')
            case_info.status = "init"
            self._save_case_info(case_path, case_info)
    
    def delete_case(self, case_name: str) -> None:
        """
        删除算例
        
        Args:
            case_name: 算例名称
        """
        case_path = self.base_path / case_name
        
        if case_path.exists():
            shutil.rmtree(case_path)
            print(f"[CaseManager] 删除算例: {case_name}")
        else:
            print(f"[CaseManager] 警告: 算例不存在 {case_name}")
    
    def get_case_info(self, case_name: str) -> Optional[CaseInfo]:
        """
        获取算例信息
        
        Args:
            case_name: 算例名称
            
        Returns:
            算例信息
        """
        case_path = self.base_path / case_name
        return self._load_case_info(case_path)
    
    def update_case_status(self, case_name: str, status: str, solver: str = "") -> None:
        """
        更新算例状态
        
        Args:
            case_name: 算例名称
            status: 新状态
            solver: 求解器名称（可选）
        """
        case_path = self.base_path / case_name
        case_info = self._load_case_info(case_path)
        
        if case_info:
            case_info.status = status
            case_info.modified_at = time.strftime('%Y-%m-%d %H:%M:%S')
            if solver:
                case_info.solver = solver
            self._save_case_info(case_path, case_info)
    
    def _save_case_info(self, case_path: Path, case_info: CaseInfo) -> None:
        """保存算例信息到JSON文件"""
        try:
            from .utils import save_json
        except ImportError:
            from utils import save_json
        info_file = case_path / ".case_info.json"
        save_json(info_file, asdict(case_info))
    
    def _load_case_info(self, case_path: Path) -> Optional[CaseInfo]:
        """从JSON文件加载算例信息"""
        try:
            from .utils import load_json
        except ImportError:
            from utils import load_json
        info_file = case_path / ".case_info.json"
        data = load_json(info_file)
        if data:
            return CaseInfo(**data)
        return None


# 便捷函数
def create_cavity_case(case_manager: CaseManager, case_name: str = "cavity") -> Path:
    """
    创建标准方腔驱动流算例
    
    Args:
        case_manager: CaseManager实例
        case_name: 算例名称
        
    Returns:
        算例路径
    """
    case_path = case_manager.create_case(case_name, physics_type="incompressible")
    
    # 创建blockMeshDict
    blockmesh_dict = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

scale   1;

vertices
(
    (0 0 0)
    (1 0 0)
    (1 1 0)
    (0 1 0)
    (0 0 0.1)
    (1 0 0.1)
    (1 1 0.1)
    (0 1 0.1)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (20 20 1) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    movingWall
    {
        type wall;
        faces
        (
            (3 7 6 2)
        );
    }
    fixedWalls
    {
        type wall;
        faces
        (
            (0 4 7 3)
            (2 6 5 1)
            (1 5 4 0)
        );
    }
    frontAndBack
    {
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }
);

// ************************************************************************* //
'''
    
    (case_path / "system" / "blockMeshDict").write_text(blockmesh_dict)
    
    # 创建controlDict
    control_dict = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     icoFoam;

startFrom       startTime;

startTime       0;

stopAt          endTime;

endTime         0.5;

deltaT          0.005;

writeControl    timeStep;

writeInterval   20;

purgeWrite      0;

writeFormat     ascii;

writePrecision  6;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

// ************************************************************************* //
'''
    
    (case_path / "system" / "controlDict").write_text(control_dict)
    
    # 创建fvSchemes
    fv_schemes = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
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

// ************************************************************************* //
'''
    
    (case_path / "system" / "fvSchemes").write_text(fv_schemes)
    
    # 创建fvSolution
    fv_solution = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
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

    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0;
    }
}

PISO
{
    nCorrectors     2;
    nNonOrthogonalCorrectors 0;
    pRefCell        0;
    pRefValue       0;
}

// ************************************************************************* //
'''
    
    (case_path / "system" / "fvSolution").write_text(fv_solution)
    
    # 创建初始条件 U
    u_field = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       volVectorField;
    object      U;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{
    movingWall
    {
        type            fixedValue;
        value           uniform (1 0 0);
    }

    fixedWalls
    {
        type            noSlip;
    }

    frontAndBack
    {
        type            empty;
    }
}

// ************************************************************************* //
'''
    
    (case_path / "0" / "U").write_text(u_field)
    
    # 创建初始条件 p
    p_field = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       volScalarField;
    object      p;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    movingWall
    {
        type            zeroGradient;
    }

    fixedWalls
    {
        type            zeroGradient;
    }

    frontAndBack
    {
        type            empty;
    }
}

// ************************************************************************* //
'''
    
    (case_path / "0" / "p").write_text(p_field)
    
    # 创建transportProperties
    transport_props = '''/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    object      transportProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

nu              0.01;

// ************************************************************************* //
'''
    
    (case_path / "constant" / "transportProperties").write_text(transport_props)
    
    print(f"[CaseManager] 方腔算例创建完成: {case_path}")
    return case_path


if __name__ == "__main__":
    # 测试
    cm = CaseManager("./test_cases")
    
    # 创建方腔算例
    case_path = create_cavity_case(cm, "test_cavity")
    
    # 列出演算例
    print("\n算例列表:", cm.list_cases())
    
    # 获取算例信息
    info = cm.get_case_info("test_cavity")
    if info:
        print(f"\n算例信息: {info}")
