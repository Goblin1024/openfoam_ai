#!/usr/bin/env python3
"""
简化测试脚本 - 适用于Python 3.14+
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_basic():
    """基础测试"""
    print("="*50)
    print("OpenFOAM AI Agent - 基础验证")
    print("="*50)
    
    # 测试1: 直接读取执行核心模块
    print("\n[1] 验证核心模块...")
    try:
        with open('openfoam_ai/core/case_manager.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ case_manager.py 语法正确")
    except Exception as e:
        print(f"  ✗ case_manager.py 错误: {e}")
        return False
    
    try:
        with open('openfoam_ai/core/validators.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ validators.py 语法正确")
    except Exception as e:
        print(f"  ✗ validators.py 错误: {e}")
        return False
    
    try:
        with open('openfoam_ai/core/file_generator.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ file_generator.py 语法正确")
    except Exception as e:
        print(f"  ✗ file_generator.py 错误: {e}")
        return False
    
    try:
        with open('openfoam_ai/core/openfoam_runner.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ openfoam_runner.py 语法正确")
    except Exception as e:
        print(f"  ✗ openfoam_runner.py 错误: {e}")
        return False
    
    # 测试2: 验证Agent模块
    print("\n[2] 验证Agent模块...")
    try:
        with open('openfoam_ai/agents/prompt_engine.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ prompt_engine.py 语法正确")
    except Exception as e:
        print(f"  ✗ prompt_engine.py 错误: {e}")
        return False
    
    try:
        with open('openfoam_ai/agents/manager_agent.py', 'r', encoding='utf-8') as f:
            source = f.read()
        exec(source, {'__name__': '__test__'})
        print("  ✓ manager_agent.py 语法正确")
    except Exception as e:
        print(f"  ✗ manager_agent.py 错误: {e}")
        return False
    
    # 测试3: 验证文件结构
    print("\n[3] 验证项目结构...")
    required_files = [
        'openfoam_ai/main.py',
        'openfoam_ai/requirements.txt',
        'openfoam_ai/README.md',
        'openfoam_ai/config/system_constitution.yaml',
        'openfoam_ai/docker/Dockerfile',
        'openfoam_ai/docker/docker-compose.yml',
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} 缺失")
            return False
    
    print("\n" + "="*50)
    print("所有基础验证通过!")
    print("="*50)
    print("\n项目结构:")
    print("  openfoam_ai/")
    print("  ├── agents/          # Agent模块")
    print("  ├── core/            # 核心功能")
    print("  ├── models/          # 物理模型")
    print("  ├── memory/          # 记忆管理")
    print("  ├── config/          # 配置文件")
    print("  ├── docker/          # Docker配置")
    print("  ├── tests/           # 测试")
    print("  ├── main.py          # 主入口")
    print("  └── requirements.txt # 依赖")
    
    return True

if __name__ == "__main__":
    success = test_basic()
    sys.exit(0 if success else 1)
