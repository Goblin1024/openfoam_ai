"""
OpenFOAM命令执行器
封装OpenFOAM命令执行、日志捕获和结果解析
支持本地执行和 Docker 容器执行两种模式
"""

import subprocess
import re
import time
import logging
import queue
import shutil
from pathlib import Path
from typing import Tuple, Iterator, Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
from .validators import load_constitution
from .conservation_checker import ConservationChecker
from .docker_executor import DockerOpenFOAMExecutor

logger = logging.getLogger(__name__)


class SolverState(Enum):
    """求解器状态"""
    IDLE = "idle"
    RUNNING = "running"
    CONVERGED = "converged"
    DIVERGING = "diverging"
    STALLED = "stalled"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class SolverMetrics:
    """求解器指标"""
    time: float
    courant_mean: float
    courant_max: float
    residuals: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "courant_mean": self.courant_mean,
            "courant_max": self.courant_max,
            "residuals": self.residuals
        }


class OpenFOAMRunner:
    """
    OpenFOAM命令执行器
    
    功能：
    - 执行blockMesh, checkMesh等预处理命令
    - 运行求解器并实时监控
    - 捕获和解析日志
    - 检测发散和异常
    - 支持本地和 Docker 两种执行模式
    """
    
    def __init__(self, case_path: Path, execution_mode: str = "auto"):
        """
        初始化执行器
        
        Args:
            case_path: 算例路径
            execution_mode: 执行模式 ("auto", "docker", "local")
                           - auto: 自动检测可用环境
                           - docker: 强制使用 Docker
                           - local: 强制使用本地 OpenFOAM
        """
        self.case_path = Path(case_path)
        self.log_dir = self.case_path / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        self.current_process: Optional[subprocess.Popen] = None
        self.latest_metrics: Optional[SolverMetrics] = None
        self.state = SolverState.IDLE
        
        # 监控阈值（从宪法读取）
        constitution = load_constitution()
        solver_standards = constitution.get('Solver_Standards', {})
        self.courant_limit = solver_standards.get('courant_limit_general', 1.0)
        self.divergence_threshold = solver_standards.get('divergence_threshold', 1.0)
        self.residual_target = solver_standards.get('min_convergence_residual', 1e-6)
        
        # 初始化执行模式
        self.execution_mode = self._detect_execution_mode(execution_mode)
        self.docker_executor: Optional[DockerOpenFOAMExecutor] = None
        
        if self.execution_mode == "docker":
            self.docker_executor = DockerOpenFOAMExecutor()
            logger.info("[OpenFOAMRunner] 使用 Docker 执行模式")
        elif self.execution_mode == "local":
            logger.info("[OpenFOAMRunner] 使用本地 OpenFOAM 执行模式")
        else:
            logger.warning("[OpenFOAMRunner] 无可用 OpenFOAM 环境，部分功能受限")
    
    def _detect_execution_mode(self, mode: str) -> str:
        """
        检测执行环境
        
        Args:
            mode: 请求的模式 ("auto", "docker", "local")
            
        Returns:
            实际的执行模式 ("docker", "local", "unavailable")
        """
        if mode == "docker":
            # 强制使用 Docker
            docker_executor = DockerOpenFOAMExecutor()
            if docker_executor.check_available():
                return "docker"
            else:
                logger.warning("[OpenFOAMRunner] Docker 模式不可用")
                return "unavailable"
                
        elif mode == "local":
            # 强制使用本地
            if shutil.which("blockMesh"):
                return "local"
            else:
                logger.warning("[OpenFOAMRunner] 本地 OpenFOAM 不可用")
                return "unavailable"
                
        else:  # auto
            # 自动检测，优先 Docker（更适合 Windows 环境）
            docker_executor = DockerOpenFOAMExecutor()
            if docker_executor.check_available():
                logger.info("[OpenFOAMRunner] 自动检测: Docker 可用")
                return "docker"
            
            # 检查本地 OpenFOAM
            if shutil.which("blockMesh"):
                logger.info("[OpenFOAMRunner] 自动检测: 本地 OpenFOAM 可用")
                return "local"
            
            logger.warning("[OpenFOAMRunner] 自动检测: 无可用 OpenFOAM 环境")
            return "unavailable"
    
    def run_blockmesh(self) -> Tuple[bool, str]:
        """
        执行blockMesh
        
        Returns:
            (是否成功, 日志内容)
        """
        print(f"[OpenFOAMRunner] 运行 blockMesh...")
        
        if self.execution_mode == "unavailable":
            return False, "OpenFOAM 环境不可用"
        
        if self.execution_mode == "docker":
            return self._run_command_docker("blockMesh", "blockMesh.log")
        else:
            return self._run_command("blockMesh", "blockMesh.log")
    
    def run_checkmesh(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行checkMesh
        
        Returns:
            (是否成功, 日志内容, 质量指标)
        """
        print(f"[OpenFOAMRunner] 运行 checkMesh...")
        
        if self.execution_mode == "unavailable":
            return False, "OpenFOAM 环境不可用", {}
        
        if self.execution_mode == "docker":
            success, log = self._run_command_docker("checkMesh", "checkMesh.log")
        else:
            success, log = self._run_command("checkMesh", "checkMesh.log")
            
        metrics = self._parse_checkmesh_log(log) if success else {}
        return success, log, metrics
    
    def run_full_pipeline(self, solver_name: str, 
                          run_parallel: int = 1) -> Dict[str, Any]:
        """
        执行完整的 OpenFOAM 仿真管线
        
        管线: blockMesh -> checkMesh -> solver
        
        Args:
            solver_name: 求解器名称
            run_parallel: 并行核数（1 = 串行）
        
        Returns:
            {
                "success": bool,
                "execution_mode": str,
                "stages": [{"name": str, "success": bool, "log": str, "duration": float}],
                "total_duration": float,
                "mesh_metrics": Dict,
                "monitor_summary": Dict
            }
        """
        result = {
            "success": False,
            "execution_mode": self.execution_mode,
            "stages": [],
            "total_duration": 0.0,
            "mesh_metrics": {},
            "monitor_summary": {}
        }
        
        total_start = time.time()
        
        # 检查环境可用性
        if self.execution_mode == "unavailable":
            result["error"] = "OpenFOAM 环境不可用"
            result["total_duration"] = time.time() - total_start
            return result
        
        # 使用 Docker 执行管线
        if self.execution_mode == "docker":
            logger.info(f"[OpenFOAMRunner] 使用 Docker 执行完整管线: {solver_name}")
            docker_result = self.docker_executor.run_pipeline(
                str(self.case_path), solver_name, run_parallel
            )
            
            result["total_duration"] = docker_result["total_duration"]
            result["success"] = docker_result["success"]
            
            # 转换阶段结果格式
            for stage in docker_result["stages"]:
                result["stages"].append({
                    "name": stage["name"],
                    "success": stage["returncode"] == 0,
                    "log": stage["stdout"] + "\n" + stage["stderr"],
                    "duration": stage["duration"]
                })
            
            # 提取 checkMesh 结果
            for stage in docker_result["stages"]:
                if stage["name"] == "checkMesh":
                    result["mesh_metrics"] = self._parse_checkmesh_log(
                        stage["stdout"] + "\n" + stage["stderr"]
                    )
            
            return result
        
        # 使用本地执行管线
        logger.info(f"[OpenFOAMRunner] 使用本地执行完整管线: {solver_name}")
        
        # 阶段 1: blockMesh
        stage_start = time.time()
        success, log = self.run_blockmesh()
        result["stages"].append({
            "name": "blockMesh",
            "success": success,
            "log": log,
            "duration": time.time() - stage_start
        })
        if not success:
            result["total_duration"] = time.time() - total_start
            return result
        
        # 阶段 2: checkMesh
        stage_start = time.time()
        success, log, metrics = self.run_checkmesh()
        result["stages"].append({
            "name": "checkMesh",
            "success": success,
            "log": log,
            "duration": time.time() - stage_start
        })
        result["mesh_metrics"] = metrics
        
        # 阶段 3: 运行求解器
        stage_start = time.time()
        solver_success = self._run_solver_sync(solver_name)
        result["stages"].append({
            "name": solver_name,
            "success": solver_success,
            "log": "",
            "duration": time.time() - stage_start
        })
        
        result["total_duration"] = time.time() - total_start
        result["success"] = solver_success
        
        if result["success"]:
            logger.info(f"[OpenFOAMRunner] 仿真完成，总耗时: {result['total_duration']:.1f}秒")
        else:
            logger.error(f"[OpenFOAMRunner] 求解器 {solver_name} 失败")
        
        return result
    
    def _run_command_docker(self, cmd: str, log_name: str) -> Tuple[bool, str]:
        """
        通过 Docker 执行单条命令
        
        Args:
            cmd: 命令名
            log_name: 日志文件名
            
        Returns:
            (是否成功, 日志内容)
        """
        if not self.docker_executor:
            return False, "Docker 执行器未初始化"
        
        start_time = time.time()
        rc, stdout, stderr = self.docker_executor.run_command(
            str(self.case_path), cmd
        )
        
        log_content = stdout + "\n" + stderr
        success = rc == 0
        elapsed = time.time() - start_time
        
        # 写入日志文件
        log_file = self.log_dir / log_name
        try:
            log_file.write_text(log_content, encoding='utf-8')
        except Exception as e:
            print(f"[OpenFOAMRunner] 无法写入日志文件 {log_file}: {e}")
        
        if success:
            print(f"[OpenFOAMRunner] {cmd} 成功 (耗时 {elapsed:.2f}s)")
        else:
            print(f"[OpenFOAMRunner] {cmd} 失败 (耗时 {elapsed:.2f}s)")
            print(f"错误详情: {stderr[:500]}...")
        
        return success, log_content
    
    def _run_solver_sync(self, solver_name: str) -> bool:
        """
        同步执行求解器（用于 run_full_pipeline）
        
        Args:
            solver_name: 求解器名称
            
        Returns:
            是否成功
        """
        print(f"[OpenFOAMRunner] 运行求解器: {solver_name}")
        
        # 收集所有指标但不实时返回
        final_state = SolverState.RUNNING
        try:
            for metrics in self.run_solver(solver_name):
                final_state = self.state
        except Exception as e:
            logger.error(f"[OpenFOAMRunner] 求解器执行异常: {e}")
            return False
        
        return final_state in (SolverState.COMPLETED, SolverState.CONVERGED)
    
    def run_solver(self, solver_name: str,
                   callback: Optional[Callable[[str], None]] = None) -> Iterator[SolverMetrics]:
        """
        执行求解器并实时返回指标，包含详细的错误处理

        Args:
            solver_name: 求解器名称
            callback: 回调函数，接收日志行
            
        Yields:
            SolverMetrics对象
        """
        # 检查环境可用性
        if self.execution_mode == "unavailable":
            print(f"[OpenFOAMRunner] 错误: OpenFOAM 环境不可用")
            self.state = SolverState.ERROR
            return
        
        # Docker 模式下的求解器运行需要特殊处理
        # 注意：Docker 模式的实时监控需要更复杂的实现
        # 这里保持兼容，提示用户使用 run_full_pipeline 获取 Docker 模式完整支持
        if self.execution_mode == "docker":
            print(f"[OpenFOAMRunner] Docker 模式建议使用 run_full_pipeline() 进行完整仿真")
            # 仍然支持通过 Docker 同步运行
            if self.docker_executor:
                log_file = self.log_dir / f"{solver_name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
                print(f"[OpenFOAMRunner] Docker 模式运行求解器: {solver_name}")
                
                rc, stdout, stderr = self.docker_executor.run_command(
                    str(self.case_path), solver_name, timeout=3600
                )
                
                log_content = stdout + "\n" + stderr
                try:
                    log_file.write_text(log_content, encoding='utf-8')
                except Exception:
                    pass
                
                if rc == 0:
                    self.state = SolverState.COMPLETED
                    print(f"[OpenFOAMRunner] Docker 求解器正常结束")
                else:
                    self.state = SolverState.ERROR
                    print(f"[OpenFOAMRunner] Docker 求解器异常结束")
                
                # Docker 模式下不产生流式指标
                return
        
        # 本地模式执行
        log_file = self.log_dir / f"{solver_name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        
        print(f"[OpenFOAMRunner] 启动求解器: {solver_name}")
        print(f"[OpenFOAMRunner] 日志文件: {log_file}")
        
        self.state = SolverState.RUNNING
        try:
            self.current_process = subprocess.Popen(
                [solver_name],
                cwd=self.case_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
        except FileNotFoundError as e:
            error_msg = f"求解器命令未找到: {solver_name}，请检查OpenFOAM安装和PATH设置。错误: {e}"
            print(f"[OpenFOAMRunner] 错误: {error_msg}")
            self.state = SolverState.ERROR
            # 不产生任何指标，直接返回空迭代器
            return
        except PermissionError as e:
            error_msg = f"权限不足，无法执行求解器 {solver_name}。错误: {e}"
            print(f"[OpenFOAMRunner] 错误: {error_msg}")
            self.state = SolverState.ERROR
            return
        except Exception as e:
            error_msg = f"求解器启动时发生未知错误: {type(e).__name__}: {e}"
            print(f"[OpenFOAMRunner] 错误: {error_msg}")
            self.state = SolverState.ERROR
            return
        
        current_time = 0.0
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                if self.current_process.stdout is None:
                    print(f"[OpenFOAMRunner] 错误: 求解器标准输出未捕获")
                    self.state = SolverState.ERROR
                    return
                for line in self.current_process.stdout:
                    try:
                        f.write(line)
                        f.flush()
                        
                        line = line.strip()
                        
                        # 调用回调
                        if callback:
                            callback(line)
                        
                        # 解析日志行
                        metrics = self._parse_solver_line(line)
                        if metrics:
                            self.latest_metrics = metrics
                            self.state = self._check_state(metrics)
                            yield metrics
                    except UnicodeDecodeError as e:
                        print(f"[OpenFOAMRunner] 警告: 日志行解码错误，跳过该行。错误: {e}")
                        continue
                    except Exception as e:
                        print(f"[OpenFOAMRunner] 警告: 处理日志行时发生错误，跳过。错误: {type(e).__name__}: {e}")
                        continue
        except Exception as e:
            print(f"[OpenFOAMRunner] 错误: 写入日志文件时发生异常: {type(e).__name__}: {e}")
            # 继续处理，不中断求解器
        
        # 等待进程结束
        try:
            self.current_process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            print(f"[OpenFOAMRunner] 警告: 求解器进程未在超时时间内结束，强制终止")
            self.current_process.kill()
            self.current_process.wait()
        except Exception as e:
            print(f"[OpenFOAMRunner] 警告: 等待求解器结束时发生错误: {type(e).__name__}: {e}")
        
        # 检查返回码
        if self.current_process.returncode == 0:
            self.state = SolverState.COMPLETED
            print(f"[OpenFOAMRunner] 求解器正常结束")
        else:
            self.state = SolverState.ERROR
            print(f"[OpenFOAMRunner] 求解器异常结束 (code: {self.current_process.returncode})")
        
        self.current_process = None
    
    def stop_solver(self) -> None:
        """停止当前求解器"""
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            print("[OpenFOAMRunner] 求解器已停止")
    
    def get_execution_status(self) -> Dict[str, Any]:
        """
        获取当前执行模式状态
        
        Returns:
            Dict: 包含执行模式、可用性等信息
        """
        status = {
            "execution_mode": self.execution_mode,
            "case_path": str(self.case_path),
            "solver_state": self.state.value if self.state else "unknown",
        }
        
        if self.execution_mode == "docker" and self.docker_executor:
            status["docker_status"] = self.docker_executor.get_status()
        
        return status
    
    def get_latest_timestep(self) -> Optional[float]:
        """
        获取最新的时间步
        
        Returns:
            最新时间步，如果没有则返回None
        """
        timesteps = []
        for item in self.case_path.iterdir():
            if item.is_dir():
                try:
                    ts = float(item.name)
                    timesteps.append(ts)
                except ValueError:
                    continue
        
        return max(timesteps) if timesteps else None
    
    def get_time_directories(self) -> List[float]:
        """
        获取所有时间步目录
        
        Returns:
            时间步列表（排序）
        """
        timesteps = []
        for item in self.case_path.iterdir():
            if item.is_dir():
                try:
                    ts = float(item.name)
                    timesteps.append(ts)
                except ValueError:
                    continue
        
        return sorted(timesteps)
    
    def _run_command(self, cmd: str, log_name: str) -> Tuple[bool, str]:
        """
        执行单条命令，包含异常处理和详细日志记录
        
        Args:
            cmd: 命令名
            log_name: 日志文件名
            
        Returns:
            (是否成功, 日志内容)
        """
        import subprocess
        import time
        log_file = self.log_dir / log_name
        
        start_time = time.time()
        success = False
        log_content = ""
        
        try:
            result = subprocess.run(
                [cmd],
                cwd=self.case_path,
                capture_output=True,
                text=True,
                check=False  # 不抛出异常，手动检查返回码
            )
            
            log_content = result.stdout + "\n" + result.stderr
            success = result.returncode == 0
            
        except FileNotFoundError as e:
            log_content = f"命令未找到: {cmd}\n错误: {e}"
            success = False
        except subprocess.CalledProcessError as e:
            log_content = f"命令执行失败 (返回码 {e.returncode}):\n{e.stderr}"
            success = False
        except Exception as e:
            log_content = f"未知错误: {type(e).__name__}: {e}"
            success = False
        
        # 写入日志文件
        try:
            log_file.write_text(log_content, encoding='utf-8')
        except Exception as e:
            print(f"[OpenFOAMRunner] 无法写入日志文件 {log_file}: {e}")
        
        elapsed = time.time() - start_time
        
        # 记录执行结果
        if success:
            print(f"[OpenFOAMRunner] {cmd} 成功 (耗时 {elapsed:.2f}s)")
        else:
            print(f"[OpenFOAMRunner] {cmd} 失败 (耗时 {elapsed:.2f}s)")
            print(f"错误详情: {log_content[:200]}...")
        
        return success, log_content
    
    def _parse_checkmesh_log(self, log: str) -> Dict[str, Any]:
        """
        解析checkMesh日志
        
        Args:
            log: 日志内容
            
        Returns:
            质量指标字典
        """
        metrics = {
            "passed": True,
            "failed_checks": 0,
            "non_orthogonality_max": 0.0,
            "non_orthogonality_avg": 0.0,
            "skewness_max": 0.0,
            "aspect_ratio_max": 0.0
        }
        
        # 提取失败检查数
        failed_match = re.search(r'Failed (\d+) mesh', log)
        if failed_match:
            metrics["failed_checks"] = int(failed_match.group(1))
            metrics["passed"] = metrics["failed_checks"] == 0
        
        # 提取非正交性
        non_ortho_match = re.search(r'Non-orthogonality.*?Max = ([\d.]+).*?average = ([\d.]+)', 
                                     log, re.DOTALL | re.IGNORECASE)
        if non_ortho_match:
            metrics["non_orthogonality_max"] = float(non_ortho_match.group(1))
            metrics["non_orthogonality_avg"] = float(non_ortho_match.group(2))
        
        # 提取偏斜度
        skewness_match = re.search(r'Max skewness = ([\d.]+)', log)
        if skewness_match:
            metrics["skewness_max"] = float(skewness_match.group(1))
        
        # 提取长宽比
        aspect_match = re.search(r'Max aspect ratio = ([\d.]+)', log)
        if aspect_match:
            metrics["aspect_ratio_max"] = float(aspect_match.group(1))
        
        return metrics
    
    def _parse_solver_line(self, line: str) -> Optional[SolverMetrics]:
        """
        解析求解器日志行
        
        Args:
            line: 日志行
            
        Returns:
            SolverMetrics或None
        """
        # 解析时间
        time_match = re.search(r'Time = ([\d.]+)', line)
        if time_match:
            self._current_time = float(time_match.group(1))
            return None
        
        # 解析库朗数
        courant_match = re.search(r'Courant Number mean: ([\d.e+-]+) max: ([\d.e+-]+)', line)
        if courant_match:
            return SolverMetrics(
                time=getattr(self, '_current_time', 0),
                courant_mean=float(courant_match.group(1)),
                courant_max=float(courant_match.group(2)),
                residuals={}
            )
        
        # 解析残差
        # 格式: "Solving for Ux, Initial residual = 1.234e-05, Final residual = 1.234e-08"
        residual_pattern = r'Solving for (\w+), Initial residual = ([\de.+-]+)'
        residual_matches = re.findall(residual_pattern, line)
        
        if residual_matches:
            residuals = {name: float(val) for name, val in residual_matches}
            return SolverMetrics(
                time=getattr(self, '_current_time', 0),
                courant_mean=0,
                courant_max=0,
                residuals=residuals
            )
        
        return None
    
    def _check_state(self, metrics: SolverMetrics) -> SolverState:
        """
        检查求解器状态
        
        Args:
            metrics: 当前指标
            
        Returns:
            求解器状态
        """
        # 检查库朗数
        if metrics.courant_max > self.courant_limit:
            return SolverState.DIVERGING
        
        # 检查残差
        for var, res in metrics.residuals.items():
            if res > self.divergence_threshold:
                return SolverState.DIVERGING
        
        return SolverState.RUNNING
    
    def clean_case(self) -> None:
        """清理算例（保留网格和配置）"""
        # 删除时间步目录
        for ts in self.get_time_directories():
            ts_dir = self.case_path / str(ts)
            if ts_dir.exists():
                shutil.rmtree(ts_dir)
        
        # 删除processor目录
        for proc_dir in self.case_path.glob("processor*"):
            if proc_dir.is_dir():
                shutil.rmtree(proc_dir)
        
        print(f"[OpenFOAMRunner] 算例已清理（保留网格）")


class SolverMonitor:
    """
    求解器监控器
    用于持续监控求解过程和检测异常
    """
    
    def __init__(self, runner: OpenFOAMRunner):
        self.runner = runner
        self.metrics_history: List[SolverMetrics] = []
        self.max_history = 100
        
        # 阈值
        self.stall_threshold = 100  # 停滞步数
        self.divergence_patience = 5  # 连续发散容忍次数
        
        self._divergence_count = 0
    
    def monitor(self, solver_name: str) -> Iterator[Tuple[SolverState, SolverMetrics]]:
        """
        监控求解器运行
        
        Args:
            solver_name: 求解器名称
            
        Yields:
            (状态, 指标)
        """
        for metrics in self.runner.run_solver(solver_name):
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history:
                self.metrics_history.pop(0)
            
            # 检测停滞
            if self._is_stalled():
                self.runner.state = SolverState.STALLED
            
            # 检测收敛
            if self._is_converged():
                self.runner.state = SolverState.CONVERGED
            
            yield self.runner.state, metrics
    
    def _is_stalled(self) -> bool:
        """检查是否停滞"""
        if len(self.metrics_history) < self.stall_threshold:
            return False
        
        # 检查最近N步的残差变化
        recent = self.metrics_history[-self.stall_threshold:]
        
        # 如果所有残差都在一个很小的范围内波动，认为停滞
        for var in ['Ux', 'Uy', 'Uz', 'p']:
            values = [m.residuals.get(var, 0) for m in recent if var in m.residuals]
            if len(values) >= 10:
                # 检查是否有明显下降
                if max(values) / (min(values) + 1e-10) < 2:
                    return True
        
        return False
    
    def _is_converged(self) -> bool:
        """检查是否收敛"""
        if not self.metrics_history:
            return False
        
        latest = self.metrics_history[-1]
        
        # 检查所有残差是否都低于目标
        for var, res in latest.residuals.items():
            if res > self.runner.residual_target:
                return False
        
        return len(latest.residuals) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        if not self.metrics_history:
            return {}
    
        latest = self.metrics_history[-1]
    
        return {
            "final_time": latest.time,
            "final_courant_max": latest.courant_max,
            "final_residuals": latest.residuals,
            "total_steps": len(self.metrics_history),
            "final_state": self.runner.state.value
        }
        
    def check_conservation(self) -> Dict[str, Any]:
        """
        执行守恒性检查
            
        在求解完成后调用，验证质量守恒、能量守恒、
        连续性误差和残差收敛情况。
            
        Returns:
            Dict: 包含守恒性检查结果的字典
        """
        # 创建守恒性检查器
        checker = ConservationChecker(self.runner.case_path)
            
        # 查找最新的日志文件
        log_file = None
        logs_dir = self.runner.log_dir
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            if log_files:
                log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                log_file = log_files[0]
            
        # 获取守恒性摘要
        summary = checker.get_summary_dict(log_file=str(log_file) if log_file else None)
            
        logger.info(f"守恒性检查完成: {'通过' if summary.get('passed', False) else '未通过'}")
            
        return summary
        
    def get_conservation_report(self) -> str:
        """
        获取守恒性检查报告
            
        Returns:
            str: 格式化的守恒性检查报告
        """
        checker = ConservationChecker(self.runner.case_path)
            
        # 查找最新的日志文件
        log_file = None
        logs_dir = self.runner.log_dir
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            if log_files:
                log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                log_file = log_files[0]
            
        return checker.generate_report(log_file=str(log_file) if log_file else None)


import queue
import threading
from typing import Callable


class MonitorDataBridge:
    """
    监控数据桥 - 连接 SolverMonitor 和 UI 的数据通道
    
    用于在仿真运行时将监控指标实时传递给 Gradio 界面。
    线程安全，支持多消费者。
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self._metrics_queue = queue.Queue(maxsize=max_queue_size)
        self._latest_metrics = {}
        self._lock = threading.Lock()
        self._callbacks = []
        self._is_running = False
        self._history = {
            "time": [],
            "courant_max": [],
            "residuals": {},  # {"Ux": [], "Uy": [], "p": []}
            "iteration": []
        }
    
    def push_metrics(self, metrics: dict):
        """推送新的监控指标（由 SolverMonitor 调用）"""
        with self._lock:
            self._latest_metrics = metrics.copy()
            # 记录历史
            self._history["time"].append(metrics.get("time", 0))
            self._history["courant_max"].append(metrics.get("courant_max", 0))
            self._history["iteration"].append(metrics.get("iteration", 0))
            # 记录残差
            for field, value in metrics.get("residuals", {}).items():
                if field not in self._history["residuals"]:
                    self._history["residuals"][field] = []
                self._history["residuals"][field].append(value)
        
        try:
            self._metrics_queue.put_nowait(metrics)
        except queue.Full:
            pass  # 队列满时丢弃旧数据
        
        # 触发回调
        for callback in self._callbacks:
            try:
                callback(metrics)
            except Exception as e:
                logger.warning(f"监控回调执行失败: {e}")
    
    def get_latest(self) -> dict:
        """获取最新的监控指标"""
        with self._lock:
            return self._latest_metrics.copy()
    
    def get_history(self) -> dict:
        """获取完整的历史指标数据"""
        with self._lock:
            return {k: list(v) if isinstance(v, list) else {sk: list(sv) for sk, sv in v.items()} 
                    for k, v in self._history.items()}
    
    def get_progress(self, end_time: float = None) -> dict:
        """获取仿真进度信息"""
        latest = self.get_latest()
        current_time = latest.get("time", 0)
        progress_pct = (current_time / end_time * 100) if end_time and end_time > 0 else 0
        return {
            "current_time": current_time,
            "end_time": end_time,
            "progress_percent": min(progress_pct, 100),
            "current_iteration": latest.get("iteration", 0),
            "courant_max": latest.get("courant_max", 0),
            "is_running": self._is_running
        }
    
    def register_callback(self, callback: Callable):
        """注册实时回调函数"""
        self._callbacks.append(callback)
    
    def start(self):
        """标记仿真开始"""
        self._is_running = True
        self._history = {"time": [], "courant_max": [], "residuals": {}, "iteration": []}
    
    def stop(self):
        """标记仿真结束"""
        self._is_running = False
    
    def reset(self):
        """重置所有数据"""
        with self._lock:
            self._latest_metrics = {}
            self._history = {"time": [], "courant_max": [], "residuals": {}, "iteration": []}
            while not self._metrics_queue.empty():
                try:
                    self._metrics_queue.get_nowait()
                except queue.Empty:
                    break
        self._is_running = False
    
    def generate_residual_plot(self):
        """生成残差收敛曲线 matplotlib Figure"""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        history = self.get_history()
        fig, ax = plt.subplots(figsize=(8, 5))
        
        iterations = history.get("iteration", [])
        residuals = history.get("residuals", {})
        
        if not iterations or not residuals:
            # 没有数据时显示占位图
            ax.text(0.5, 0.5, "Waiting for simulation data...", ha='center', va='center', fontsize=14, color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            for field_name, values in residuals.items():
                ax.semilogy(iterations[:len(values)], values, label=field_name, linewidth=1.5)
            ax.set_xlabel("Iteration", fontsize=12)
            ax.set_ylabel("Residual", fontsize=12)
            ax.set_title("Residual Convergence Curve", fontsize=14)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def generate_courant_plot(self):
        """生成库朗数变化曲线 matplotlib Figure"""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        history = self.get_history()
        fig, ax = plt.subplots(figsize=(8, 4))
        
        iterations = history.get("iteration", [])
        courant = history.get("courant_max", [])
        
        if not iterations or not courant:
            ax.text(0.5, 0.5, "Waiting for simulation data...", ha='center', va='center', fontsize=14, color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            ax.plot(iterations, courant, 'r-', linewidth=1.5, label='Max Courant')
            ax.axhline(y=1.0, color='orange', linestyle='--', label='Co=1 (Warning)')
            ax.axhline(y=0.5, color='green', linestyle='--', alpha=0.5, label='Co=0.5 (Recommended)')
            ax.set_xlabel("Iteration", fontsize=12)
            ax.set_ylabel("Courant Number", fontsize=12)
            ax.set_title("Courant Number Variation", fontsize=14)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig


if __name__ == "__main__":
    # 测试需要实际的OpenFOAM环境
    print("OpenFOAMRunner 模块测试")
    print("=" * 50)
    
    # 创建临时目录进行测试
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test_case"
        case_path.mkdir()
        
        # 创建基本目录结构
        for d in ["0", "constant", "system", "logs"]:
            (case_path / d).mkdir(exist_ok=True)
        
        # 测试runner初始化
        runner = OpenFOAMRunner(case_path)
        print(f"[测试] Case path: {runner.case_path}")
        print(f"[测试] Log dir: {runner.log_dir}")
        
        # 测试时间步检测
        for ts in [0, 0.1, 0.2, 0.5]:
            (case_path / str(ts)).mkdir()
        
        latest = runner.get_latest_timestep()
        print(f"[测试] 最新时间步: {latest}")
        
        all_ts = runner.get_time_directories()
        print(f"[测试] 所有时间步: {all_ts}")
