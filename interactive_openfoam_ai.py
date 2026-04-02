#!/usr/bin/env python3
"""
OpenFOAM AI Agent - Interactive Mode
交互式智能对话模式 - 持续修改和优化仿真模型

Features:
- 自然语言创建算例
- 查看和修改现有算例
- AI 辅助优化建议
- 多轮对话迭代
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# ============================================================================
# Configuration
# ============================================================================
KIMI_API_KEY = "sk-Y4G2lAGkFIhUeLvfaQEi5RzOpYbupjhPtkbp0Cb0KQCS2Jnr"
CASES_DIR = "./interactive_cases"

# ============================================================================
# Setup Paths
# ============================================================================
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

from prompt_engine import PromptEngine, ConfigRefiner
from critic_agent import CriticAgent, ReviewVerdict
from case_manager import CaseManager, create_cavity_case

# ============================================================================
# Interactive Session Manager
# ============================================================================
class InteractiveSession:
    def __init__(self):
        self.engine = None
        self.case_manager = CaseManager(CASES_DIR)
        self.critic = CriticAgent(use_llm=False)
        self.refiner = ConfigRefiner()
        self.current_config: Optional[Dict] = None
        self.current_case_path: Optional[Path] = None
        self.history: list = []
        
    def initialize_llm(self) -> bool:
        """初始化 LLM"""
        try:
            self.engine = PromptEngine(
                provider="kimi",
                api_key=KIMI_API_KEY,
                model="moonshot-v1-8k"
            )
            if self.engine.mock_mode:
                print("[WARNING] Running in MOCK mode (no real LLM)")
                return False
            return True
        except Exception as e:
            print(f"[ERROR] Failed to initialize LLM: {e}")
            return False
    
    def print_banner(self):
        print("=" * 70)
        print("")
        print("     OpenFOAM AI Agent - Interactive Mode")
        print("              Powered by KIMI LLM")
        print("")
        print("=" * 70)
        print()
        print("Type 'help' for available commands")
        print()
    
    def print_help(self):
        print("\n" + "=" * 70)
        print("Available Commands:")
        print("=" * 70)
        print()
        print("  create <description>  - Create new case from description")
        print("  modify <instruction>  - Modify current case")
        print("  review                - Review current case with Critic")
        print("  optimize              - Get AI optimization suggestions")
        print("  show                  - Display current configuration")
        print("  files                 - List generated case files")
        print("  preview               - Generate visualization preview image")
        print("  export <name>         - Export current config to JSON")
        print("  import <name>         - Import config from JSON")
        print("  new                   - Clear current case and start new")
        print("  help                  - Show this help message")
        print("  exit / quit           - Exit the program")
        print()
        print("Examples:")
        print('  > create a 2D cavity flow with Re=100')
        print('  > modify increase mesh resolution to 100x100')
        print('  > optimize for better convergence')
        print()
    
    def cmd_create(self, description: str):
        """创建新算例"""
        if not description:
            print("[ERROR] Please provide a description")
            return
        
        print(f"\n[AI] Analyzing: '{description}'")
        print("[AI] Sending to KIMI LLM...")
        
        try:
            config = self.engine.natural_language_to_config(description)
            config = self.refiner.refine(config)
            
            self.current_config = config
            self.history.append({"action": "create", "description": description, "config": config.copy()})
            
            print(f"\n[OK] Configuration generated!")
            self._show_config_summary()
            
            # Ask if user wants to create files
            response = input("\nCreate case files? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                self._create_case_files()
            
        except Exception as e:
            print(f"[ERROR] Failed to create configuration: {e}")
    
    def cmd_modify(self, instruction: str):
        """修改当前算例"""
        if not self.current_config:
            print("[ERROR] No active case. Create one first with 'create'")
            return
        
        if not instruction:
            print("[ERROR] Please provide modification instruction")
            return
        
        print(f"\n[AI] Modifying based on: '{instruction}'")
        
        # Build context for LLM
        context = {
            "current_config": self.current_config,
            "modification_request": instruction
        }
        
        prompt = f"""You are modifying an existing OpenFOAM simulation configuration.

Current Configuration:
{json.dumps(self.current_config, indent=2, ensure_ascii=False)}

Modification Request: {instruction}

Please provide the COMPLETE updated configuration in JSON format with ALL fields.
Maintain the same structure but apply the requested changes.
"""
        
        try:
            # Use LLM to generate modified config
            config = self.engine.natural_language_to_config(prompt)
            config = self.refiner.refine(config)
            
            self.current_config = config
            self.history.append({"action": "modify", "instruction": instruction, "config": config.copy()})
            
            print(f"\n[OK] Configuration modified!")
            self._show_config_summary()
            
            # Ask if user wants to update files
            if self.current_case_path:
                response = input("\nUpdate case files? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    self._create_case_files()
            else:
                response = input("\nCreate case files? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    self._create_case_files()
                    
        except Exception as e:
            print(f"[ERROR] Failed to modify configuration: {e}")
    
    def cmd_review(self):
        """审查当前算例"""
        if not self.current_config:
            print("[ERROR] No active case to review")
            return
        
        print("\n[CRITIC] Reviewing configuration...")
        report = self.critic.review(self.current_config)
        
        print(f"\n{'='*70}")
        print(f"Review Score: {report.score}/100")
        print(f"Verdict: {report.verdict.name}")
        print(f"{'='*70}")
        
        if report.strengths:
            print(f"\n[Strengths] ({len(report.strengths)}):")
            for s in report.strengths:
                print(f"  + {s}")
        
        if report.issues:
            print(f"\n[Issues] ({len(report.issues)}):")
            for issue in report.issues:
                print(f"  - [{issue.severity}] {issue.description}")
                if issue.suggestion:
                    print(f"    Suggestion: {issue.suggestion}")
        
        if report.recommendations:
            print(f"\n[Recommendations]:")
            for rec in report.recommendations:
                print(f"  * {rec}")
    
    def cmd_optimize(self):
        """获取 AI 优化建议"""
        if not self.current_config:
            print("[ERROR] No active case to optimize")
            return
        
        print("\n[AI] Analyzing for optimization opportunities...")
        
        prompt = f"""As a CFD optimization expert, analyze this OpenFOAM configuration and provide specific optimization suggestions:

Current Configuration:
{json.dumps(self.current_config, indent=2, ensure_ascii=False)}

Please provide:
1. Performance optimization suggestions
2. Numerical stability improvements
3. Accuracy enhancements
4. Resource efficiency tips

Be specific with parameter values and settings."""
        
        try:
            # Get optimization suggestions from LLM
            response = self.engine.llm.chat(
                message=prompt,
                system_prompt="You are a CFD optimization expert. Provide practical, actionable advice.",
                temperature=0.5
            )
            
            if response.success:
                print(f"\n[AI] Optimization Suggestions:")
                print("-" * 70)
                print(response.content)
                print("-" * 70)
                
                # Ask if user wants to apply suggestions
                response = input("\nApply these optimizations? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    self.cmd_modify("Apply the optimization suggestions")
            else:
                print(f"[ERROR] Failed to get suggestions: {response.error}")
                
        except Exception as e:
            print(f"[ERROR] Optimization failed: {e}")
    
    def cmd_show(self):
        """显示当前配置"""
        if not self.current_config:
            print("[INFO] No active case")
            return
        
        print(f"\n{'='*70}")
        print("Current Configuration:")
        print(f"{'='*70}")
        print(json.dumps(self.current_config, indent=2, ensure_ascii=False))
    
    def cmd_files(self):
        """列出算例文件"""
        if not self.current_case_path:
            print("[INFO] No case files generated yet")
            return
        
        if not self.current_case_path.exists():
            print(f"[ERROR] Case path not found: {self.current_case_path}")
            return
        
        print(f"\nCase Files: {self.current_case_path}")
        print("-" * 50)
        
        for item in sorted(self.current_case_path.rglob("*")):
            rel_path = item.relative_to(self.current_case_path)
            if item.is_dir():
                print(f"  [{rel_path}/]")
            else:
                size = item.stat().st_size
                print(f"  {rel_path} ({size} bytes)")
    
    def cmd_preview(self):
        """生成并显示算例预览图"""
        if not self.current_case_path:
            print("[ERROR] No case to preview. Create a case first.")
            return
        
        print("\n[INFO] Generating visualization preview...")
        self._generate_visualization()
        
        # Show preview file info
        preview_file = self.current_case_path / "preview.png"
        if preview_file.exists():
            print(f"\n[OK] Preview saved to: {preview_file}")
            print(f"[INFO] File size: {preview_file.stat().st_size / 1024:.1f} KB")
            print("[INFO] Open this image to see:")
            print("       - Geometry & Mesh")
            print("       - Boundary Conditions")
            print("       - Initial Flow Field")
            print("       - Expected Results (e.g., Karman Vortex)")
    
    def cmd_export(self, name: str):
        """导出配置"""
        if not self.current_config:
            print("[ERROR] No configuration to export")
            return
        
        if not name:
            name = self.current_config.get('task_id', 'config')
        
        export_path = Path(CASES_DIR) / f"{name}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(self.current_config, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Configuration exported to: {export_path}")
    
    def cmd_import(self, name: str):
        """导入配置"""
        if not name:
            print("[ERROR] Please provide config name")
            return
        
        import_path = Path(CASES_DIR) / f"{name}.json"
        
        if not import_path.exists():
            print(f"[ERROR] Config file not found: {import_path}")
            return
        
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                self.current_config = json.load(f)
            
            self.history.append({"action": "import", "name": name, "config": self.current_config.copy()})
            print(f"[OK] Configuration imported from: {import_path}")
            self._show_config_summary()
            
        except Exception as e:
            print(f"[ERROR] Failed to import: {e}")
    
    def cmd_new(self):
        """新建算例"""
        self.current_config = None
        self.current_case_path = None
        print("[OK] Cleared current case. Ready for new simulation.")
    
    def _show_config_summary(self):
        """显示配置摘要"""
        if not self.current_config:
            return
        
        config = self.current_config
        print(f"\n{'='*70}")
        print("Configuration Summary:")
        print(f"{'='*70}")
        print(f"  Task ID:        {config.get('task_id', 'N/A')}")
        print(f"  Physics Type:   {config.get('physics_type', 'N/A')}")
        
        solver = config.get('solver', {})
        print(f"  Solver:         {solver.get('name', 'N/A')}")
        print(f"  End Time:       {solver.get('endTime', 'N/A')}")
        print(f"  Delta T:        {solver.get('deltaT', 'N/A')}")
        
        geometry = config.get('geometry', {})
        mesh = geometry.get('mesh_resolution', {})
        print(f"  Mesh:           {mesh.get('nx')} x {mesh.get('ny')} x {mesh.get('nz')}")
        
        bc_count = len(config.get('boundary_conditions', {}))
        print(f"  Boundary Conds: {bc_count}")
    
    def _create_case_files(self):
        """创建算例文件"""
        if not self.current_config:
            return
        
        case_name = self.current_config.get('task_id', 'case')
        
        try:
            self.current_case_path = create_cavity_case(self.case_manager, case_name)
            print(f"\n[OK] Case files created: {self.current_case_path}")
            
            # Count files
            files = list(self.current_case_path.glob("**/*"))
            file_count = len([f for f in files if f.is_file()])
            print(f"[OK] Total files: {file_count}")
            
            # 保存完整配置到 .case_info.json
            self._save_full_config()
            
            # 生成可视化预览
            self._generate_visualization()
            
        except Exception as e:
            print(f"[ERROR] Failed to create case files: {e}")
    
    def _save_full_config(self):
        """保存完整配置到 case_info.json"""
        if not self.current_case_path or not self.current_config:
            return
        
        try:
            info_file = self.current_case_path / ".case_info.json"
            
            # 合并现有信息和完整配置
            full_info = {
                "name": self.current_config.get('task_id', 'case'),
                "path": str(self.current_case_path.absolute()),
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "physics_type": self.current_config.get('physics_type', 'incompressible'),
                "solver": self.current_config.get('solver', {}),
                "geometry": self.current_config.get('geometry', {}),
                "boundary_conditions": self.current_config.get('boundary_conditions', {}),
                "nu": self.current_config.get('nu'),
                "status": "init"
            }
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(full_info, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] Configuration saved")
        except Exception as e:
            print(f"[WARNING] Could not save full config: {e}")
    
    def _generate_visualization(self):
        """生成算例可视化预览"""
        try:
            # 导入可视化工具
            sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "utils"))
            from case_visualizer import generate_preview
            
            if self.current_case_path:
                preview_path = generate_preview(self.current_case_path)
                print(f"[OK] Preview generated: {preview_path}")
                print(f"[INFO] Open this image to see geometry, mesh, and expected flow patterns")
        except Exception as e:
            print(f"[WARNING] Could not generate visualization: {e}")
            print("[INFO] Install matplotlib to enable visualization: pip install matplotlib")
    
    def run(self):
        """主循环"""
        self.print_banner()
        
        # Initialize LLM
        print("Initializing KIMI LLM...")
        if self.initialize_llm():
            print("[OK] KIMI LLM connected successfully!")
        else:
            print("[WARNING] Using MOCK mode (no real AI)")
        print()
        
        # Main loop
        while True:
            try:
                user_input = input("> ").strip()
                if not user_input:
                    continue
                
                # Parse command
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""
                
                # Check if it's a known command first
                known_commands = ["help", "create", "modify", "review", "optimize", 
                                  "show", "files", "export", "import", "new", "exit", "quit"]
                
                if cmd not in known_commands:
                    # Treat as create command with full input
                    self.cmd_create(user_input)
                    continue
                
                if cmd in ["exit", "quit"]:
                    print("\nGoodbye! Saving session history...")
                    break
                
                elif cmd == "help":
                    self.print_help()
                
                elif cmd == "create":
                    self.cmd_create(arg)
                
                elif cmd == "modify":
                    self.cmd_modify(arg)
                
                elif cmd == "review":
                    self.cmd_review()
                
                elif cmd == "optimize":
                    self.cmd_optimize()
                
                elif cmd == "show":
                    self.cmd_show()
                
                elif cmd == "files":
                    self.cmd_files()
                
                elif cmd == "preview":
                    self.cmd_preview()
                
                elif cmd == "export":
                    self.cmd_export(arg)
                
                elif cmd == "import":
                    self.cmd_import(arg)
                
                elif cmd == "new":
                    self.cmd_new()
                
                print()
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                print()

# ============================================================================
# Entry Point
# ============================================================================
if __name__ == "__main__":
    session = InteractiveSession()
    session.run()
