"""
CaseManager 单元测试
测试算例管理器的核心功能：创建、复制、清理、删除算例。
"""

import tempfile
import shutil
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.case_manager import CaseManager, CaseInfo


def test_case_manager_initialization():
    """测试CaseManager初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        assert cm.base_path == Path(tmpdir)
        assert cm.base_path.exists()


def test_create_case():
    """测试创建算例目录结构"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        case_path = cm.create_case("test_case", "incompressible")
        
        # 验证目录创建
        assert case_path.exists()
        assert (case_path / "0").exists()
        assert (case_path / "constant").exists()
        assert (case_path / "system").exists()
        assert (case_path / "logs").exists()
        
        # 验证算例信息文件
        info_file = case_path / ".case_info.json"
        assert info_file.exists()
        
        # 验证CaseInfo加载
        case_info = cm._load_case_info(case_path)
        assert case_info is not None
        assert case_info.name == "test_case"
        assert case_info.physics_type == "incompressible"
        assert case_info.status == "init"


def test_copy_template():
    """测试从模板复制算例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建源模板目录
        src_template = Path(tmpdir) / "template"
        src_template.mkdir()
        (src_template / "0").mkdir()
        (src_template / "constant").mkdir()
        (src_template / "system").mkdir()
        (src_template / "logs").mkdir()
        (src_template / "0" / "U").write_text("dummy")
        
        cm = CaseManager(tmpdir)
        dst_path = cm.copy_template(str(src_template), "copied_case")
        
        # 验证复制
        assert dst_path.exists()
        assert (dst_path / "0" / "U").exists()
        assert (dst_path / "0" / "U").read_text() == "dummy"


def test_list_cases():
    """测试列出算例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        cm.create_case("case1", "incompressible")
        cm.create_case("case2", "heatTransfer")
        
        cases = cm.list_cases()
        assert "case1" in cases
        assert "case2" in cases
        assert len(cases) == 2


def test_get_case():
    """测试获取算例路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        case_path = cm.create_case("test_case", "incompressible")
        
        retrieved = cm.get_case("test_case")
        assert retrieved == case_path
        
        # 不存在的算例应返回None
        assert cm.get_case("nonexistent") is None


def test_cleanup():
    """测试清理算例文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        case_path = cm.create_case("cleanup_test", "incompressible")
        
        # 创建一些时间步目录
        (case_path / "0.1").mkdir()
        (case_path / "0.2").mkdir()
        (case_path / "processor0").mkdir()
        
        # 创建日志文件
        log_dir = case_path / "logs"
        (log_dir / "solver.log").write_text("log content")
        (log_dir / "old.log").write_text("old log")
        
        # 执行清理（不保留结果）
        cm.cleanup("cleanup_test", keep_results=False)
        
        # 验证时间步目录被删除
        assert not (case_path / "0.1").exists()
        assert not (case_path / "0.2").exists()
        assert not (case_path / "processor0").exists()
        
        # 验证日志被清理（仅保留最近3个，但我们只有2个）
        # 实际上，旧日志会被删除
        assert (log_dir / "solver.log").exists()  # 应保留
        # 旧日志可能被删除，取决于时间戳
        
        # 验证算例状态重置为init
        info = cm._load_case_info(case_path)
        assert info is not None
        assert info.status == "init"


def test_delete_case():
    """测试删除算例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        case_path = cm.create_case("to_delete", "incompressible")
        assert case_path.exists()
        
        cm.delete_case("to_delete")
        assert not case_path.exists()


def test_case_info_persistence():
    """测试算例信息持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CaseManager(tmpdir)
        case_path = cm.create_case("persist_test", "compressible")
        
        # 修改信息
        info = cm._load_case_info(case_path)
        assert info is not None
        info.status = "meshed"
        cm._save_case_info(case_path, info)
        
        # 重新加载验证
        new_info = cm._load_case_info(case_path)
        assert new_info is not None
        assert new_info.status == "meshed"


if __name__ == "__main__":
    # 简单运行测试（也可用pytest）
    test_case_manager_initialization()
    print("✓ test_case_manager_initialization")
    test_create_case()
    print("✓ test_create_case")
    test_copy_template()
    print("✓ test_copy_template")
    test_list_cases()
    print("✓ test_list_cases")
    test_get_case()
    print("✓ test_get_case")
    test_cleanup()
    print("✓ test_cleanup")
    test_delete_case()
    print("✓ test_delete_case")
    test_case_info_persistence()
    print("✓ test_case_info_persistence")
    print("所有测试通过！")