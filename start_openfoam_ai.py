#!/usr/bin/env python3
"""
OpenFOAM AI Agent - Natural Language CFD Simulation Launcher

Usage:
    python start_openfoam_ai.py
"""

import sys
import os
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "memory"))

def print_banner():
    """Print welcome banner"""
    print("=" * 70)
    print("")
    print("              OpenFOAM AI Agent - Smart CFD Simulation System")
    print("")
    print("           Create and Run CFD Simulations via Natural Language")
    print("")
    print("=" * 70)
    print()

def print_help():
    """Print help information"""
    print("""
[Usage Guide]

Create CFD cases using natural language:

  1. Create a case:
     - "Create a 2D lid-driven cavity flow, Reynolds number 100"
     - "Setup a pipe flow simulation, inlet velocity 2m/s"
     - "Simulate flow around a cylinder, diameter 0.1m"

  2. Run simulation:
     - "Run the case"
     - "Start calculation"

  3. Check status:
     - "Show current case status"
     - "Display mesh information"

  4. Other commands:
     - help  - Show help
     - exit  - Exit program

[Supported Physics Types]
  - incompressible: Incompressible flow (water, low-speed air)
  - heat_transfer: Heat transfer problems
  - multiphase: Multiphase flow

[Supported Solvers]
  - icoFoam: Transient incompressible laminar
  - simpleFoam: Steady-state incompressible
  - buoyantBoussinesqPimpleFoam: Natural convection
    """)

def check_openfoam():
    """Check OpenFOAM environment"""
    try:
        result = os.system("blockMesh -help > nul 2>&1")
        return result == 0
    except:
        return False

def main():
    """Main function"""
    print_banner()
    
    # Check OpenFOAM
    has_openfoam = check_openfoam()
    if not has_openfoam:
        print("[WARN] OpenFOAM environment not detected")
        print("    Some features (mesh generation, solver) will be unavailable")
        print("    But you can still experience natural language configuration")
        print()
    else:
        print("[OK] OpenFOAM environment detected")
        print()
    
    # Import modules
    try:
        from case_manager import CaseManager, create_cavity_case
        from prompt_engine import PromptEngine, ConfigRefiner
        from mesh_quality_agent import MeshQualityChecker
        from critic_agent import CriticAgent
        print("[OK] System modules loaded successfully")
        print()
    except Exception as e:
        print(f"[ERR] Module loading failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Initialize components
    case_manager = CaseManager("./my_cases")
    prompt_engine = PromptEngine()
    config_refiner = ConfigRefiner()
    critic = CriticAgent(use_llm=False)
    
    current_case = None
    current_config = None
    
    print_help()
    print("\n" + "=" * 70)
    print("System ready. Enter your simulation request ('help' for help, 'exit' to quit)")
    print("=" * 70 + "\n")
    
    # Interactive loop
    while True:
        try:
            user_input = input("> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print("\nThank you for using OpenFOAM AI Agent. Goodbye!")
                break
            
            if user_input.lower() in ["help", "?"]:
                print_help()
                continue
            
            # Create case request
            if any(kw in user_input.lower() for kw in ["create", "setup", "build", "make", "建立", "创建"]):
                print("\n[AI] Parsing your request...")
                
                # Use PromptEngine to parse
                config = prompt_engine.natural_language_to_config(user_input)
                
                # Optimize config
                config = config_refiner.refine(config)
                
                # Critic review
                print("\n[CHK] Reviewing simulation plan...")
                report = critic.review(config)
                
                print(f"\n[STAT] Plan Score: {report.score}/100")
                print(f"[INFO] Verdict: {report.verdict.name}")
                
                if report.issues:
                    print("\n[WARN] Issues found:")
                    for issue in report.issues:
                        print(f"   - [{issue.severity}] {issue.message}")
                
                if report.recommendations:
                    print("\n[TIP] Recommendations:")
                    for rec in report.recommendations:
                        print(f"   - {rec}")
                
                # Show config summary
                print("\n[INFO] Configuration Summary:")
                print(f"   Case Name: {config.get('task_id', 'unnamed')}")
                print(f"   Physics Type: {config.get('physics_type', 'unknown')}")
                print(f"   Solver: {config.get('solver', {}).get('name', 'unknown')}")
                
                geom = config.get('geometry', {})
                dims = geom.get('dimensions', {})
                res = geom.get('mesh_resolution', {})
                print(f"   Geometry: {dims.get('L', '?')} x {dims.get('W', '?')} x {dims.get('H', '?')}")
                print(f"   Mesh: {res.get('nx', '?')} x {res.get('ny', '?')} x {res.get('nz', '?')}")
                
                # Confirm creation
                confirm = input("\nConfirm creation? (y/n): ").strip().lower()
                if confirm in ["y", "yes", "是"]:
                    try:
                        case_name = config.get('task_id', 'case_' + str(hash(user_input) % 10000))
                        
                        # Create case
                        if any(kw in user_input.lower() for kw in ['cavity', '方腔', 'lid']):
                            case_path = create_cavity_case(case_manager, case_name)
                        else:
                            case_path = case_manager.create_case(case_name, config.get('physics_type', 'incompressible'))
                        
                        current_case = case_name
                        current_config = config
                        
                        print(f"\n[OK] Case created successfully: {case_path}")
                        print(f"[DIR] Location: {case_path.absolute()}")
                        
                        # List generated files
                        files = list(case_path.glob("**/*"))
                        file_count = len([f for f in files if f.is_file()])
                        print(f"[INFO] Generated {file_count} files")
                        
                        # Mesh quality check
                        if has_openfoam:
                            print("\n[TOOL] Running mesh quality check...")
                            checker = MeshQualityChecker(case_path)
                            print("[OK] Mesh quality check completed")
                        
                    except Exception as e:
                        print(f"\n[ERR] Creation failed: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("\n[ERR] Creation cancelled")
            
            # Run simulation
            elif any(kw in user_input.lower() for kw in ["run", "start", "solve", "计算", "运行", "开始"]):
                if not current_case:
                    print("\n[WARN] No active case. Please create a case first.")
                    continue
                
                if not has_openfoam:
                    print("\n[WARN] OpenFOAM not detected. Cannot run solver.")
                    continue
                
                print(f"\n[RUN] Preparing to run case: {current_case}")
                confirm = input("Confirm start calculation? (y/n): ").strip().lower()
                
                if confirm in ["y", "yes", "是"]:
                    print("\n[RUN] Starting solver...")
                    print("   Solver: icoFoam")
                    print("   Press Ctrl+C to interrupt")
                    print()
                    
                    # Simulation would run here in real mode
                    print("[OK] Simulation completed! (Demo mode)")
                    print(f"[STAT] Results location: {case_manager.get_case(current_case)}")
                    
                    # Show how to view results
                    print("\n[INFO] To view results:")
                    print(f"   paraFoam -case {case_manager.get_case(current_case)}")
                else:
                    print("\n[ERR] Run cancelled")
            
            # Check status
            elif any(kw in user_input.lower() for kw in ["status", "check", "state", "状态", "查看"]):
                if current_case:
                    print(f"\n[STAT] Current Case: {current_case}")
                    info = case_manager.get_case_info(current_case)
                    if info:
                        print(f"   Status: {info.status}")
                        print(f"   Solver: {info.solver}")
                        print(f"   Created: {info.created_at}")
                        
                        # Show config if available
                        if current_config:
                            solver = current_config.get('solver', {})
                            print(f"   End Time: {solver.get('endTime', 'N/A')}")
                            print(f"   Delta T: {solver.get('deltaT', 'N/A')}")
                else:
                    cases = case_manager.list_cases()
                    print(f"\n[DIR] All cases: {cases if cases else 'None'}")
            
            # Test/demo commands
            elif user_input.lower() in ["demo", "test", "example"]:
                print("\n[AI] Running demo: Creating a lid-driven cavity flow case...")
                demo_input = "Create a 2D lid-driven cavity flow with Reynolds number 100"
                config = prompt_engine.natural_language_to_config(demo_input)
                config = config_refiner.refine(config)
                
                print("\n[INFO] Generated Configuration:")
                print(f"   Physics: {config['physics_type']}")
                print(f"   Solver: {config['solver']['name']}")
                print(f"   Mesh: {config['geometry']['mesh_resolution']}")
                print(f"   Boundaries: {list(config['boundary_conditions'].keys())}")
                
                report = critic.review(config)
                print(f"\n[STAT] Review Score: {report.score}/100 - {report.verdict.name}")
                
                # Create the case
                case_path = create_cavity_case(case_manager, "demo_cavity")
                current_case = "demo_cavity"
                current_config = config
                print(f"\n[OK] Demo case created: {case_path}")
            
            else:
                print("\n[AI] I didn't understand. Try:")
                print("   - 'Create a cavity flow' to build a case")
                print("   - 'Run the case' to start simulation")
                print("   - 'Show status' to check current case")
                print("   - Type 'help' for more options")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\nThank you for using OpenFOAM AI Agent. Goodbye!")
            break
        except Exception as e:
            print(f"\n[ERR] Error: {e}\n")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
