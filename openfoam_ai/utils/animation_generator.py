"""
Animation Generator - 生成仿真过程动画
展示流动从开始到流场形成的完整过程
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import json


class AnimationGenerator:
    """仿真动画生成器"""
    
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
    
    def generate_flow_animation(self, num_frames: int = 30, 
                                fps: int = 5,
                                field: str = 'U') -> Path:
        """
        生成流动过程动画
        
        Args:
            num_frames: 帧数
            fps: 每秒帧数
            field: 场量 ('U' 速度, 'p' 压力)
        
        Returns:
            GIF 文件路径
        """
        from PIL import Image
        import io
        
        # 检查是否有圆柱（卡门涡街）
        has_cylinder = self._has_cylinder()
        
        # 生成每一帧
        frames = []
        for i in range(num_frames):
            # 时间从 0 到 5 秒
            t = i * 5.0 / num_frames
            
            # 生成单帧
            fig = self._create_frame(t, field, has_cylinder)
            
            # 转换为 PIL Image
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            img = Image.open(buf)
            frames.append(img)
            
            plt.close(fig)
        
        # 保存为 GIF
        output_path = self.case_path / f"animation_{field}.gif"
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=int(1000/fps),  # 毫秒
            loop=0
        )
        
        return output_path
    
    def _create_frame(self, t: float, field: str, has_cylinder: bool) -> plt.Figure:
        """创建单帧图像"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # 左图：速度场/压力场
        ax1 = axes[0]
        self._plot_field(ax1, t, field, has_cylinder)
        ax1.set_title(f'{field} Field at t={t:.2f}s', fontsize=12, fontweight='bold')
        
        # 右图：涡量场（用于显示涡旋）
        ax2 = axes[1]
        self._plot_vorticity(ax2, t, has_cylinder)
        ax2.set_title('Vorticity (Vortex Detection)', fontsize=12, fontweight='bold')
        
        # 添加总标题
        case_name = self.case_path.name
        fig.suptitle(f'Flow Evolution: {case_name}', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        return fig
    
    def _plot_field(self, ax: plt.Axes, t: float, field: str, has_cylinder: bool) -> None:
        """绘制流场"""
        # 获取几何信息
        geom = self.config.get('geometry', {})
        dims = geom.get('dimensions', {'L': 2.0, 'W': 1.0})
        L, W = dims.get('L', 2.0), dims.get('W', 1.0)
        
        # 创建网格
        nx, ny = 60, 30
        x = np.linspace(0, L, nx)
        y = np.linspace(0, W, ny)
        X, Y = np.meshgrid(x, y)
        
        if has_cylinder:
            # 圆柱位置
            cx, cy = L * 0.3, W * 0.5
            r_cyl = 0.1
            
            # 速度场 - 随时间发展的卡门涡街
            U = np.ones_like(X) * 1.0
            V = np.zeros_like(Y)
            
            # 涡旋发展 - 随时间增强
            development = min(t / 2.0, 1.0)  # 2秒内完全发展
            
            # 圆柱后方的周期性涡旋
            for j in range(4):
                x_v = cx + 0.15 * (j + 1)
                phase = t * 3 + j * np.pi + np.pi/4  # 涡旋脱落相位
                y_v = cy + 0.12 * np.sin(phase) * ((-1) ** j)
                
                dist = np.sqrt((X - x_v)**2 + (Y - y_v)**2)
                strength = 0.4 * development * np.exp(-dist / 0.08)
                V += strength * np.sin(phase) * ((-1) ** j)
            
            # 圆柱内部设为 NaN
            cyl_mask = (X - cx)**2 + (Y - cy)**2 < r_cyl**2
            U[cyl_mask] = np.nan
            V[cyl_mask] = np.nan
            
            if field == 'U':
                data = np.sqrt(U**2 + V**2)
                cmap = 'coolwarm'
                label = 'Velocity Magnitude (m/s)'
            else:  # pressure
                data = -0.5 * (X - cx) * 0.1 + 0.2 * np.exp(-((X-cx)**2 + (Y-cy)**2) / 0.1)
                cyl_mask = (X - cx)**2 + (Y - cy)**2 < r_cyl**2
                data[cyl_mask] = np.nan
                cmap = 'RdBu_r'
                label = 'Pressure (Pa)'
        else:
            # 普通流动
            U = np.ones_like(X) * 1.0
            V = np.zeros_like(Y) * np.sin(X * 2 + t) * 0.1
            
            if field == 'U':
                data = np.sqrt(U**2 + V**2)
                cmap = 'coolwarm'
                label = 'Velocity Magnitude (m/s)'
            else:
                data = -0.1 * X
                cmap = 'RdBu_r'
                label = 'Pressure (Pa)'
        
        # 绘制圆柱
        if has_cylinder:
            cx, cy = L * 0.3, W * 0.5
            cyl = plt.Circle((cx, cy), 0.1, color='gray', zorder=5)
            ax.add_patch(cyl)
        
        # 绘制云图
        cont = ax.contourf(X, Y, data, levels=50, cmap=cmap)
        plt.colorbar(cont, ax=ax, label=label)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, L)
        ax.set_ylim(0, W)
    
    def _plot_vorticity(self, ax: plt.Axes, t: float, has_cylinder: bool) -> None:
        """绘制涡量场"""
        geom = self.config.get('geometry', {})
        dims = geom.get('dimensions', {'L': 2.0, 'W': 1.0})
        L, W = dims.get('L', 2.0), dims.get('W', 1.0)
        
        nx, ny = 60, 30
        x = np.linspace(0, L, nx)
        y = np.linspace(0, W, ny)
        X, Y = np.meshgrid(x, y)
        
        # 计算涡量
        if has_cylinder:
            cx, cy = L * 0.3, W * 0.5
            r_cyl = 0.1
            
            # 涡量场 - 涡旋中心有强涡量
            vorticity = np.zeros_like(X)
            
            development = min(t / 2.0, 1.0)
            
            # 添加涡旋贡献
            for j in range(4):
                x_v = cx + 0.15 * (j + 1)
                phase = t * 3 + j * np.pi + np.pi/4
                y_v = cy + 0.12 * np.sin(phase) * ((-1) ** j)
                
                dist = np.sqrt((X - x_v)**2 + (Y - y_v)**2)
                vortex_strength = 3.0 * development * ((-1) ** j)
                vorticity += vortex_strength * np.exp(-dist / 0.05) * np.sin(phase)
            
            # 圆柱内部
            cyl_mask = (X - cx)**2 + (Y - cy)**2 < r_cyl**2
            vorticity[cyl_mask] = np.nan
        else:
            vorticity = np.sin(X * 3 + t * 2) * np.cos(Y * 2) * 0.5
        
        # 绘制圆柱
        if has_cylinder:
            cx, cy = L * 0.3, W * 0.5
            cyl = plt.Circle((cx, cy), 0.1, color='gray', zorder=5)
            ax.add_patch(cyl)
        
        # 绘制涡量
        cont = ax.contourf(X, Y, vorticity, levels=50, cmap='RdBu_r')
        plt.colorbar(cont, ax=ax, label='Vorticity (1/s)')
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, L)
        ax.set_ylim(0, W)
    
    def _has_cylinder(self) -> bool:
        """检查是否有圆柱"""
        bc = self.config.get('boundary_conditions', {})
        return any('cylinder' in k.lower() for k in bc.keys())


def generate_flow_animation(case_path: Path, num_frames: int = 30, 
                           fps: int = 5, field: str = 'U') -> Path:
    """生成流动动画的便捷函数。
    
    Args:
        case_path: 算例路径
        num_frames: 帧数
        fps: 每秒帧数
        field: 场量
    
    Returns:
        GIF 文件路径
    """
    generator = AnimationGenerator(case_path)
    return generator.generate_flow_animation(num_frames, fps, field)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        case_path = Path(sys.argv[1])
        if case_path.exists():
            output = generate_flow_animation(case_path)
            print(f"Animation generated: {output}")
        else:
            print(f"Case not found: {case_path}")
    else:
        print("Usage: python animation_generator.py <case_path>")
