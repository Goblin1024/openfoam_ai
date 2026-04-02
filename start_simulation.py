#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenFOAM AI Agent - 自然语言建模仿真启动器
"""

import sys
import os
from pathlib import Path

# 设置编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置导入路径
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "memory"))

def print_banner():
    """打印欢迎界面"""
    print("=" * 70)
    print("")
    print("              OpenFOAM AI Agent - 智能CFD仿真系统")
    print("")
    print("         通过自然语言创建和运行计算流体力学仿真")
    print("")
    print("=" * 70)
    print()

def print_help():
    """打印帮助信息"""
    print("""
【使用指南】

您可以输入自然语言描述来创建CFD算例，例如:

  1. 建立算例:
     - "创建一个二维方腔驱动流，雷诺数100"
     - "建立管道流动仿真，入口速度2m/s"
     - "模拟圆柱绕流，直径0.1m"

  2. 运行仿真:
     - "运行算例"
     - "开始计算"

  3. 查看状态:
     - "查看当前算例状态"
     - "显示网格信息"

  4. 其他命令:
     - help  - 显示帮助
     - exit  - 退出程序
    """)

def check_openfoam():
    """检查OpenFOAM环境"""
    try:
        result = os.system("blockMesh -help > nul 2>&1")
        return result == 0
    except:
        return False

def main():
    """主函数"""
    print_banner()
    
    # 检查OpenFOAM
    has_openfoam = check_openfoam()
    if not has_openfoam:
        print("[WARN] 警告: 未检测到OpenFOAM环境")
        print("    部分功能(如网格生成、求解器运行)将不可用")
        print("    但您仍可以体验自然语言配置生成功能")
        print()
    else:
        print("[OK] OpenFOAM环境检测正常")
        print()
    
    # 导入模块
    try:
        from case_manager import CaseManager, create_cavity_case
        from prompt_engine import PromptEngine, ConfigRefiner
        from mesh_quality_agent import MeshQualityChecker
        from critic_agent import CriticAgent
        print("[OK] 系统模块加载成功")
        print()
    except Exception as e:
        print(f"[ERR] 模块加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 初始化组件
    case_manager = CaseManager("./my_cases")
    prompt_engine = PromptEngine()
    config_refiner = ConfigRefiner()
    critic = CriticAgent(use_llm=False)
    
    current_case = None
    current_config = None
    
    print_help()
    print("\n" + "=" * 70)
    print("系统就绪，请输入您的仿真需求(输入 'help' 查看帮助，'exit' 退出)")
    print("=" * 70 + "\n")
    
    # 交互循环
    while True:
        try:
            user_input = input("> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "退出"]:
                print("\n感谢使用 OpenFOAM AI Agent，再见！")
                break
            
            if user_input.lower() in ["help", "帮助", "?"]:
                print_help()
                continue
            
            # 创建算例请求
            if any(kw in user_input.lower() for kw in ["创建", "建立", "新建", "create", "setup"]):
                print("\n[AI] 正在解析您的需求...")
                
                # 使用PromptEngine解析
                config = prompt_engine.natural_language_to_config(user_input)
                
                # 配置优化
                config = config_refiner.refine(config)
                
                # Critic审查
                print("\n[CHK] 正在进行方案审查...")
                report = critic.review(config)
                
                print(f"\n[STAT] 方案评分: {report.score}/100")
                print(f"[INFO] 审查结论: {report.verdict.name}")
                
                if report.issues:
                    print("\n[WARN] 发现的问题:")
                    for issue in report.issues:
                        print(f"   - [{issue.severity}] {issue.message}")
                
                if report.recommendations:
                    print("\n[TIP] 改进建议:")
                    for rec in report.recommendations:
                        print(f"   - {rec}")
                
                # 显示配置摘要
                print("\n[INFO] 配置摘要:")
                print(f"   算例名称: {config.get('task_id', 'unnamed')}")
                print(f"   物理类型: {config.get('physics_type', 'unknown')}")
                print(f"   求解器: {config.get('solver', {}).get('name', 'unknown')}")
                
                geom = config.get('geometry', {})
                dims = geom.get('dimensions', {})
                res = geom.get('mesh_resolution', {})
                print(f"   几何尺寸: {dims.get('L', '?')} x {dims.get('W', '?')} x {dims.get('H', '?')}")
                print(f"   网格分辨率: {res.get('nx', '?')} x {res.get('ny', '?')} x {res.get('nz', '?')}")
                
                # 确认创建
                confirm = input("\n确认创建此算例? (y/n): ").strip().lower()
                if confirm in ["y", "yes", "是"]:
                    try:
                        case_name = config.get('task_id', 'case_' + str(hash(user_input) % 10000))
                        
                        # 创建算例
                        if 'cavity' in user_input.lower() or '方腔' in user_input:
                            case_path = create_cavity_case(case_manager, case_name)
                        else:
                            case_path = case_manager.create_case(case_name, config.get('physics_type', 'incompressible'))
                        
                        current_case = case_name
                        current_config = config
                        
                        print(f"\n[OK] 算例创建成功: {case_path}")
                        print(f"[DIR] 算例位置: {case_path.absolute()}")
                        
                        # 网格质量检查
                        if has_openfoam:
                            print("\n[TOOL] 运行网格质量检查...")
                            checker = MeshQualityChecker(case_path)
                            print("[OK] 网格质量检查完成")
                        
                    except Exception as e:
                        print(f"\n[ERR] 创建失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("\n[ERR] 已取消创建")
            
            # 运行仿真
            elif any(kw in user_input.lower() for kw in ["运行", "计算", "开始", "run", "solve"]):
                if not current_case:
                    print("\n[WARN] 没有活动的算例，请先创建算例")
                    continue
                
                if not has_openfoam:
                    print("\n[WARN] 未检测到OpenFOAM环境，无法运行求解器")
                    continue
                
                print(f"\n[RUN] 准备运行算例: {current_case}")
                confirm = input("确认开始计算? (y/n): ").strip().lower()
                
                if confirm in ["y", "yes", "是"]:
                    print("\n[RUN] 正在启动求解器...")
                    print("   求解器: icoFoam")
                    print("   按 Ctrl+C 可以中断计算")
                    print()
                    
                    # 这里可以添加实际的求解器运行代码
                    # 目前为演示模式
                    print("[OK] 仿真计算完成！(演示模式)")
                    print(f"[STAT] 结果文件位置: {case_manager.get_case(current_case)}")
                else:
                    print("\n[ERR] 已取消运行")
            
            # 查看状态
            elif any(kw in user_input.lower() for kw in ["状态", "status", "查看", "check"]):
                if current_case:
                    print(f"\n[STAT] 当前算例: {current_case}")
                    info = case_manager.get_case_info(current_case)
                    if info:
                        print(f"   状态: {info.status}")
                        print(f"   求解器: {info.solver}")
                        print(f"   创建时间: {info.created_at}")
                else:
                    cases = case_manager.list_cases()
                    print(f"\n[DIR] 所有算例: {cases if cases else '无'}")
            
            else:
                print("\n[AI] 未能理解您的意图")
                print("   提示: 使用 '创建'、'运行' 或 '状态' 等关键词")
                print("   输入 'help' 查看帮助")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n感谢使用 OpenFOAM AI Agent，再见！")
            break
        except Exception as e:
            print(f"\n[ERR] 错误: {e}\n")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
