#!/usr/bin/env python3
"""
OpenFOAM AI - Interactive GUI with Real-time Simulation
交互式 GUI，支持实时仿真运行、结果可视化和交互操作
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Optional, Tuple
import threading

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "core"))
sys.path.insert(0, str(Path(__file__).parent / "openfoam_ai" / "utils"))

import gradio as gr
from prompt_engine import PromptEngine, ConfigRefiner
from critic_agent import CriticAgent
from case_manager import CaseManager, create_cavity_case
from case_visualizer import generate_preview
from of_simulator import OpenFOAMSimulator
from result_visualizer import ResultVisualizer
from animation_generator import generate_flow_animation

# Configuration
KIMI_API_KEY = "sk-Y4G2lAGkFIhUeLvfaQEi5RzOpYbupjhPtkbp0Cb0KQCS2Jnr"
CASES_DIR = "./gui_cases"

class OpenFOAMApp:
    def __init__(self):
        self.engine = None
        self.case_manager = CaseManager(CASES_DIR)
        self.critic = CriticAgent(use_llm=False)
        self.refiner = ConfigRefiner()
        self.current_config = None
        self.current_case_path = None
        self.simulator = None
        self.visualizer = None
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        
    def initialize(self):
        """Initialize LLM"""
        try:
            self.engine = PromptEngine(
                provider="kimi",
                api_key=KIMI_API_KEY,
                model="moonshot-v1-8k"
            )
            return not self.engine.mock_mode
        except Exception as e:
            print(f"LLM init failed: {e}")
            return False
    
    def create_case(self, description):
        """Create new case from description"""
        if not description:
            return [None, "Please enter a description"]
        
        try:
            # Generate config
            config = self.engine.natural_language_to_config(description)
            config = self.refiner.refine(config)
            self.current_config = config
            
            # Create case files
            case_name = config.get('task_id', 'case')
            self.current_case_path = create_cavity_case(self.case_manager, case_name)
            
            # Save full config
            self._save_config()
            
            # Generate preview
            preview_path = generate_preview(self.current_case_path)
            
            # Initialize visualizer
            self.visualizer = ResultVisualizer(self.current_case_path)
            
            info = f"Case created: {case_name}\nLocation: {self.current_case_path}"
            return [str(preview_path), info]
            
        except Exception as e:
            return [None, f"Error: {str(e)}"]
    
    def _save_config(self):
        """Save full config"""
        if self.current_case_path and self.current_config:
            info_file = self.current_case_path / ".case_info.json"
            full_info = {
                "task_id": self.current_config.get('task_id'),
                "physics_type": self.current_config.get('physics_type'),
                "solver": self.current_config.get('solver', {}),
                "geometry": self.current_config.get('geometry', {}),
                "boundary_conditions": self.current_config.get('boundary_conditions', {}),
                "nu": self.current_config.get('nu')
            }
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(full_info, f, indent=2, ensure_ascii=False)
    
    def run_mesh(self):
        """Generate mesh"""
        if not self.current_case_path:
            return [None, "No case available"]
        
        self.simulator = OpenFOAMSimulator(self.current_case_path)
        
        # Check OpenFOAM availability
        has_openfoam = self.simulator.check_openfoam()
        if not has_openfoam:
            info = """[NOTICE] OpenFOAM not found.

To generate real mesh:
1. Install OpenFOAM (https://openfoam.org/download/)
2. Restart this application

Using preview mode (mesh configuration shown but not generated)."""
            preview_path = generate_preview(self.current_case_path)
            return [str(preview_path), info]
        
        # Run real blockMesh
        success, msg = self.simulator.generate_mesh()
        
        # Update preview after mesh
        preview_path = generate_preview(self.current_case_path)
        
        status = "[OK] Mesh generated!\n" if success else "[ERROR] Mesh generation failed\n"
        return [str(preview_path), status + msg]
    
    def run_simulation(self, max_time, use_openfoam: bool = False):
        """Run simulation"""
        if not self.current_case_path:
            return None, "No case available"
        
        if not self.simulator:
            self.simulator = OpenFOAMSimulator(self.current_case_path)
        
        # Check OpenFOAM availability
        has_openfoam = self.simulator.check_openfoam()
        
        if not has_openfoam:
            # Use simulation mode with animated results
            info = """[NOTICE] OpenFOAM not found. Running in SIMULATION MODE.

This mode generates animated flow evolution based on CFD theory.
To run real OpenFOAM simulation:
1. Install OpenFOAM (https://openfoam.org/download/)
2. Restart this application

Generating animated results..."""
            
            # Generate animation instead of static result
            try:
                # Generate multiple time steps and create animation
                anim_path = self.generate_animation(num_frames=20, fps=4)
                return [str(anim_path), info + "\n[OK] Animation generated!"]
            except Exception as e:
                # Fallback to static result
                result_path = self.visualizer.create_result_figure(time_step='2.0')
                return [str(result_path), info + f"\n[WARNING] Animation failed, showing static result: {e}"]
        
        # Run real OpenFOAM simulation
        max_t = float(max_time) if max_time else 10.0
        success, msg = self.simulator.run_simulation(max_time=max_t)
        
        # Generate result figure
        if success:
            result_path = self.visualizer.create_result_figure()
            return [str(result_path), "[OK] OpenFOAM simulation completed!\n" + msg]
        
        return None, msg
    
    def generate_animation(self, num_frames, fps):
        """Generate flow evolution animation"""
        if not self.current_case_path:
            return [None, "No case available. Create a case first."]
        
        try:
            num_frames = int(num_frames) if num_frames else 20
            fps = int(fps) if fps else 4
            
            anim_path = generate_flow_animation(
                self.current_case_path,
                num_frames=num_frames,
                fps=fps,
                field='U'
            )
            info = f"[OK] Animation generated!\nFrames: {num_frames}, FPS: {fps}\nFile: {anim_path.name}"
            return [str(anim_path), info]
        except Exception as e:
            return [None, f"[ERROR] Animation generation failed: {str(e)}"]
    
    def update_result_view(self, time_step, field, zoom, pan_x, pan_y):
        """Update result view with zoom and pan"""
        if not self.visualizer:
            return None, "No visualizer available"
        
        # Calculate zoom region
        if zoom != 1.0 or pan_x != 0 or pan_y != 0:
            L, W = 2.0, 1.0
            center_x = L/2 + pan_x
            center_y = W/2 + pan_y
            width = L / zoom
            height = W / zoom
            zoom_region = (
                center_x - width/2,
                center_x + width/2,
                center_y - height/2,
                center_y + height/2
            )
        else:
            zoom_region = None
        
        result_path = self.visualizer.create_result_figure(
            time_step=time_step if time_step else None,
            field=field,
            zoom_region=zoom_region
        )
        
        info = f"Field: {field}, Time: {time_step or 'latest'}, Zoom: {zoom}x"
        return [str(result_path), info]
    
    def modify_case(self, modification):
        """Modify current case"""
        if not self.current_config:
            return None, "No case to modify"
        
        if not modification:
            return None, "Please enter modification"
        
        try:
            # 特殊处理：局部网格加密
            if any(kw in modification.lower() for kw in ['加密', 'refine', 'mesh', '网格', '局部']):
                return self._apply_mesh_refinement(modification)
            
            # Use LLM to modify
            system_prompt = """You are a CFD expert. Modify the given OpenFOAM configuration according to user's request.
Return a valid JSON configuration with the same structure as the input.

IMPORTANT: For mesh refinement around cylinder/vortex regions:
- Increase nx, ny in the wake region behind cylinder
- Use graded mesh with smaller cells near cylinder"""
            
            user_prompt = f"""Original configuration:
{json.dumps(self.current_config, indent=2)}

Modification request: {modification}

Return ONLY the updated JSON configuration."""
            
            # 使用 LLM 进行修改
            response = self.engine.llm.chat(
                message=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3
            )
            
            if response.success:
                import json
                # 解析 JSON 响应
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                config = json.loads(content)
                config = self.refiner.refine(config)
                self.current_config = config
                
                # Save updated config
                self._save_config()
                
                # Generate new preview
                preview_path = generate_preview(self.current_case_path)
                
                return [str(preview_path), f"[OK] Modified: {modification}\nChanges applied successfully!"]
            else:
                return [None, f"[ERROR] LLM failed: {response.error}"]
            
        except Exception as e:
            return [None, f"[ERROR] {str(e)}"]
    
    def _apply_mesh_refinement(self, modification: str):
        """应用局部网格加密"""
        try:
            config = self.current_config.copy()
            geom = config.get('geometry', {})
            mesh = geom.get('mesh_resolution', {}).copy()
            
            # 解析加密要求
            nx = mesh.get('nx', 50)
            ny = mesh.get('ny', 50)
            
            # 根据请求增加网格数
            if any(kw in modification.lower() for kw in ['精细', 'fine', '高', 'high']):
                nx = max(nx * 2, 100)
                ny = max(ny * 2, 100)
            elif any(kw in modification.lower() for kw in ['加密', 'refine']):
                nx = int(nx * 1.5)
                ny = int(ny * 1.5)
            
            # 圆柱绕流特殊处理 - 在圆柱周围加密
            if self._has_cylinder():
                # 添加网格分级信息（用于 blockMesh）
                config['mesh_refinement'] = {
                    'cylinder_refinement': True,
                    'wake_refinement': True,
                    'grading': {'x': '1 2 1', 'y': '1 1 1'}
                }
            
            # 更新网格配置
            if 'geometry' not in config:
                config['geometry'] = {}
            config['geometry']['mesh_resolution'] = {'nx': nx, 'ny': ny, 'nz': 1}
            
            self.current_config = config
            self._save_config()
            
            preview_path = generate_preview(self.current_case_path)
            
            info = f"[OK] Mesh refined: {nx} x {ny}\n"
            if self._has_cylinder():
                info += "Cylinder wake region will be refined.\n"
            info += "Click 'Generate Mesh' to apply new mesh."
            
            return [str(preview_path), info]
            
        except Exception as e:
            return [None, f"[ERROR] Mesh refinement failed: {str(e)}"]
    
    def _has_cylinder(self) -> bool:
        """Check if case has cylinder"""
        if not self.current_config:
            return False
        bc = self.current_config.get('boundary_conditions', {})
        return any('cylinder' in k.lower() for k in bc.keys())
    
    def review_case(self):
        """Review case with Critic"""
        if not self.current_config:
            return "No case to review"
        
        report = self.critic.review(self.current_config)
        
        result = f"""Review Report
Score: {report.score}/100
Verdict: {report.verdict.name}

Issues: {len(report.issues)}
"""
        for issue in report.issues:
            result += f"- [{issue.severity}] {issue.description}\n"
        
        return result
    
    def get_case_info(self):
        """Get case information"""
        if not self.current_config:
            return "No case available"
        
        return json.dumps(self.current_config, indent=2, ensure_ascii=False)


# Create Gradio interface
def create_interface():
    app = OpenFOAMApp()
    llm_ready = app.initialize()
    
    with gr.Blocks(title="OpenFOAM AI - Interactive Simulation") as demo:
        gr.Markdown("""
        # OpenFOAM AI - Interactive Simulation Platform
        ### Real-time CFD Simulation with AI-powered Case Generation
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                # Left panel - Controls
                gr.Markdown("## Case Creation")
                description = gr.Textbox(
                    label="Case Description",
                    placeholder="e.g., Cylinder flow with Re=100 for Karman vortex study",
                    lines=3
                )
                create_btn = gr.Button("Create Case", variant="primary")
                
                gr.Markdown("## Modification")
                modification = gr.Textbox(
                    label="Modification Request",
                    placeholder="e.g., Increase mesh resolution to 100x50",
                    lines=2
                )
                modify_btn = gr.Button("Modify Case")
                
                gr.Markdown("## Simulation Control")
                with gr.Row():
                    mesh_btn = gr.Button("Generate Mesh")
                    run_btn = gr.Button("Run Simulation", variant="primary")
                max_time = gr.Number(label="Max Time (s)", value=5.0, minimum=0.1, maximum=100.0)
                
                gr.Markdown("## View Control")
                field_select = gr.Dropdown(
                    choices=["U", "p"],
                    value="U",
                    label="Field"
                )
                zoom_slider = gr.Slider(minimum=0.5, maximum=5.0, value=1.0, step=0.1, label="Zoom")
                pan_x_slider = gr.Slider(minimum=-1.0, maximum=1.0, value=0.0, step=0.1, label="Pan X")
                pan_y_slider = gr.Slider(minimum=-0.5, maximum=0.5, value=0.0, step=0.1, label="Pan Y")
                update_view_btn = gr.Button("Update View")
                
                gr.Markdown("## Animation")
                anim_btn = gr.Button("Generate Flow Animation")
                anim_frames = gr.Slider(minimum=10, maximum=50, value=20, step=5, label="Frames")
                anim_fps = gr.Slider(minimum=1, maximum=10, value=4, step=1, label="FPS")
                
                gr.Markdown("## Review")
                review_btn = gr.Button("Review Case")
                refresh_btn = gr.Button("Refresh Info")
                
            with gr.Column(scale=2):
                # Right panel - Display
                gr.Markdown("## Preview / Results / Animation")
                image_display = gr.Image(label="Case Preview / Results", type="filepath")
                animation_display = gr.Image(label="Flow Animation (GIF)", type="filepath")
                
                with gr.Row():
                    info_text = gr.Textbox(label="Status", lines=5)
                    review_text = gr.Textbox(label="Review Report", lines=5)
                
                case_info = gr.Textbox(label="Case Configuration", lines=10)
                
                # OpenFOAM status indicator
                has_openfoam = OpenFOAMSimulator(Path(".")).check_openfoam()
                status_color = "green" if has_openfoam else "orange"
                status_text = "OpenFOAM: Installed (Real Simulation)" if has_openfoam else "OpenFOAM: Not Found (Simulation Mode)"
                gr.Markdown(f"""
                <div style="padding: 10px; background-color: {status_color}; color: white; border-radius: 5px;">
                    <b>{status_text}</b>
                </div>
                """)
        
        # Event handlers
        create_btn.click(
            fn=app.create_case,
            inputs=description,
            outputs=[image_display, info_text]
        )
        
        modify_btn.click(
            fn=app.modify_case,
            inputs=modification,
            outputs=[image_display, info_text]
        )
        
        mesh_btn.click(
            fn=app.run_mesh,
            inputs=[],
            outputs=[image_display, info_text]
        )
        
        run_btn.click(
            fn=app.run_simulation,
            inputs=max_time,
            outputs=[image_display, info_text]
        )
        
        update_view_btn.click(
            fn=app.update_result_view,
            inputs=[gr.Textbox(value="", visible=False), field_select, zoom_slider, pan_x_slider, pan_y_slider],
            outputs=[image_display, info_text]
        )
        
        review_btn.click(
            fn=app.review_case,
            inputs=[],
            outputs=review_text
        )
        
        refresh_btn.click(
            fn=app.get_case_info,
            inputs=[],
            outputs=case_info
        )
        
        anim_btn.click(
            fn=app.generate_animation,
            inputs=[anim_frames, anim_fps],
            outputs=[animation_display, info_text]
        )
        
        gr.Markdown(f"""
        ---
        **Status**: {'✅ KIMI LLM Ready' if llm_ready else '⚠️ Mock Mode'}
        """)
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
