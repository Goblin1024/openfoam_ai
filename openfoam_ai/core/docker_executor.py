"""
Docker OpenFOAM 执行器
通过 Docker 容器运行 OpenFOAM 命令，支持 Windows 环境
"""
import subprocess
import os
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class DockerOpenFOAMExecutor:
    """通过 Docker 容器执行 OpenFOAM 命令"""
    
    # 默认 OpenFOAM Docker 镜像（OpenFOAM Foundation v11）
    DEFAULT_IMAGE = "openfoam/openfoam11-paraview510"
    
    # OpenFOAM 环境初始化命令（v11 镜像中 OpenFOAM 安装在 /opt/openfoam11）
    OPENFOAM_SOURCE = "source /opt/openfoam11/etc/bashrc"
    
    def __init__(self, image_name: Optional[str] = None):
        """
        初始化 Docker 执行器
        
        Args:
            image_name: Docker 镜像名称，默认使用 openfoam/openfoam2312-default
        """
        self.image = image_name or os.environ.get("OPENFOAM_DOCKER_IMAGE", self.DEFAULT_IMAGE)
        self._available = None  # 缓存可用性检查结果
        logger.info(f"[DockerExecutor] 使用镜像: {self.image}")
    
    def check_available(self) -> bool:
        """
        检测 Docker 和 OpenFOAM 镜像是否就绪
        
        Returns:
            bool: Docker 和镜像是否可用
        """
        if self._available is not None:
            return self._available
        
        try:
            # 1. 检查 Docker 是否运行
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.warning("[DockerExecutor] Docker 未运行")
                self._available = False
                return False
            
            logger.info("[DockerExecutor] Docker 已运行")
            
            # 2. 检查镜像是否存在
            result = subprocess.run(
                ["docker", "images", "-q", self.image],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if not result.stdout.strip():
                logger.warning(f"[DockerExecutor] 镜像 {self.image} 不存在，尝试拉取...")
                if not self.pull_image():
                    self._available = False
                    return False
            
            # 3. 测试镜像是否可用（验证 OpenFOAM 环境）
            test_result = self._test_image()
            if test_result:
                logger.info(f"[DockerExecutor] 镜像 {self.image} 可用")
                self._available = True
            else:
                logger.warning(f"[DockerExecutor] 镜像 {self.image} 无法正常执行 OpenFOAM 命令")
                self._available = False
            
            return self._available
            
        except FileNotFoundError:
            logger.error("[DockerExecutor] Docker 命令未找到，请安装 Docker Desktop")
            self._available = False
            return False
        except subprocess.TimeoutExpired:
            logger.error("[DockerExecutor] Docker 检查超时")
            self._available = False
            return False
        except Exception as e:
            logger.error(f"[DockerExecutor] 检查失败: {e}")
            self._available = False
            return False
    
    def _test_image(self) -> bool:
        """
        测试镜像是否能正常执行 OpenFOAM 命令
        
        Returns:
            bool: 测试是否成功
        """
        try:
            # 尝试运行简单的 OpenFOAM 命令来验证环境
            test_cmd = f"{self.OPENFOAM_SOURCE} && blockMesh -help"
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--entrypoint", "/bin/bash",
                    self.image,
                    "-c", test_cmd
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            # 只要能执行就算成功
            return result.returncode == 0 or "Usage" in result.stdout or "Usage" in result.stderr
        except Exception as e:
            logger.error(f"[DockerExecutor] 镜像测试失败: {e}")
            return False
    
    def run_command(self, case_path: str, command: str, 
                    timeout: int = 3600) -> Tuple[int, str, str]:
        """
        在 Docker 容器中执行单个 OpenFOAM 命令
        
        Args:
            case_path: Windows 上的案例目录绝对路径
            command: OpenFOAM 命令（如 "blockMesh", "icoFoam"）
            timeout: 超时秒数
        
        Returns:
            (returncode, stdout, stderr)
        """
        case_path = str(Path(case_path).resolve())
        
        # Docker Desktop on Windows 直接使用 Windows 路径即可
        # 格式: E:\path\to\case -> 使用原始路径
        # Docker Desktop 自动处理路径转换
        
        # 构建 docker run 命令
        # 使用 bash -c 来 source OpenFOAM 环境并执行命令
        full_cmd = f"{self.OPENFOAM_SOURCE} && cd /work && {command}"
        
        docker_cmd = [
            "docker", "run", "--rm",
            "--entrypoint", "/bin/bash",
            "-v", f"{case_path}:/work",
            "-w", "/work",
            self.image,
            "-c", full_cmd
        ]
        
        logger.info(f"[DockerExecutor] 执行: {command} (案例: {case_path})")
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                logger.info(f"[DockerExecutor] {command} 完成（成功）")
            else:
                logger.warning(f"[DockerExecutor] {command} 完成（返回码: {result.returncode}）")
                if result.stderr:
                    logger.warning(f"[DockerExecutor] stderr: {result.stderr[:500]}")
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            logger.error(f"[DockerExecutor] {command} 超时（{timeout}秒）")
            return -1, "", f"命令超时（{timeout}秒）"
        except FileNotFoundError:
            logger.error("[DockerExecutor] Docker 命令未找到")
            return -1, "", "Docker 命令未找到，请确保 Docker Desktop 已安装并运行"
        except Exception as e:
            logger.error(f"[DockerExecutor] 执行失败: {e}")
            return -1, "", str(e)
    
    def run_pipeline(self, case_path: str, solver_name: str,
                     run_parallel: int = 1) -> Dict:
        """
        执行完整的 OpenFOAM 仿真管线
        
        管线: blockMesh -> checkMesh -> solver
        
        Args:
            case_path: 案例目录路径
            solver_name: 求解器名称
            run_parallel: 并行核数（1 = 串行）
        
        Returns:
            {
                "success": bool,
                "stages": [{"name": str, "returncode": int, "stdout": str, "stderr": str, "duration": float}],
                "total_duration": float
            }
        """
        result = {
            "success": False,
            "stages": [],
            "total_duration": 0.0,
            "case_path": case_path,
            "solver": solver_name
        }
        
        total_start = time.time()
        
        # 阶段 1: blockMesh
        stage_start = time.time()
        rc, stdout, stderr = self.run_command(case_path, "blockMesh")
        result["stages"].append({
            "name": "blockMesh",
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
            "duration": time.time() - stage_start
        })
        if rc != 0:
            logger.error(f"[DockerExecutor] blockMesh 失败")
            result["total_duration"] = time.time() - total_start
            return result
        
        # 阶段 2: checkMesh（可选，不阻断）
        stage_start = time.time()
        rc, stdout, stderr = self.run_command(case_path, "checkMesh")
        result["stages"].append({
            "name": "checkMesh",
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
            "duration": time.time() - stage_start
        })
        # checkMesh 失败只是警告，不中止
        if rc != 0:
            logger.warning("[DockerExecutor] checkMesh 有警告，继续执行求解器")
        
        # 阶段 3: 运行求解器
        stage_start = time.time()
        rc, stdout, stderr = self.run_command(case_path, solver_name, timeout=3600)
        result["stages"].append({
            "name": solver_name,
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
            "duration": time.time() - stage_start
        })
        
        result["total_duration"] = time.time() - total_start
        result["success"] = (rc == 0)
        
        if result["success"]:
            logger.info(f"[DockerExecutor] 仿真完成，总耗时: {result['total_duration']:.1f}秒")
        else:
            logger.error(f"[DockerExecutor] 求解器 {solver_name} 失败")
        
        return result
    
    def pull_image(self) -> bool:
        """
        拉取 OpenFOAM Docker 镜像
        
        Returns:
            bool: 是否成功拉取
        """
        logger.info(f"[DockerExecutor] 拉取镜像: {self.image}")
        try:
            result = subprocess.run(
                ["docker", "pull", self.image],
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                logger.info(f"[DockerExecutor] 镜像 {self.image} 拉取成功")
                return True
            else:
                logger.error(f"[DockerExecutor] 拉取镜像失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("[DockerExecutor] 拉取镜像超时")
            return False
        except Exception as e:
            logger.error(f"[DockerExecutor] 拉取失败: {e}")
            return False
    
    def get_status(self) -> Dict:
        """
        获取执行器状态信息
        
        Returns:
            Dict: 包含执行器类型、镜像和可用性状态
        """
        return {
            "executor_type": "docker",
            "image": self.image,
            "available": self.check_available(),
        }
    
    def reset_availability_cache(self):
        """重置可用性缓存，强制下次检查重新检测"""
        self._available = None


# 模块测试
if __name__ == "__main__":
    print("DockerOpenFOAMExecutor 模块测试")
    print("=" * 50)
    
    executor = DockerOpenFOAMExecutor()
    
    # 测试可用性检测
    print(f"\n[测试] 检测 Docker 可用性...")
    available = executor.check_available()
    print(f"[测试] Docker 可用: {available}")
    
    # 获取状态
    status = executor.get_status()
    print(f"[测试] 执行器状态: {status}")
