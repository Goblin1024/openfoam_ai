"""
基础测试 - 验证核心模块可导入
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """测试所有核心模块可导入"""
    print("测试模块导入...")
    
    try:
        from core.case_manager import CaseManager, create_cavity_case
        print("✓ case_manager")
    except Exception as e:
        print(f"✗ case_manager: {e}")
        return False
    
    try:
        from core.validators import validate_simulation_config, PhysicsValidator
        print("✓ validators")
    except Exception as e:
        print(f"✗ validators: {e}")
        return False
    
    try:
        from core.file_generator import CaseGenerator
        print("✓ file_generator")
    except Exception as e:
        print(f"✗ file_generator: {e}")
        return False
    
    try:
        from core.openfoam_runner import OpenFOAMRunner
        print("✓ openfoam_runner")
    except Exception as e:
        print(f"✗ openfoam_runner: {e}")
        return False
    
    try:
        from agents.prompt_engine import PromptEngine, ConfigRefiner
        print("✓ prompt_engine")
    except Exception as e:
        print(f"✗ prompt_engine: {e}")
        return False
    
    try:
        from agents.manager_agent import ManagerAgent
        print("✓ manager_agent")
    except Exception as e:
        print(f"✗ manager_agent: {e}")
        return False
    
    return True


def test_case_manager():
    """测试CaseManager基本功能"""
    print("\n测试 CaseManager...")
    
    import tempfile
    from core.case_manager import CaseManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建实例
        cm = CaseManager(tmpdir)
        
        # 测试创建算例
        case_path = cm.create_case("test_case", "incompressible")
        assert case_path.exists(), "算例目录未创建"
        
        # 测试列出算例
        cases = cm.list_cases()
        assert "test_case" in cases, "算例未在列表中"
        
        print("✓ CaseManager 基本功能正常")
        return True


def test_validators():
    """测试验证器"""
    print("\n测试 Validators...")
    
    from core.validators import validate_simulation_config
    
    # 测试有效配置
    valid_config = {
        "task_id": "test_001",
        "physics_type": "incompressible",
        "geometry": {
            "nx": 50, "ny": 50, "nz": 1,
            "L": 1.0, "W": 1.0, "H": 0.1
        },
        "solver": {
            "name": "icoFoam",
            "endTime": 0.5,
            "deltaT": 0.005
        }
    }
    
    passed, errors = validate_simulation_config(valid_config)
    if passed:
        print("✓ 有效配置验证通过")
    else:
        print(f"✗ 有效配置验证失败: {errors}")
        return False
    
    # 测试无效配置
    invalid_config = valid_config.copy()
    invalid_config["geometry"] = {
        "nx": 5,  # 小于最小值
        "ny": 50,
        "nz": 1,
        "L": 1.0, "W": 1.0, "H": 0.1
    }
    
    passed, errors = validate_simulation_config(invalid_config)
    if not passed:
        print("✓ 无效配置正确识别")
    else:
        print("✗ 无效配置未被识别")
        return False
    
    return True


def test_file_generator():
    """测试文件生成器"""
    print("\n测试 FileGenerator...")
    
    import tempfile
    from core.file_generator import CaseGenerator
    
    config = {
        "task_id": "test_gen",
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
    
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test_case"
        case_path.mkdir()
        
        # 创建必要的子目录
        for d in ["0", "constant", "system", "logs"]:
            (case_path / d).mkdir(exist_ok=True)
        
        generator = CaseGenerator(config)
        generator.generate_all(case_path)
        
        # 验证文件生成
        expected_files = [
            "system/blockMeshDict",
            "system/controlDict",
            "system/fvSchemes",
            "system/fvSolution",
            "constant/transportProperties",
            "0/U",
            "0/p"
        ]
        
        for file in expected_files:
            file_path = case_path / file
            if not file_path.exists():
                print(f"✗ 文件未生成: {file}")
                return False
        
        print("✓ 所有文件生成成功")
        return True


def test_prompt_engine():
    """测试PromptEngine"""
    print("\n测试 PromptEngine...")
    
    from agents.prompt_engine import PromptEngine, ConfigRefiner
    
    # 测试mock模式
    engine = PromptEngine()  # 无API key，自动进入mock模式
    
    config = engine.natural_language_to_config("建立一个方腔驱动流")
    
    if config.get("physics_type") == "incompressible":
        print("✓ Mock模式配置生成正常")
    else:
        print(f"✗ Mock模式异常: {config}")
        return False
    
    # 测试配置优化
    refiner = ConfigRefiner()
    
    test_config = {
        "task_id": "",
        "geometry": {
            "mesh_resolution": {"nx": 5, "ny": 5, "nz": 10}
        },
        "solver": {
            "deltaT": 0.0001,
            "endTime": 1000
        }
    }
    
    refined = refiner.refine(test_config)
    
    # 检查优化结果
    if refined["geometry"]["mesh_resolution"]["nx"] >= 10:
        print("✓ 配置优化正常")
    else:
        print("✗ 配置优化异常")
        return False
    
    return True


def main():
    """运行所有测试"""
    print("="*50)
    print("OpenFOAM AI Agent - 基础测试")
    print("="*50)
    
    tests = [
        ("模块导入", test_imports),
        ("CaseManager", test_case_manager),
        ("Validators", test_validators),
        ("FileGenerator", test_file_generator),
        ("PromptEngine", test_prompt_engine),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} 测试异常: {e}")
            results.append((name, False))
    
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status:10} {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
