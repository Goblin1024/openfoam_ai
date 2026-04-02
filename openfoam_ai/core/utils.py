"""
通用工具函数
用于减少代码重复，提高模块独立性
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def save_json(path: Path, data: Dict[str, Any], indent: int = 2) -> bool:
    """
    安全保存JSON文件

    Args:
        path: 文件路径
        data: 字典数据
        indent: 缩进空格数

    Returns:
        是否成功
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.debug(f"JSON文件已保存: {path}")
        return True
    except Exception as e:
        logger.error(f"保存JSON文件失败 {path}: {e}")
        return False


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """
    安全加载JSON文件

    Args:
        path: 文件路径

    Returns:
        字典数据，失败返回None
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"JSON文件已加载: {path}")
        return data
    except FileNotFoundError:
        logger.warning(f"JSON文件不存在: {path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误 {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"加载JSON文件失败 {path}: {e}")
        return None


def ensure_directory(path: Path) -> Path:
    """
    确保目录存在，若不存在则创建

    Args:
        path: 目录路径

    Returns:
        创建的目录路径
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"创建目录: {path}")
    return path


def format_size(bytes_size: int) -> str:
    """
    将字节数格式化为易读字符串

    Args:
        bytes_size: 字节数

    Returns:
        格式化字符串，例如 "1.2 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def log_execution_time(func: callable) -> callable:
    """装饰器：记录函数执行时间。
    
    将此装饰器应用于任何函数，将自动记录该函数的执行时间。
    
    Args:
        func: 要装饰的函数
    
    Returns:
        包装后的函数，执行时会记录时间
    
    Example:
        @log_execution_time
        def my_function():
            time.sleep(1)
    """
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"函数 {func.__name__} 执行时间: {elapsed:.3f}秒")
        return result
    return wrapper