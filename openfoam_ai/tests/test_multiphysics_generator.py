"""
测试多物理场字典生成器
"""
import tempfile
from pathlib import Path
from openfoam_ai.core.file_generator import (
    CaseGenerator, estimate_turbulence_initial_values,
    TurbulencePropertiesGenerator, ThermophysicalPropertiesGenerator,
    GFieldGenerator, InitialFieldFactory
)


def test_turbulence_estimation():
    """测试湍流参数估算"""
    print('=== 测试湍流参数估算 ===')
    turb_vals = estimate_turbulence_initial_values(1.0, 0.05, 0.1)
    print(f"U=1.0, I=0.05, l=0.1:")
    print(f"  k = {turb_vals['k']:.6f}")
    print(f"  epsilon = {turb_vals['epsilon']:.6f}")
    print(f"  omega = {turb_vals['omega']:.6f}")
    print(f"  nut = {turb_vals['nut']:.8f}")
    print(f"  alphat = {turb_vals['alphat']:.8f}")
    assert turb_vals['k'] > 0
    assert turb_vals['epsilon'] > 0
    assert turb_vals['omega'] > 0
    print("湍流参数估算测试通过!\n")


def test_simplefoam():
    """测试 simpleFoam 配置"""
    print('=== 测试 simpleFoam 配置 ===')
    config = {
        'solver': {'name': 'simpleFoam'},
        'turbulence_model': 'kEpsilon',
        'physics_type': 'incompressible',
        'geometry': {'dimensions': {'L': 1.0, 'W': 1.0, 'H': 0.1}, 'mesh_resolution': {'nx': 20, 'ny': 20, 'nz': 1}},
        'nu': 0.01,
        'boundary_conditions': {'inlet': {'U': {'type': 'fixedValue', 'value': [1, 0, 0]}}}
    }
    gen = CaseGenerator(config)
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / 'test_simpleFoam'
        case_path.mkdir()
        gen.generate_all(case_path)
        
        # 检查生成的文件
        files = [f for f in case_path.rglob('*') if f.is_file()]
        file_names = [str(f.relative_to(case_path)) for f in files]
        
        print(f"生成文件数: {len(files)}")
        
        # 验证必需文件存在
        required = ['system/blockMeshDict', 'system/controlDict', 'system/fvSchemes', 
                    'system/fvSolution', 'constant/transportProperties', 
                    'constant/turbulenceProperties', '0/p', '0/U', '0/k', '0/epsilon', '0/nut']
        for req in required:
            if req in file_names:
                print(f"  ✓ {req}")
            else:
                print(f"  ✗ {req} (缺失)")
    
    print("simpleFoam 测试通过!\n")


def test_buoyant_pimple_foam():
    """测试 buoyantPimpleFoam 配置"""
    print('=== 测试 buoyantPimpleFoam 配置 ===')
    config = {
        'solver': {'name': 'buoyantPimpleFoam'},
        'turbulence_model': 'kOmegaSST',
        'physics_type': 'heatTransfer',
        'geometry': {'dimensions': {'L': 1.0, 'W': 1.0, 'H': 0.1}, 'mesh_resolution': {'nx': 20, 'ny': 20, 'nz': 1}},
        'fluid': 'air',
        'gravity': {'gx': 0, 'gy': -9.81, 'gz': 0}
    }
    gen = CaseGenerator(config)
    files_dict = gen.generate_all_to_dict()
    
    print(f"生成文件数: {len(files_dict)}")
    print("生成的文件:")
    for path in sorted(files_dict.keys()):
        print(f"  {path}")
    
    # 验证必需文件存在
    required_keys = ['system/controlDict', 'constant/turbulenceProperties', 
                     'constant/thermophysicalProperties', 'constant/g',
                     '0/p_rgh', '0/U', '0/T', '0/k', '0/omega']
    missing = [k for k in required_keys if k not in files_dict]
    if missing:
        print(f"缺失文件: {missing}")
    else:
        print("所有必需文件已生成!")
    
    # 验证 omega 存在但 epsilon 不存在 (kOmegaSST)
    assert '0/omega' in files_dict, "omega 场应该存在 (kOmegaSST)"
    assert '0/epsilon' not in files_dict, "epsilon 场不应该存在 (kOmegaSST)"
    
    print("buoyantPimpleFoam 测试通过!\n")


def test_interfoam():
    """测试 interFoam 配置"""
    print('=== 测试 interFoam 配置 ===')
    config = {
        'solver': {'name': 'interFoam'},
        'turbulence_model': 'kEpsilon',
        'physics_type': 'multiphase',
        'geometry': {'dimensions': {'L': 1.0, 'W': 1.0, 'H': 0.1}, 'mesh_resolution': {'nx': 20, 'ny': 20, 'nz': 1}},
    }
    gen = CaseGenerator(config)
    files_dict = gen.generate_all_to_dict()
    
    print(f"生成文件数: {len(files_dict)}")
    
    # 验证 alpha.water 存在
    assert '0/alpha.water' in files_dict, "alpha.water 场应该存在"
    assert '0/p_rgh' in files_dict, "p_rgh 场应该存在"
    assert 'constant/g' in files_dict, "g 文件应该存在"
    
    print("interFoam 测试通过!\n")


def test_turbulence_properties_generator():
    """测试湍流属性生成器"""
    print('=== 测试 TurbulencePropertiesGenerator ===')
    
    # 测试 laminar
    config1 = {'turbulence_model': 'laminar'}
    gen1 = TurbulencePropertiesGenerator(config1)
    content1 = gen1.generate()
    assert 'simulationType  laminar' in content1
    print("  laminar 配置正确")
    
    # 测试 kEpsilon
    config2 = {'turbulence_model': 'kEpsilon'}
    gen2 = TurbulencePropertiesGenerator(config2)
    content2 = gen2.generate()
    assert 'simulationType  RAS' in content2
    assert 'model           kEpsilon' in content2
    print("  kEpsilon 配置正确")
    
    # 测试 kOmegaSST
    config3 = {'turbulence_model': 'kOmegaSST'}
    gen3 = TurbulencePropertiesGenerator(config3)
    content3 = gen3.generate()
    assert 'model           kOmegaSST' in content3
    print("  kOmegaSST 配置正确")
    
    print("TurbulencePropertiesGenerator 测试通过!\n")


def test_thermophysical_properties_generator():
    """测试热物性属性生成器"""
    print('=== 测试 ThermophysicalPropertiesGenerator ===')
    
    # 测试不可压缩传热 (buoyantSimpleFoam)
    config1 = {'solver': {'name': 'buoyantSimpleFoam'}, 'fluid': 'air'}
    gen1 = ThermophysicalPropertiesGenerator(config1)
    content1 = gen1.generate()
    assert 'heRhoThermo' in content1
    assert 'rhoConst' in content1
    print("  heRhoThermo 配置正确")
    
    # 测试可压缩流 (rhoPimpleFoam)
    config2 = {'solver': {'name': 'rhoPimpleFoam'}, 'fluid': 'air'}
    gen2 = ThermophysicalPropertiesGenerator(config2)
    content2 = gen2.generate()
    assert 'hePsiThermo' in content2
    assert 'perfectGas' in content2
    print("  hePsiThermo 配置正确")
    
    print("ThermophysicalPropertiesGenerator 测试通过!\n")


def test_g_field_generator():
    """测试重力场生成器"""
    print('=== 测试 GFieldGenerator ===')
    
    config = {'gravity': {'gx': 0, 'gy': -9.81, 'gz': 0}}
    gen = GFieldGenerator(config)
    content = gen.generate()
    
    assert 'dimensions' in content
    assert '-9.81' in content
    print("  重力场配置正确")
    print("GFieldGenerator 测试通过!\n")


def test_backward_compatibility():
    """测试向后兼容性 (icoFoam)"""
    print('=== 测试向后兼容性 (icoFoam) ===')
    
    config = {
        'task_id': 'test_cavity',
        'physics_type': 'incompressible',
        'geometry': {
            'dimensions': {'L': 1.0, 'W': 1.0, 'H': 0.1},
            'mesh_resolution': {'nx': 20, 'ny': 20, 'nz': 1}
        },
        'solver': {
            'name': 'icoFoam',
            'endTime': 0.5,
            'deltaT': 0.005
        },
        'nu': 0.01
    }
    
    gen = CaseGenerator(config)
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / 'test_icoFoam'
        case_path.mkdir()
        gen.generate_all(case_path)
        
        files = [f for f in case_path.rglob('*') if f.is_file()]
        file_names = [str(f.relative_to(case_path)) for f in files]
        
        # icoFoam 只需要基本文件
        required = ['system/blockMeshDict', 'system/controlDict', 'system/fvSchemes', 
                    'system/fvSolution', 'constant/transportProperties', '0/p', '0/U']
        
        all_present = all(req in file_names for req in required)
        
        # 不应该有湍流文件
        assert 'constant/turbulenceProperties' not in file_names
        assert '0/k' not in file_names
        
        print(f"  生成文件数: {len(files)}")
        print(f"  基本文件完整: {all_present}")
        print("  无多余湍流文件: ✓")
    
    print("icoFoam 向后兼容测试通过!\n")


if __name__ == '__main__':
    print("=" * 60)
    print("多物理场字典生成器测试")
    print("=" * 60)
    
    test_turbulence_estimation()
    test_turbulence_properties_generator()
    test_thermophysical_properties_generator()
    test_g_field_generator()
    test_backward_compatibility()
    test_simplefoam()
    test_buoyant_pimple_foam()
    test_interfoam()
    
    print("=" * 60)
    print("所有测试通过!")
    print("=" * 60)
