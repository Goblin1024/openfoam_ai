#!/usr/bin/env python3
"""
OpenFOAM AI Agent - 使用真实 LLM 的启动器

使用方法:
    # 使用环境变量中的 API Key
    python start_with_llm.py
    
    # 指定提供商
    python start_with_llm.py --provider kimi
    
    # 直接传入 API Key
    python start_with_llm.py --provider deepseek --api-key sk-xxx
"""

import sys
import os
import argparse
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[INFO] 已加载 .env 文件")
except ImportError:
    pass


def print_banner():
    """打印欢迎界面"""
    print("=" * 70)
    print("")
    print("              OpenFOAM AI Agent - 智能CFD仿真系统")
    print("                        [LLM 模式]")
    print("")
    print("         使用真实大语言模型进行自然语言建模仿真")
    print("")
    print("=" * 70)
    print()


def check_llm_available():
    """检查 LLM 适配器是否可用"""
    try:
        from llm_adapter import LLMFactory
        return True, LLMFactory.list_providers()
    except ImportError:
        return False, []


def main():
    parser = argparse.ArgumentParser(description='OpenFOAM AI Agent with LLM')
    parser.add_argument('--provider', type=str, default=None,
                       help='LLM提供商 (kimi/deepseek/openai/glm/minimax/aliyun)')
    parser.add_argument('--api-key', type=str, default=None,
                       help='API Key (如不指定则从环境变量读取)')
    parser.add_argument('--model', type=str, default=None,
                       help='模型名称 (可选)')
    parser.add_argument('--mock', action='store_true',
                       help='强制使用Mock模式')
    args = parser.parse_args()
    
    print_banner()
    
    # 检查 LLM 适配器
    llm_available, providers = check_llm_available()
    if not llm_available:
        print("[ERR] LLM 适配器未找到，请确保 llm_adapter.py 存在")
        print("[INFO] 切换到 Mock 模式...")
        args.mock = True
    else:
        print(f"[OK] 支持的 LLM 提供商: {', '.join(providers)}")
    
    # 确定提供商
    if args.mock:
        provider = "mock"
    elif args.provider:
        provider = args.provider
    else:
        provider = os.getenv("DEFAULT_LLM_PROVIDER", "kimi")
    
    print(f"[INFO] 使用提供商: {provider}")
    
    # 导入模块
    try:
        from prompt_engine import PromptEngine, ConfigRefiner
        from case_manager import CaseManager, create_cavity_case
        from critic_agent import CriticAgent
        print("[OK] 核心模块加载成功")
    except Exception as e:
        print(f"[ERR] 模块加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 初始化 PromptEngine
    try:
        if args.mock:
            engine = PromptEngine(mock_mode=True)
        else:
            engine = PromptEngine(
                provider=provider,
                api_key=args.api_key,
                model=args.model
            )
        
        if engine.mock_mode:
            print("[WARN] 当前运行在 Mock 模式（未使用真实 LLM）")
        else:
            print(f"[OK] 成功连接到 {provider} LLM")
    except Exception as e:
        print(f"[ERR] 初始化 LLM 失败: {e}")
        print("[INFO] 切换到 Mock 模式...")
        engine = PromptEngine(mock_mode=True)
    
    # 初始化其他组件
    case_manager = CaseManager("./my_cases")
    config_refiner = ConfigRefiner()
    critic = CriticAgent(use_llm=False)
    
    current_case = None
    current_config = None
    
    print("\n" + "=" * 70)
    print("系统就绪！请输入您的仿真需求")
    print("示例:")
    print("  - '创建一个二维方腔驱动流，雷诺数100'")
    print("  - '建立管道流动仿真，入口速度2m/s'")
    print("  - 'help' 查看帮助，'exit' 退出")
    print("=" * 70 + "\n")
    
    # 交互循环
    while True:
        try:
            user_input = input("> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "退出"]:
                print("\n感谢使用！再见！")
                break
            
            if user_input.lower() in ["help", "帮助", "?"]:
                print_help()
                continue
            
            # 创建算例
            if any(kw in user_input.lower() for kw in ["创建", "建立", "新建", "create", "setup"]):
                print("\n[AI] 正在解析您的需求...")
                
                # 使用 LLM 解析
                config = engine.natural_language_to_config(user_input)
                
                # 配置优化
                config = config_refiner.refine(config)
                
                # Critic 审查
                print("\n[CHK] 正在进行方案审查...")
                report = critic.review(config)
                
                print(f"\n[STAT] 方案评分: {report.score}/100")
                print(f"[INFO] 审查结论: {report.verdict.name}")
                
                if report.issues:
                    print("\n[WARN] 发现的问题:")
                    for issue in report.issues:
                        print(f"  - [{issue.severity}] {issue.description}")
                
                # 显示配置
                print("\n[INFO] 配置摘要:")
                print(f"  算例名称: {config.get('task_id', 'unnamed')}")
                print(f"  物理类型: {config.get('physics_type', 'unknown')}")
                print(f"  求解器: {config.get('solver', {}).get('name', 'unknown')}")
                
                geom = config.get('geometry', {})
                dims = geom.get('dimensions', {})
                res = geom.get('mesh_resolution', {})
                print(f"  几何尺寸: {dims.get('L', '?')} x {dims.get('W', '?')}")
                print(f"  网格分辨率: {res.get('nx', '?')} x {res.get('ny', '?')}")
                
                # 显示 LLM 解释
                if not engine.mock_mode:
                    print("\n[AI] 正在生成配置说明...")
                    explanation = engine.explain_config(config)
                    print(explanation)
                
                # 确认创建
                confirm = input("\n确认创建此算例? (y/n): ").strip().lower()
                if confirm in ["y", "yes", "是"]:
                    try:
                        case_name = config.get('task_id', 'case_' + str(hash(user_input) % 10000))
                        
                        # 创建算例
                        if 'cavity' in user_input.lower() or '方腔' in user_input:
                            case_path = create_cavity_case(case_manager, case_name)
                        else:
                            case_path = case_manager.create_case(case_name, config.get('physics_type'))
                        
                        current_case = case_name
                        current_config = config
                        
                        print(f"\n[OK] 算例创建成功!")
                        print(f"[DIR] 位置: {case_path}")
                        
                    except Exception as e:
                        print(f"\n[ERR] 创建失败: {e}")
                else:
                    print("\n[INFO] 已取消创建")
            
            # 其他命令...
            elif any(kw in user_input.lower() for kw in ["状态", "status", "查看"]):
                if current_case:
                    print(f"\n[STAT] 当前算例: {current_case}")
                else:
                    cases = case_manager.list_cases()
                    print(f"\n[DIR] 所有算例: {cases if cases else '无'}")
            
            else:
                print("\n[AI] 请输入 '创建'、'运行' 或 '状态' 等关键词")
                print("      输入 'help' 查看完整帮助")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n感谢使用！再见！")
            break
        except Exception as e:
            print(f"\n[ERR] 错误: {e}\n")


def print_help():
    """打印帮助"""
    print("""
[使用指南]

创建算例:
  - 创建一个二维方腔驱动流
  - 建立管道流动仿真，入口速度2m/s
  - 模拟圆柱绕流，直径0.1m

运行仿真:
  - 运行算例
  - 开始计算

查看状态:
  - 查看状态
  - 显示所有算例

其他命令:
  - help  显示帮助
  - exit  退出程序

支持的物理类型:
  - incompressible: 不可压流
  - heatTransfer: 传热问题
  - multiphase: 多相流
    """)


if __name__ == "__main__":
    main()
