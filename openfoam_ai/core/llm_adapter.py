#!/usr/bin/env python3
"""
LLM 适配器 - 支持多种大语言模型

支持的模型:
- OpenAI (GPT-3.5/GPT-4)
- KIMI (Moonshot AI)
- DeepSeek
- 豆包 (ByteDance)
- GLM (Zhipu AI)
- MiniMax
- 阿里云百炼

使用方式:
    from llm_adapter import LLMFactory
    
    # 使用 KIMI
    llm = LLMFactory.create("kimi", api_key="your_key")
    response = llm.chat("创建一个CFD算例配置")
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 响应数据结构"""
    content: str
    model: str
    usage: Dict[str, int]
    success: bool
    error: Optional[str] = None


class BaseLLM(ABC):
    """LLM 基类"""
    
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    @abstractmethod
    def chat(self, message: str, system_prompt: Optional[str] = None, 
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        """发送聊天请求"""
        pass
    
    def _safe_json_parse(self, text: str) -> tuple:
        """安全解析 JSON，返回 (success, result)"""
        try:
            return True, json.loads(text)
        except json.JSONDecodeError as e:
            return False, str(e)


class OpenAIAdapter(BaseLLM):
    """OpenAI 适配器"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        super().__init__(api_key, model)
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
            self.available = True
        except ImportError:
            print("[WARN] openai package not installed, using requests mode")
            self.client = None
            self.available = False
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        try:
            if self.client:
                # 使用官方 SDK
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": message})
                
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature
                }
                if response_format == "json":
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = self.client.chat.completions.create(**kwargs)
                
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    },
                    success=True
                )
            else:
                # 使用 requests
                return self._chat_with_requests(message, system_prompt, temperature, response_format)
                
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )
    
    def _chat_with_requests(self, message: str, system_prompt: Optional[str],
                           temperature: float, response_format: Optional[str]) -> LLMResponse:
        import requests
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        if response_format == "json":
            data["response_format"] = {"type": "json_object"}
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200:
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=result.get("model", self.model),
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("error", {}).get("message", "Unknown error")
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class KimiAdapter(BaseLLM):
    """KIMI (Moonshot AI) 适配器"""
    
    BASE_URL = "https://api.moonshot.cn/v1"
    
    DEFAULT_MODELS = {
        "kimi-latest": "kimi-latest",
        "kimi-k2": "kimi-k2-0711-preview",  # 最新模型
        "kimi-k1.5": "kimi-k1.5",
        "moonshot-v1-8k": "moonshot-v1-8k",
        "moonshot-v1-32k": "moonshot-v1-32k",
        "moonshot-v1-128k": "moonshot-v1-128k"
    }
    
    def __init__(self, api_key: str, model: str = "kimi-latest"):
        # 映射模型名称
        if model in self.DEFAULT_MODELS:
            model = self.DEFAULT_MODELS[model]
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200:
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=result.get("model", self.model),
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("error", {}).get("message", str(result))
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class DeepSeekAdapter(BaseLLM):
    """DeepSeek 适配器"""
    
    BASE_URL = "https://api.deepseek.com"
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if response_format == "json":
            data["response_format"] = {"type": "json_object"}
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200:
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=result.get("model", self.model),
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("error", {}).get("message", str(result))
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class DoubaoAdapter(BaseLLM):
    """豆包 (ByteDance) 适配器 - 通过阿里云百炼"""
    
    BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    
    DEFAULT_MODELS = {
        "doubao-pro": "doubao-pro-128k",
        "doubao-lite": "doubao-lite-128k",
        "doubao-vision": "doubao-vision-pro-32k"
    }
    
    def __init__(self, api_key: str, model: str = "doubao-pro"):
        if model in self.DEFAULT_MODELS:
            model = self.DEFAULT_MODELS[model]
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "result_format": "message"
            }
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200 and "output" in result:
                return LLMResponse(
                    content=result["output"]["choices"][0]["message"]["content"],
                    model=self.model,
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("message", str(result))
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class GLMAdapter(BaseLLM):
    """GLM (Zhipu AI) 适配器"""
    
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    
    DEFAULT_MODELS = {
        "glm-4": "glm-4",
        "glm-4-plus": "glm-4-plus",
        "glm-4-flash": "glm-4-flash",
        "glm-4v": "glm-4v-plus"  # 多模态
    }
    
    def __init__(self, api_key: str, model: str = "glm-4"):
        if model in self.DEFAULT_MODELS:
            model = self.DEFAULT_MODELS[model]
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200:
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=result.get("model", self.model),
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("error", {}).get("message", str(result))
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class MiniMaxAdapter(BaseLLM):
    """MiniMax 适配器"""
    
    BASE_URL = "https://api.minimax.chat/v1"
    
    DEFAULT_MODELS = {
        "abab6.5": "abab6.5-chat",
        "abab6": "abab6-chat",
        "abab5.5": "abab5.5-chat"
    }
    
    def __init__(self, api_key: str, model: str = "abab6.5"):
        if model in self.DEFAULT_MODELS:
            model = self.DEFAULT_MODELS[model]
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt, "name": "system"})
        messages.append({"role": "user", "content": message, "name": "user"})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200 and result.get("base_resp", {}).get("status_code") == 0:
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=self.model,
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                error_msg = result.get("base_resp", {}).get("status_msg", str(result))
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=error_msg
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class AliyunBailianAdapter(BaseLLM):
    """阿里云百炼适配器"""
    
    BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    
    DEFAULT_MODELS = {
        "qwen-max": "qwen-max",
        "qwen-plus": "qwen-plus",
        "qwen-turbo": "qwen-turbo",
        "qwen-vl": "qwen-vl-max"  # 多模态
    }
    
    def __init__(self, api_key: str, model: str = "qwen-max"):
        if model in self.DEFAULT_MODELS:
            model = self.DEFAULT_MODELS[model]
        super().__init__(api_key, model, self.BASE_URL)
    
    def chat(self, message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.3, response_format: Optional[str] = None) -> LLMResponse:
        import requests
        
        url = f"{self.base_url}/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        data = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "result_format": "message"
            }
        }
        
        if response_format == "json":
            data["parameters"]["response_format"] = "json"
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            if resp.status_code == 200 and "output" in result:
                return LLMResponse(
                    content=result["output"]["choices"][0]["message"]["content"],
                    model=self.model,
                    usage=result.get("usage", {}),
                    success=True
                )
            else:
                return LLMResponse(
                    content="",
                    model=self.model,
                    usage={},
                    success=False,
                    error=result.get("message", str(result))
                )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e)
            )


class LLMFactory:
    """LLM 工厂类"""
    
    ADAPTERS = {
        "openai": OpenAIAdapter,
        "kimi": KimiAdapter,
        "moonshot": KimiAdapter,
        "deepseek": DeepSeekAdapter,
        "doubao": DoubaoAdapter,
        "glm": GLMAdapter,
        "zhipu": GLMAdapter,
        "minimax": MiniMaxAdapter,
        "aliyun": AliyunBailianAdapter,
        "bailian": AliyunBailianAdapter
    }
    
    @classmethod
    def create(cls, provider: str, api_key: str, model: Optional[str] = None) -> BaseLLM:
        """
        创建 LLM 适配器
        
        Args:
            provider: 提供商名称 (openai/kimi/deepseek/doubao/glm/minimax/aliyun)
            api_key: API Key
            model: 模型名称（可选，使用默认值）
        
        Returns:
            LLM 适配器实例
        """
        provider = provider.lower()
        if provider not in cls.ADAPTERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls.ADAPTERS.keys())}")
        
        adapter_class = cls.ADAPTERS[provider]
        
        # 使用默认模型
        if model is None:
            default_models = {
                "openai": "gpt-4",
                "kimi": "kimi-latest",
                "moonshot": "kimi-latest",
                "deepseek": "deepseek-chat",
                "doubao": "doubao-pro",
                "glm": "glm-4",
                "zhipu": "glm-4",
                "minimax": "abab6.5",
                "aliyun": "qwen-max",
                "bailian": "qwen-max"
            }
            model = default_models.get(provider)
        
        return adapter_class(api_key, model)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """返回所有支持的提供商"""
        return list(cls.ADAPTERS.keys())


# 便捷函数
def create_llm(provider: str, api_key: Optional[str] = None, model: Optional[str] = None) -> BaseLLM:
    """
    快速创建 LLM 实例
    
    如果未提供 api_key，会尝试从环境变量读取:
    - OPENAI_API_KEY
    - KIMI_API_KEY
    - DEEPSEEK_API_KEY
    - DOUBAO_API_KEY
    - GLM_API_KEY
    - MINIMAX_API_KEY
    - ALIYUN_API_KEY
    """
    if api_key is None:
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "kimi": "KIMI_API_KEY",
            "moonshot": "KIMI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "doubao": "DOUBAO_API_KEY",
            "glm": "GLM_API_KEY",
            "zhipu": "GLM_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "aliyun": "ALIYUN_API_KEY",
            "bailian": "ALIYUN_API_KEY"
        }
        env_var = env_vars.get(provider.lower())
        if env_var:
            api_key = os.getenv(env_var)
        
        if not api_key:
            raise ValueError(f"API Key not provided and {env_var} not set in environment")
    
    return LLMFactory.create(provider, api_key, model)


if __name__ == "__main__":
    # 测试代码
    print("支持的 LLM 提供商:")
    for provider in LLMFactory.list_providers():
        print(f"  - {provider}")
    print()
    
    # 测试环境变量读取
    print("环境变量检查:")
    env_vars = ["OPENAI_API_KEY", "KIMI_API_KEY", "DEEPSEEK_API_KEY", 
                "DOUBAO_API_KEY", "GLM_API_KEY", "MINIMAX_API_KEY", "ALIYUN_API_KEY"]
    for var in env_vars:
        value = os.getenv(var)
        status = "已设置" if value else "未设置"
        print(f"  {var}: {status}")
