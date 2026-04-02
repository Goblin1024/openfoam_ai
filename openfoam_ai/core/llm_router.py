"""
多模型智能路由器

根据任务类型自动选择最优 LLM 提供商，支持 fallback 降级和缓存。
"""

import os
import logging
from typing import Dict, Optional, Any
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class MultiLLMRouter:
    """多模型智能路由器"""
    
    # 提供商对应的 API Key 环境变量名
    PROVIDER_KEY_MAP = {
        "openai": "OPENAI_API_KEY",
        "kimi": "KIMI_API_KEY",
        "moonshot": "KIMI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "glm": "GLM_API_KEY",
        "zhipu": "GLM_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "aliyun": "ALIYUN_API_KEY",
        "bailian": "ALIYUN_API_KEY",
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化路由器，加载配置并扫描可用提供商"""
        # 加载配置
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "llm_routing.yaml"
        self.config = self._load_config(config_path)
        
        # 扫描可用提供商
        self.available_providers = self._scan_available_providers()
        
        # LLM 实例缓存
        self._llm_cache: Dict[str, Any] = {}
        
        # 路由统计
        self._route_stats: Dict[str, Dict[str, int]] = {}
        
        logger.info(f"[MultiLLMRouter] 初始化完成，可用提供商: {list(self.available_providers)}")
    
    def _load_config(self, config_path) -> Dict:
        """加载 YAML 配置"""
        try:
            config_path = Path(config_path)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logger.info(f"[MultiLLMRouter] 已加载路由配置: {config_path}")
                return config
        except Exception as e:
            logger.warning(f"[MultiLLMRouter] 加载路由配置失败: {e}")
        
        # 返回默认配置
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """返回默认路由配置（当 YAML 文件不存在时）"""
        return {
            "routing_enabled": True,
            "routing_mode": "balanced",
            "task_profiles": {
                "config_generation": {"priority": ["deepseek", "kimi", "aliyun"], "temperature": 0.3, "response_format": "json"},
                "reasoning_review": {"priority": ["deepseek", "kimi", "aliyun"], "temperature": 0.5},
                "explanation": {"priority": ["kimi", "deepseek", "aliyun"], "temperature": 0.7},
                "intent_recognition": {"priority": ["aliyun", "deepseek", "kimi"], "temperature": 0.2},
                "log_analysis": {"priority": ["deepseek", "aliyun", "kimi"], "temperature": 0.3},
            },
            "fallback_enabled": True,
        }
    
    def _scan_available_providers(self) -> Dict[str, str]:
        """扫描环境变量，返回可用的提供商及其 API Key"""
        available = {}
        for provider, key_var in self.PROVIDER_KEY_MAP.items():
            api_key = os.environ.get(key_var, "")
            if api_key and not api_key.startswith("your-") and len(api_key) > 10:
                available[provider] = api_key
        return available
    
    def select_provider(self, task_type: str) -> Optional[str]:
        """根据任务类型选择最优可用提供商"""
        profiles = self.config.get("task_profiles", {})
        profile = profiles.get(task_type)
        
        if not profile:
            logger.warning(f"[MultiLLMRouter] 未知任务类型: {task_type}，使用默认提供商")
            return self._get_any_available()
        
        # 检查环境变量覆盖
        env_override = self._check_env_override(task_type)
        if env_override and env_override in self.available_providers:
            logger.info(f"[MultiLLMRouter] 任务 '{task_type}' 使用环境变量覆盖: {env_override}")
            return env_override
        
        # 按优先级查找可用提供商
        priority_list = profile.get("priority", [])
        for provider in priority_list:
            if provider in self.available_providers:
                logger.info(f"[MultiLLMRouter] 任务 '{task_type}' -> 提供商: {provider}")
                self._record_route(task_type, provider)
                return provider
        
        # Fallback: 使用任何可用的
        if self.config.get("fallback_enabled", True):
            fallback = self._get_any_available()
            if fallback:
                logger.warning(f"[MultiLLMRouter] 任务 '{task_type}' 降级到: {fallback}")
                self._record_route(task_type, fallback)
                return fallback
        
        logger.error(f"[MultiLLMRouter] 任务 '{task_type}' 无可用提供商")
        return None
    
    def _check_env_override(self, task_type: str) -> Optional[str]:
        """检查是否有环境变量覆盖特定任务的提供商"""
        env_map = {
            "config_generation": "LLM_PROVIDER_CONFIG_GEN",
            "reasoning_review": "LLM_PROVIDER_REVIEW",
            "explanation": "LLM_PROVIDER_EXPLAIN",
            "intent_recognition": "LLM_PROVIDER_INTENT",
            "log_analysis": "LLM_PROVIDER_LOG_ANALYSIS",
        }
        env_var = env_map.get(task_type)
        if env_var:
            return os.environ.get(env_var)
        return None
    
    def get_llm(self, task_type: str):
        """获取指定任务类型的 LLM 实例（带缓存）"""
        provider = self.select_provider(task_type)
        if not provider:
            return None
        
        # 缓存检查
        if provider in self._llm_cache:
            return self._llm_cache[provider]
        
        # 创建新实例 — 使用 llm_adapter 的工厂函数
        try:
            from openfoam_ai.core.llm_adapter import create_llm
            llm = create_llm(provider)
            self._llm_cache[provider] = llm
            return llm
        except Exception as e:
            logger.error(f"[MultiLLMRouter] 创建 LLM 实例失败 ({provider}): {e}")
            return None
    
    def get_task_config(self, task_type: str) -> Dict:
        """获取任务类型的配置（temperature、response_format 等）"""
        profiles = self.config.get("task_profiles", {})
        return profiles.get(task_type, {})
    
    def _get_any_available(self) -> Optional[str]:
        """返回任意一个可用的提供商"""
        # 优先返回主流提供商
        preferred_order = ["deepseek", "kimi", "aliyun", "glm", "doubao", "openai", "minimax"]
        for p in preferred_order:
            if p in self.available_providers:
                return p
        return next(iter(self.available_providers), None) if self.available_providers else None
    
    def _record_route(self, task_type: str, provider: str):
        """记录路由统计"""
        if task_type not in self._route_stats:
            self._route_stats[task_type] = {}
        stats = self._route_stats[task_type]
        stats[provider] = stats.get(provider, 0) + 1
    
    def get_routing_info(self) -> Dict:
        """返回当前路由状态信息"""
        return {
            "routing_enabled": self.config.get("routing_enabled", False),
            "routing_mode": self.config.get("routing_mode", "balanced"),
            "available_providers": list(self.available_providers.keys()),
            "task_profiles": {
                k: {"priority": v.get("priority", []), "description": v.get("description", "")}
                for k, v in self.config.get("task_profiles", {}).items()
            },
            "route_stats": self._route_stats,
        }
    
    def __repr__(self):
        return f"MultiLLMRouter(available={list(self.available_providers.keys())}, mode={self.config.get('routing_mode', 'balanced')})"
