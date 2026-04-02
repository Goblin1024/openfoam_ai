"""
阶段三测试套件 - 记忆性建模与充分交互

测试内容:
1. MemoryManager - 记忆管理
2. ConfigurationDiffer - 配置差异分析
3. SessionManager - 会话管理
4. GradioInterface - Web界面（可选）
5. CLIInterface - 命令行界面（可选）

运行方式:
    cd openfoam_ai
    python -m pytest tests/test_phase3.py -v
    python tests/test_phase3.py  # 直接运行
"""

import sys
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

# 确保可以导入模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openfoam_ai.memory.memory_manager import (
    MemoryManager, MemoryEntry, ConfigurationDiffer, create_memory_manager
)
from openfoam_ai.memory.session_manager import (
    SessionManager, ConversationContext, PendingOperation, create_session
)


class TestConfigurationDiffer(unittest.TestCase):
    """测试配置差异分析器"""
    
    def setUp(self):
        """设置测试数据"""
        self.old_config = {
            "physics_type": "incompressible",
            "solver": {"name": "icoFoam", "endTime": 0.5},
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0},
                "mesh_resolution": {"nx": 20, "ny": 20}
            },
            "fluid_properties": {"nu": 0.01}
        }
        
        self.new_config = {
            "physics_type": "incompressible",
            "solver": {"name": "icoFoam", "endTime": 1.0},
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0},
                "mesh_resolution": {"nx": 40, "ny": 40}
            },
            "fluid_properties": {"nu": 0.001},
            "new_param": "value"
        }
    
    def test_compute_diff_basic(self):
        """测试基本差异计算"""
        diff = ConfigurationDiffer.compute_diff(self.old_config, self.new_config)
        
        self.assertTrue(diff.has_changes)
        self.assertGreater(len(diff.modified), 0)
        
        # 检查具体修改
        self.assertIn("solver.endTime", [k for k in diff.modified.keys()])
        self.assertIn("geometry.mesh_resolution.nx", [k for k in diff.modified.keys()])
    
    def test_compute_diff_no_change(self):
        """测试无变化的情况"""
        diff = ConfigurationDiffer.compute_diff(self.old_config, self.old_config)
        
        self.assertFalse(diff.has_changes)
        self.assertEqual(len(diff.added), 0)
        self.assertEqual(len(diff.removed), 0)
        self.assertEqual(len(diff.modified), 0)
    
    def test_apply_diff(self):
        """测试应用差异"""
        diff = ConfigurationDiffer.compute_diff(self.old_config, self.new_config)
        
        # 应用差异到旧配置
        applied = ConfigurationDiffer.apply_diff(self.old_config, diff)
        
        # 验证结果
        self.assertEqual(applied['geometry']['mesh_resolution']['nx'], 40)
        self.assertEqual(applied['fluid_properties']['nu'], 0.001)
        self.assertEqual(applied['new_param'], 'value')
    
    def test_nested_diff(self):
        """测试嵌套字典的差异"""
        old = {"a": {"b": {"c": 1}}}
        new = {"a": {"b": {"c": 2, "d": 3}}}
        
        diff = ConfigurationDiffer.compute_diff(old, new)
        
        self.assertTrue(diff.has_changes)
        self.assertIn("a.b.c", diff.modified)
        self.assertIn("a.b.d", diff.added)


class TestMemoryManager(unittest.TestCase):
    """测试记忆管理器"""
    
    def setUp(self):
        """创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = MemoryManager(db_path=self.temp_dir, use_mock=True)
        
        self.sample_config = {
            "physics_type": "incompressible",
            "solver": {"name": "icoFoam"},
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0},
                "mesh_resolution": {"nx": 20, "ny": 20}
            }
        }
    
    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_store_memory(self):
        """测试存储记忆"""
        memory_id = self.memory.store_memory(
            case_name="test_case",
            user_prompt="测试算例",
            config=self.sample_config
        )
        
        self.assertIsNotNone(memory_id)
        self.assertIsInstance(memory_id, str)
        self.assertGreater(len(memory_id), 0)
    
    def test_search_similar(self):
        """测试相似性检索"""
        # 存储几个记忆
        self.memory.store_memory(
            case_name="cavity_flow",
            user_prompt="建立方腔驱动流",
            config=self.sample_config,
            tags=["incompressible"]
        )
        
        self.memory.store_memory(
            case_name="pipe_flow",
            user_prompt="建立管道流动",
            config={**self.sample_config, "physics_type": "compressible"},
            tags=["compressible"]
        )
        
        # 检索
        results = self.memory.search_similar("方腔流动", n_results=2)
        
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)
    
    def test_find_case_history(self):
        """测试获取算例历史"""
        case_name = "history_test"
        
        # 存储多个版本
        for i in range(3):
            config = self.sample_config.copy()
            config['version'] = i
            self.memory.store_memory(
                case_name=case_name,
                user_prompt=f"版本 {i}",
                config=config
            )
        
        # 获取历史
        history = self.memory.find_case_history(case_name)
        
        self.assertEqual(len(history), 3)
    
    def test_get_latest_config(self):
        """测试获取最新配置"""
        case_name = "latest_test"
        
        # 存储旧版本
        old_config = {**self.sample_config, "version": 1}
        self.memory.store_memory(
            case_name=case_name,
            user_prompt="旧版本",
            config=old_config
        )
        
        # 存储新版本
        new_config = {**self.sample_config, "version": 2}
        self.memory.store_memory(
            case_name=case_name,
            user_prompt="新版本",
            config=new_config
        )
        
        # 获取最新
        latest = self.memory.get_latest_config(case_name)
        
        self.assertIsNotNone(latest)
        self.assertEqual(latest['version'], 2)
    
    def test_create_incremental_update(self):
        """测试增量更新"""
        case_name = "incremental_test"
        
        # 存储初始配置
        self.memory.store_memory(
            case_name=case_name,
            user_prompt="初始配置",
            config=self.sample_config
        )
        
        # 创建增量更新
        new_config = {
            **self.sample_config,
            "geometry": {
                **self.sample_config["geometry"],
                "mesh_resolution": {"nx": 40, "ny": 40}
            }
        }
        
        diff, memory_id = self.memory.create_incremental_update(
            case_name=case_name,
            modification_prompt="加密网格",
            new_config=new_config
        )
        
        self.assertTrue(diff.has_changes)
        self.assertIn("geometry.mesh_resolution.nx", diff.modified)
        self.assertIsNotNone(memory_id)
    
    def test_statistics(self):
        """测试统计信息"""
        # 存储几个记忆
        for i in range(3):
            self.memory.store_memory(
                case_name=f"case_{i}",
                user_prompt=f"测试 {i}",
                config=self.sample_config
            )
        
        stats = self.memory.get_statistics()
        
        self.assertEqual(stats['total_memories'], 3)
        self.assertEqual(stats['unique_cases'], 3)
        self.assertEqual(stats['storage_mode'], 'mock')
    
    def test_export_import(self):
        """测试导出导入"""
        # 存储记忆
        self.memory.store_memory(
            case_name="export_test",
            user_prompt="导出测试",
            config=self.sample_config
        )
        
        # 导出
        export_file = self.memory.export_memory()
        
        self.assertTrue(Path(export_file).exists())
        
        # 创建新的MemoryManager
        new_memory = MemoryManager(db_path=self.temp_dir + "_new", use_mock=True)
        
        # 导入
        count = new_memory.import_memory(export_file)
        
        self.assertEqual(count, 1)


class TestSessionManager(unittest.TestCase):
    """测试会话管理器"""
    
    def setUp(self):
        """创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.session = SessionManager(
            session_id="test_session",
            storage_path=self.temp_dir
        )
    
    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_add_message(self):
        """测试添加消息"""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi there")
        
        self.assertEqual(len(self.session.messages), 2)
        self.assertEqual(self.session.messages[0].role, "user")
        self.assertEqual(self.session.messages[1].role, "assistant")
    
    def test_set_current_case(self):
        """测试设置当前算例"""
        config = {"name": "test", "type": "incompressible"}
        
        self.session.set_current_case("my_case", config)
        
        self.assertEqual(self.session.context.current_case, "my_case")
        self.assertEqual(self.session.context.current_config, config)
    
    def test_create_pending_operation(self):
        """测试创建待确认操作"""
        op = self.session.create_pending_operation(
            operation_type="create_case",
            description="创建测试算例",
            details={"case_name": "test"}
        )
        
        self.assertIsNotNone(op)
        self.assertEqual(op.operation_type, "create_case")
        self.assertEqual(op.status, "pending")
        self.assertIn(op.risk_level, ['low', 'medium', 'high', 'critical'])
    
    def test_confirm_operation(self):
        """测试确认操作"""
        op = self.session.create_pending_operation(
            operation_type="create_case",
            description="创建测试算例",
            details={}
        )
        
        result = self.session.confirm_operation(op.operation_id)
        
        self.assertTrue(result)
        self.assertEqual(op.status, "confirmed")
    
    def test_reject_operation(self):
        """测试拒绝操作"""
        op = self.session.create_pending_operation(
            operation_type="delete_case",
            description="删除算例",
            details={}
        )
        
        result = self.session.reject_operation(op.operation_id)
        
        self.assertTrue(result)
        self.assertEqual(op.status, "rejected")
    
    def test_get_pending_operations(self):
        """测试获取待确认操作"""
        # 创建几个操作
        op1 = self.session.create_pending_operation(
            operation_type="create_case",
            description="创建",
            details={}
        )
        op2 = self.session.create_pending_operation(
            operation_type="modify_case",
            description="修改",
            details={}
        )
        
        # 确认一个
        self.session.confirm_operation(op1.operation_id)
        
        # 获取待确认的
        pending = self.session.get_pending_operations()
        
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].operation_id, op2.operation_id)
    
    def test_is_high_risk_operation(self):
        """测试高风险操作判断"""
        self.assertTrue(self.session.is_high_risk_operation("delete_case"))
        self.assertTrue(self.session.is_high_risk_operation("overwrite_data"))
        self.assertFalse(self.session.is_high_risk_operation("create_case"))
    
    def test_generate_confirmation_prompt(self):
        """测试生成确认提示"""
        op = self.session.create_pending_operation(
            operation_type="delete_case",
            description="删除算例",
            details={"case_name": "important_case"}
        )
        
        # delete_case应该是critical级别
        self.assertEqual(op.risk_level, "critical")
        
        prompt = self.session.generate_confirmation_prompt(op)
        
        self.assertIn("delete_case", prompt)
        self.assertIn("important_case", prompt)
        self.assertIn("警告", prompt)
    
    def test_conversation_history(self):
        """测试对话历史"""
        for i in range(5):
            self.session.add_message("user", f"消息 {i}")
        
        history = self.session.get_conversation_history(n_messages=3)
        
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]['content'], "消息 2")
        self.assertEqual(history[-1]['content'], "消息 4")
    
    def test_session_persistence(self):
        """测试会话持久化"""
        # 添加消息
        self.session.add_message("user", "Test")
        self.session.set_current_case("test_case")
        
        # 保存
        self.session.save()
        
        # 创建新实例，应该能加载
        new_session = SessionManager(
            session_id="test_session",
            storage_path=self.temp_dir
        )
        
        self.assertEqual(len(new_session.messages), 1)
        self.assertEqual(new_session.context.current_case, "test_case")
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi")
        self.session.set_current_case("test")
        
        stats = self.session.get_statistics()
        
        self.assertEqual(stats['total_messages'], 2)
        self.assertEqual(stats['user_messages'], 1)
        self.assertEqual(stats['assistant_messages'], 1)
        self.assertEqual(stats['current_case'], "test")


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = MemoryManager(db_path=self.temp_dir, use_mock=True)
        self.session = SessionManager(
            session_id="integration_test",
            storage_path=self.temp_dir
        )
    
    def tearDown(self):
        """清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_memory_and_session_integration(self):
        """测试记忆和会话集成"""
        config = {
            "physics_type": "incompressible",
            "solver": {"name": "icoFoam"},
            "geometry": {"mesh_resolution": {"nx": 20, "ny": 20}}
        }
        
        # 存储到记忆
        memory_id = self.memory.store_memory(
            case_name="integration_case",
            user_prompt="测试算例",
            config=config
        )
        
        # 记录到会话
        self.session.add_message("user", "创建算例")
        self.session.add_message("assistant", "已创建")
        self.session.set_current_case("integration_case", config)
        
        # 验证
        self.assertEqual(self.memory.get_statistics()['total_memories'], 1)
        self.assertEqual(len(self.session.messages), 2)
    
    def test_incremental_workflow(self):
        """测试增量更新工作流"""
        case_name = "incremental_workflow"
        
        # 初始配置
        initial_config = {
            "physics_type": "incompressible",
            "solver": {"name": "icoFoam"},
            "geometry": {"mesh_resolution": {"nx": 20, "ny": 20}}
        }
        
        # 用户请求1
        self.session.add_message("user", "建立方腔驱动流")
        self.memory.store_memory(
            case_name=case_name,
            user_prompt="建立方腔驱动流",
            config=initial_config,
            tags=["initial"]
        )
        
        # 用户请求2（增量修改）
        self.session.add_message("user", "加密网格到40x40")
        
        new_config = {
            **initial_config,
            "geometry": {"mesh_resolution": {"nx": 40, "ny": 40}}
        }
        
        diff, memory_id = self.memory.create_incremental_update(
            case_name=case_name,
            modification_prompt="加密网格到40x40",
            new_config=new_config
        )
        
        # 创建待确认操作
        op = self.session.create_pending_operation(
            operation_type="modify_case",
            description="加密网格",
            details={"changes": diff.modified}
        )
        
        # 验证工作流
        self.assertTrue(diff.has_changes)
        self.assertEqual(len(self.session.get_pending_operations()), 1)
        
        # 确认并执行
        self.session.confirm_operation(op.operation_id)
        self.assertEqual(op.status, "confirmed")


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationDiffer))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
