#!/usr/bin/env python3
"""
OpenFOAM AI Agent - 统一主入口

使用方式:
    python main.py                    # 默认运行阶段4功能（最新）
    python main.py --phase 1          # 运行阶段1：基础交互
    python main.py --phase 2          # 运行阶段2：AI自我修复
    python main.py --phase 3          # 运行阶段3：记忆性建模
    python main.py --phase 4          # 运行阶段4：多模态解析（默认）
    python main.py --list-phases      # 显示各阶段功能摘要
    
阶段1 参数:
    python main.py --phase 1 --demo             # 运行演示
    python main.py --phase 1 --case "描述"      # 直接创建算例

阶段2 参数:
    python main.py --phase 2 --demo    # 运行功能演示
    python main.py --phase 2 --test    # 运行单元测试

阶段3 参数:
    python main.py --phase 3 --demo    # 运行功能演示（默认）
    python main.py --phase 3 --cli     # 启动CLI交互模式
    python main.py --phase 3 --web     # 启动Web界面
    python main.py --phase 3 --test    # 运行测试

阶段4 参数:
    python main.py --phase 4 --demo      # 运行所有演示（默认）
    python main.py --phase 4 --geometry  # 几何图像解析演示
    python main.py --phase 4 --plot      # 自然语言绘图演示
    python main.py --phase 4 --script    # PyVista脚本生成演示
    python main.py --phase 4 --execute   # 绘图执行演示
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path

# 项目根目录
project_root = Path(__file__).parent.parent
openfoam_ai_dir = project_root / "openfoam_ai"


def print_banner():
    """打印欢迎信息"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              OpenFOAM AI Agent v1.0.0                        ║
║                                                              ║
║      基于大语言模型的自动化CFD仿真智能体系统                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_phases_info():
    """打印各阶段功能摘要"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    各阶段功能摘要                              ║
╠══════════════════════════════════════════════════════════════╣
║ 阶段1: 基础交互与算例创建                                       ║
║        - 交互式对话模式                                         ║
║        - 快速创建算例                                          ║
║        - 标准方腔驱动流演示                                     ║
╠══════════════════════════════════════════════════════════════╣
║ 阶段2: AI自我修复与验证                                        ║
║        - 网格质量自动检查与修复                                 ║
║        - 求解器稳定性实时监控                                   ║
║        - 发散自动检测与自愈                                     ║
║        - 物理一致性验证                                        ║
║        - Critic Agent审查                                      ║
╠══════════════════════════════════════════════════════════════╣
║ 阶段3: 记忆性建模与充分交互                                     ║
║        - MemoryManager: 算例配置的向量存储和检索                ║
║        - SessionManager: 多轮对话和上下文管理                   ║
║        - ConfigurationDiffer: 配置差异分析                     ║
║        - Gradio Web UI: 现代化Web界面                          ║
║        - CLI Interface: 增强版命令行界面                        ║
╠══════════════════════════════════════════════════════════════╣
║ 阶段4: 多模态解析与后处理（默认）                               ║
║        - 几何图像解析                                          ║
║        - 自然语言绘图生成                                      ║
║        - PyVista脚本生成                                       ║
║        - 高分辨率绘图输出                                      ║
╚══════════════════════════════════════════════════════════════╝

使用示例:
  python main.py --phase 1 --case "建立一个方腔驱动流"
  python main.py --phase 2 --demo
  python main.py --phase 3 --web
  python main.py --phase 4 --demo
    """)


def run_phase1(args):
    """运行阶段1：基础交互"""
    # 阶段1功能通过interactive_openfoam_ai.py提供
    if args.demo:
        print_banner()
        print("阶段1演示模式：创建标准方腔驱动流算例")
        print("请使用: python start_simulation.py 或 python interactive_openfoam_ai.py")
        return
    elif args.case:
        print_banner()
        print(f"阶段1快速创建: {args.case}")
        print("请使用: python interactive_openfoam_ai.py")
        return
    else:
        # 启动交互模式
        script_path = project_root / "interactive_openfoam_ai.py"
        if script_path.exists():
            subprocess.run([sys.executable, str(script_path)])
        else:
            print("错误: 找不到 interactive_openfoam_ai.py")
            print("请确保文件存在于项目根目录")


def run_phase2(args):
    """运行阶段2：AI自我修复"""
    print_banner()
    print("=" * 70)
    print("         OpenFOAM AI Agent v0.2.0 - Phase 2: AI Self-Correction")
    print("=" * 70)
    
    if args.test:
        print("\n运行阶段2测试...")
        test_file = openfoam_ai_dir / "tests" / "test_phase2.py"
        if test_file.exists():
            subprocess.run([sys.executable, str(test_file)])
        else:
            print(f"错误: 找不到测试文件 {test_file}")
    else:
        # 运行演示
        print("\n阶段2功能演示:")
        print("-" * 70)
        print("""
阶段2新增功能:
  [1] Mesh Quality Auto-Check & Fix
      - 网格质量自动检查与修复
      
  [2] Solver Stability Real-time Monitor
      - 求解器稳定性实时监控
      
  [3] Divergence Auto-Detection & Healing
      - 发散自动检测与自愈
      
  [4] Physics Consistency Validation
      - 物理一致性验证
      
  [5] Critic Agent Review
      - Critic Agent审查

相关模块:
  - agents/mesh_quality_agent.py
  - agents/self_healing_agent.py
  - agents/physics_validation_agent.py
  - agents/critic_agent.py

使用方式:
  from openfoam_ai.agents.mesh_quality_agent import MeshQualityChecker
  from openfoam_ai.agents.self_healing_agent import SelfHealingController
  from openfoam_ai.agents.physics_validation_agent import PhysicsConsistencyValidator
  from openfoam_ai.agents.critic_agent import CriticAgent
        """)
        print("-" * 70)


def run_phase3(args):
    """运行阶段3：记忆性建模"""
    print_banner()
    print("=" * 70)
    print(" OpenFOAM AI Agent - 阶段三: 记忆性建模与充分交互")
    print("=" * 70)
    
    if args.test:
        print("\n运行阶段3测试...")
        test_file = openfoam_ai_dir / "tests" / "test_phase3.py"
        if test_file.exists():
            subprocess.run([sys.executable, "-m", "pytest", str(test_file), "-v"])
        else:
            print(f"错误: 找不到测试文件 {test_file}")
    elif args.cli:
        print("\n启动CLI交互模式...")
        cli_script = openfoam_ai_dir / "ui" / "cli_interface.py"
        if cli_script.exists():
            subprocess.run([sys.executable, str(cli_script)])
        else:
            print(f"错误: 找不到CLI文件 {cli_script}")
    elif args.web:
        print("\n启动Web界面...")
        print("请使用: python launch_gui.py")
        print("或: python -m openfoam_ai.ui.gradio_interface")
    else:
        # 默认显示功能说明
        print("""
阶段3新增功能:
  [1] MemoryManager
      - 算例配置的向量存储和检索
      - 支持增量更新和相似性搜索
      
  [2] SessionManager
      - 多轮对话和上下文管理
      - 待确认操作和会话导出
      
  [3] ConfigurationDiffer
      - 配置差异分析
      - 自动变更摘要生成
      
  [4] Gradio Web UI
      - 现代化Web界面
      
  [5] CLI Interface
      - 增强版命令行界面

相关模块:
  - memory/memory_manager.py
  - memory/session_manager.py
  - ui/gradio_interface.py
  - ui/cli_interface.py

使用方式:
  from openfoam_ai.memory.memory_manager import MemoryManager
  from openfoam_ai.memory.session_manager import SessionManager
  from openfoam_ai.ui.gradio_interface import create_ui
  from openfoam_ai.ui.cli_interface import run_cli
        """)


def run_phase4(args):
    """运行阶段4：多模态解析"""
    print_banner()
    print("=" * 70)
    print(" OpenFOAM AI Agent - 阶段四: 多模态解析与后处理")
    print("=" * 70)
    
    if args.geometry:
        print("\n[演示] 几何图像解析")
        print("-" * 70)
        print("""
功能: GeometryImageParser
  - 从几何示意图中提取关键特征
  - 转换为结构化的OpenFOAM配置参数
  - 支持多种几何类型（矩形、圆形、管道等）

使用方式:
  from openfoam_ai.agents.geometry_image_agent import create_geometry_parser
  parser = create_geometry_parser(api_key=None)
  features = parser.parse_image("path/to/image.png")
        """)
    elif args.plot:
        print("\n[演示] 自然语言绘图生成")
        print("-" * 70)
        print("""
功能: PostProcessingAgent - 自然语言解析
  - 将自然语言描述转换为绘图请求
  - 支持多种绘图类型（云图、流线图、矢量图等）

使用方式:
  from openfoam_ai.agents.postprocessing_agent import create_postprocessing_agent
  agent = create_postprocessing_agent(case_path)
  request = agent.parse_natural_language("Plot velocity contour at center slice")
        """)
    elif args.script:
        print("\n[演示] PyVista脚本生成")
        print("-" * 70)
        print("""
功能: PostProcessingAgent - 脚本生成
  - 自动生成PyVista可视化脚本
  - 支持多种输出格式（PNG、PDF、SVG等）

使用方式:
  from openfoam_ai.agents.postprocessing_agent import PlotRequest, PlotType
  request = PlotRequest(plot_type=PlotType.CONTOUR, field_name="U")
  script = agent.generate_pyvista_script(request, "output.py")
        """)
    elif args.execute:
        print("\n[演示] 绘图执行")
        print("-" * 70)
        print("""
功能: PostProcessingAgent - 绘图执行
  - 执行绘图生成
  - 输出高分辨率图像

使用方式:
  result = agent.execute_plot(request, output_dir="./plots")
  if result.success:
      print(f"绘图已保存: {result.output_path}")
        """)
    else:
        # 默认显示所有功能
        print("""
阶段4新增功能:
  [1] Geometry Image Parser
      - 几何图像解析
      - 从示意图提取OpenFOAM配置
      
  [2] Natural Language Plot Generation
      - 自然语言绘图生成
      - 支持云图、流线图、矢量图等
      
  [3] PyVista Script Generation
      - PyVista脚本自动生成
      - 支持多种输出格式
      
  [4] High-Resolution Plot Output
      - 高分辨率绘图输出

相关模块:
  - agents/geometry_image_agent.py
  - agents/postprocessing_agent.py

使用方式:
  from openfoam_ai.agents.geometry_image_agent import create_geometry_parser
  from openfoam_ai.agents.postprocessing_agent import create_postprocessing_agent

子命令:
  --geometry  # 几何图像解析演示
  --plot      # 自然语言绘图演示
  --script    # PyVista脚本生成演示
  --execute   # 绘图执行演示
        """)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OpenFOAM AI Agent - 自动化CFD仿真",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --list-phases              # 显示各阶段功能摘要
  python main.py --phase 1                  # 阶段1：交互模式
  python main.py --phase 1 --demo           # 阶段1：运行演示
  python main.py --phase 1 --case "描述"    # 阶段1：快速创建算例
  python main.py --phase 2 --demo           # 阶段2：AI自我修复演示
  python main.py --phase 2 --test           # 阶段2：运行测试
  python main.py --phase 3 --cli            # 阶段3：启动CLI交互
  python main.py --phase 3 --web            # 阶段3：启动Web界面
  python main.py --phase 4 --demo           # 阶段4：多模态解析演示（默认）
        """
    )
    
    # 阶段选择
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=4,
        help="选择运行阶段 (1-4)，默认为4（最新阶段）"
    )
    
    # 阶段1参数
    parser.add_argument(
        "--demo", 
        action="store_true",
        help="运行演示模式"
    )
    parser.add_argument(
        "--case",
        type=str,
        metavar="DESCRIPTION",
        help="直接创建算例（描述字符串，阶段1使用）"
    )
    
    # 阶段2参数
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行单元测试（阶段2、3使用）"
    )
    
    # 阶段3参数
    parser.add_argument(
        "--cli",
        action="store_true",
        help="启动CLI交互模式（阶段3使用）"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动Web界面（阶段3使用）"
    )
    
    # 阶段4参数
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="几何图像解析演示（阶段4使用）"
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="自然语言绘图演示（阶段4使用）"
    )
    parser.add_argument(
        "--script",
        action="store_true",
        help="PyVista脚本生成演示（阶段4使用）"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="绘图执行演示（阶段4使用）"
    )
    
    # 帮助选项
    parser.add_argument(
        "--list-phases",
        action="store_true",
        help="显示各阶段功能摘要"
    )
    
    args = parser.parse_args()
    
    # 显示阶段信息
    if args.list_phases:
        print_phases_info()
        return
    
    # 检查OpenFOAM环境（仅阶段1需要）
    if args.phase == 1:
        try:
            result = os.system("blockMesh -help > nul 2>&1")
            if result != 0:
                print("⚠️ 警告: 未检测到OpenFOAM环境")
                print("   某些功能可能无法使用")
                print("   请确保OpenFOAM已安装并添加到PATH\n")
        except:
            pass
    
    # 根据阶段执行
    if args.phase == 1:
        run_phase1(args)
    elif args.phase == 2:
        run_phase2(args)
    elif args.phase == 3:
        run_phase3(args)
    elif args.phase == 4:
        run_phase4(args)


if __name__ == "__main__":
    main()
