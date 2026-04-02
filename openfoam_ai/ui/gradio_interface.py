"""
Gradio Web UI - Web交互界面

基于Gradio的现代化Web界面，支持：
- 自然语言输入
- 对话历史显示
- 算例配置可视化
- 操作确认对话框
- 实时状态更新
- 分步向导模式
- 仿真监控
- 结果可视化
- 学习中心
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import asdict

# 尝试导入Gradio
try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    print("[GradioInterface] 警告: Gradio不可用，Web UI功能将受限")

from ..agents.manager_agent import ManagerAgent
from ..memory.memory_manager import MemoryManager, ConfigurationDiffer
from ..memory.session_manager import SessionManager, PendingOperation

# 导入事件处理函数
from . import event_handlers as eh


class GradioInterface:
    """
    Gradio Web界面
    
    提供直观的Web交互界面，支持多轮对话和可视化操作。
    包含5个标签页：智能对话、向导模式、仿真监控、结果查看、学习中心
    """
    
    def __init__(self,
                 manager_agent: Optional[ManagerAgent] = None,
                 memory_manager: Optional[MemoryManager] = None,
                 session_manager: Optional[SessionManager] = None):
        """
        初始化Gradio界面
        
        Args:
            manager_agent: 管理Agent（可选）
            memory_manager: 记忆管理器（可选）
            session_manager: 会话管理器（可选）
        """
        if not GRADIO_AVAILABLE:
            raise ImportError("Gradio未安装，无法创建Web界面")
        
        self.manager = manager_agent or ManagerAgent()
        self.memory = memory_manager
        self.session = session_manager or SessionManager()
        
        # 当前待确认操作
        self.pending_operation: Optional[PendingOperation] = None
        
        # 界面组件
        self.chatbot: Optional[gr.Chatbot] = None
        self.msg_input: Optional[gr.Textbox] = None
        self.config_display: Optional[gr.JSON] = None
        self.status_display: Optional[gr.Textbox] = None
        
        # 向导引擎状态
        self._wizard_engine = None
        self._wizard_current_step = 0
        
        # 用于传递引用给事件处理器
        self._pending_op_ref = {"pending_operation": None}
        self._wizard_engine_ref = {"engine": None}
        self._wizard_step_ref = {"step": 0}
        
        print(f"[GradioInterface] 初始化完成 (会话: {self.session.session_id})")
    
    # ============ 界面创建方法 ============
    
    def create_interface(self) -> gr.Blocks:
        """创建Gradio多标签页界面"""
        with gr.Blocks(title="OpenFOAM AI 智能仿真助手") as interface:
            gr.Markdown("""
            # 🤖 OpenFOAM AI 智能仿真助手
            
            基于大语言模型的CFD自动化仿真平台 | 支持自然语言交互和分步向导
            """)
            
            with gr.Tabs():
                # ========== Tab 1: 智能对话 ==========
                self._build_chat_tab()
                
                # ========== Tab 2: 向导模式 ==========
                self._build_wizard_tab()
                
                # ========== Tab 3: 仿真监控 ==========
                self._build_monitor_tab()
                
                # ========== Tab 4: 结果查看 ==========
                self._build_results_tab()
                
                # ========== Tab 5: 学习中心 ==========
                self._build_learning_tab()
            
            gr.Markdown("""
            ---
            💡 **提示**: 高风险操作（如删除算例、覆盖数据）需要确认。输入 Y 确认，N 取消。
            """)
        
        return interface
    
    def _build_chat_tab(self):
        """构建智能对话标签页"""
        with gr.Tab("💬 智能对话"):
            gr.Markdown("### 与AI助手对话，用自然语言描述您的CFD仿真需求")
            
            with gr.Row():
                # 左侧：对话区域
                with gr.Column(scale=3):
                    self.chatbot = gr.Chatbot(
                        label="对话历史",
                        height=500
                    )
                    
                    with gr.Row():
                        self.msg_input = gr.Textbox(
                            label="输入指令",
                            placeholder="描述您的CFD仿真需求...",
                            scale=8
                        )
                        submit_btn = gr.Button("发送", scale=1, variant="primary")
                
                # 右侧：配置和控制区域
                with gr.Column(scale=1):
                    self.status_display = gr.Textbox(
                        label="状态",
                        value="就绪",
                        interactive=False
                    )
                    
                    self.config_display = gr.JSON(
                        label="当前配置",
                        value={}
                    )
                    
                    # 快捷操作按钮
                    gr.Markdown("#### 快捷操作")
                    with gr.Row():
                        quick_cavity_btn = gr.Button("🔲 创建方腔算例", size="sm")
                        quick_run_btn = gr.Button("▶️ 运行计算", size="sm")
                        quick_status_btn = gr.Button("📊 查看状态", size="sm")
                    
                    with gr.Accordion("记忆功能", open=False):
                        memory_query = gr.Textbox(
                            label="检索历史配置",
                            placeholder="输入关键词..."
                        )
                        search_btn = gr.Button("检索")
                        memory_output = gr.Textbox(
                            label="检索结果",
                            interactive=False,
                            lines=5
                        )
                        export_btn = gr.Button("导出记忆")
                    
                    with gr.Accordion("系统信息", open=False):
                        stats_btn = gr.Button("显示统计")
                        stats_output = gr.Textbox(
                            label="统计信息",
                            interactive=False,
                            lines=10
                        )
            
            # 事件绑定
            submit_btn.click(
                fn=lambda msg, hist: eh.handle_user_message(
                    msg, hist, self.manager, self.session, self.memory, self._pending_op_ref
                ),
                inputs=[self.msg_input, self.chatbot],
                outputs=[self.msg_input, self.chatbot, self.status_display, self.config_display]
            )
            
            self.msg_input.submit(
                fn=lambda msg, hist: eh.handle_user_message(
                    msg, hist, self.manager, self.session, self.memory, self._pending_op_ref
                ),
                inputs=[self.msg_input, self.chatbot],
                outputs=[self.msg_input, self.chatbot, self.status_display, self.config_display]
            )
            
            # 快捷按钮
            quick_cavity_btn.click(
                fn=lambda: eh.handle_user_message(
                    "创建一个二维方腔驱动流，顶部速度1m/s", [], 
                    self.manager, self.session, self.memory, self._pending_op_ref
                ),
                outputs=[self.msg_input, self.chatbot, self.status_display, self.config_display]
            )
            
            quick_run_btn.click(
                fn=lambda: eh.handle_user_message(
                    "开始运行计算", 
                    self.chatbot.value if self.chatbot else [],
                    self.manager, self.session, self.memory, self._pending_op_ref
                ),
                outputs=[self.msg_input, self.chatbot, self.status_display, self.config_display]
            )
            
            quick_status_btn.click(
                fn=lambda: eh.handle_user_message(
                    "查看当前算例状态", 
                    self.chatbot.value if self.chatbot else [],
                    self.manager, self.session, self.memory, self._pending_op_ref
                ),
                outputs=[self.msg_input, self.chatbot, self.status_display, self.config_display]
            )
            
            search_btn.click(
                fn=lambda q: eh.handle_memory_search(q, self.memory),
                inputs=[memory_query],
                outputs=[memory_output]
            )
            
            export_btn.click(
                fn=lambda: eh.handle_export_memory(self.memory),
                outputs=[memory_output]
            )
            
            stats_btn.click(
                fn=lambda: eh.handle_show_stats(self.session, self.memory),
                outputs=[stats_output]
            )
    
    def _build_wizard_tab(self):
        """构建向导模式标签页"""
        with gr.Tab("🧭 向导模式"):
            gr.Markdown("### 分步引导创建仿真算例\n无需专业知识，跟随向导逐步完成配置")
            
            # 步骤进度指示器
            step_progress = gr.HTML(value=eh.render_step_progress(0))
            
            # 使用 gr.State 存储当前步骤索引
            wizard_step_state = gr.State(value=0)
            
            # 步骤1: 场景选择
            with gr.Group(visible=True) as step1_group:
                gr.Markdown("#### 步骤 1/6: 选择仿真场景")
                scenario_info = gr.Markdown("选择一个场景开始...")
                scenario_radio = gr.Radio(
                    choices=[
                        ("🔲 方腔驱动流", "cavity"),
                        ("🔵 管道流动", "pipe"),
                        ("⭕ 圆柱绕流", "cylinder"),
                        ("📐 后台阶流", "backward_step"),
                        ("➖ 平板通道流", "channel"),
                        ("🌡️ 自然对流", "natural_convection"),
                        ("🌊 溃坝", "dam_break"),
                        ("⚙️ 自定义", "custom")
                    ],
                    label="选择仿真场景",
                    info="选择最接近您需求的场景类型"
                )
                scenario_detail = gr.Markdown("")  # 场景详细说明
            
            # 步骤2: 几何参数
            with gr.Group(visible=False) as step2_group:
                gr.Markdown("#### 步骤 2/6: 设置几何参数")
                step2_teaching = gr.Markdown(eh.get_teaching_for_step("geometry"))
                with gr.Row():
                    geo_L = gr.Number(label="长度 L (m)", value=1.0, minimum=0.001)
                    geo_W = gr.Number(label="宽度 W (m)", value=1.0, minimum=0.001)
                    geo_H = gr.Number(label="高度 H (m)", value=0.1, minimum=0.0001)
            
            # 步骤3: 网格设置
            with gr.Group(visible=False) as step3_group:
                gr.Markdown("#### 步骤 3/6: 网格设置")
                step3_teaching = gr.Markdown(eh.get_teaching_for_step("mesh"))
                with gr.Row():
                    mesh_nx = gr.Slider(10, 200, value=20, step=1, label="X方向网格数")
                    mesh_ny = gr.Slider(10, 200, value=20, step=1, label="Y方向网格数")
                    mesh_nz = gr.Slider(1, 100, value=1, step=1, label="Z方向网格数")
                mesh_preview = gr.Plot(label="网格预览")  # matplotlib图
                mesh_info = gr.Markdown("")  # 显示总网格数等信息
            
            # 步骤4: 边界条件
            with gr.Group(visible=False) as step4_group:
                gr.Markdown("#### 步骤 4/6: 边界条件")
                step4_teaching = gr.Markdown(eh.get_teaching_for_step("boundary"))
                # 根据场景动态显示边界设置
                boundary_config = gr.JSON(label="边界条件配置", value={})
                boundary_explanation = gr.Markdown("边界条件将根据选择的场景自动配置")
            
            # 步骤5: 求解器配置
            with gr.Group(visible=False) as step5_group:
                gr.Markdown("#### 步骤 5/6: 求解器配置")
                step5_teaching = gr.Markdown(eh.get_teaching_for_step("solver"))
                solver_dropdown = gr.Dropdown(
                    choices=["icoFoam", "simpleFoam", "pimpleFoam", 
                             "buoyantBoussinesqPimpleFoam", "interFoam"],
                    label="求解器", value="icoFoam"
                )
                with gr.Row():
                    end_time = gr.Number(label="结束时间 (s)", value=0.5)
                    delta_t = gr.Number(label="时间步长 (s)", value=0.005)
                    nu_input = gr.Number(label="运动粘度 (m²/s)", value=0.01)
            
            # 步骤6: 审查与运行
            with gr.Group(visible=False) as step6_group:
                gr.Markdown("#### 步骤 6/6: 审查与运行")
                review_summary = gr.Markdown("")  # 完整配置摘要
                review_score = gr.Markdown("")    # CriticAgent 审查评分
                config_json = gr.JSON(label="完整配置")
            
            # 导航按钮
            with gr.Row():
                prev_btn = gr.Button("⬅️ 上一步", interactive=False)
                next_btn = gr.Button("下一步 ➡️", variant="primary")
                run_btn = gr.Button("🚀 开始运行", visible=False, variant="primary")
            
            # 验证反馈
            validation_output = gr.Markdown("")
            
            # 事件绑定
            scenario_radio.change(
                fn=lambda sid: eh.wizard_select_scenario(sid, self._wizard_engine_ref, self._wizard_step_ref),
                inputs=[scenario_radio],
                outputs=[scenario_detail, validation_output]
            )
            
            # 网格预览更新
            mesh_nx.change(
                fn=eh.update_mesh_preview, 
                inputs=[mesh_nx, mesh_ny, mesh_nz], 
                outputs=[mesh_preview, mesh_info]
            )
            mesh_ny.change(
                fn=eh.update_mesh_preview, 
                inputs=[mesh_nx, mesh_ny, mesh_nz], 
                outputs=[mesh_preview, mesh_info]
            )
            mesh_nz.change(
                fn=eh.update_mesh_preview, 
                inputs=[mesh_nx, mesh_ny, mesh_nz], 
                outputs=[mesh_preview, mesh_info]
            )
            
            # 下一步按钮事件绑定
            def on_next_step(current_step, geo_L_val, geo_W_val, geo_H_val, 
                           mesh_nx_val, mesh_ny_val, mesh_nz_val,
                           solver_val, end_time_val, delta_t_val, nu_val):
                # 根据当前步骤准备参数
                if current_step == 1:
                    args = (geo_L_val, geo_W_val, geo_H_val)
                elif current_step == 2:
                    args = (mesh_nx_val, mesh_ny_val, mesh_nz_val)
                elif current_step == 4:
                    args = (solver_val, end_time_val, delta_t_val, nu_val)
                else:
                    args = ()
                
                result = eh.wizard_next_step(
                    current_step, args, self._wizard_engine_ref, self._wizard_step_ref
                )
                
                # 返回所有输出值，确保步骤索引在有效范围内
                new_step = self._wizard_step_ref.get("step", current_step)
                new_step = max(0, min(new_step, 5))  # 边界保护：步骤范围0-5
                return (
                    new_step,  # wizard_step_state
                    result.get("step_progress", ""),
                    result.get("validation_output", ""),
                    result.get("step1_group", gr.update()),
                    result.get("step2_group", gr.update()),
                    result.get("step3_group", gr.update()),
                    result.get("step4_group", gr.update()),
                    result.get("step5_group", gr.update()),
                    result.get("step6_group", gr.update()),
                )
            
            next_btn.click(
                fn=on_next_step,
                inputs=[wizard_step_state, geo_L, geo_W, geo_H,
                       mesh_nx, mesh_ny, mesh_nz,
                       solver_dropdown, end_time, delta_t, nu_input],
                outputs=[wizard_step_state, step_progress, validation_output,
                        step1_group, step2_group, step3_group, 
                        step4_group, step5_group, step6_group]
            )
            
            # 上一步按钮事件绑定
            def on_prev_step(current_step):
                result = eh.wizard_prev_step(
                    current_step, self._wizard_engine_ref, self._wizard_step_ref
                )
                
                new_step = self._wizard_step_ref.get("step", current_step)
                new_step = max(0, min(new_step, 5))  # 边界保护：步骤范围0-5
                return (
                    new_step,  # wizard_step_state
                    result.get("step_progress", ""),
                    result.get("validation_output", ""),
                    result.get("step1_group", gr.update()),
                    result.get("step2_group", gr.update()),
                    result.get("step3_group", gr.update()),
                    result.get("step4_group", gr.update()),
                    result.get("step5_group", gr.update()),
                    result.get("step6_group", gr.update()),
                )
            
            prev_btn.click(
                fn=on_prev_step,
                inputs=[wizard_step_state],
                outputs=[wizard_step_state, step_progress, validation_output,
                        step1_group, step2_group, step3_group, 
                        step4_group, step5_group, step6_group]
            )
    
    def _build_monitor_tab(self):
        """构建仿真监控标签页"""
        with gr.Tab("📊 仿真监控"):
            gr.Markdown("### 仿真运行状态监控")
            
            with gr.Row():
                with gr.Column(scale=2):
                    residual_plot = gr.Plot(label="残差收敛曲线")
                    courant_plot = gr.Plot(label="库朗数变化")
                with gr.Column(scale=1):
                    progress_bar = gr.Slider(0, 100, value=0, label="计算进度 %", interactive=False)
                    current_time = gr.Textbox(label="当前时间", value="0.0", interactive=False)
                    current_step = gr.Textbox(label="迭代步数", value="0", interactive=False)
                    max_courant = gr.Textbox(label="最大库朗数", value="-", interactive=False)
                    max_residual = gr.Textbox(label="最大残差", value="-", interactive=False)
            
            log_display = gr.Textbox(label="运行日志", lines=10, interactive=False, max_lines=20)
            
            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新状态")
                stop_btn = gr.Button("⏹️ 停止计算", variant="stop")
            
            # 刷新按钮点击时生成模拟的残差曲线
            refresh_btn.click(
                fn=eh.refresh_monitor,
                outputs=[residual_plot, log_display]
            )
    
    def _build_results_tab(self):
        """构建结果查看标签页"""
        with gr.Tab("🖼️ 结果查看"):
            gr.Markdown("### 仿真结果可视化")
            
            with gr.Row():
                field_selector = gr.Dropdown(
                    choices=["速度场 (U)", "压力场 (p)", "温度场 (T)"],
                    label="选择物理场", value="速度场 (U)"
                )
                timestep_slider = gr.Slider(0, 100, value=0, step=1, label="时间步")
            
            result_image = gr.Image(label="场分布云图", type="filepath")
            
            with gr.Row():
                animation_display = gr.Image(label="流场动画", type="filepath")
            
            with gr.Accordion("数据下载", open=False):
                download_btn = gr.Button("📥 导出结果数据")
                download_output = gr.File(label="下载文件")
    
    def _build_learning_tab(self):
        """构建学习中心标签页"""
        with gr.Tab("📚 学习中心"):
            gr.Markdown("### CFD 基础知识学习")
            
            with gr.Tabs():
                with gr.Tab("快速入门"):
                    gr.Markdown(eh.get_quick_start_content())
                
                with gr.Tab("术语表"):
                    glossary_search = gr.Textbox(label="搜索术语", placeholder="输入关键词...")
                    glossary_display = gr.Markdown(eh.format_glossary())
                    glossary_search.change(
                        fn=eh.search_glossary,
                        inputs=[glossary_search],
                        outputs=[glossary_display]
                    )
                
                with gr.Tab("场景案例库"):
                    scenario_selector = gr.Dropdown(
                        choices=["方腔驱动流", "管道流动", "圆柱绕流", "后台阶流",
                                 "平板通道流", "自然对流", "溃坝", "翼型绕流"],
                        label="选择场景"
                    )
                    scenario_explanation = gr.Markdown("选择一个场景查看详细说明...")
                    
                    scenario_selector.change(
                        fn=eh.get_scenario_explanation,
                        inputs=[scenario_selector],
                        outputs=[scenario_explanation]
                    )
                
                with gr.Tab("最佳实践"):
                    gr.Markdown(eh.get_best_practices_content())
    
    def launch(self, 
               share: bool = False,
               server_name: str = "0.0.0.0",
               server_port: int = 7860,
               **kwargs) -> None:
        """
        启动Web界面
        
        Args:
            share: 是否创建公开链接
            server_name: 服务器地址
            server_port: 服务器端口
            **kwargs: 其他Gradio参数
        """
        if not GRADIO_AVAILABLE:
            print("❌ Gradio未安装，无法启动Web界面")
            print("请运行: pip install gradio")
            return
        
        interface = self.create_interface()
        
        print(f"\n🚀 启动 OpenFOAM AI 智能仿真助手")
        print(f"   本地地址: http://{server_name}:{server_port}")
        if share:
            print("   正在创建公开链接...")
        
        interface.launch(
            share=share,
            server_name=server_name,
            server_port=server_port,
            **kwargs
        )


def create_ui(manager_agent: Optional[ManagerAgent] = None,
              memory_manager: Optional[MemoryManager] = None,
              session_manager: Optional[SessionManager] = None) -> GradioInterface:
    """
    创建Gradio界面实例
    
    Args:
        manager_agent: 管理Agent
        memory_manager: 记忆管理器
        session_manager: 会话管理器
        
    Returns:
        GradioInterface实例
    """
    return GradioInterface(
        manager_agent=manager_agent,
        memory_manager=memory_manager,
        session_manager=session_manager
    )


def demo_gradio_interface():
    """演示Gradio界面（仅结构）"""
    print("=" * 60)
    print("GradioInterface 演示")
    print("=" * 60)
    
    if not GRADIO_AVAILABLE:
        print("\n❌ Gradio未安装")
        print("请运行: pip install gradio")
        return
    
    print("\n✅ Gradio已安装")
    print("创建界面实例...")
    
    # 创建界面（不启动）
    ui = create_ui()
    print(f"   会话ID: {ui.session.session_id}")
    print(f"   界面创建成功")
    
    print("\n要启动界面，请运行:")
    print("  ui.launch()")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo_gradio_interface()
