"""
OpenFOAM Simulator - 运行仿真并生成结果
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
import time
import threading


class OpenFOAMSimulator:
    """OpenFOAM 仿真运行器"""
    
    def __init__(self, case_path: Path):
        self.case_path = Path(case_path)
        self.process: Optional[subprocess.Popen] = None
        self.log_file: Optional[Path] = None
        self.is_running = False
        
    def check_openfoam(self) -> bool:
        """检查 OpenFOAM 是否安装"""
        return shutil.which("blockMesh") is not None
    
    def generate_mesh(self) -> Tuple[bool, str]:
        """生成网格"""
        if not self.check_openfoam():
            return False, "OpenFOAM not found. Please install OpenFOAM."
        
        try:
            # 运行 blockMesh
            result = subprocess.run(
                ["blockMesh"],
                cwd=self.case_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, "Mesh generated successfully"
            else:
                return False, f"blockMesh failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "blockMesh timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def run_simulation(self, max_time: Optional[float] = None) -> Tuple[bool, str]:
        """运行仿真"""
        if not self.check_openfoam():
            return False, "OpenFOAM not found"
        
        # 获取求解器名称
        solver = self._get_solver()
        if not solver:
            return False, "Solver not specified in case"
        
        try:
            self.is_running = True
            self.log_file = self.case_path / "logs" / f"{solver}.log"
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 启动求解器
            with open(self.log_file, 'w') as log:
                self.process = subprocess.Popen(
                    [solver],
                    cwd=self.case_path,
                    stdout=log,
                    stderr=subprocess.STDOUT
                )
            
            # 等待完成或超时
            if max_time:
                self.process.wait(timeout=max_time)
            else:
                self.process.wait()
            
            self.is_running = False
            
            if self.process.returncode == 0:
                return True, f"Simulation completed successfully"
            else:
                return False, f"Solver failed with code {self.process.returncode}"
                
        except subprocess.TimeoutExpired:
            self.stop_simulation()
            return True, f"Simulation stopped after {max_time}s"
        except Exception as e:
            self.is_running = False
            return False, f"Error: {str(e)}"
    
    def run_async(self, callback: Optional[Callable[[bool, str], None]] = None) -> threading.Thread:
        """异步运行仿真"""
        def run():
            success, msg = self.run_simulation()
            if callback:
                callback(success, msg)
        
        thread = threading.Thread(target=run)
        thread.start()
        return thread
    
    def stop_simulation(self):
        """停止仿真"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(1)
            if self.process.poll() is None:
                self.process.kill()
        self.is_running = False
    
    def _get_solver(self) -> Optional[str]:
        """获取求解器名称"""
        # 从 controlDict 读取
        control_dict = self.case_path / "system" / "controlDict"
        if control_dict.exists():
            with open(control_dict, 'r') as f:
                for line in f:
                    if 'application' in line:
                        # 提取应用名称
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[-1].rstrip(';')
        
        # 从 case_info.json 读取
        info_file = self.case_path / ".case_info.json"
        if info_file.exists():
            import json
            with open(info_file, 'r') as f:
                info = json.load(f)
                solver = info.get('solver', {})
                if isinstance(solver, dict):
                    return solver.get('name')
                elif isinstance(solver, str):
                    return solver
        
        return "icoFoam"  # 默认求解器
    
    def get_latest_time(self) -> Optional[str]:
        """获取最新的时间步"""
        times = []
        for item in self.case_path.iterdir():
            if item.is_dir():
                try:
                    float(item.name)
                    times.append(item.name)
                except ValueError:
                    pass
        
        if times:
            # 按数值排序
            times.sort(key=lambda x: float(x))
            return times[-1]
        return None
    
    def get_residuals(self) -> Dict[str, List[float]]:
        """获取残差历史"""
        residuals = {}
        
        if self.log_file and self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in f:
                    # 解析残差行
                    if 'Solving for' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            field = parts[2]
                            residual = parts[-1].rstrip(',')
                            try:
                                if field not in residuals:
                                    residuals[field] = []
                                residuals[field].append(float(residual))
                            except ValueError:
                                pass
        
        return residuals
