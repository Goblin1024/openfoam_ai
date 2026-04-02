"""
阶段二测试用例
测试AI自查与自愈能力
"""

import unittest
import tempfile
from pathlib import Path
import sys
import os

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# 导入阶段二模块（作为包的一部分）
from openfoam_ai.agents import mesh_quality_agent
from openfoam_ai.agents import self_healing_agent
from openfoam_ai.agents import physics_validation_agent
from openfoam_ai.agents import critic_agent

# 从core导入
from openfoam_ai.core import openfoam_runner


class TestMeshQualityAgent(unittest.TestCase):
    """测试网格质量自查Agent"""
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_path = Path(self.temp_dir.name) / "test_case"
        self.case_path.mkdir()
        
        # 创建基本目录结构
        for d in ["0", "constant", "system", "logs"]:
            (self.case_path / d).mkdir(exist_ok=True)
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_mesh_quality_checker_init(self):
        """测试网格质量检查器初始化"""
        checker = mesh_quality_agent.MeshQualityChecker(self.case_path)
        self.assertEqual(checker.case_path, self.case_path)
        self.assertIsNotNone(checker.runner)
    
    def test_mesh_quality_assessment(self):
        """测试网格质量评估"""
        checker = mesh_quality_agent.MeshQualityChecker(self.case_path)
        
        # 测试质量等级评估
        metrics_excellent = {
            'non_orthogonality_max': 20,
            'skewness_max': 0.5,
            'aspect_ratio_max': 10,
            'failed_checks': 0
        }
        level = checker._assess_quality_level(metrics_excellent)
        self.assertEqual(level, mesh_quality_agent.MeshQualityLevel.EXCELLENT)
        
        # 测试临界问题
        metrics_critical = {
            'non_orthogonality_max': 90,
            'skewness_max': 15,
            'aspect_ratio_max': 2000,
            'failed_checks': 1
        }
        level = checker._assess_quality_level(metrics_critical)
        self.assertEqual(level, mesh_quality_agent.MeshQualityLevel.CRITICAL)
    
    def test_issue_identification(self):
        """测试问题识别"""
        checker = mesh_quality_agent.MeshQualityChecker(self.case_path)
        
        metrics = {
            'non_orthogonality_max': 75,
            'skewness_max': 5.0,
            'aspect_ratio_max': 150,
            'failed_checks': 0
        }
        
        warnings, errors = checker._identify_issues(metrics)
        
        # 应该有警告
        self.assertTrue(len(warnings) > 0)
        # 非正交性警告
        self.assertTrue(any('非正交' in w for w in warnings))
    
    def test_fix_strategy(self):
        """测试修复策略"""
        checker = mesh_quality_agent.MeshQualityChecker(self.case_path)
        
        # 创建fvSolution文件
        fv_solution = self.case_path / "system" / "fvSolution"
        fv_solution.write_text("""
PIMPLE
{
    nOuterCorrectors 1;
}
""")
        
        # 测试添加非正交修正器
        result = checker._fix_add_nonorthogonal_correctors()
        self.assertTrue(result)
        
        # 验证文件内容
        content = fv_solution.read_text()
        self.assertIn("nNonOrthogonalCorrectors", content)


class TestSelfHealingAgent(unittest.TestCase):
    """测试自愈Agent"""
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_path = Path(self.temp_dir.name) / "test_case"
        self.case_path.mkdir()
        
        # 创建基本目录结构和配置
        for d in ["0", "constant", "system", "logs"]:
            (self.case_path / d).mkdir(exist_ok=True)
        
        # 创建controlDict
        control_dict = self.case_path / "system" / "controlDict"
        control_dict.write_text("""
deltaT 0.01;
startFrom startTime;
startTime 0;
""")
        
        # 创建fvSolution
        fv_solution = self.case_path / "system" / "fvSolution"
        fv_solution.write_text("""
PIMPLE
{
    nOuterCorrectors 1;
}

relaxationFactors
{
    U 0.7;
    p 0.3;
}
""")
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_stability_monitor_init(self):
        """测试稳定性监控器初始化"""
        monitor = self_healing_agent.SolverStabilityMonitor()
        self.assertEqual(monitor.max_history, 200)
        self.assertEqual(len(monitor.metrics_history), 0)
    
    def test_courant_check(self):
        """测试库朗数检查"""
        monitor = self_healing_agent.SolverStabilityMonitor()
        monitor.courant_critical = 5.0
        monitor.courant_warning = 1.0
        
        # 正常库朗数
        metrics_normal = openfoam_runner.SolverMetrics(
            time=0.1, courant_mean=0.2, courant_max=0.5, residuals={}
        )
        event = monitor._check_courant(metrics_normal)
        self.assertIsNone(event)
        
        # 临界库朗数
        metrics_critical = openfoam_runner.SolverMetrics(
            time=0.1, courant_mean=3.0, courant_max=6.0, residuals={}
        )
        event = monitor._check_courant(metrics_critical)
        self.assertIsNotNone(event)
        self.assertEqual(event.divergence_type, self_healing_agent.DivergenceType.COURANT_EXCEEDED)
    
    def test_residual_explosion_check(self):
        """测试残差爆炸检查"""
        monitor = self_healing_agent.SolverStabilityMonitor()
        monitor.residual_explosion_threshold = 1.0
        
        # 正常残差
        metrics_normal = openfoam_runner.SolverMetrics(
            time=0.1, courant_mean=0.2, courant_max=0.5,
            residuals={'Ux': 1e-5, 'p': 1e-4}
        )
        event = monitor._check_residuals(metrics_normal)
        self.assertIsNone(event)
        
        # 爆炸残差
        metrics_explosion = openfoam_runner.SolverMetrics(
            time=0.1, courant_mean=0.2, courant_max=0.5,
            residuals={'Ux': 10.0, 'p': 1e-4}
        )
        event = monitor._check_residuals(metrics_explosion)
        self.assertIsNotNone(event)
        self.assertEqual(event.divergence_type, self_healing_agent.DivergenceType.RESIDUAL_EXPLOSION)
    
    def test_self_healing_controller_init(self):
        """测试自愈控制器初始化"""
        healer = self_healing_agent.SelfHealingController(self.case_path)
        self.assertEqual(healer.case_path, self.case_path)
        self.assertEqual(healer.max_attempts, 3)
        self.assertEqual(healer.healing_attempts, 0)
    
    def test_heal_courant_issue(self):
        """测试库朗数问题修复"""
        healer = self_healing_agent.SelfHealingController(self.case_path)
        
        # 模拟发散事件
        event = self_healing_agent.DivergenceEvent(
            timestamp="2024-01-01 00:00:00",
            divergence_type=self_healing_agent.DivergenceType.COURANT_EXCEEDED,
            severity="critical",
            description="库朗数超标",
            metrics_snapshot={},
            suggested_action="减小时间步长"
        )
        
        # 执行修复
        healed, message = healer._heal_courant_issue(event)
        self.assertTrue(healed)
        
        # 验证配置已修改
        control_dict = self.case_path / "system" / "controlDict"
        content = control_dict.read_text()
        self.assertIn("deltaT 0.005", content)  # 应该减半
        self.assertIn("startFrom latestTime", content)


class TestPhysicsValidationAgent(unittest.TestCase):
    """测试物理校验Agent"""
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_path = Path(self.temp_dir.name) / "test_case"
        self.case_path.mkdir()
        (self.case_path / "logs").mkdir()
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_validator_init(self):
        """测试校验器初始化"""
        validator = physics_validation_agent.PhysicsConsistencyValidator(self.case_path)
        self.assertEqual(validator.case_path, self.case_path)
        self.assertEqual(validator.mass_tolerance, 0.001)
    
    def test_mass_conservation_validation(self):
        """测试质量守恒验证"""
        validator = physics_validation_agent.PhysicsConsistencyValidator(self.case_path)
        
        # 测试通过的情况
        result = validator.validate_mass_conservation()
        self.assertIsNotNone(result)
        self.assertEqual(result.validation_type, physics_validation_agent.ValidationType.MASS_CONSERVATION)
        self.assertIn("误差", result.message)
    
    def test_energy_conservation_validation(self):
        """测试能量守恒验证"""
        validator = physics_validation_agent.PhysicsConsistencyValidator(self.case_path)
        
        result = validator.validate_energy_conservation()
        self.assertIsNotNone(result)
        self.assertEqual(result.validation_type, physics_validation_agent.ValidationType.ENERGY_CONSERVATION)
    
    def test_convergence_validation(self):
        """测试收敛性验证"""
        # 创建模拟日志
        log_content = """
Time = 0.5
Solving for Ux, Initial residual = 1.234e-07
Solving for Uy, Initial residual = 5.678e-08
Solving for p, Initial residual = 2.345e-07
"""
        (self.case_path / "logs" / "solver.log").write_text(log_content)
        
        validator = physics_validation_agent.PhysicsConsistencyValidator(self.case_path)
        result = validator.validate_convergence()
        
        self.assertEqual(result.validation_type, physics_validation_agent.ValidationType.CONVERGENCE_CHECK)
        # 应该通过，因为残差都很小
        self.assertTrue(result.passed)


class TestCriticAgent(unittest.TestCase):
    """测试审查者Agent"""
    
    def test_critic_init(self):
        """测试Critic Agent初始化"""
        c = critic_agent.CriticAgent(use_llm=False)
        self.assertIsNotNone(c.constitution_checker)
        self.assertFalse(c.use_llm)
    
    def test_constitution_check(self):
        """测试宪法规则检查"""
        c = critic_agent.CriticAgent(use_llm=False)
        
        # 测试低分辨率配置
        low_res_config = {
            "task_id": "test_001",
            "physics_type": "incompressible",
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
                "mesh_resolution": {"nx": 10, "ny": 10, "nz": 1}
            },
            "solver": {
                "name": "icoFoam",
                "endTime": 0.5,
                "deltaT": 0.01
            }
        }
        
        issues = c.constitution_checker.check_config(low_res_config)
        # 应该有网格数量问题
        mesh_issues = [i for i in issues if i.category == "mesh"]
        self.assertTrue(len(mesh_issues) > 0)
    
    def test_review_calculation(self):
        """测试评分计算"""
        c = critic_agent.CriticAgent(use_llm=False)
        
        # 好的配置
        good_config = {
            "task_id": "test_001",
            "physics_type": "incompressible",
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
                "mesh_resolution": {"nx": 50, "ny": 50, "nz": 1}
            },
            "solver": {
                "name": "icoFoam",
                "endTime": 0.5,
                "deltaT": 0.005
            },
            "boundary_conditions": {
                "inlet": {"type": "fixedValue"},
                "outlet": {"type": "zeroGradient"}
            }
        }
        
        report = c.review(good_config)
        self.assertGreater(report.score, 50)  # 应该及格
        self.assertIn(report.verdict, [critic_agent.ReviewVerdict.APPROVE, 
                                       critic_agent.ReviewVerdict.CONDITIONAL])


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_phase2_workflow(self):
        """测试阶段二完整工作流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = Path(tmpdir) / "test_case"
            case_path.mkdir()
            for d in ["0", "constant", "system", "logs"]:
                (case_path / d).mkdir()
            
            # 创建配置文件
            (case_path / "system" / "controlDict").write_text("deltaT 0.01;\n")
            (case_path / "system" / "fvSolution").write_text("PIMPLE{}\n")
            
            # 1. Critic审查
            config = {
                "task_id": "integration_test",
                "physics_type": "incompressible",
                "geometry": {
                    "mesh_resolution": {"nx": 50, "ny": 50, "nz": 1}
                },
                "solver": {"name": "icoFoam", "deltaT": 0.005}
            }
            
            critic = critic_agent.CriticAgent(use_llm=False)
            report = critic.review(config)
            self.assertIsNotNone(report)
            
            # 2. 网格质量检查
            mesh_checker = mesh_quality_agent.MeshQualityChecker(case_path)
            self.assertIsNotNone(mesh_checker)
            
            # 3. 物理校验器初始化
            validator = physics_validation_agent.PhysicsConsistencyValidator(case_path)
            self.assertIsNotNone(validator)
            
            # 4. 自愈控制器初始化
            healer = self_healing_agent.SelfHealingController(case_path)
            self.assertIsNotNone(healer)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestMeshQualityAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestSelfHealingAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestPhysicsValidationAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestCriticAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
