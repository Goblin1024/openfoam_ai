#!/usr/bin/env python3
"""
Launch OpenFOAM AI Interactive GUI
"""

import sys
import os
import random
from pathlib import Path

# 加载 .env 配置文件
try:
    from dotenv import load_dotenv
    # 优先加载项目根目录的 .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[Config] 已加载环境配置: {env_path}")
    else:
        # 尝试模块级 .env
        env_path2 = Path(__file__).parent / "openfoam_ai" / ".env"
        if env_path2.exists():
            load_dotenv(env_path2)
            print(f"[Config] 已加载环境配置: {env_path2}")
except ImportError:
    pass

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "utils"))

def check_dependencies():
    """Check dependencies"""
    print("Checking dependencies...")
    
    try:
        import gradio
        print(f"  [OK] Gradio {gradio.__version__}")
    except ImportError:
        print("  [MISSING] Gradio not installed")
        print("  Installing Gradio...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio>=4.0.0", "-q"])
        print("  [OK] Gradio installed")
    
    try:
        import matplotlib
        print("  [OK] Matplotlib")
    except ImportError:
        print("  [MISSING] Matplotlib not installed")
        return False
    
    try:
        import numpy
        print("  [OK] NumPy")
    except ImportError:
        print("  [MISSING] NumPy not installed")
        return False
    
    return True

def find_free_port():
    """Find a free port"""
    import socket
    while True:
        port = random.randint(7860, 7900)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port

def main():
    print("="*60)
    print("OpenFOAM AI - Interactive GUI Launcher")
    print("="*60)
    print()
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies:")
        print("  pip install matplotlib numpy")
        return
    
    # Find free port
    port = find_free_port()
    print(f"\nUsing port: {port}")
    
    print()
    print("Starting GUI server...")
    print(f"The interface will open at: http://127.0.0.1:{port}")
    print()
    
    # Import and launch
    try:
        # 首先尝试使用新的重构界面
        try:
            from openfoam_ai.ui.gradio_interface import create_ui
            ui = create_ui()
            demo = ui.create_interface()
            print("✅ 使用新版多标签页界面")
        except Exception as e1:
            print(f"新版界面加载失败: {e1}")
            # 回退到旧版界面
            from interactive_gui import create_interface
            demo = create_interface()
            print("⚠️ 使用旧版界面")
        
        demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            share=False,
            show_error=True,
            quiet=False,
            inbrowser=True
        )
    except Exception as e:
        print(f"Error starting GUI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
