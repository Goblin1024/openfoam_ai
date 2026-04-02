"""
OpenFOAM AI Core Module
包含算例管理、文件生成、验证器和求解器运行等核心功能。
"""

__version__ = "0.1.0"

# 导出 SchemeAdvisor 相关类
from .scheme_advisor import SchemeAdvisor, SchemeRecommendation, DivergenceDiagnosis

# 导出 MultiLLMRouter
from .llm_router import MultiLLMRouter

# 导出 DockerOpenFOAMExecutor
from .docker_executor import DockerOpenFOAMExecutor

__all__ = [
    "SchemeAdvisor",
    "SchemeRecommendation", 
    "DivergenceDiagnosis",
    "MultiLLMRouter",
    "DockerOpenFOAMExecutor",
]
