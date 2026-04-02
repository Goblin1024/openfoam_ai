"""
Intent Resolver Module
意图识别与指代消解模块

负责：
1. 用户意图识别（关键词匹配 + LLM分类）
2. 上下文辅助意图判断
3. 指代消解（将模糊指代转换为具体参数）
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple

from openfoam_ai.core.llm_router import MultiLLMRouter

logger = logging.getLogger(__name__)


class IntentResolver:
    """
    意图解析器
    
    职责：
    1. 接收用户输入，理解意图
    2. 指代消解 - 将模糊指代转换为具体参数
    """
    
    # 置信度阈值常量
    HIGH_CONFIDENCE = 0.8  # 高置信度，直接返回结果
    LOW_CONFIDENCE = 0.3   # 低置信度，需要LLM辅助
    CONTEXT_CONFIDENCE = 0.85  # 上下文辅助判断的置信度
    
    # 意图关键词映射
    INTENT_KEYWORDS = {
        "create": ["建立", "创建", "新建", "setup", "create", "build", "make", "new"],
        "modify": ["修改", "改变", "调整", "update", "modify", "change", "改成", "换成", "设为", "改为"],
        "run": ["运行", "计算", "开始", "run", "start", "execute", "solve", "启动", "仿真", "simulate", "simulation", "求解"],
        "status": ["状态", "进度", "情况", "status", "progress", "check", "查看"],
        "help": ["帮助", "help", "怎么用", "说明", "如何使用"],
        "explain": ["解释", "什么是", "为什么", "explain", "why", "what", "含义", "意思", "介绍"],
        "compare": ["对比", "比较", "区别", "compare", "difference", "vs", "versus", "有什么不同"],
        "optimize": ["优化", "改进", "提升", "optimize", "improve", "better", "建议"],
        "routing": ["选择求解器", "什么求解器", "推荐求解器", "solver", "物理模型", "可压缩", "多相流", "传热"]
    }
    
    # 参数显示名称映射
    PARAM_DISPLAY_NAMES = {
        "nx": "X方向网格数",
        "ny": "Y方向网格数",
        "nz": "Z方向网格数",
        "deltaT": "时间步长",
        "endTime": "结束时间",
        "nu": "运动粘度",
        "L": "长度",
        "W": "宽度",
        "H": "高度"
    }
    
    # 相对修改映射
    RELATIVE_MODS = {
        "大一点": 1.5, "大一些": 1.5, "增大": 2.0, "加大": 2.0,
        "小一点": 0.7, "小一些": 0.7, "减小": 0.5, "缩小": 0.5,
        "加倍": 2.0, "翻倍": 2.0, "减半": 0.5
    }
    
    # 代词列表
    PRONOUNS = ["它", "这个", "那个", "这", "那"]
    
    # 历史引用词
    HISTORY_REFS = ["上次的", "之前的", "刚才的"]
    
    # 参数提取正则模式
    PARAM_PATTERNS = {
        "nx": [r"(\d+)\s*x\s*\d+", r"网格.*?(\d+)", r"nx.*?[=:]?\s*(\d+)"],
        "ny": [r"\d+\s*x\s*(\d+)", r"网格.*?\d+\s*x\s*(\d+)", r"ny.*?[=:]?\s*(\d+)"],
        "nz": [r"\d+\s*x\s*\d+\s*x\s*(\d+)", r"nz.*?[=:]?\s*(\d+)"],
        "deltaT": [r"时间步长.*?([\d.eE-]+)", r"dt.*?[=:]?\s*([\d.eE-]+)", r"deltaT.*?[=:]?\s*([\d.eE-]+)"],
        "endTime": [r"结束时间.*?([\d.eE-]+)", r"endTime.*?[=:]?\s*([\d.eE-]+)", r"运行到.*?([\d.eE-]+)"],
        "nu": [r"粘度.*?([\d.eE-]+)", r"nu.*?[=:]?\s*([\d.eE-]+)", r"运动粘度.*?([\d.eE-]+)"],
    }
    
    # 关注点关键词
    FOCUS_KEYWORDS = {
        "mesh": ["网格", "mesh", "分辨率", "nx", "ny", "nz"],
        "boundary": ["边界", "boundary", "入口", "出口", "inlet", "outlet", "壁面"],
        "solver": ["求解器", "solver", "时间步", "步长", "迭代"],
        "physics": ["物理", "physics", "流体", "粘度", "密度"]
    }
    
    def __init__(self, prompt_engine: Optional[Any] = None, context: Optional[Dict[str, Any]] = None, router: Optional[MultiLLMRouter] = None):
        """
        初始化IntentResolver
        
        Args:
            prompt_engine: 提示词引擎（用于LLM意图分类）
            context: 对话上下文
            router: 多LLM路由器（可选）
        """
        self.prompt_engine = prompt_engine
        self.router = router
        self.context = context or {
            "intent_chain": [],           # 意图链历史
            "mentioned_params": {},       # 最近提及的参数和值
            "current_focus": None,        # 当前关注点（如 "mesh", "boundary"）
            "unresolved_questions": [],   # 未解决的问题
            "last_config_change": None,   # 最近一次配置变更
        }
    
    def resolve_references(self, user_input: str, execution_history: Optional[List[Dict[str, Any]]] = None) -> str:
        """指代消解 - 将模糊指代转换为具体参数
        
        处理的指代类型：
        - "它" / "这个" → 最近修改的参数
        - "上次的" / "之前的" → 从历史中查找
        - "大一点" / "小一点" → 相对修改
        - "那个参数" → 上下文中最近的参数
        
        Args:
            user_input: 原始用户输入
            execution_history: 执行历史（用于处理历史引用）
        
        Returns:
            消解后的用户输入（如果无法消解则返回原文）
        """
        resolved = user_input
        
        # 获取上下文信息
        mentioned_params = self.context.get("mentioned_params", {})
        
        # 1. 处理 "它"、"这个" 指代
        for pronoun in self.PRONOUNS:
            if pronoun in resolved and mentioned_params:
                # 用最近提及的参数名替换
                last_param = list(mentioned_params.keys())[-1] if mentioned_params else None
                if last_param:
                    display_name = self.PARAM_DISPLAY_NAMES.get(last_param, last_param)
                    resolved = resolved.replace(pronoun, display_name, 1)
        
        # 2. 处理相对修改："大一点" / "小一点" / "加倍" / "减半"
        for mod_word, factor in self.RELATIVE_MODS.items():
            if mod_word in resolved and mentioned_params:
                last_param = list(mentioned_params.keys())[-1]
                last_value = mentioned_params[last_param]
                if isinstance(last_value, (int, float)):
                    new_value = last_value * factor
                    if isinstance(last_value, int):
                        new_value = int(new_value)
                    # 更新上下文
                    self.context["mentioned_params"][last_param] = new_value
                    
                    param_name = self.PARAM_DISPLAY_NAMES.get(last_param, last_param)
                    resolved = f"把{param_name}改为{new_value}"
                    break
        
        # 3. 处理 "上次的" / "之前的"
        if execution_history:
            for ref in self.HISTORY_REFS:
                if ref in resolved and execution_history:
                    last_case = execution_history[-1].get("case_name", "")
                    if last_case:
                        resolved = resolved.replace(ref, f"算例{last_case}的")
        
        return resolved
    
    def detect_intent(self, user_input: str) -> Tuple[str, float]:
        """
        双路径意图识别：快速关键词 + LLM备选
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            (intent: str, confidence: float)
        """
        # 快速路径
        intent, confidence = self._keyword_intent(user_input)
        if confidence >= self.HIGH_CONFIDENCE:
            return intent, confidence
        
        # 上下文辅助判断
        context_intent = self._context_assisted_intent(user_input)
        if context_intent:
            return context_intent, self.CONTEXT_CONFIDENCE
        
        # LLM路径（如果可用且不在mock模式）
        if self.prompt_engine and hasattr(self.prompt_engine, 'mock_mode') and not self.prompt_engine.mock_mode:
            try:
                llm_intent, llm_conf = self._llm_intent_classify(user_input)
                if llm_conf > confidence:
                    return llm_intent, llm_conf
            except Exception as e:
                logger.warning(f"LLM意图分类失败: {e}")
        
        # 回退到关键词结果
        return intent if confidence > self.LOW_CONFIDENCE else "unknown", confidence
    
    def _keyword_intent(self, user_input: str) -> Tuple[str, float]:
        """快速路径：关键词匹配意图识别，返回 (intent, confidence)"""
        input_lower = user_input.lower()
        
        # 计算每个意图的匹配度
        best_intent = "unknown"
        best_confidence = 0.0
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in input_lower)
            if matches > 0:
                # 基础置信度：至少匹配一个关键词就给0.5
                # 额外置信度：每个额外匹配增加0.15
                confidence = 0.5 + (matches - 1) * 0.15
                confidence = min(confidence, 0.95)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_intent = intent
        
        return best_intent, best_confidence
    
    def _context_assisted_intent(self, user_input: str) -> Optional[str]:
        """上下文辅助判断意图"""
        intent_chain = self.context.get("intent_chain", [])
        current_focus = self.context.get("current_focus")
        
        # 如果最近是创建意图，且输入包含数值，可能是modify
        if intent_chain and intent_chain[-1] == "create":
            if any(c.isdigit() for c in user_input):
                return "modify"
        
        # 如果当前关注点是特定参数，可能是modify
        if current_focus in ["mesh", "boundary", "solver"]:
            modify_indicators = ["改", "调", "设", "变", "增大", "减小", "增加", "减少"]
            if any(ind in user_input for ind in modify_indicators):
                return "modify"
        
        return None
    
    def _llm_intent_classify(self, user_input: str) -> Tuple[str, float]:
        """LLM路径：使用LLM进行意图分类"""
        # 构建提示词
        prompt = f"""请分析以下用户输入的意图，从以下类别中选择最匹配的一个：

可选意图：
- create: 创建/建立新的仿真算例
- modify: 修改现有算例的配置
- run: 运行/开始仿真计算
- status: 查看算例状态/进度
- help: 请求帮助/说明
- explain: 解释某个概念或参数
- compare: 对比不同方案或概念
- optimize: 优化/改进配置
- unknown: 无法确定

用户输入："{user_input}"

请以JSON格式返回：{{"intent": "意图类别", "confidence": 0.0-1.0}}"""
        
        try:
            # 优先使用路由器的LLM（如果可用）
            if self.router:
                llm = self.router.get_llm("intent_recognition")
                if llm and hasattr(llm, 'chat'):
                    import json
                    task_config = self.router.get_task_config("intent_recognition")
                    response = llm.chat(
                        messages=[
                            {"role": "system", "content": "你是一个意图分类助手，只返回JSON格式结果。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=task_config.get("temperature", 0.2),
                        response_format={"type": "json_object"}
                    )
                    result = json.loads(response)
                    provider = self.router.select_provider("intent_recognition")
                    logger.info(f"[IntentResolver] 使用路由器提供商 '{provider}' 进行意图分类")
                    return result.get("intent", "unknown"), result.get("confidence", 0.5)
            
            # 回退到使用prompt_engine的LLM
            if self.prompt_engine and hasattr(self.prompt_engine, 'client') and self.prompt_engine.client:
                import json
                response = self.prompt_engine.client.chat.completions.create(
                    model=self.prompt_engine.model,
                    messages=[
                        {"role": "system", "content": "你是一个意图分类助手，只返回JSON格式结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                result = json.loads(response.choices[0].message.content)
                return result.get("intent", "unknown"), result.get("confidence", 0.5)
        except Exception as e:
            print(f"[IntentResolver] LLM意图分类失败: {e}")
        
        return "unknown", 0.0
    
    def update_context(self, user_input: str) -> None:
        """更新对话上下文"""
        # 提取参数提及
        for param, patterns in self.PARAM_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    try:
                        value_str = match.group(1)
                        if '.' in value_str or 'e' in value_str.lower():
                            value = float(value_str)
                        else:
                            value = int(value_str)
                        self.context["mentioned_params"][param] = value
                    except (ValueError, IndexError):
                        pass
                    break
        
        # 检测当前关注点
        for focus, keywords in self.FOCUS_KEYWORDS.items():
            if any(kw in user_input for kw in keywords):
                self.context["current_focus"] = focus
                break
    
    def record_intent(self, intent: str) -> None:
        """记录意图到意图链"""
        self.context["intent_chain"].append(intent)
