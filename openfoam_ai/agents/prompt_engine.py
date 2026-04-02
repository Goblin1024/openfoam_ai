"""
LLM Prompt Engine - 支持多种大语言模型

支持模型: OpenAI, KIMI, DeepSeek, 豆包, GLM, MiniMax, 阿里云百炼
负责与LLM交互，将自然语言转换为结构化配置
"""

import json
import os
import sys
import random
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

# 尝试导入 llm_adapter
try:
    # 正常导入（作为包的一部分）
    from ..core.llm_adapter import create_llm, LLMFactory, LLMResponse
    LLM_ADAPTER_AVAILABLE = True
except ImportError:
    try:
        # 作为脚本直接运行时
        sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
        from llm_adapter import create_llm, LLMFactory, LLMResponse
        LLM_ADAPTER_AVAILABLE = True
    except ImportError:
        LLM_ADAPTER_AVAILABLE = False

# 尝试导入OpenAI，如果不可用则使用mock
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# 尝试导入 MultiLLMRouter
try:
    from openfoam_ai.core.llm_router import MultiLLMRouter
    LLM_ROUTER_AVAILABLE = True
except ImportError:
    MultiLLMRouter = None
    LLM_ROUTER_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)


class PromptEngine:
    """
    LLM提示词引擎 - 支持多种模型
    
    使用方式:
        # 使用 OpenAI (默认)
        engine = PromptEngine(api_key="your_key")
        
        # 使用 KIMI
        engine = PromptEngine(provider="kimi", api_key="your_key")
        
        # 使用 DeepSeek
        engine = PromptEngine(provider="deepseek", api_key="your_key")
        
        # 从环境变量自动读取 API Key
        engine = PromptEngine(provider="kimi")
    
    负责：
    - 管理System Prompt
    - 将自然语言转换为JSON配置
    - 处理多轮对话上下文
    """
    
    # 系统提示词模板
    SYSTEM_PROMPT_TEMPLATE = """你是一位专业的OpenFOAM CFD工程师助手。

你的任务是将用户的自然语言描述转换为结构化的CFD仿真配置。

可用物理类型：
- incompressible: 不可压流（如水流、低速气流）
- compressible: 可压流（如高速气流）
- heatTransfer: 传热问题（包括对流、传导）
- multiphase: 多相流

可用求解器：
- icoFoam: 瞬态不可压层流求解器
- simpleFoam: 稳态不可压求解器
- pimpleFoam: 瞬态不可压求解器（支持大时间步）
- buoyantBoussinesqPimpleFoam: 瞬态浮力驱动流（Boussinesq近似）
- buoyantPimpleFoam: 瞬态浮力驱动流（完全可压）

输出必须是有效的JSON格式，遵循以下结构：
{
    "task_id": "唯一标识符",
    "physics_type": "物理类型",
    "geometry": {
        "dimensions": {"L": 长度, "W": 宽度, "H": 高度},
        "mesh_resolution": {"nx": x网格数, "ny": y网格数, "nz": z网格数}
    },
    "solver": {
        "name": "求解器名",
        "endTime": 结束时间,
        "deltaT": 时间步长
    },
    "boundary_conditions": {
        "边界名": {"type": "边界类型", "value": 值}
    },
    "nu": 运动粘度
}

约束条件：
1. 网格分辨率nx, ny, nz必须在10-1000之间
2. 时间步长deltaT必须保证库朗数小于1（对于icoFoam）
3. 边界条件必须物理合理
4. 对于传热问题，必须选择合适的求解器

只输出JSON，不要包含任何解释文字。"""
    
    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None, 
                 model: Optional[str] = None, mock_mode: bool = False,
                 enable_routing: bool = True):
        """
        初始化PromptEngine
        
        Args:
            provider: 模型提供商 (openai/kimi/deepseek/doubao/glm/minimax/aliyun)，
                     如果为None则使用OpenAI
            api_key: API密钥，如果为None则从环境变量读取
            model: 模型名称，如果为None则使用默认模型
            mock_mode: 是否强制使用Mock模式（用于测试）
            enable_routing: 是否启用多模型智能路由（默认True）
        """
        self.provider = (provider or os.getenv("DEFAULT_LLM_PROVIDER") or "openai").lower()
        self.api_key = api_key
        self.model_name = model
        self.enable_routing = enable_routing
        
        # 确定是否使用mock模式
        if mock_mode:
            self.mock_mode = True
            self.llm = None
            self.client = None
            self.router = None  # mock模式下不初始化路由器
            print("[PromptEngine] 强制运行在无API模式（mock）")
            return
        
        # 优先使用 llm_adapter（如果可用且指定了provider）
        if LLM_ADAPTER_AVAILABLE and self.provider != "openai":
            try:
                self.llm = create_llm(self.provider, api_key, model)
                self.mock_mode = False
                self.client = None
                print(f"[PromptEngine] Using provider: {self.provider}")
                if model:
                    print(f"[PromptEngine] Model: {model}")
                # 初始化多模型路由器
                if enable_routing and LLM_ROUTER_AVAILABLE:
                    try:
                        self.router = MultiLLMRouter()
                        logger.info("[PromptEngine] 多模型路由器已启用")
                    except Exception as e:
                        logger.warning(f"[PromptEngine] 路由器初始化失败: {e}")
                        self.router = None
                else:
                    self.router = None
                return
            except Exception as e:
                print(f"[WARN] LLM init failed: {e}, fallback to Mock")
        
        # 回退到原生OpenAI
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.mock_mode = not HAS_OPENAI or not self.api_key
        self.llm = None
        
        if not self.mock_mode:
            self.client = openai.OpenAI(api_key=self.api_key)
            print(f"[PromptEngine] Using OpenAI")
        else:
            self.client = None
            print("[PromptEngine] 运行在无API模式（mock）")
        
        # 初始化多模型路由器（仅在启用路由且非mock模式时）
        if enable_routing and not self.mock_mode and LLM_ROUTER_AVAILABLE:
            try:
                self.router = MultiLLMRouter()
                logger.info("[PromptEngine] 多模型路由器已启用")
            except Exception as e:
                logger.warning(f"[PromptEngine] 路由器初始化失败: {e}")
                self.router = None
        else:
            self.router = None
    
    def _get_llm_for_task(self, task_type: str):
        """
        获取指定任务类型的 LLM 实例
        
        优先使用路由器选择最优模型，如果路由器不可用则回退到 self.llm
        
        Args:
            task_type: 任务类型 (config_generation/explanation/reasoning_review等)
            
        Returns:
            LLM 实例或 None
        """
        # 如果路由器存在，尝试从路由器获取 LLM
        if self.router is not None:
            llm = self.router.get_llm(task_type)
            if llm is not None:
                model_info = llm.model if hasattr(llm, 'model') else 'unknown'
                logger.info(f"[PromptEngine] 任务 '{task_type}' 使用模型: {model_info}")
                return llm
            else:
                logger.warning(f"[PromptEngine] 路由器未找到可用模型，回退到默认 LLM")
        
        # 回退到原有的 self.llm
        if self.llm is not None:
            model_info = self.llm.model if hasattr(self.llm, 'model') else self.provider
            logger.info(f"[PromptEngine] 任务 '{task_type}' 使用默认模型: {model_info}")
            return self.llm
        
        # 无可用 LLM
        logger.warning(f"[PromptEngine] 任务 '{task_type}' 无可用 LLM 实例")
        return None
    
    def natural_language_to_config(self, user_input: str) -> Dict[str, Any]:
        """
        将自然语言转换为配置
        
        Args:
            user_input: 用户输入的自然语言描述
            
        Returns:
            结构化配置字典
        """
        if self.mock_mode:
            return self._mock_generate_config(user_input)
    
        # 获取任务配置（temperature等）
        task_config = {}
        if self.router is not None:
            task_config = self.router.get_task_config("config_generation")
            
        # 使用路由器获取 LLM（如果可用）
        llm = self._get_llm_for_task("config_generation")
        if llm is not None:
            return self._generate_config_with_adapter(user_input, llm, task_config)
    
        # 使用原生OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.model_name or "gpt-4",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT_TEMPLATE},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"},
                temperature=task_config.get("temperature", 0.3)
            )
            
            content = response.choices[0].message.content
            config = json.loads(content)
            
            print(f"[PromptEngine] 生成配置: {config.get('task_id', 'unknown')}")
            return config
            
        except Exception as e:
            print(f"[PromptEngine] 错误: {e}")
            # 出错时返回默认配置
            return self._mock_generate_config(user_input)
    
    def _generate_config_with_adapter(self, user_input: str, llm=None, task_config: Dict = None) -> Dict[str, Any]:
        """
        使用 llm_adapter 生成配置
        
        Args:
            user_input: 用户输入
            llm: LLM 实例（可选，默认使用 self.llm）
            task_config: 任务配置（temperature 等）
        """
        if task_config is None:
            task_config = {}
        if llm is None:
            llm = self.llm
            
        if llm is None:
            return self._mock_generate_config(user_input)
            
        try:
            response = llm.chat(
                message=user_input,
                system_prompt=self.SYSTEM_PROMPT_TEMPLATE,
                temperature=task_config.get("temperature", 0.3)
            )
            
            if not response.success:
                print(f"[PromptEngine] LLM call failed: {response.error}")
                print("[PromptEngine] Fallback to Mock mode")
                return self._mock_generate_config(user_input)
            
            # 解析JSON响应
            content = response.content.strip()
            
            # 尝试提取JSON（如果LLM返回了Markdown代码块）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            config = json.loads(content)
            
            print(f"[PromptEngine] LLM generated config: {config.get('task_id', 'unknown')}")
            if hasattr(response, 'usage') and response.usage:
                print(f"[PromptEngine] Token usage: {response.usage}")
            
            return config
            
        except json.JSONDecodeError as e:
            print(f"[PromptEngine] JSON parse error: {e}")
            print(f"[PromptEngine] Raw response: {content[:200]}...")
            return self._mock_generate_config(user_input)
            
        except Exception as e:
            print(f"[PromptEngine] Error: {e}")
            return self._mock_generate_config(user_input)
    
    def explain_config(self, config: Dict[str, Any]) -> str:
        """
        解释配置的含义
        
        Args:
            config: 配置字典
            
        Returns:
            自然语言解释
        """
        if self.mock_mode:
            return self._mock_explain_config(config)
        
        prompt = f"""请解释以下CFD配置的含义：

{json.dumps(config, indent=2, ensure_ascii=False)}

请用通俗易懂的语言解释：
1. 这是什么类型的仿真
2. 几何和网格设置
3. 边界条件的含义
4. 求解器选择的原因
5. 可能的应用场景
"""
        
        # 获取任务配置（temperature等）
        task_config = {}
        if self.router is not None:
            task_config = self.router.get_task_config("explanation")
        
        # 使用路由器获取 LLM（如果可用）
        llm = self._get_llm_for_task("explanation")
        if llm is not None:
            try:
                response = llm.chat(
                    message=prompt,
                    system_prompt="你是一位CFD教育工作者，善于用简单语言解释复杂概念。",
                    temperature=task_config.get("temperature", 0.7)
                )
                
                if response.success:
                    return response.content
                else:
                    return f"解释失败: {response.error}"
            except Exception as e:
                return f"解释失败: {e}"
        
        # 使用原生OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.model_name or "gpt-4",
                messages=[
                    {"role": "system", "content": "你是一位CFD教育工作者，善于用简单语言解释复杂概念。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=task_config.get("temperature", 0.7)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"[PromptEngine] 解释失败: {e}")
            return "无法生成解释"
    
    def suggest_improvements(self, config: Dict[str, Any], 
                            log_summary: str) -> List[str]:
        """
        根据运行日志建议改进
        
        Args:
            config: 当前配置
            log_summary: 日志摘要
            
        Returns:
            改进建议列表
        """
        if self.mock_mode:
            return ["使用真实API以获取改进建议"]
        
        prompt = f"""基于以下CFD仿真配置和运行日志，请提供改进建议：

配置：
{json.dumps(config, indent=2, ensure_ascii=False)}

日志摘要：
{log_summary}

请从以下方面分析：
1. 收敛性（残差曲线）
2. 稳定性（库朗数）
3. 网格质量
4. 求解器设置
5. 物理参数

输出改进建议列表（JSON格式）：["建议1", "建议2", ...]"""
        
        # 获取任务配置（temperature等）
        task_config = {}
        if self.router is not None:
            task_config = self.router.get_task_config("reasoning_review")
        
        # 使用路由器获取 LLM（如果可用）
        llm = self._get_llm_for_task("reasoning_review")
        if llm is not None:
            try:
                response = llm.chat(
                    message=prompt,
                    system_prompt="你是一位经验丰富的CFD工程师，专注于优化仿真性能。",
                    temperature=task_config.get("temperature", 0.7)
                )
                
                if response.success:
                    try:
                        result = json.loads(response.content)
                        return result if isinstance(result, list) else [str(result)]
                    except:
                        return [response.content]
                else:
                    return [f"建议生成失败: {response.error}"]
            except Exception as e:
                return [f"建议生成失败: {e}"]
        
        # 使用原生OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.model_name or "gpt-4",
                messages=[
                    {"role": "system", "content": "你是一位经验丰富的CFD工程师，专注于优化仿真性能。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("suggestions", [])
            
        except Exception as e:
            print(f"[PromptEngine] 建议生成失败: {e}")
            return []
    
    def _mock_generate_config(self, user_input: str) -> Dict[str, Any]:
        """
        Mock模式：根据关键词生成符合宪法规则的配置
        支持多种物理场景和几何类型
        """
        user_lower = user_input.lower()
        
        # 场景定义
        scenarios = {
            "cavity": {
                "description": "方腔驱动流（不可压缩层流）",
                "physics": "incompressible",
                "solver": "icoFoam",
                "dims": {"L": 1.0, "W": 1.0, "H": 0.1},
                "res": {"nx": 40, "ny": 40, "nz": 1},  # 满足2D最小网格数1600 > 400
                "boundary_conditions": {
                    "movingWall": {"type": "fixedValue", "value": [1, 0, 0]},
                    "fixedWalls": {"type": "noSlip"},
                    "frontAndBack": {"type": "empty"}
                },
                "nu": 0.01,
                "endTime": 0.5,
                "deltaT": 0.001  # 满足CFL条件
            },
            "pipe": {
                "description": "管道流动（不可压缩湍流）",
                "physics": "incompressible",
                "solver": "simpleFoam",
                "dims": {"L": 5.0, "W": 0.5, "H": 0.5},
                "res": {"nx": 100, "ny": 30, "nz": 30},  # 总网格数90000 > 8000
                "boundary_conditions": {
                    "inlet": {"type": "fixedValue", "value": [1, 0, 0]},
                    "outlet": {"type": "zeroGradient"},
                    "walls": {"type": "noSlip"}
                },
                "nu": 1e-05,
                "endTime": 1000,  # 稳态
                "deltaT": 1.0
            },
            "airfoil": {
                "description": "翼型绕流（可压缩流）",
                "physics": "compressible",
                "solver": "rhoPimpleFoam",
                "dims": {"L": 10.0, "W": 3.0, "H": 0.1},
                "res": {"nx": 100, "ny": 50, "nz": 1},  # 2D网格5000 > 400
                "boundary_conditions": {
                    "inlet": {"type": "fixedValue", "value": [100, 0, 0], "p": 101325},
                    "outlet": {"type": "fixedValue", "p": 101325},
                    "airfoil": {"type": "noSlip"},
                    "farField": {"type": "slip"}
                },
                "nu": 1.5e-05,
                "endTime": 0.01,
                "deltaT": 1e-6
            },
            "heat_transfer": {
                "description": "自然对流（传热）",
                "physics": "heatTransfer",
                "solver": "buoyantBoussinesqPimpleFoam",
                "dims": {"L": 0.5, "W": 0.5, "H": 1.0},
                "res": {"nx": 20, "ny": 20, "nz": 40},  # 3D网格16000 > 8000
                "boundary_conditions": {
                    "hotWall": {"type": "fixedValue", "T": 350},
                    "coldWall": {"type": "fixedValue", "T": 300},
                    "adiabaticWalls": {"type": "zeroGradient"},
                    "frontAndBack": {"type": "empty"}
                },
                "nu": 1e-06,
                "endTime": 100,
                "deltaT": 0.1
            },
            "multiphase": {
                "description": "液‑气两相流（VOF）",
                "physics": "multiphase",
                "solver": "interFoam",
                "dims": {"L": 2.0, "W": 0.5, "H": 0.5},
                "res": {"nx": 80, "ny": 20, "nz": 20},  # 3D网格32000 > 8000
                "boundary_conditions": {
                    "inlet": {"type": "fixedValue", "value": [0.5, 0, 0], "alpha.water": 1},
                    "outlet": {"type": "zeroGradient"},
                    "walls": {"type": "noSlip"},
                    "atmosphere": {"type": "fixedValue", "p": 101325}
                },
                "nu": 1e-06,
                "endTime": 1.0,
                "deltaT": 0.001
            }
        }
        
        # 关键词匹配
        selected = scenarios["cavity"]  # 默认
        if "方腔" in user_input or "cavity" in user_lower:
            selected = scenarios["cavity"]
        elif "管道" in user_input or "pipe" in user_lower or "tube" in user_lower:
            selected = scenarios["pipe"]
        elif "翼型" in user_input or "airfoil" in user_lower or "aerofoil" in user_lower:
            selected = scenarios["airfoil"]
        elif "传热" in user_input or "heat" in user_lower or "温度" in user_input or "natural convection" in user_lower:
            selected = scenarios["heat_transfer"]
        elif "多相" in user_input or "multiphase" in user_lower or "vof" in user_lower or "两相" in user_input:
            selected = scenarios["multiphase"]
        # 如果未匹配，随机选择一个场景（除默认外）
        else:
            # 随机选择但排除默认（可选）
            selected = random.choice(list(scenarios.values()))
        
        # 确保符合宪法规则（网格最小数）
        nx, ny, nz = selected["res"]["nx"], selected["res"]["ny"], selected["res"]["nz"]
        total_cells = nx * ny * (nz if nz > 1 else 1)
        if nz == 1 and total_cells < 400:
            # 自动提升分辨率
            factor = (400 / total_cells) ** 0.5
            selected["res"]["nx"] = max(selected["res"]["nx"], int(selected["res"]["nx"] * factor))
            selected["res"]["ny"] = max(selected["res"]["ny"], int(selected["res"]["ny"] * factor))
        elif nz > 1 and total_cells < 8000:
            factor = (8000 / total_cells) ** (1/3)
            selected["res"]["nx"] = max(selected["res"]["nx"], int(selected["res"]["nx"] * factor))
            selected["res"]["ny"] = max(selected["res"]["ny"], int(selected["res"]["ny"] * factor))
            selected["res"]["nz"] = max(selected["res"]["nz"], int(selected["res"]["nz"] * factor))
        
        # 构建配置
        config = {
            "task_id": f"mock_{int(os.urandom(4).hex(), 16)}",
            "physics_type": selected["physics"],
            "geometry": {
                "dimensions": selected["dims"],
                "mesh_resolution": selected["res"]
            },
            "solver": {
                "name": selected["solver"],
                "endTime": selected["endTime"],
                "deltaT": selected["deltaT"],
                "writeInterval": 100  # 宪法默认值
            },
            "boundary_conditions": selected["boundary_conditions"],
            "nu": selected["nu"],
            "note": f"Generated in mock mode: {selected['description']}"
        }
        
        # 添加额外物理参数
        if selected["physics"] == "compressible":
            config["rho"] = 1.2
            config["gamma"] = 1.4
        if selected["physics"] == "heatTransfer":
            config["beta"] = 3.4e-3  # 热膨胀系数
            config["T_ref"] = 300
        if selected["physics"] == "multiphase":
            config["rho1"] = 1000  # 水密度
            config["rho2"] = 1.2   # 空气密度
            config["nu1"] = 1e-06
            config["nu2"] = 1.5e-05
        
        return config
    
    def _mock_explain_config(self, config: Dict[str, Any]) -> str:
        """Mock模式：详细解释配置，包括宪法符合性检查"""
        physics = config.get("physics_type", "unknown")
        solver = config.get("solver", {}).get("name", "unknown")
        dims = config.get('geometry', {}).get('dimensions', {})
        res = config.get('geometry', {}).get('mesh_resolution', {})
        end_time = config.get('solver', {}).get('endTime', 'unknown')
        delta_t = config.get('solver', {}).get('deltaT', 'unknown')
        nu = config.get('nu', 'unknown')
        note = config.get('note', '')
        
        # 计算总网格数
        nx = res.get('nx', 1)
        ny = res.get('ny', 1)
        nz = res.get('nz', 1)
        total_cells = nx * ny * nz
        
        # 宪法符合性检查
        constitution_checks = []
        if nz == 1:
            if total_cells >= 400:
                constitution_checks.append("✅ 2D网格数满足宪法最小值（≥400）")
            else:
                constitution_checks.append("⚠️ 2D网格数不足400，可能需要加密")
        else:
            if total_cells >= 8000:
                constitution_checks.append("✅ 3D网格数满足宪法最小值（≥8000）")
            else:
                constitution_checks.append("⚠️ 3D网格数不足8000，可能需要加密")
        
        # CFL条件粗略估计
        if isinstance(delta_t, (int, float)) and isinstance(nx, (int, float)) and dims.get('L'):
            dx = dims['L'] / nx
            u_est = 1.0  # 假设特征速度
            courant = u_est * delta_t / dx if dx > 0 else 0
            if courant > 0.5:
                constitution_checks.append(f"⚠️ 估计库朗数{courant:.2f}可能超过显式求解器上限0.5")
            else:
                constitution_checks.append(f"✅ 估计库朗数{courant:.2f}在安全范围内")
        
        # 边界条件摘要
        bc = config.get('boundary_conditions', {})
        bc_summary = ', '.join([f"{name}: {spec.get('type', '?')}" for name, spec in bc.items()])[:100]
        
        # 额外物理参数
        extra_params = []
        if physics == "compressible":
            extra_params.append(f"密度: {config.get('rho', '?')}")
            extra_params.append(f"比热比: {config.get('gamma', '?')}")
        elif physics == "heatTransfer":
            extra_params.append(f"热膨胀系数: {config.get('beta', '?')}")
            extra_params.append(f"参考温度: {config.get('T_ref', '?')} K")
        elif physics == "multiphase":
            extra_params.append(f"水密度: {config.get('rho1', '?')}")
            extra_params.append(f"空气密度: {config.get('rho2', '?')}")
        
        explanation = f"""
配置解释（Mock模式）：
======================

物理类型：{physics}
求解器：{solver}

几何尺寸：{dims}
网格分辨率：{res}（总网格数：{total_cells}）

运行时间：0 → {end_time} 秒
时间步长：{delta_t} 秒
运动粘度：{nu}

边界条件：{bc_summary}

额外物理参数：{', '.join(extra_params) if extra_params else '无'}

宪法符合性检查：
{chr(10).join('  ' + check for check in constitution_checks)}

备注：{note}

（此解释基于Mock模式生成，实际仿真前建议使用验证器进行完整检查。）
"""
        return explanation
    
    def _default_config(self) -> Dict[str, Any]:
        """返回默认配置"""
        return {
            "task_id": "default_fallback",
            "physics_type": "incompressible",
            "geometry": {
                "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
                "mesh_resolution": {"nx": 20, "ny": 20, "nz": 1}
            },
            "solver": {
                "name": "icoFoam",
                "endTime": 0.5,
                "deltaT": 0.005
            },
            "nu": 0.01
        }


class ConfigRefiner:
    """
    配置优化器
    对LLM生成的配置进行本地优化和修正
    """
    
    def __init__(self):
        pass
    
    def refine(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化配置
        
        Args:
            config: 原始配置
            
        Returns:
            优化后的配置
        """
        refined = config.copy()
        
        # 确保task_id存在
        if not refined.get("task_id"):
            refined["task_id"] = f"case_{int(time.time())}"
        
        # 优化网格分辨率
        geometry = refined.get("geometry", {})
        res = geometry.get("mesh_resolution", {})
        
        # 确保网格数在合理范围内
        for key in ["nx", "ny", "nz"]:
            val = res.get(key, 20)
            val = max(10, min(1000, int(val)))
            res[key] = val
        
        # 确保2D问题的nz=1
        if res.get("nz", 1) > 1 and geometry.get("dimensions", {}).get("H", 0.1) < 0.2:
            res["nz"] = 1
        
        geometry["mesh_resolution"] = res
        refined["geometry"] = geometry
        
        # 优化时间步长
        solver = refined.get("solver", {})
        delta_t = solver.get("deltaT", 0.01)
        end_time = solver.get("endTime", 1.0)
        
        # 确保deltaT不会导致计算步数过多
        max_steps = 10000
        if end_time / delta_t > max_steps:
            solver["deltaT"] = end_time / max_steps
            print(f"[ConfigRefiner] 调整时间步长为{solver['deltaT']}")
        
        refined["solver"] = solver
        
        return refined
    
    def validate_critical_params(self, config: Dict[str, Any]) -> List[str]:
        """
        验证关键参数
        
        Returns:
            警告信息列表
        """
        warnings = []
        
        # 检查物理类型与求解器匹配
        physics = config.get("physics_type")
        solver = config.get("solver", {}).get("name", "")
        
        if physics == "incompressible" and solver not in ["icoFoam", "simpleFoam", "pimpleFoam"]:
            warnings.append(f"不可压流可能不适合使用求解器{solver}")
        
        if physics == "heatTransfer" and "buoyant" not in solver:
            warnings.append(f"传热问题建议使用buoyant求解器，当前使用{solver}")
        
        # 检查网格分辨率
        res = config.get("geometry", {}).get("mesh_resolution", {})
        total_cells = res.get("nx", 1) * res.get("ny", 1) * res.get("nz", 1)
        
        if total_cells < 100:
            warnings.append(f"网格数{total_cells}过少，可能影响精度")
        if total_cells > 1000000:
            warnings.append(f"网格数{total_cells}过多，计算时间可能很长")
        
        # 检查时间步长
        delta_t = config.get("solver", {}).get("deltaT", 0.01)
        end_time = config.get("solver", {}).get("endTime", 1.0)
        
        steps = end_time / delta_t
        if steps > 10000:
            warnings.append(f"计算步数约{int(steps)}步，可能耗时较长")
        
        return warnings


# 保持向后兼容：PromptEngineV2 作为 PromptEngine 的别名
PromptEngineV2 = PromptEngine


if __name__ == "__main__":
    # 测试PromptEngine
    print("PromptEngine 模块测试")
    print("=" * 50)
    
    engine = PromptEngine()
    
    # 测试自然语言转换
    test_inputs = [
        "建立一个二维方腔驱动流，顶部速度为1m/s",
        "模拟管道内的水流，雷诺数1000",
        "计算方腔内的自然对流，上下壁面恒温"
    ]
    
    for user_input in test_inputs:
        print(f"\n输入: {user_input}")
        config = engine.natural_language_to_config(user_input)
        print(f"输出配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
    
    # 测试配置优化
    print("\n" + "=" * 50)
    print("测试配置优化")
    
    refiner = ConfigRefiner()
    
    test_config = {
        "task_id": "",
        "geometry": {
            "mesh_resolution": {"nx": 5, "ny": 5, "nz": 10}
        },
        "solver": {
            "deltaT": 0.0001,
            "endTime": 1000
        }
    }
    
    print(f"原始配置: {json.dumps(test_config, indent=2)}")
    
    refined = refiner.refine(test_config)
    print(f"优化后: {json.dumps(refined, indent=2)}")
    
    warnings = refiner.validate_critical_params(refined)
    print(f"警告: {warnings}")
    
    # 测试支持的提供商
    print("\n" + "=" * 50)
    print("支持的LLM提供商:")
    if LLM_ADAPTER_AVAILABLE:
        for provider in LLMFactory.list_providers():
            print(f"   - {provider}")
    else:
        print("   llm_adapter 不可用，仅支持OpenAI")
