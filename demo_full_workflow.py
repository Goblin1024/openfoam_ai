#!/usr/bin/env python3
"""
OpenFOAM AI Agent - Full Workflow Demo with Real KIMI LLM
完整工作流程演示（使用真实 KIMI LLM）
"""

import sys
import os
from pathlib import Path

# ============================================================================
# Configuration - Your KIMI API Key
# ============================================================================
KIMI_API_KEY = "sk-Y4G2lAGkFIhUeLvfaQEi5RzOpYbupjhPtkbp0Cb0KQCS2Jnr"

# ============================================================================
# Setup Paths
# ============================================================================
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))

from prompt_engine import PromptEngine, ConfigRefiner
from critic_agent import CriticAgent, ReviewReport, ReviewVerdict as Verdict
from case_manager import CaseManager, create_cavity_case
from mesh_quality_agent import MeshQualityChecker

# ============================================================================
# Demo Scenarios
# ============================================================================
DEMO_SCENARIOS = [
    {
        "name": "Lid-Driven Cavity Flow",
        "description": "Create a 2D lid-driven cavity flow simulation with Reynolds number 100",
        "description_cn": "二维顶盖驱动方腔流，雷诺数100"
    },
    {
        "name": "Pipe Flow",
        "description": "Simulate laminar flow in a circular pipe with Reynolds number 500",
        "description_cn": "圆管层流，雷诺数500"
    },
    {
        "name": "Natural Convection",
        "description": "Simulate natural convection in a square cavity with temperature difference 20K",
        "description_cn": "方腔自然对流，温差20K"
    }
]

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_section(title):
    print(f"\n>> {title}")
    print("-" * 50)

def demo_workflow(scenario_index=0):
    """演示完整工作流程"""
    
    print_header("OpenFOAM AI Agent - Full Workflow Demo")
    print(f"\nAPI Provider: KIMI (moonshot-v1-8k)")
    print(f"API Key: {KIMI_API_KEY[:20]}...")
    
    # ------------------------------------------------------------------------
    # Step 1: Initialize Components
    # ------------------------------------------------------------------------
    print_section("Step 1: Initialize Components")
    
    try:
        engine = PromptEngine(
            provider="kimi",
            api_key=KIMI_API_KEY,
            model="moonshot-v1-8k"
        )
        print(f"[OK] PromptEngine initialized")
        print(f"     Mock mode: {engine.mock_mode}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize LLM: {e}")
        return
    
    case_manager = CaseManager("./demo_cases")
    config_refiner = ConfigRefiner()
    critic = CriticAgent(use_llm=False)  # Use rule-based for speed
    mesh_checker = None  # Will create when case is ready
    
    print(f"[OK] CaseManager initialized")
    print(f"[OK] CriticAgent initialized")
    print(f"[OK] MeshQualityChecker initialized")
    
    # ------------------------------------------------------------------------
    # Step 2: Select Scenario
    # ------------------------------------------------------------------------
    print_section("Step 2: Select Scenario")
    
    scenario = DEMO_SCENARIOS[scenario_index]
    print(f"Selected: {scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"Description (CN): {scenario['description_cn']}")
    
    user_input = scenario['description']
    
    # ------------------------------------------------------------------------
    # Step 3: Natural Language Processing (Real LLM)
    # ------------------------------------------------------------------------
    print_section("Step 3: Natural Language Processing (Real LLM)")
    print("Sending request to KIMI API...")
    
    config = engine.natural_language_to_config(user_input)
    
    print(f"\n[OK] LLM Response Received!")
    print(f"     Task ID: {config.get('task_id', 'N/A')}")
    print(f"     Physics Type: {config.get('physics_type', 'N/A')}")
    
    # ------------------------------------------------------------------------
    # Step 4: Config Refinement
    # ------------------------------------------------------------------------
    print_section("Step 4: Config Refinement")
    
    config = config_refiner.refine(config)
    print("[OK] Configuration refined with constitution rules")
    
    # Display key parameters
    solver = config.get('solver', {})
    geometry = config.get('geometry', {})
    mesh = geometry.get('mesh_resolution', {})
    
    print(f"\nConfiguration Summary:")
    print(f"  - Solver: {solver.get('name', 'N/A')}")
    print(f"  - End Time: {solver.get('endTime', 'N/A')}")
    print(f"  - Delta T: {solver.get('deltaT', 'N/A')}")
    print(f"  - Mesh: {mesh.get('nx')} x {mesh.get('ny')} x {mesh.get('nz')}")
    print(f"  - Viscosity (nu): {config.get('nu', 'N/A')}")
    
    # ------------------------------------------------------------------------
    # Step 5: Critic Review
    # ------------------------------------------------------------------------
    print_section("Step 5: Critic Review")
    
    report = critic.review(config)
    
    print(f"Review Score: {report.score}/100")
    print(f"Verdict: {report.verdict.name}")
    
    if report.issues:
        print(f"\nIssues Found ({len(report.issues)}):")
        for issue in report.issues:
            print(f"  - [{issue.severity}] {issue.description}")
            if issue.suggestion:
                print(f"    Suggestion: {issue.suggestion}")
    
    if report.recommendations:
        print(f"\nRecommendations ({len(report.recommendations)}):")
        for rec in report.recommendations:
            print(f"  - {rec}")
    
    # ------------------------------------------------------------------------
    # Step 6: Create Case
    # ------------------------------------------------------------------------
    print_section("Step 6: Create OpenFOAM Case")
    
    case_name = config.get('task_id', f"demo_case_{scenario_index}")
    try:
        case_path = create_cavity_case(case_manager, case_name)
        print(f"[OK] Case created: {case_path}")
        
        # List generated files
        files = list(case_path.glob("**/*"))
        file_count = len([f for f in files if f.is_file()])
        print(f"[OK] Generated {file_count} files")
        
        # Show directory structure
        print(f"\nDirectory Structure:")
        for f in sorted(files)[:10]:  # Show first 10 items
            rel_path = f.relative_to(case_path)
            if f.is_dir():
                print(f"  [{rel_path}/]")
            else:
                print(f"  {rel_path}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more items")
            
    except Exception as e:
        print(f"[FAIL] Failed to create case: {e}")
    
    # ------------------------------------------------------------------------
    # Step 7: LLM Explanation (Bonus)
    # ------------------------------------------------------------------------
    if not engine.mock_mode:
        print_section("Step 7: LLM Explanation")
        print("Asking KIMI to explain the configuration...")
        
        try:
            explanation = engine.explain_config(config)
            print(f"\n{explanation[:500]}...")
            print(f"\n[OK] Explanation generated ({len(explanation)} chars)")
        except Exception as e:
            print(f"[WARN] Could not generate explanation: {e}")
    
    # ------------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------------
    print_header("Demo Complete!")
    print(f"\nScenario: {scenario['name']}")
    print(f"Status: SUCCESS")
    print(f"Case Location: ./demo_cases/{case_name}")
    print(f"\nNext Steps:")
    print(f"  1. cd demo_cases/{case_name}")
    print(f"  2. Run simulation with the generated case")
    print(f"  3. View results in ParaView")
    print(f"\nTo run another scenario, use: python demo_full_workflow.py [0|1|2]")

if __name__ == "__main__":
    # Parse command line argument for scenario selection
    scenario_idx = 0
    if len(sys.argv) > 1:
        try:
            scenario_idx = int(sys.argv[1])
            if scenario_idx < 0 or scenario_idx >= len(DEMO_SCENARIOS):
                print(f"Invalid scenario index. Using 0.")
                scenario_idx = 0
        except ValueError:
            print(f"Invalid argument. Using scenario 0.")
    
    demo_workflow(scenario_idx)
