#!/usr/bin/env python3
"""
OpenFOAM AI Agent - 快速启动脚本
自动检测环境变量并使用第一个可用的 LLM
"""

import os
import sys
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

from llm_adapter import LLMFactory

def find_first_available_llm():
    """查找第一个可用的 LLM 配置"""
    env_map = {
        "kimi": "KIMI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "glm": "GLM_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "aliyun": "ALIYUN_API_KEY",
        "openai": "OPENAI_API_KEY"
    }
    
    # 首先检查 DEFAULT_LLM_PROVIDER
    default = os.getenv("DEFAULT_LLM_PROVIDER")
    if default:
        env_var = env_map.get(default.lower())
        if env_var and os.getenv(env_var):
            return default.lower(), os.getenv(env_var)
    
    # 按优先级查找
    for provider, env_var in env_map.items():
        api_key = os.getenv(env_var)
        if api_key:
            return provider, api_key
    
    return None, None


def main():
    print("=" * 60)
    print("OpenFOAM AI Agent - 快速启动")
    print("=" * 60)
    print()
    
    # 查找可用 LLM
    provider, api_key = find_first_available_llm()
    
    if provider:
        print(f"✓ 检测到 {provider.upper()} API Key")
        print(f"  正在启动 LLM 模式...")
        print()
        
        # 导入并启动
        try:
            from start_with_llm import main as start_main
            
            # 设置命令行参数
            sys.argv = ['start_with_llm.py', '--provider', provider]
            start_main()
            
        except Exception as e:
            print(f"✗ 启动失败: {e}")
            print("\n切换到 Mock 模式...")
            
            # 使用 Mock 模式启动
            sys.argv = ['start_with_llm.py', '--mock']
            from start_with_llm import main as start_main
            start_main()
    else:
        print("⚠ 未检测到任何 LLM API Key")
        print("\n支持的 API Key 环境变量:")
        print("  - KIMI_API_KEY (推荐)")
        print("  - DEEPSEEK_API_KEY")
        print("  - GLM_API_KEY")
        print("  - DOUBAO_API_KEY")
        print("  - MINIMAX_API_KEY")
        print("  - ALIYUN_API_KEY")
        print()
        print("选项:")
        print("  1. 设置环境变量后重新运行")
        print("  2. 使用 Mock 模式体验")
        print()
        
        choice = input("选择 (1/2): ").strip()
        
        if choice == "2":
            print("\n启动 Mock 模式...")
            sys.argv = ['start_with_llm.py', '--mock']
            from start_with_llm import main as start_main
            start_main()
        else:
            print("\n请设置 API Key 后重新运行:")
            print("  Windows: set KIMI_API_KEY=sk-your-key")
            print("  Linux/Mac: export KIMI_API_KEY=sk-your-key")


if __name__ == "__main__":
    main()
