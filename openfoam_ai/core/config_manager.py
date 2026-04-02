"""
统一配置管理器
集中管理宪法规则、环境变量和默认配置
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Union
from threading import RLock
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    统一配置管理器
    
    功能：
    1. 加载并缓存宪法规则 (system_constitution.yaml)
    2. 读取环境变量配置
    3. 提供统一访问接口
    4. 支持配置热重载（开发模式）
    5. 提供默认值机制
    """
    
    _instance = None
    _lock = RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        with self._lock:
            self._constitution = None
            self._config_cache = {}
            self._constitution_path = None
            self._env_vars = {}
            self._defaults = self._load_defaults()
            self._load_environment_vars()
            self._initialized = True
    
    def _load_defaults(self) -> Dict[str, Any]:
        """加载内置默认配置"""
        return {
            "mesh": {
                "min_cells_2d": 400,
                "min_cells_3d": 8000,
                "min_cells_per_direction": 20,
                "max_aspect_ratio": 100,
                "max_non_orthogonality": 70,
            },
            "solver": {
                "courant_limit_general": 1.0,
                "divergence_threshold": 1.0,
                "min_convergence_residual": 1e-6,
                "max_cells_per_core": 1000000,
            },
            "performance": {
                "max_parallel_threads": os.cpu_count() or 4,
                "memory_limit_gb": 16,
                "timeout_hours": 24,
            }
        }
    
    def _load_environment_vars(self):
        """加载环境变量配置"""
        self._env_vars = {
            "openfoam_path": os.environ.get("OPENFOAM_PATH"),
            "openfoam_version": os.environ.get("OPENFOAM_VERSION", "v2512"),
            "openfoam_install_dir": os.environ.get("OPENFOAM_INSTALL_DIR"),
            "openfoam_user_dir": os.environ.get("OPENFOAM_USER_DIR", str(Path.home() / "OpenFOAM")),
            "parallel_cores": int(os.environ.get("PARALLEL_CORES", "1")),
            "debug_mode": os.environ.get("DEBUG_MODE", "false").lower() == "true",
        }
    
    def _get_constitution_path(self) -> Path:
        """获取宪法文件路径"""
        if self._constitution_path is None:
            # 默认路径：项目根目录下的 config/system_constitution.yaml
            self._constitution_path = (
                Path(__file__).parent.parent / "config" / "system_constitution.yaml"
            )
        return self._constitution_path
    
    def load_constitution(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        加载宪法规则文件
        
        Args:
            force_reload: 强制重新加载
            
        Returns:
            宪法规则字典
        """
        with self._lock:
            if self._constitution is not None and not force_reload:
                return self._constitution
            
            constitution_path = self._get_constitution_path()
            try:
                with open(constitution_path, 'r', encoding='utf-8') as f:
                    self._constitution = yaml.safe_load(f) or {}
                    logger.info(f"宪法文件加载成功: {constitution_path}")
            except Exception as e:
                logger.warning(f"无法加载宪法文件 {constitution_path}: {e}")
                self._constitution = {}
            
            # 合并默认值（如果宪法文件缺少某些部分）
            self._merge_defaults()
            return self._constitution
    
    def _merge_defaults(self):
        """将默认值合并到宪法中（仅当宪法缺少对应键时）"""
        if self._constitution is None:
            return
        
        def deep_merge(target: Dict, source: Dict):
            for key, value in source.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    deep_merge(target[key], value)
                # 否则保留目标值
        
        deep_merge(self._constitution, self._defaults)
    
    def get(self, key: str, default: Any = None, use_env: bool = True) -> Any:
        """
        获取配置值，支持点分隔路径
        
        Args:
            key: 配置键，支持点分隔（如 "Mesh_Standards.min_cells_2d"）
            default: 默认值（如果未找到）
            use_env: 是否同时检查环境变量
            
        Returns:
            配置值
        """
        # 首先检查环境变量（如果启用）
        if use_env:
            env_key = key.replace('.', '_').upper()
            env_value = os.environ.get(env_key)
            if env_value is not None:
                # 尝试转换为适当类型
                try:
                    if env_value.lower() in ('true', 'false'):
                        return env_value.lower() == 'true'
                    elif env_value.isdigit():
                        return int(env_value)
                    elif env_value.replace('.', '', 1).isdigit():
                        return float(env_value)
                    else:
                        return env_value
                except:
                    return env_value
        
        # 检查宪法配置
        if self._constitution is None:
            self.load_constitution()
        
        # 按点分隔路径查找
        parts = key.split('.')
        current = self._constitution
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # 未找到，返回默认值
                return default
        
        return current
    
    def get_mesh_standard(self, key: str, default: Any = None) -> Any:
        """获取网格标准配置"""
        return self.get(f"Mesh_Standards.{key}", default)
    
    def get_solver_standard(self, key: str, default: Any = None) -> Any:
        """获取求解器标准配置"""
        return self.get(f"Solver_Standards.{key}", default)
    
    def get_performance_setting(self, key: str, default: Any = None) -> Any:
        """获取性能配置"""
        return self.get(f"Performance.{key}", default)
    
    def get_environment(self, key: str, default: Any = None) -> Any:
        """获取环境变量配置"""
        return self._env_vars.get(key, default)
    
    def set_constitution_path(self, path: Union[str, Path]):
        """设置宪法文件路径（用于测试或自定义路径）"""
        with self._lock:
            self._constitution_path = Path(path)
            self._constitution = None  # 强制重新加载
    
    def reload(self):
        """重新加载所有配置"""
        with self._lock:
            self._constitution = None
            self._load_environment_vars()
            self.load_constitution(force_reload=True)
    
    def dump_config(self) -> Dict[str, Any]:
        """导出所有配置（用于调试）"""
        return {
            "constitution": self._constitution or self.load_constitution(),
            "environment": self._env_vars,
            "defaults": self._defaults,
        }

    def get_routing_config(self) -> Dict:
        """获取 LLM 路由配置，支持环境变量覆盖"""
        config = {
            "routing_enabled": os.environ.get("ENABLE_LLM_ROUTING", "true").lower() == "true",
            "routing_mode": os.environ.get("LLM_ROUTING_MODE", "balanced"),
            "provider_overrides": {}
        }

        # 检查各任务类型的提供商覆盖
        override_map = {
            "config_generation": "LLM_PROVIDER_CONFIG_GEN",
            "explanation": "LLM_PROVIDER_EXPLAIN",
            "reasoning_review": "LLM_PROVIDER_REVIEW",
            "intent_recognition": "LLM_PROVIDER_INTENT",
            "log_analysis": "LLM_PROVIDER_LOG_ANALYSIS",
        }

        for task_type, env_var in override_map.items():
            value = os.environ.get(env_var)
            if value:
                config["provider_overrides"][task_type] = value

        return config


# 全局单例实例
config = ConfigManager()


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config