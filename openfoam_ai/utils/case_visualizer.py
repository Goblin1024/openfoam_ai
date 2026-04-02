"""
Case Visualizer - 生成算例预览图
无需运行 OpenFOAM，生成网格和流场示意图
"""

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json


class CaseVisualizer:
    """算例可视化器"""
    
    def __init__(self, case_path: Path):
        self.case_path = Path(case_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载算例配置"""
        info_file = self.case_path / ".case_info.json"
        if info_file.exists():
            with open(info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def visualize(self, output_path: Optional[Path] = None) -> Path:
        """
        生成算例可视化预览
        
        Returns:
            生成的图片路径
        """
        if output_path is None:
            output_path = self.case_path / "preview.png"
        
        # 创建图形
        fig = plt.figure(figsize=(16, 10))
        
        # 1. 几何和网格预览
        ax1 = fig.add_subplot(2, 3, 1)
        self._plot_geometry(ax1)
        ax1.set_title("Geometry & Mesh", fontsize=12, fontweight='bold')
        
        # 2. 边界条件示意
        ax2 = fig.add_subplot(2, 3, 2)
        self._plot_boundary_conditions(ax2)
        ax2.set_title("Boundary Conditions", fontsize=12, fontweight='bold')
        
        # 3. 初始流场示意
        ax3 = fig.add_subplot(2, 3, 3)
        self._plot_initial_flow(ax3)
        ax3.set_title("Initial Flow Field", fontsize=12, fontweight='bold')
        
        # 4. 参数摘要
        ax4 = fig.add_subplot(2, 3, 4)
        self._plot_parameters(ax4)
        
        # 5. 求解器设置
        ax5 = fig.add_subplot(2, 3, 5)
        self._plot_solver_settings(ax5)
        
        # 6. 预期结果示意（卡门涡街等）
        ax6 = fig.add_subplot(2, 3, 6)
        self._plot_expected_results(ax6)
        ax6.set_title("Expected Results", fontsize=12, fontweight='bold')
        
        # 添加总标题
        case_name = self.case_path.name
        physics_type = self.config.get('physics_type', 'N/A')
        fig.suptitle(f"OpenFOAM Case Preview: {case_name} ({physics_type})", 
                     fontsize=14, fontweight='bold', y=0.98)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def _plot_geometry(self, ax: plt.Axes) -> None:
        """绘制几何和网格"""
        ax.set_xlim(-0.5, 1.5)
        ax.set_ylim(-0.5, 1.5)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        
        # 获取几何信息
        geom = self.config.get('geometry', {})
        dims = geom.get('dimensions', {'L': 1.0, 'W': 1.0})
        mesh = geom.get('mesh_resolution', {'nx': 20, 'ny': 20})
        
        L = dims.get('L', 1.0)
        W = dims.get('W', 1.0)
        
        # 绘制计算域
        rect = patches.Rectangle((0, 0), L, W, linewidth=2, 
                                  edgecolor='black', facecolor='lightblue', alpha=0.3)
        ax.add_patch(rect)
        
        # 如果有圆柱，绘制圆柱
        bc = self.config.get('boundary_conditions', {})
        if any('cylinder' in k.lower() for k in bc.keys()):
            # 圆柱绕流 - 在中心绘制圆柱
            cylinder = patches.Circle((L*0.3, W*0.5), 0.1, 
                                        linewidth=2, edgecolor='red', 
                                        facecolor='gray', label='Cylinder')
            ax.add_patch(cylinder)
            ax.annotate('Cylinder', xy=(L*0.3, W*0.5), fontsize=9, ha='center')
        
        # 绘制网格示意
        nx, ny = mesh.get('nx', 20), mesh.get('ny', 20)
        for i in range(0, nx+1, max(1, nx//5)):
            x = i * L / nx
            ax.axvline(x=x, color='gray', alpha=0.3, linewidth=0.5)
        for j in range(0, ny+1, max(1, ny//5)):
            y = j * W / ny
            ax.axhline(y=y, color='gray', alpha=0.3, linewidth=0.5)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
    
    def _plot_boundary_conditions(self, ax: plt.Axes) -> None:
        """绘制边界条件"""
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        
        bc = self.config.get('boundary_conditions', {})
        
        # 绘制方框表示边界
        rect = patches.Rectangle((0.2, 0.2), 0.6, 0.6, linewidth=2, 
                                  edgecolor='black', facecolor='none')
        ax.add_patch(rect)
        
        # 标注边界条件
        y_pos = 0.9
        for name, config in bc.items():
            bc_type = config.get('type', 'unknown') if isinstance(config, dict) else str(config)
            value = config.get('value', 'N/A') if isinstance(config, dict) else 'N/A'
            text = f"{name}: {bc_type} = {value}"
            ax.text(0.5, y_pos, text, ha='center', fontsize=8, 
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            y_pos -= 0.15
    
    def _plot_initial_flow(self, ax: plt.Axes) -> None:
        """绘制初始流场"""
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        
        # 创建网格
        x = np.linspace(0, 1, 20)
        y = np.linspace(0, 1, 10)
        X, Y = np.meshgrid(x, y)
        
        # 获取入口速度
        bc = self.config.get('boundary_conditions', {})
        U_inlet = 1.0  # 默认
        for name, config in bc.items():
            if 'inlet' in name.lower():
                if isinstance(config, dict):
                    val = config.get('value', 1.0)
                    if isinstance(val, (int, float)):
                        U_inlet = val
                    elif isinstance(val, list) and len(val) > 0:
                        U_inlet = val[0]
        
        # 绘制速度矢量
        U = np.ones_like(X) * U_inlet
        V = np.zeros_like(Y)
        
        # 如果有圆柱，添加扰动
        if any('cylinder' in k.lower() for k in bc.keys()):
            # 圆柱后方添加涡旋示意
            mask = X > 0.4
            V[mask] = 0.1 * np.sin(5 * Y[mask]) * np.exp(-(X[mask] - 0.4) * 3)
        
        ax.quiver(X, Y, U, V, alpha=0.6)
        ax.set_title(f"U_inlet = {U_inlet} m/s")
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
    
    def _plot_parameters(self, ax: plt.Axes) -> None:
        """绘制参数表格"""
        ax.axis('off')
        
        solver = self.config.get('solver', {})
        if isinstance(solver, str):
            solver = {'name': solver}
        geom = self.config.get('geometry', {})
        mesh = geom.get('mesh_resolution', {}) if isinstance(geom, dict) else {}
        
        params = [
            ["Parameter", "Value"],
            ["Solver", solver.get('name', 'N/A')],
            ["Physics", self.config.get('physics_type', 'N/A')],
            ["End Time", str(solver.get('endTime', 'N/A'))],
            ["Delta T", str(solver.get('deltaT', 'N/A'))],
            ["Mesh", f"{mesh.get('nx', 'N/A')} x {mesh.get('ny', 'N/A')}"],
            ["Viscosity (nu)", str(self.config.get('nu', 'N/A'))],
        ]
        
        table = ax.table(cellText=params, loc='center', cellLoc='left')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        
        # 设置表头样式
        for i in range(len(params[0])):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')
    
    def _plot_solver_settings(self, ax: plt.Axes) -> None:
        """绘制求解器设置"""
        ax.axis('off')
        
        solver = self.config.get('solver', {})
        if isinstance(solver, str):
            solver = {'name': solver}
        
        settings = [
            f"Solver: {solver.get('name', 'N/A')}",
            f"",
            f"Time Settings:",
            f"  End Time: {solver.get('endTime', 'N/A')} s",
            f"  Delta T: {solver.get('deltaT', 'N/A')} s",
            f"",
            f"Expected Steps: {int(solver.get('endTime', 0) / solver.get('deltaT', 1)) if solver.get('deltaT', 0) != 0 else 'N/A'}",
        ]
        
        ax.text(0.1, 0.9, '\n'.join(settings), fontsize=10, 
               verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
    
    def _plot_expected_results(self, ax: plt.Axes) -> None:
        """绘制预期结果示意"""
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, 0.5)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # 获取边界条件判断流动类型
        bc = self.config.get('boundary_conditions', {})
        
        if any('cylinder' in k.lower() for k in bc.keys()):
            # 卡门涡街示意
            ax.set_title("Expected: Karman Vortex Street", color='blue')
            
            # 绘制圆柱
            cylinder = patches.Circle((0.2, 0), 0.08, 
                                        facecolor='gray', edgecolor='black')
            ax.add_patch(cylinder)
            
            # 绘制涡旋
            x_vortex = np.linspace(0.35, 0.9, 8)
            for i, x in enumerate(x_vortex):
                y_offset = 0.15 * ((-1) ** i)
                # 上涡旋
                if i % 2 == 0:
                    vortex = patches.FancyArrowPatch((x, y_offset), (x+0.05, y_offset-0.05),
                                                      arrowstyle='->', color='red', 
                                                      mutation_scale=15, linewidth=2)
                    ax.add_patch(vortex)
                    ax.annotate('O', xy=(x, y_offset), fontsize=20, color='red', ha='center')
                else:
                    vortex = patches.FancyArrowPatch((x, -y_offset), (x+0.05, -y_offset+0.05),
                                                      arrowstyle='->', color='blue',
                                                      mutation_scale=15, linewidth=2)
                    ax.add_patch(vortex)
                    ax.annotate('O', xy=(x, -y_offset), fontsize=20, color='blue', ha='center')
            
            ax.annotate('Vortex Shedding\nPattern', xy=(0.5, 0.4), fontsize=10, ha='center')
            
        else:
            # 一般流动示意
            ax.set_title("Expected: Steady Flow", color='green')
            x = np.linspace(0, 1, 10)
            y = np.zeros_like(x)
            ax.quiver(x, y, np.ones_like(x), y, scale=5, color='blue', alpha=0.6)
            ax.annotate('Flow Direction ->', xy=(0.5, 0.2), fontsize=10, ha='center')


def generate_preview(case_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    为算例生成预览图
    
    Args:
        case_path: 算例目录路径
        output_path: 输出图片路径（可选）
    
    Returns:
        生成的图片路径
    """
    visualizer = CaseVisualizer(case_path)
    return visualizer.visualize(output_path)


class MeshPreviewGenerator:
    """
    网格预览生成器
    
    为向导模式提供网格密度的可视化预览。
    """
    
    def generate_2d_mesh_preview(self, nx: int, ny: int, 
                                  L: float = 1.0, W: float = 1.0) -> plt.Figure:
        """生成2D网格预览图
        
        显示网格线框图，让用户直观看到网格密度。
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, ax = plt.subplots(figsize=(6, 6 * W / L))
        
        # 绘制网格线
        x = np.linspace(0, L, nx + 1)
        y = np.linspace(0, W, ny + 1)
        
        # 水平线
        for yi in y:
            ax.plot([0, L], [yi, yi], 'b-', linewidth=0.5, alpha=0.6)
        # 垂直线
        for xi in x:
            ax.plot([xi, xi], [0, W], 'b-', linewidth=0.5, alpha=0.6)
        
        # 边界高亮
        ax.plot([0, L, L, 0, 0], [0, 0, W, W, 0], 'k-', linewidth=2)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_title(f'Mesh Preview: {nx}×{ny} = {nx*ny} cells')
        ax.set_aspect('equal')
        ax.grid(False)
        
        plt.tight_layout()
        return fig
    
    def generate_mesh_quality_preview(self, nx: int, ny: int, nz: int = 1, 
                                       L: float = 1.0, W: float = 1.0, H: float = 0.1) -> plt.Figure:
        """生成网格质量预览信息
        
        Returns:
            dict with quality metrics visualization
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        
        total_cells = nx * ny * max(nz, 1)
        dx = L / nx
        dy = W / ny
        aspect_ratio = max(dx/dy, dy/dx) if min(dx, dy) > 0 else float('inf')
        
        # 生成包含网格质量信息的图
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        # 左图：网格预览（只显示局部）
        # 显示左下角的一小块网格细节
        show_nx = min(nx, 10)
        show_ny = min(ny, 10)
        x = np.linspace(0, L * show_nx/nx, show_nx + 1)
        y = np.linspace(0, W * show_ny/ny, show_ny + 1)
        for yi in y:
            ax1.plot([x[0], x[-1]], [yi, yi], 'b-', linewidth=0.5)
        for xi in x:
            ax1.plot([xi, xi], [y[0], y[-1]], 'b-', linewidth=0.5)
        ax1.set_title(f'Mesh Local Preview ({show_nx}×{show_ny})')
        ax1.set_aspect('equal')
        
        # 右图：网格质量指标
        metrics = ['Total Cells', 'Aspect Ratio', 'dx (m)', 'dy (m)']
        values = [total_cells, f'{aspect_ratio:.2f}', f'{dx:.4f}', f'{dy:.4f}']
        colors = ['green' if total_cells >= 400 else 'red',
                  'green' if aspect_ratio < 5 else 'orange',
                  'blue', 'blue']
        
        ax2.barh(metrics, [1]*4, color=colors, alpha=0.3)
        for i, (m, v) in enumerate(zip(metrics, values)):
            ax2.text(0.5, i, str(v), ha='center', va='center', fontsize=14, fontweight='bold')
        ax2.set_xlim(0, 1)
        ax2.set_title('Mesh Quality Metrics')
        ax2.set_xticks([])
        
        plt.tight_layout()
        return fig


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        case_path = Path(sys.argv[1])
        if case_path.exists():
            output = generate_preview(case_path)
            print(f"Preview generated: {output}")
        else:
            print(f"Case not found: {case_path}")
    else:
        print("Usage: python case_visualizer.py <case_path>")
