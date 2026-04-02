#!/usr/bin/env python3
"""
测试 LLM API 连接
验证各提供商的 API Key 是否有效
"""

import os
import sys
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

from llm_adapter import LLMFactory, create_llm

def test_provider(provider: str, api_key: str, model: str = None):
    """测试单个提供商"""
    print(f"\n{'='*60}")
    print(f"测试 {provider.upper()}")
    print('='*60)
    
    try:
        # 创建 LLM 实例
        llm = LLMFactory.create(provider, api_key, model)
        print(f"✓ 创建 LLM 实例成功")
        print(f"  模型: {llm.model}")
        
        # 发送测试请求
        test_message = "你好，请用一句话介绍自己。"
        print(f"\n发送测试消息: '{test_message}'")
        
        response = llm.chat(
            message=test_message,
            system_prompt="你是一个有帮助的AI助手。",
            temperature=0.7
        )
        
        if response.success:
            print(f"✓ API 调用成功")
            print(f"  响应: {response.content[:100]}...")
            print(f"  Token使用: {response.usage}")
            return True
        else:
            print(f"✗ API 调用失败")
            print(f"  错误: {response.error}")
            return False
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def main():
    """主函数"""
    print("="*60)
    print("LLM API 连接测试工具")
    print("="*60)
    print("\n支持的提供商:")
    for provider in LLMFactory.list_providers():
        print(f"  - {provider}")
    
    # 检查环境变量
    print("\n" + "="*60)
    print("检查环境变量")
    print("="*60)
    
    env_vars = {
        "openai": "OPENAI_API_KEY",
        "kimi": "KIMI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "glm": "GLM_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "aliyun": "ALIYUN_API_KEY"
    }
    
    available_providers = []
    
    for provider, env_var in env_vars.items():
        api_key = os.getenv(env_var)
        if api_key:
            # 隐藏大部分 key 只显示前8位
            masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            print(f"✓ {provider:12s}: {env_var} 已设置 ({masked_key})")
            available_providers.append((provider, api_key))
        else:
            print(f"✗ {provider:12s}: {env_var} 未设置")
    
    if not available_providers:
        print("\n⚠ 警告: 没有检测到任何 API Key")
        print("请设置以下环境变量之一:")
        for env_var in env_vars.values():
            print(f"  export {env_var}=your_api_key")
        return
    
    # 测试每个可用的提供商
    print("\n" + "="*60)
    print("开始测试 API 连接")
    print("="*60)
    
    results = {}
    for provider, api_key in available_providers:
        success = test_provider(provider, api_key)
        results[provider] = success
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for provider, success in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{provider:15s}: {status}")
    
    # 推荐
    print("\n" + "="*60)
    print("使用建议")
    print("="*60)
    
    working = [p for p, s in results.items() if s]
    if working:
        print(f"推荐使用的提供商: {', '.join(working)}")
        print(f"\n启动命令:")
        print(f"  set DEFAULT_LLM_PROVIDER={working[0]}")
        print(f"  python start_openfoam_ai.py")
    else:
        print("没有可用的 LLM 提供商")
        print("请检查 API Key 是否正确设置")


if __name__ == "__main__":
    main()
