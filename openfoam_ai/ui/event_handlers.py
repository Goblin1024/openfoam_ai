"""
Event Handlers - 事件处理函数

提取自 gradio_interface.py 的事件回调函数
这些函数接受必要的依赖作为参数，不依赖类实例
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import asdict

try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False


# ============ 向导步骤常量 ============
MAX_WIZARD_STEPS = 6  # 向导模式总步骤数（步骤0-5）


# ============ 配置格式化 ============

def format_config_for_display(config: Dict[str, Any]) -> Dict[str, Any]:
    """格式化配置用于显示"""
    if not config:
        return {}
    
    # 提取关键信息
    display = {
        "算例类型": config.get("physics_type", "unknown"),
        "求解器": config.get("solver", {}).get("name", "unknown"),
    }
    
    # 几何信息
    geom = config.get("geometry", {})
    dims = geom.get("dimensions", {})
    res = geom.get("mesh_resolution", {})
    
    if dims:
        display["几何尺寸"] = f"{dims.get('L', '?')} x {dims.get('W', '?')} x {dims.get('H', '?')}"
    if res:
        total_cells = res.get("nx", 1) * res.get("ny", 1) * res.get("nz", 1)
        display["网格分辨率"] = f"{res.get('nx', '?')} x {res.get('ny', '?')} x {res.get('nz', '?')}"
        display["总网格数"] = total_cells
    
    # 运行参数
    solver = config.get("solver", {})
    if solver:
        display["结束时间"] = solver.get("endTime", "?")
        display["时间步长"] = solver.get("deltaT", "?")
    
    return display


# ============ 消息处理 ============

def handle_user_message(
    message: str, 
    history: List[Dict[str, str]],
    manager,
    session,
    memory,
    pending_operation_ref: Dict
) -> Tuple[str, List[Dict[str, str]], str, Dict]:
    """
    处理用户消息
    
    Args:
        message: 用户输入
        history: 对话历史
        manager: ManagerAgent 实例
        session: SessionManager 实例
        memory: MemoryManager 实例（可选）
        pending_operation_ref: 包含 pending_operation 的字典引用
        
    Returns:
        (清空输入, 更新历史, 状态文本, 配置显示)
    """
    try:
        if not message.strip():
            return "", history, "请输入有效内容", {}
        
        # 添加到会话
        session.add_message("user", message)
        
        # 检查是否有待确认操作
        if pending_operation_ref.get("pending_operation"):
            return handle_confirmation(message, history, manager, session, memory, pending_operation_ref)
        
        # 处理新请求
        return process_new_request(message, history, manager, session, memory, pending_operation_ref)
    except Exception as e:
        error_msg = f"处理消息时出错: {str(e)}"
        print(f"[handle_user_message] {error_msg}")
        return "", history, error_msg, {}


def process_new_request(
    message: str, 
    history: List[Dict[str, str]],
    manager,
    session,
    memory,
    pending_operation_ref: Dict
) -> Tuple[str, List[Dict[str, str]], str, Dict]:
    """处理新请求"""
    try:
        # 先进行相似性检索
        similar_cases = []
        if memory:
            similar_cases = memory.search_similar(message, n_results=2)
        
        # 处理输入
        response = manager.process_input(message)
        
        response_type = response.get("type", "unknown")
        response_msg = response.get("message", "未知响应")
        
        # 检查是否包含图像路径
        image_paths = response.get("image_paths", [])
        
        # 更新历史
        history.append({"role": "user", "content": message})
        
        # 如果有图像，添加到消息中
        if image_paths:
            # 使用 markdown 格式添加图像
            images_md = "\n\n".join([f"![结果图像]({path})" for path in image_paths])
            response_msg_with_images = f"{response_msg}\n\n{images_md}"
            history.append({"role": "assistant", "content": response_msg_with_images})
        else:
            history.append({"role": "assistant", "content": response_msg})
        
        # 添加到会话
        session.add_message("assistant", response_msg, 
                           metadata={"type": response_type, "image_paths": image_paths})
        
        # 处理不同类型的响应
        if response_type == "plan":
            # 创建待确认操作
            plan = response.get("plan", {})
            config = manager.current_config
            
            # 存储到记忆
            if memory and config:
                memory.store_memory(
                    case_name=manager.current_case or "unnamed",
                    user_prompt=message,
                    config=config
                )
            
            # 创建高风险操作
            op = session.create_pending_operation(
                operation_type="create_case",
                description=f"创建算例: {manager.current_case}",
                details={
                    "case_name": manager.current_case,
                    "steps": plan.get("steps", []),
                    "estimated_time": plan.get("estimated_time", "unknown")
                }
            )
            
            # 如果配置较复杂，添加到确认队列
            if len(plan.get("steps", [])) > 3:
                pending_operation_ref["pending_operation"] = op
                confirm_prompt = session.generate_confirmation_prompt(op)
                history.append({"role": "assistant", "content": confirm_prompt})
                status = f"等待确认操作: {op.operation_type}"
            else:
                # 低风险操作，自动执行
                status = f"准备执行: {manager.current_case}"
        
        elif response_type == "case_created":
            # 案例创建成功
            status = f"算例已创建: {response.get('case_path', '')}"
            
            # 存储到记忆
            if memory and manager.current_config:
                memory.store_memory(
                    case_name=manager.current_case or "unnamed",
                    user_prompt=message,
                    config=manager.current_config
                )
        
        elif response_type == "simulation_complete":
            # 仿真完成
            status = "仿真运行完成"
            case_path = response.get("case_path", "")
            if case_path:
                status += f" - {case_path}"
            
            # 存储到记忆
            if memory and manager.current_config:
                memory.store_memory(
                    case_name=manager.current_case or "unnamed",
                    user_prompt=message,
                    config=manager.current_config
                )
        
        elif response_type == "simulation_error":
            # 仿真失败
            status = "仿真运行失败"
        
        elif response_type == "status":
            status = response_msg
        
        elif response_type == "error":
            status = f"错误: {response_msg}"
        
        else:
            status = "处理完成"
        
        # 更新配置显示
        config_display = {}
        if manager.current_config:
            config_display = format_config_for_display(manager.current_config)
        
        return "", history, status, config_display
    except Exception as e:
        error_msg = f"处理请求时出错: {str(e)}"
        print(f"[process_new_request] {error_msg}")
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": f"抱歉，处理您的请求时出现了错误: {str(e)}"})
        return "", history, error_msg, {}


def handle_confirmation(
    message: str, 
    history: List[Dict[str, str]],
    manager,
    session,
    memory,
    pending_operation_ref: Dict
) -> Tuple[str, List[Dict[str, str]], str, Dict]:
    """处理用户确认"""
    try:
        pending_op = pending_operation_ref.get("pending_operation")
        if not pending_op:
            return "", history, "没有待确认的操作", {}
        
        message_lower = message.strip().lower()
        
        if message_lower in ['y', 'yes', '是', '确认', '确定']:
            # 确认操作
            session.confirm_operation(pending_op.operation_id)
            
            # 执行操作
            result = manager.execute_plan(
                pending_op.operation_type,
                confirmed=True
            )
            
            response = f"✅ {result.message}"
            if result.logs:
                response += "\n\n执行日志:\n" + "\n".join(f"  • {log}" for log in result.logs[:5])
            
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})
            session.add_message("assistant", response)
            
            status = f"操作已完成: {pending_op.operation_type}"
            pending_operation_ref["pending_operation"] = None
            
        elif message_lower in ['n', 'no', '否', '取消', '不']:
            # 拒绝操作
            session.reject_operation(pending_op.operation_id)
            
            response = "操作已取消。您可以提出其他需求。"
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})
            session.add_message("assistant", response)
            
            status = "操作已取消"
            pending_operation_ref["pending_operation"] = None
        else:
            # 不明确的回答
            response = "请明确回答 Y（确认）或 N（取消）"
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})
            status = "等待确认..."
        
        # 更新配置显示
        config_display = {}
        if manager.current_config:
            config_display = format_config_for_display(manager.current_config)
        
        return "", history, status, config_display
    except Exception as e:
        error_msg = f"处理确认时出错: {str(e)}"
        print(f"[handle_confirmation] {error_msg}")
        return "", history, error_msg, {}


# ============ 记忆功能 ============

def handle_memory_search(query: str, memory) -> str:
    """处理记忆检索"""
    try:
        if not memory:
            return "记忆功能未启用"
        
        if not query.strip():
            return "请输入检索关键词"
        
        results = memory.search_similar(query, n_results=3)
        
        if not results:
            return "未找到相似的历史配置"
        
        output = "🔍 检索结果:\n\n"
        for i, entry in enumerate(results, 1):
            output += f"{i}. **{entry.case_name}**\n"
            output += f"   描述: {entry.user_prompt}\n"
            output += f"   时间: {entry.timestamp}\n\n"
        
        return output
    except Exception as e:
        return f"检索出错: {str(e)}"


def handle_export_memory(memory) -> str:
    """处理导出记忆"""
    try:
        if not memory:
            return "记忆功能未启用"
        
        export_file = memory.export_memory()
        return f"✅ 记忆已导出到: {export_file}"
    except Exception as e:
        return f"❌ 导出失败: {str(e)}"


def handle_show_stats(session, memory) -> str:
    """显示统计信息"""
    try:
        stats = session.get_statistics()
        
        output = "📊 会话统计\n\n"
        output += f"会话ID: {stats['session_id']}\n"
        output += f"总消息数: {stats['total_messages']}\n"
        output += f"用户消息: {stats['user_messages']}\n"
        output += f"助手消息: {stats['assistant_messages']}\n"
        output += f"当前算例: {stats['current_case'] or '无'}\n"
        output += f"对话阶段: {stats['conversation_stage']}\n"
        output += f"待确认操作: {stats['pending_operations']}\n"
        
        if memory:
            mem_stats = memory.get_statistics()
            output += f"\n记忆库统计:\n"
            output += f"  总记忆数: {mem_stats['total_memories']}\n"
            output += f"  唯一算例: {mem_stats['unique_cases']}\n"
        
        return output
    except Exception as e:
        return f"获取统计信息失败: {str(e)}"


# ============ 辅助方法 ============

def render_step_progress(current_step: int) -> str:
    """渲染步骤进度条HTML"""
    steps = ["场景选择", "几何参数", "网格设置", "边界条件", "求解器", "审查运行"]
    html = '<div style="display:flex;justify-content:space-between;margin:10px 0;">'
    for i, step in enumerate(steps):
        color = "#2196F3" if i == current_step else ("#4CAF50" if i < current_step else "#ddd")
        text_color = "white" if i <= current_step else "#666"
        html += f'<div style="flex:1;text-align:center;padding:8px;margin:2px;'
        html += f'background:{color};color:{text_color};border-radius:4px;">'
        html += f'{i+1}. {step}</div>'
    html += '</div>'
    return html


def get_quick_start_content() -> str:
    """生成快速入门内容"""
    return """
## 什么是CFD仿真？

**计算流体力学 (CFD)** 是利用计算机数值方法求解流体运动方程的技术。
简单来说，就是用计算机模拟流体（水、空气等）的运动。

### 仿真流程

1. **定义问题** - 选择要模拟的物理场景
2. **设置几何** - 确定计算域的形状和大小
3. **生成网格** - 将计算域划分为小单元
4. **设置边界** - 定义入口、出口、壁面等条件
5. **选择求解器** - 选择合适的数学模型
6. **运行计算** - 求解并监控收敛
7. **查看结果** - 可视化分析结果

### 使用本系统

- **新手推荐**：使用 "向导模式" 标签页，跟随引导逐步完成
- **有经验用户**：使用 "智能对话" 标签页，直接用自然语言描述需求
"""


def format_glossary() -> str:
    """格式化术语表显示"""
    try:
        from ..core.teaching_engine import TeachingEngine
        teacher = TeachingEngine()
        glossary = teacher.get_glossary()
        output = "## CFD 术语表\n\n"
        for term, info in glossary.items():
            if isinstance(info, dict):
                output += f"### {info.get('cn', term)} ({info.get('en', term)})\n"
                output += f"{info.get('desc', info.get('description', ''))}\n\n"
            else:
                output += f"### {term}\n{info}\n\n"
        return output
    except Exception as e:
        return f"术语表加载中... ({str(e)})"


def search_glossary(query: str) -> str:
    """搜索术语表"""
    if not query.strip():
        return format_glossary()
    try:
        from ..core.teaching_engine import TeachingEngine
        teacher = TeachingEngine()
        # 如果有 search_glossary 方法就用，否则简单过滤
        if hasattr(teacher, 'search_glossary'):
            results = teacher.search_glossary(query)
            if results:
                output = f"## 搜索结果: \"{query}\"\n\n"
                for term, info in results.items():
                    if isinstance(info, dict):
                        output += f"### {info.get('cn', term)} ({info.get('en', term)})\n"
                        output += f"{info.get('desc', info.get('description', ''))}\n\n"
                    else:
                        output += f"### {term}\n{info}\n\n"
                return output
        return f"未找到与 \"{query}\" 相关的术语"
    except Exception as e:
        return f"搜索失败: {str(e)}"


def get_best_practices_content() -> str:
    """生成最佳实践内容"""
    return """
## CFD 仿真最佳实践

### 网格生成
- 2D问题至少使用 50×50 网格
- 3D问题至少使用 50×50×50 网格
- 在梯度大的区域（壁面、尾流）局部加密
- 网格长宽比尽量小于 10

### 时间步长选择
- 确保库朗数 Co < 1（显式格式）
- 估算方法：Δt < Δx / U_max
- 不确定时先使用小时间步测试

### 边界条件设置
- 入口固定速度，出口固定压力
- 壁面使用无滑移条件（noSlip）
- 确保质量守恒（入口流量 = 出口流量）

### 收敛判断
- 残差下降到 1e-6 以下
- 监控物理量（力、流量）是否稳定
- 至少运行到流动达到统计稳态

### 验证与确认
- 进行网格无关性验证
- 与实验数据或文献结果对比
- 检查物理合理性
"""


def get_scenario_detail(scenario_id: str) -> str:
    """获取场景详细说明"""
    try:
        from ..core.wizard_engine import SCENARIO_TEMPLATES
        if scenario_id in SCENARIO_TEMPLATES:
            template = SCENARIO_TEMPLATES[scenario_id]
            return f"""
**{template['icon']} {template['name']}** ({template['name_en']})

{template['description']}

**难度**: {template['difficulty']}
**推荐求解器**: {template['recommended_solver']}
**物理类型**: {template['physics_type']}

**关键参数**: {', '.join(template.get('key_parameters', []))}
"""
        return "请选择一个场景查看详细说明..."
    except Exception as e:
        return f"加载场景信息失败: {str(e)}"


def generate_mesh_preview(nx: int, ny: int, nz: int) -> Any:
    """生成网格预览图"""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, ax = plt.subplots(figsize=(6, 5))
        
        # 绘制网格线
        for i in range(nx + 1):
            ax.axvline(x=i/nx, color='gray', linewidth=0.5)
        for j in range(ny + 1):
            ax.axhline(y=j/ny, color='gray', linewidth=0.5)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.set_title(f'网格预览: {nx}×{ny}' + (f'×{nz}' if nz > 1 else ''))
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        
        total_cells = nx * ny * nz
        ax.text(0.5, -0.1, f'总网格数: {total_cells}', 
               transform=ax.transAxes, ha='center')
        
        plt.tight_layout()
        return fig
    except Exception as e:
        print(f"生成网格预览失败: {e}")
        return None


def generate_residual_plot() -> Any:
    """生成残差曲线图"""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        # 模拟残差数据
        iterations = np.arange(0, 1000, 10)
        residual_u = 1e-1 * np.exp(-iterations/200) + 1e-8
        residual_p = 1e-1 * np.exp(-iterations/150) + 1e-7
        
        ax1.semilogy(iterations, residual_u, 'b-', label='U')
        ax1.semilogy(iterations, residual_p, 'r-', label='p')
        ax1.set_xlabel('迭代步数')
        ax1.set_ylabel('残差')
        ax1.set_title('残差收敛曲线')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 库朗数
        courant = 0.5 + 0.3 * np.sin(iterations/50) * np.exp(-iterations/500)
        ax2.plot(iterations, courant, 'g-', label='Co')
        ax2.axhline(y=1.0, color='r', linestyle='--', label='Co=1')
        ax2.set_xlabel('迭代步数')
        ax2.set_ylabel('库朗数')
        ax2.set_title('库朗数变化')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    except Exception as e:
        print(f"生成残差图失败: {e}")
        return None


def get_teaching_for_step(step_name: str) -> str:
    """获取步骤的教学说明"""
    try:
        from ..core.teaching_engine import TeachingEngine
        teacher = TeachingEngine()
        return teacher.explain_step(step_name)
    except Exception as e:
        return f"加载教学说明... ({str(e)})"


# ============ 向导模式回调 ============

def wizard_select_scenario(
    scenario_id: str,
    wizard_engine_ref: Dict,
    wizard_current_step_ref: Dict
) -> Tuple[str, str]:
    """向导：选择场景"""
    try:
        from ..core.wizard_engine import create_wizard, WizardStep
        
        if wizard_engine_ref.get("engine") is None:
            wizard_engine_ref["engine"] = create_wizard()
        
        wizard_engine = wizard_engine_ref["engine"]
        
        # 验证并保存
        is_valid, errors, suggestions = wizard_engine.validate_step(
            WizardStep.SCENARIO, {"scenario_id": scenario_id}
        )
        
        if not is_valid:
            return get_scenario_detail(scenario_id), "❌ " + "; ".join(errors)
        
        # 保存并前进
        wizard_engine.advance({"scenario_id": scenario_id})
        wizard_current_step_ref["step"] = 1
        
        # 获取几何步骤的教学说明
        from ..core.teaching_engine import TeachingEngine
        teacher = TeachingEngine()
        teaching = teacher.explain_step("geometry")
        
        detail = get_scenario_detail(scenario_id)
        return detail, f"✅ 已选择场景，请点击'下一步'继续\n\n{teaching[:200]}..."
    except Exception as e:
        return f"选择场景失败: {str(e)}", ""


def wizard_next_step(
    current_step: int,
    args: tuple,
    wizard_engine_ref: Dict,
    wizard_current_step_ref: Dict
) -> Dict:
    """向导：下一步"""
    try:
        from ..core.wizard_engine import WizardStep
        
        outputs = {}
        wizard_engine = wizard_engine_ref.get("engine")
        
        if wizard_engine is None:
            return {"validation_output": "❌ 向导引擎未初始化"}
        
        # 根据当前步骤保存参数
        if current_step == 1:  # 几何参数
            geom_params = {
                "L": args[0] if len(args) > 0 else 1.0,
                "W": args[1] if len(args) > 1 else 1.0,
                "H": args[2] if len(args) > 2 else 0.1
            }
            is_valid, errors, suggestions = wizard_engine.validate_step(
                WizardStep.GEOMETRY, geom_params
            )
            if not is_valid:
                return {**outputs, "validation_output": "❌ " + "; ".join(errors)}
            wizard_engine.advance(geom_params)
            
        elif current_step == 2:  # 网格设置
            mesh_params = {
                "nx": int(args[0]) if len(args) > 0 else 20,
                "ny": int(args[1]) if len(args) > 1 else 20,
                "nz": int(args[2]) if len(args) > 2 else 1
            }
            is_valid, errors, suggestions = wizard_engine.validate_step(
                WizardStep.MESH, mesh_params
            )
            if not is_valid:
                return {**outputs, "validation_output": "❌ " + "; ".join(errors)}
            wizard_engine.advance(mesh_params)
            
        elif current_step == 3:  # 边界条件
            wizard_engine.advance({})
            
        elif current_step == 4:  # 求解器配置
            solver_params = {
                "solver_name": args[0] if len(args) > 0 else "icoFoam",
                "endTime": args[1] if len(args) > 1 else 0.5,
                "deltaT": args[2] if len(args) > 2 else 0.005,
                "nu": args[3] if len(args) > 3 else 0.01
            }
            is_valid, errors, suggestions = wizard_engine.validate_step(
                WizardStep.SOLVER, solver_params
            )
            if not is_valid:
                return {**outputs, "validation_output": "❌ " + "; ".join(errors)}
            wizard_engine.advance(solver_params)
        
        wizard_current_step_ref["step"] = min(current_step + 1, MAX_WIZARD_STEPS - 1)
        
        # 返回各组的可见性状态
        step_groups = [gr.update(visible=False) for _ in range(MAX_WIZARD_STEPS)]
        # 防御性 clamp：确保索引在有效范围内
        safe_index = max(0, min(wizard_current_step_ref["step"], MAX_WIZARD_STEPS - 1))
        step_groups[safe_index] = gr.update(visible=True)
        
        return {
            "step_progress": render_step_progress(wizard_current_step_ref["step"]),
            "validation_output": "✅ 步骤完成",
            **{f"step{i+1}_group": step_groups[i] for i in range(6)}
        }
    except Exception as e:
        return {"validation_output": f"❌ 出错: {str(e)}"}


def wizard_prev_step(
    current_step: int,
    wizard_engine_ref: Dict,
    wizard_current_step_ref: Dict
) -> Dict:
    """向导：上一步"""
    try:
        wizard_engine = wizard_engine_ref.get("engine")
        
        if current_step > 0 and wizard_engine:
            wizard_current_step_ref["step"] = max(current_step - 1, 0)
            wizard_engine.go_back()
        
        new_step = wizard_current_step_ref.get("step", 0)
        # 防御性 clamp：确保索引在有效范围内
        new_step = max(0, min(new_step, MAX_WIZARD_STEPS - 1))
        
        # 返回各组的可见性状态
        step_groups = [gr.update(visible=False) for _ in range(MAX_WIZARD_STEPS)]
        step_groups[new_step] = gr.update(visible=True)
        
        return {
            "step_progress": render_step_progress(new_step),
            "validation_output": "",
            **{f"step{i+1}_group": step_groups[i] for i in range(6)}
        }
    except Exception as e:
        return {"validation_output": f"❌ 出错: {str(e)}"}


def wizard_run_simulation(wizard_engine_ref: Dict) -> str:
    """向导：运行仿真"""
    try:
        wizard_engine = wizard_engine_ref.get("engine")
        
        if wizard_engine is None:
            return "请先完成向导配置"
        
        config = wizard_engine.build_config()
        
        # 显示配置摘要
        summary = f"""
## 配置摘要

**算例类型**: {config.get('physics_type', 'unknown')}
**求解器**: {config.get('solver', {}).get('name', 'unknown')}
**几何尺寸**: {config.get('geometry', {}).get('L', 1.0)} x {config.get('geometry', {}).get('W', 1.0)} x {config.get('geometry', {}).get('H', 0.1)}
**网格**: {config.get('geometry', {}).get('nx', 20)} x {config.get('geometry', {}).get('ny', 20)} x {config.get('geometry', {}).get('nz', 1)}
**结束时间**: {config.get('solver', {}).get('endTime', 0.5)}
**时间步长**: {config.get('solver', {}).get('deltaT', 0.005)}

✅ 配置已生成，可以开始运行仿真
"""
        return summary
    except Exception as e:
        return f"运行仿真失败: {str(e)}"


# ============ 学习中心回调 ============

def get_scenario_explanation(scenario: str) -> str:
    """获取场景说明"""
    mapping = {
        "方腔驱动流": "cavity",
        "管道流动": "pipe",
        "圆柱绕流": "cylinder",
        "后台阶流": "backward_step",
        "平板通道流": "channel",
        "自然对流": "natural_convection",
        "溃坝": "dam_break",
        "翼型绕流": "airfoil"
    }
    scenario_id = mapping.get(scenario, "cavity")
    try:
        from ..core.teaching_engine import TeachingEngine
        teacher = TeachingEngine()
        return teacher.get_best_practice(scenario_id)
    except Exception as e:
        return f"加载场景说明失败: {str(e)}"


# ============ 监控回调 ============

def refresh_monitor() -> Tuple[Any, str]:
    """刷新监控状态"""
    fig = generate_residual_plot()
    return fig, "日志更新...\nTime=0.1s, Co=0.45\nTime=0.2s, Co=0.42"


# ============ 网格预览更新 ============

def update_mesh_preview(nx: int, ny: int, nz: int) -> Tuple[Any, str]:
    """更新网格预览"""
    fig = generate_mesh_preview(nx, ny, nz)
    total = nx * ny * nz
    return fig, f"总网格数: {total}"
