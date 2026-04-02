# Phase 4 Unit Tests

import unittest
import tempfile
import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# 直接导入具体模块，避免__init__.py的循环导入
sys.path.insert(0, str(project_root / "agents"))
sys.path.insert(0, str(project_root / "core"))

# 导入阶段四模块
import geometry_image_agent
import postprocessing_agent


class TestGeometryImageParser(unittest.TestCase):
    def setUp(self):
        self.parser = geometry_image_agent.create_geometry_parser(api_key=None)
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parser_initialization(self):
        self.assertIsNotNone(self.parser)
        self.assertTrue(self.parser.mock_mode)
        print("[OK] GeometryImageParser initialized")

    def test_parse_cavity_mock(self):
        test_image = self.temp_dir / "test_cavity.png"
        test_image.write_text("fake")
        features = self.parser.parse_image(str(test_image))
        self.assertIsInstance(features, geometry_image_agent.GeometryFeatures)
        self.assertEqual(features.geometry_type, geometry_image_agent.GeometryType.CAVITY)
        print("[OK] Cavity geometry parsed")

    def test_parse_pipe_mock(self):
        test_image = self.temp_dir / "test_pipe.png"
        test_image.write_text("fake")
        features = self.parser.parse_image(str(test_image))
        self.assertIsInstance(features, geometry_image_agent.GeometryFeatures)
        self.assertEqual(features.geometry_type, geometry_image_agent.GeometryType.PIPE)
        print("[OK] Pipe geometry parsed")

    def test_convert_to_config(self):
        """测试将几何特征转换为仿真配置"""
        test_image = self.temp_dir / "test_cavity.png"
        test_image.write_text("fake")
        features = self.parser.parse_image(str(test_image))
        
        # 转换为配置
        config = self.parser.convert_to_simulation_config(features)
        
        # 返回的是SimulationConfig对象，检查关键属性
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.geometry)
        self.assertIsNotNone(config.solver)
        print("[OK] Converted to simulation config")


class TestPostProcessingAgent(unittest.TestCase):
    def setUp(self):
        self.agent = postprocessing_agent.create_postprocessing_agent()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_agent_initialization(self):
        self.assertIsNotNone(self.agent)
        self.assertIsNotNone(self.agent.script_generator)
        print("[OK] PostProcessingAgent initialized")

    def test_parse_contour_request(self):
        request = self.agent.parse_natural_language("生成速度云图")
        self.assertEqual(request.plot_type, postprocessing_agent.PlotType.CONTOUR)
        self.assertEqual(request.field, "U")
        print("[OK] Contour request parsed")

    def test_parse_streamline_request(self):
        request = self.agent.parse_natural_language("绘制流线")
        self.assertEqual(request.plot_type, postprocessing_agent.PlotType.STREAMLINE)
        print("[OK] Streamline request parsed")

    def test_parse_with_time_and_format(self):
        request = self.agent.parse_natural_language("导出压力分布PDF，时间0.5秒")
        self.assertEqual(request.field, "p")
        self.assertEqual(request.output_format, postprocessing_agent.OutputFormat.PDF)
        self.assertEqual(request.time_value, 0.5)
        print("[OK] Complex request parsed")

    def test_generate_pyvista_script(self):
        script_path = self.temp_dir / "generated_script.py"
        request = postprocessing_agent.PlotRequest(
            plot_type=postprocessing_agent.PlotType.CONTOUR,
            field="U",
            output_path=str(self.temp_dir / "output.png"),
            output_format=postprocessing_agent.OutputFormat.PNG
        )
        
        script = self.agent.generate_pyvista_script(request, str(script_path))
        self.assertIn("pyvista", script)
        self.assertIn("U", script)
        print("[OK] PyVista script generated")

    def test_execute_plot_mock(self):
        request = postprocessing_agent.PlotRequest(
            plot_type=postprocessing_agent.PlotType.CONTOUR,
            field="p",
            output_path=str(self.temp_dir / "test_output.png"),
            output_format=postprocessing_agent.OutputFormat.PNG
        )
        
        # Mock模式执行
        result = self.agent.execute_plot(request, "/fake/case/path")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.output_file)
        self.assertIsNotNone(result.script_file)
        print("[OK] Plot executed in mock mode")


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # 1. 解析几何图像
            parser = geometry_image_agent.create_geometry_parser(api_key=None)
            test_image = temp_dir / "geometry.png"
            test_image.write_text("fake")
            
            features = parser.parse_image(str(test_image))
            self.assertIsNotNone(features)
            
            # 2. 转换为配置
            config = parser.convert_to_simulation_config(features)
            self.assertIsNotNone(config)
            
            # 3. 创建后处理Agent并生成绘图
            agent = postprocessing_agent.create_postprocessing_agent()
            request = agent.parse_natural_language("生成速度矢量图")
            
            self.assertEqual(request.plot_type, postprocessing_agent.PlotType.VECTOR)
            
            print("[OK] Full workflow test passed")
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestGeometryImageParser))
    suite.addTests(loader.loadTestsFromTestCase(TestPostProcessingAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
