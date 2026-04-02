"""
物理现象路由器模块 (PhysicsRouter)
通过多轮问答确定最佳OpenFOAM求解器的路由引擎
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingDimension(Enum):
    """决策维度枚举"""
    COMPRESSIBILITY = "compressibility"
    PHASES = "phases"
    HEAT_TRANSFER = "heat_transfer"
    TURBULENCE = "turbulence"
    TURBULENCE_MODEL = "turbulence_model"
    TIME_DEPENDENCY = "time_dependency"


@dataclass
class QuestionOption:
    """问题选项数据类"""
    value: Any
    label: str
    description: Optional[str] = None


@dataclass
class RoutingQuestion:
    """路由问题数据类"""
    dimension: str
    question: str
    explanation: str
    options: List[QuestionOption]
    skippable: bool = False
    skip_condition: Optional[Dict[str, Any]] = None


@dataclass
class RoutingState:
    """路由状态数据类"""
    compressibility: Optional[bool] = None  # True=可压缩, False=不可压缩
    phases: Optional[str] = None  # single_phase/two_phase/multi_phase
    heat_transfer: Optional[str] = None  # none/natural_convection/forced_convection/conjugate
    turbulence: Optional[str] = None  # laminar/transitional/turbulent
    turbulence_model: Optional[str] = None  # kEpsilon/kOmegaSST/LES
    time_dependency: Optional[str] = None  # steady/transient


class PhysicsRouter:
    """
    问卷向导式物理现象路由器，通过多轮对话确定求解器
    
    核心功能：
    1. 通过5个决策维度（可压缩性、相态、传热、湍流、时间特性）确定最佳求解器
    2. 智能跳过逻辑：根据已有回答跳过不必要的问题
    3. 提供详细的求解器推荐和配置建议
    """
    
    # 求解器映射矩阵
    SOLVER_MATRIX: Dict[str, Dict[str, Any]] = {
        # 不可压 + 单相 + 无传热 + 层流 + 瞬态
        "incomp_single_none_lam_transient": {
            "solver": "icoFoam",
            "description": "瞬态不可压层流求解器"
        },
        # 不可压 + 单相 + 无传热 + 湍流 + 稳态
        "incomp_single_none_turb_steady": {
            "solver": "simpleFoam",
            "description": "稳态不可压湍流求解器"
        },
        # 不可压 + 单相 + 无传热 + 湍流 + 瞬态
        "incomp_single_none_turb_transient": {
            "solver": "pimpleFoam",
            "description": "瞬态不可压湍流求解器"
        },
        # 不可压 + 单相 + 传热(自然/强制) + 湍流 + 稳态
        "incomp_single_heat_turb_steady": {
            "solver": "buoyantSimpleFoam",
            "description": "稳态不可压传热求解器"
        },
        # 不可压 + 单相 + 传热(自然/强制) + 湍流 + 瞬态
        "incomp_single_heat_turb_transient": {
            "solver": "buoyantPimpleFoam",
            "description": "瞬态不可压传热求解器"
        },
        # 不可压 + 两相 + * + * + 瞬态
        "incomp_two_phase_transient": {
            "solver": "interFoam",
            "description": "VOF多相流求解器"
        },
        # 不可压 + 多相 + * + * + 瞬态
        "incomp_multi_phase_transient": {
            "solver": "multiphaseInterFoam",
            "description": "多相VOF求解器"
        },
        # 可压 + 单相 + * + 湍流 + 稳态
        "comp_single_turb_steady": {
            "solver": "rhoSimpleFoam",
            "description": "稳态可压缩湍流求解器"
        },
        # 可压 + 单相 + * + 湍流 + 瞬态
        "comp_single_turb_transient": {
            "solver": "rhoPimpleFoam",
            "description": "瞬态可压缩湍流求解器"
        },
        # 共轭传热
        "cht": {
            "solver": "chtMultiRegionFoam",
            "description": "共轭传热多区域求解器"
        }
    }
    
    # 湍流模型配置
    TURBULENCE_MODELS: Dict[str, Dict[str, Any]] = {
        "kEpsilon": {
            "name": "kEpsilon",
            "description": "k-ε湍流模型",
            "fields": ["k", "epsilon", "nut"],
            "wall_function": True,
            "yplus_requirement": "y+ > 30"
        },
        "kOmegaSST": {
            "name": "kOmegaSST",
            "description": "k-ω SST湍流模型",
            "fields": ["k", "omega", "nut"],
            "wall_function": False,
            "yplus_requirement": "y+ < 1"
        },
        "LES": {
            "name": "LES",
            "description": "大涡模拟",
            "fields": ["k", "nuSgs"],
            "wall_function": False,
            "yplus_requirement": "y+ < 1, 需要精细网格"
        }
    }
    
    # 求解器所需字典文件映射
    SOLVER_DICTS: Dict[str, List[str]] = {
        "icoFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution"],
        "simpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution", 
                       "turbulenceProperties"],
        "pimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                       "turbulenceProperties"],
        "buoyantSimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                              "thermophysicalProperties", "turbulenceProperties", "g"],
        "buoyantPimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                              "thermophysicalProperties", "turbulenceProperties", "g"],
        "interFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                      "transportProperties"],
        "multiphaseInterFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                                "transportProperties"],
        "rhoSimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                          "thermophysicalProperties", "turbulenceProperties"],
        "rhoPimpleFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                          "thermophysicalProperties", "turbulenceProperties"],
        "chtMultiRegionFoam": ["blockMeshDict", "controlDict", "fvSchemes", "fvSolution",
                               "thermophysicalProperties", "turbulenceProperties", "g"]
    }
    
    # 初始场变量映射
    INITIAL_FIELDS: Dict[str, List[str]] = {
        "icoFoam": ["p", "U"],
        "simpleFoam": ["p", "U", "k", "epsilon", "nut"],
        "pimpleFoam": ["p", "U", "k", "epsilon", "nut"],
        "buoyantSimpleFoam": ["p_rgh", "U", "T", "k", "epsilon", "nut", "alphat"],
        "buoyantPimpleFoam": ["p_rgh", "U", "T", "k", "epsilon", "nut", "alphat"],
        "interFoam": ["alpha.water", "p_rgh", "U"],
        "multiphaseInterFoam": ["alpha.*", "p_rgh", "U"],
        "rhoSimpleFoam": ["p", "U", "T", "k", "epsilon", "nut"],
        "rhoPimpleFoam": ["p", "U", "T", "k", "epsilon", "nut"],
        "chtMultiRegionFoam": ["p", "U", "T", "k", "epsilon", "nut"]
    }
    
    def __init__(self):
        """初始化PhysicsRouter"""
        self._state = RoutingState()
        self._answered_dimensions: List[str] = []
        self._current_dimension: Optional[str] = None
        self._is_complete: bool = False
        self._recommendation: Optional[Dict[str, Any]] = None
        
        logger.info("PhysicsRouter初始化完成")
    
    def _get_questions(self) -> List[RoutingQuestion]:
        """获取所有问题定义"""
        return [
            RoutingQuestion(
                dimension="compressibility",
                question="您的流动马赫数是否超过0.3？",
                explanation="马赫数Ma = 流速/音速。当Ma > 0.3时，密度变化不可忽略，需要使用可压缩求解器。对于水等液体流动，通常选择不可压。",
                options=[
                    QuestionOption(value=False, label="不可压缩（Ma < 0.3，如水流、低速气流）"),
                    QuestionOption(value=True, label="可压缩（Ma > 0.3，如高速气流、声学）")
                ]
            ),
            RoutingQuestion(
                dimension="phases",
                question="流动涉及多少相态？",
                explanation="单相流指单一介质（如水或空气），多相流涉及两种及以上介质（如气液两相、油水混合等）。",
                options=[
                    QuestionOption(value="single_phase", label="单相流（单一介质）"),
                    QuestionOption(value="two_phase", label="两相流（如气液界面）"),
                    QuestionOption(value="multi_phase", label="多相流（三种及以上介质）")
                ]
            ),
            RoutingQuestion(
                dimension="heat_transfer",
                question="是否涉及温度变化或传热？",
                explanation="传热问题需要考虑能量方程。自然对流由浮力驱动，强制对流由外力驱动，共轭传热涉及流体与固体间的热交换。",
                options=[
                    QuestionOption(value="none", label="无传热（等温流动）"),
                    QuestionOption(value="natural_convection", label="自然对流（浮力驱动）"),
                    QuestionOption(value="forced_convection", label="强制对流（外力驱动）"),
                    QuestionOption(value="conjugate", label="共轭传热（流体-固体耦合）")
                ],
                skippable=True,
                skip_condition={"phases": ["two_phase", "multi_phase"]}
            ),
            RoutingQuestion(
                dimension="turbulence",
                question="流动的雷诺数大约是多少？",
                explanation="雷诺数Re = ρUL/μ 表征惯性力与粘性力之比。Re < 2300为层流，Re > 4000为湍流，之间为过渡区。",
                options=[
                    QuestionOption(value="laminar", label="层流（Re < 2300，流动稳定分层）"),
                    QuestionOption(value="transitional", label="过渡区（2300 < Re < 4000）"),
                    QuestionOption(value="turbulent", label="湍流（Re > 4000，存在涡旋混合）")
                ],
                skippable=True,
                skip_condition={"phases": ["two_phase", "multi_phase"]}
            ),
            RoutingQuestion(
                dimension="turbulence_model",
                question="请选择湍流模型：",
                explanation="k-ε模型计算效率高，适合大多数工程应用；k-ω SST对逆压梯度和分离流更准确；LES需要精细网格但精度最高。",
                options=[
                    QuestionOption(value="kEpsilon", label="k-ε模型（标准RANS，计算高效）"),
                    QuestionOption(value="kOmegaSST", label="k-ω SST模型（对分离流更准确）"),
                    QuestionOption(value="LES", label="大涡模拟LES（高精度，需要精细网格）")
                ],
                skippable=True,
                skip_condition={
                    "turbulence": ["laminar", "transitional"],
                    "phases": ["two_phase", "multi_phase"]
                }
            ),
            RoutingQuestion(
                dimension="time_dependency",
                question="关注稳态结果还是瞬态过程？",
                explanation="稳态求解器只求解最终状态，计算快；瞬态求解器捕捉时间演化，适合非定常现象（如涡旋脱落、波动）。",
                options=[
                    QuestionOption(value="steady", label="稳态（只关心最终结果）"),
                    QuestionOption(value="transient", label="瞬态（关心时间演化过程）")
                ]
            )
        ]
    
    def _should_skip_question(self, question: RoutingQuestion) -> bool:
        """判断是否应该跳过某个问题"""
        if not question.skippable or not question.skip_condition:
            return False
        
        for dimension, skip_values in question.skip_condition.items():
            state_value = getattr(self._state, dimension, None)
            if state_value in skip_values:
                return True
        
        return False
    
    def _get_next_question(self) -> Optional[RoutingQuestion]:
        """获取下一个需要回答的问题"""
        questions = self._get_questions()
        
        for question in questions:
            # 如果已经回答过，跳过
            if question.dimension in self._answered_dimensions:
                continue
            
            # 检查是否应该跳过
            if self._should_skip_question(question):
                # 记录为已回答（跳过）
                self._answered_dimensions.append(question.dimension)
                continue
            
            return question
        
        return None
    
    def _build_solver_key(self) -> str:
        """构建求解器查找键"""
        # 共轭传热特殊情况
        if self._state.heat_transfer == "conjugate":
            return "cht"
        
        # 多相流特殊情况
        if self._state.phases == "two_phase":
            return "incomp_two_phase_transient"
        if self._state.phases == "multi_phase":
            return "incomp_multi_phase_transient"
        
        # 构建标准键
        parts = []
        
        # 可压缩性
        parts.append("comp" if self._state.compressibility else "incomp")
        
        # 相态（简化为 single）
        parts.append("single")
        
        # 传热
        if self._state.heat_transfer and self._state.heat_transfer != "none":
            parts.append("heat")
        else:
            parts.append("none")
        
        # 湍流
        if self._state.turbulence == "laminar":
            parts.append("lam")
        else:
            parts.append("turb")
        
        # 时间特性
        parts.append(self._state.time_dependency or "transient")
        
        return "_".join(parts)
    
    def _generate_recommendation(self) -> Dict[str, Any]:
        """生成求解器推荐"""
        solver_key = self._build_solver_key()
        solver_info = self.SOLVER_MATRIX.get(solver_key, {
            "solver": "pimpleFoam",
            "description": "通用不可压瞬态求解器"
        })
        
        solver = solver_info["solver"]
        
        # 构建推理说明
        reasoning_parts = []
        if self._state.compressibility is not None:
            reasoning_parts.append("可压缩" if self._state.compressibility else "不可压")
        if self._state.phases:
            phase_map = {
                "single_phase": "单相",
                "two_phase": "两相",
                "multi_phase": "多相"
            }
            reasoning_parts.append(phase_map.get(self._state.phases, self._state.phases))
        if self._state.heat_transfer and self._state.heat_transfer != "none":
            heat_map = {
                "natural_convection": "自然对流",
                "forced_convection": "强制对流",
                "conjugate": "共轭传热"
            }
            reasoning_parts.append(heat_map.get(self._state.heat_transfer, self._state.heat_transfer))
        if self._state.turbulence:
            turb_map = {
                "laminar": "层流",
                "transitional": "过渡区",
                "turbulent": "湍流"
            }
            reasoning_parts.append(turb_map.get(self._state.turbulence, self._state.turbulence))
        if self._state.turbulence_model:
            model_map = {
                "kEpsilon": "k-ε",
                "kOmegaSST": "k-ω SST",
                "LES": "LES"
            }
            reasoning_parts.append(model_map.get(self._state.turbulence_model, self._state.turbulence_model))
        if self._state.time_dependency:
            time_map = {
                "steady": "稳态",
                "transient": "瞬态"
            }
            reasoning_parts.append(time_map.get(self._state.time_dependency, self._state.time_dependency))
        
        reasoning = f"检测到：{' + '.join(reasoning_parts)} -> 推荐 {solver}"
        
        # 获取湍流模型
        turbulence_model = None
        if self._state.turbulence == "turbulent" and self._state.turbulence_model:
            turbulence_model = self._state.turbulence_model
        
        # 构建警告
        warnings = []
        if turbulence_model == "kOmegaSST":
            warnings.append("建议确保壁面网格y+ < 1以匹配k-omega SST壁面处理")
        elif turbulence_model == "LES":
            warnings.append("LES需要非常精细的网格（y+ < 1）和较小的时间步长")
        elif turbulence_model == "kEpsilon":
            warnings.append("k-ε模型需要使用壁面函数，确保壁面网格y+ > 30")
        
        if self._state.turbulence == "transitional":
            warnings.append("过渡区流动建议使用专门的转捩模型或进行网格敏感性验证")
        
        # 构建物理标签
        physics_tags = {
            "compressible": self._state.compressibility,
            "phases": self._state.phases,
            "heat": self._state.heat_transfer,
            "turbulence": turbulence_model or self._state.turbulence,
            "transient": self._state.time_dependency == "transient"
        }
        
        recommendation = {
            "solver": solver,
            "reasoning": reasoning,
            "turbulence_model": turbulence_model,
            "required_dicts": self.SOLVER_DICTS.get(solver, []),
            "initial_fields": self.INITIAL_FIELDS.get(solver, []),
            "warnings": warnings,
            "physics_tags": physics_tags
        }
        
        logger.info(f"生成求解器推荐: {solver}")
        return recommendation
    
    def start_routing(self) -> Dict[str, Any]:
        """
        开始路由流程，返回第一个问题
        
        Returns:
            包含第一个问题的字典
        """
        self.reset()
        
        first_question = self._get_next_question()
        if first_question:
            self._current_dimension = first_question.dimension
            return {
                "status": "next_question",
                "question": {
                    "dimension": first_question.dimension,
                    "question": first_question.question,
                    "explanation": first_question.explanation,
                    "options": [
                        {"value": opt.value, "label": opt.label}
                        for opt in first_question.options
                    ]
                },
                "progress": self.get_progress()
            }
        
        return {
            "status": "error",
            "message": "无法获取第一个问题"
        }
    
    def answer_question(self, dimension: str, answer: Any) -> Dict[str, Any]:
        """
        处理用户回答，返回下一个问题或最终推荐
        
        Args:
            dimension: 回答的维度
            answer: 回答的值
            
        Returns:
            包含下一个问题或最终推荐的字典
            {"status": "next_question"|"complete", "question": ... | "recommendation": ...}
        """
        # 验证维度（允许回答当前维度或已跳过的维度）
        if dimension != self._current_dimension:
            # 检查是否是已经回答过的维度
            if dimension in self._answered_dimensions:
                logger.debug(f"维度 {dimension} 已回答，忽略")
                return {
                    "status": "next_question",
                    "question": self._get_current_question_dict(),
                    "progress": self.get_progress()
                }
            logger.warning(f"维度不匹配: 期望 {self._current_dimension}, 实际 {dimension}")
            return {
                "status": "error",
                "message": f"期望回答维度 '{self._current_dimension}', 但收到 '{dimension}'"
            }
        
        # 保存回答
        setattr(self._state, dimension, answer)
        self._answered_dimensions.append(dimension)
        
        logger.debug(f"回答维度 {dimension}: {answer}")
        
        # 获取下一个问题
        next_question = self._get_next_question()
        
        if next_question:
            self._current_dimension = next_question.dimension
            return {
                "status": "next_question",
                "question": {
                    "dimension": next_question.dimension,
                    "question": next_question.question,
                    "explanation": next_question.explanation,
                    "options": [
                        {"value": opt.value, "label": opt.label}
                        for opt in next_question.options
                    ]
                },
                "progress": self.get_progress()
            }
        else:
            # 所有问题回答完毕，生成推荐
            self._is_complete = True
            self._recommendation = self._generate_recommendation()
            return {
                "status": "complete",
                "recommendation": self._recommendation,
                "progress": self.get_progress()
            }
    
    def _get_current_question_dict(self) -> Dict[str, Any]:
        """获取当前问题的字典表示"""
        questions = self._get_questions()
        for question in questions:
            if question.dimension == self._current_dimension:
                return {
                    "dimension": question.dimension,
                    "question": question.question,
                    "explanation": question.explanation,
                    "options": [
                        {"value": opt.value, "label": opt.label}
                        for opt in question.options
                    ]
                }
        return {}
    
    def get_recommendation(self) -> Optional[Dict[str, Any]]:
        """
        获取最终推荐
        
        Returns:
            推荐结果字典，如果未完成则返回None
        """
        if not self._is_complete:
            return None
        return self._recommendation
    
    def get_progress(self) -> Dict[str, Any]:
        """
        获取当前进度
        
        Returns:
            进度信息字典
        """
        total_questions = len(self._get_questions())
        answered_count = len(self._answered_dimensions)
        
        # 计算实际总问题数（考虑跳过）
        remaining_questions = 0
        for question in self._get_questions():
            if question.dimension not in self._answered_dimensions:
                if not self._should_skip_question(question):
                    remaining_questions += 1
        
        actual_total = answered_count + remaining_questions
        
        return {
            "answered": answered_count,
            "total": actual_total,
            "percentage": int((answered_count / actual_total) * 100) if actual_total > 0 else 0,
            "current_dimension": self._current_dimension,
            "is_complete": self._is_complete
        }
    
    def reset(self) -> None:
        """重置路由器状态"""
        self._state = RoutingState()
        self._answered_dimensions = []
        self._current_dimension = None
        self._is_complete = False
        self._recommendation = None
        
        logger.debug("PhysicsRouter状态已重置")
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        获取当前状态（用于调试和显示）
        
        Returns:
            当前状态字典
        """
        return {
            "compressibility": self._state.compressibility,
            "phases": self._state.phases,
            "heat_transfer": self._state.heat_transfer,
            "turbulence": self._state.turbulence,
            "turbulence_model": self._state.turbulence_model,
            "time_dependency": self._state.time_dependency,
            "answered_dimensions": self._answered_dimensions,
            "current_dimension": self._current_dimension,
            "is_complete": self._is_complete
        }
    
    def get_solver_info(self, solver_name: str) -> Dict[str, Any]:
        """
        获取求解器详细信息
        
        Args:
            solver_name: 求解器名称
            
        Returns:
            求解器信息字典
        """
        # 在SOLVER_MATRIX中查找
        for key, info in self.SOLVER_MATRIX.items():
            if info["solver"] == solver_name:
                return {
                    "name": solver_name,
                    "description": info["description"],
                    "required_dicts": self.SOLVER_DICTS.get(solver_name, []),
                    "initial_fields": self.INITIAL_FIELDS.get(solver_name, [])
                }
        
        # 返回默认信息
        return {
            "name": solver_name,
            "description": "未知求解器",
            "required_dicts": self.SOLVER_DICTS.get(solver_name, []),
            "initial_fields": self.INITIAL_FIELDS.get(solver_name, [])
        }


def create_physics_router() -> PhysicsRouter:
    """创建新的PhysicsRouter实例"""
    return PhysicsRouter()


if __name__ == "__main__":
    # 测试PhysicsRouter
    print("=" * 60)
    print("PhysicsRouter 模块测试")
    print("=" * 60)
    
    router = create_physics_router()
    
    # 测试1: 启动路由
    print("\n【测试1: 启动路由】")
    result = router.start_routing()
    print(f"状态: {result['status']}")
    print(f"问题: {result['question']['question']}")
    print(f"进度: {result['progress']['percentage']}%")
    
    # 测试2: 回答所有问题（不可压+单相+无传热+层流+瞬态）-> icoFoam
    print("\n【测试2: 完整流程 - icoFoam】")
    router.reset()
    result = router.start_routing()  # 必须先启动路由
    
    answers = [
        ("compressibility", False),  # 不可压
        ("phases", "single_phase"),  # 单相
        ("heat_transfer", "none"),  # 无传热
        ("turbulence", "laminar"),  # 层流
        ("time_dependency", "transient")  # 瞬态
    ]
    
    for dimension, answer in answers:
        result = router.answer_question(dimension, answer)
        print(f"\n回答: {dimension} = {answer}")
        if result['status'] == 'next_question':
            print(f"下一个问题: {result['question']['question']}")
        else:
            print(f"推荐求解器: {result['recommendation']['solver']}")
            print(f"推理: {result['recommendation']['reasoning']}")
    
    # 测试3: 测试跳过逻辑（湍流+稳态）-> simpleFoam
    print("\n【测试3: 测试跳过逻辑 - simpleFoam】")
    router.reset()
    result = router.start_routing()  # 必须先启动路由
    
    answers2 = [
        ("compressibility", False),  # 不可压
        ("phases", "single_phase"),  # 单相
        ("heat_transfer", "none"),  # 无传热
        ("turbulence", "turbulent"),  # 湍流
        ("turbulence_model", "kEpsilon"),  # k-ε模型
        ("time_dependency", "steady")  # 稳态
    ]
    
    for dimension, answer in answers2:
        result = router.answer_question(dimension, answer)
        print(f"回答: {dimension} = {answer}")
        if result['status'] == 'complete':
            print(f"推荐求解器: {result['recommendation']['solver']}")
            print(f"推理: {result['recommendation']['reasoning']}")
    
    # 测试4: 多相流测试 -> interFoam
    print("\n【测试4: 多相流 - interFoam】")
    router.reset()
    result = router.start_routing()  # 必须先启动路由
    
    answers3 = [
        ("compressibility", False),  # 不可压
        ("phases", "two_phase"),  # 两相
        ("time_dependency", "transient")  # 瞬态
    ]
    
    for dimension, answer in answers3:
        result = router.answer_question(dimension, answer)
        print(f"回答: {dimension} = {answer}")
        if result['status'] == 'complete':
            print(f"推荐求解器: {result['recommendation']['solver']}")
            print(f"推理: {result['recommendation']['reasoning']}")
            print(f"所需字典: {result['recommendation']['required_dicts']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
