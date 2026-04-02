import sys
sys.path.insert(0, '.')
import tempfile
import shutil
from pathlib import Path
from openfoam_ai.core.case_manager import CaseManager

print("测试重构后的CaseManager")
with tempfile.TemporaryDirectory() as tmpdir:
    manager = CaseManager(base_path=tmpdir)
    print(f"基础路径: {manager.base_path}")
    
    # 测试创建算例
    case_path = manager.create_case("test_case", "incompressible")
    print(f"创建算例路径: {case_path}")
    assert case_path.exists()
    assert (case_path / "0").exists()
    assert (case_path / "constant").exists()
    assert (case_path / "system").exists()
    print("✓ 目录结构正确")
    
    # 测试获取算例信息
    info = manager.get_case_info("test_case")
    print(f"算例信息: {info}")
    assert info is not None
    assert info.name == "test_case"
    print("✓ 算例信息持久化")
    
    # 测试列出算例
    cases = manager.list_cases()
    print(f"算例列表: {cases}")
    assert "test_case" in cases
    print("✓ 列出算例正常")
    
    # 清理
    manager.delete_case("test_case")
    assert not manager.get_case("test_case")
    print("✓ 删除算例正常")

print("所有测试通过")