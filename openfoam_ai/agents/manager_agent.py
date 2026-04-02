"""
Manager Agent
交互与记忆总控Agent - 负责任务调度、用户交互和状态管理
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from .prompt_engine import PromptEngine, ConfigRefiner

logger = logging.getLogger(__name__)
from .intent_resolver import IntentResolver
from .case_modifier import CaseModifier
from .error_recovery import ErrorRecovery
from ..core.case_manager import CaseManager, create_cavity_case
from ..core.validators import validate_simulation_config, validate_with_friendly_errors, PhysicsValidator
from ..core.file_generator import CaseGenerator
from ..core.openfoam_runner import OpenFOAMRunner, SolverMonitor
from ..core.physics_router import PhysicsRouter
from ..core.llm_router import MultiLLMRouter


@dataclass
class TaskPlan:
    """任务计划"""
    task_id: str
    description: str
    steps: List[Dict[str, Any]]
    requires_confirmation: bool
    estimated_time: str


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    message: str
    outputs: Dict[str, Any]
    logs: List[str]


class ManagerAgent:
    """
    管理Agent
    
    核心职责：
    1. 接收用户输入，理解意图
    2. 生成执行计划
    3. 协调各子Agent完成任务
    4. 管理会话状态
    5. 与用户确认关键操作
    """
    
    def __init__(self,
                 case_manager: Optional[CaseManager] = None,
                 prompt_engine: Optional[PromptEngine] = None,
                 config_refiner: Optional[ConfigRefiner] = None):
        """
        初始化ManagerAgent
        
        Args:
            case_manager: 算例管理器
            prompt_engine: 提示词引擎
            config_refiner: 配置优化器
        """
        self.case_manager = case_manager or CaseManager("./cases")
        self.prompt_engine = prompt_engine or PromptEngine()
        self.config_refiner = config_refiner or ConfigRefiner()
        
        # 会话状态
        self.current_case: Optional[str] = None
        self.current_config: Optional[Dict[str, Any]] = None
        self.execution_history: List[Dict[str, Any]] = []
        
        # 配置
        self.require_confirmation = True  # 是否需要确认
        self.auto_fix = True  # 是否自动修复
        
        # 上下文管理
        self.conversation_context = {
            "intent_chain": [],           # 意图链历史
            "mentioned_params": {},       # 最近提及的参数和值
            "current_focus": None,        # 当前关注点（如 "mesh", "boundary"）
            "unresolved_questions": [],   # 未解决的问题
            "last_config_change": None,   # 最近一次配置变更
        }
        
        # 初始化LLM路由器（非mock模式时）
        self.router: Optional[MultiLLMRouter] = None
        if not getattr(self.prompt_engine, 'mock_mode', True):
            try:
                self.router = MultiLLMRouter()
                logger.info(f"[ManagerAgent] LLM路由: {self.router.get_routing_info()}")
            except Exception as e:
                logger.warning(f"[ManagerAgent] 初始化LLM路由器失败: {e}")
        
        # 初始化子模块
        self.intent_resolver = IntentResolver(
            prompt_engine=self.prompt_engine,
            context=self.conversation_context,
            router=self.router
        )
        self.case_modifier = CaseModifier()
        self.error_recovery = ErrorRecovery()
        self.physics_router = PhysicsRouter()
        
        # 初始化 OpenFOAMRunner（延迟创建，需要时根据案例路径初始化）
        self.runner: Optional[OpenFOAMRunner] = None
        self._runner_case_path: Optional[Path] = None
        
        # 路由状态
        self._routing_mode = False  # 是否处于路由问答模式
    
    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户输入
        
        Args:
            user_input: 自然语言输入
            
        Returns:
            响应字典
        """
        print(f"[ManagerAgent] 处理输入: {user_input[:50]}...")
        
        # 如果处于路由模式，处理路由问答
        if self._routing_mode:
            return self._handle_routing_input(user_input)
        
        # 指代消解
        resolved_input = self.intent_resolver.resolve_references(
            user_input, self.execution_history
        )
        if resolved_input != user_input:
            print(f"[ManagerAgent] 指代消解: '{user_input}' -> '{resolved_input}'")
        
        # 使用消解后的输入进行后续处理
        # 更新上下文
        self.intent_resolver.update_context(resolved_input)
        
        # 意图识别（使用新的双路径方法）
        intent, confidence = self.intent_resolver.detect_intent(resolved_input)
        
        # 记录意图链
        self.intent_resolver.record_intent(intent)
        
        if intent == "create":
            return self._handle_create_case(user_input)
        elif intent == "modify":
            return self._handle_modify_case(user_input)
        elif intent == "run":
            return self._handle_run()
        elif intent == "status":
            return self._handle_check_status()
        elif intent == "help":
            return self._handle_help()
        elif intent == "explain":
            return self._handle_explain(user_input)
        elif intent == "compare":
            return self._handle_compare(user_input)
        elif intent == "optimize":
            return self._handle_optimize(user_input)
        elif intent == "routing":
            return self._handle_routing()
        else:
            return {
                "type": "unknown",
                "message": "未能理解您的意图。请尝试描述：\n- 创建算例：\"建立一个方腔驱动流\"\n- 运行计算：\"开始计算\"\n- 查看状态：\"查看状态\"\n- 解释概念：\"什么是库朗数\"\n- 对比方案：\"icoFoam和simpleFoam有什么区别\"\n- 优化建议：\"优化当前配置\"\n- 选择求解器：\"帮我选择求解器\""
            }
    
    def get_stage_suggestions(self) -> List[str]:
        """根据当前对话阶段返回建议操作"""
        stage = self.conversation_context.get("current_stage", "exploring")
        
        suggestions = {
            "exploring": [
                "💡 试试说: '创建一个方腔驱动流算例'",
                "💡 试试说: '什么是CFD仿真？'",
                "💡 或者使用向导模式标签页"
            ],
            "configuring": [
                "💡 试试说: '把网格改成40x40'",
                "💡 试试说: '运动粘度设为1e-6'",
                "💡 试试说: '查看当前配置'"
            ],
            "running": [
                "💡 试试说: '查看计算状态'",
                "💡 试试说: '计算进度如何？'"
            ],
            "reviewing": [
                "💡 试试说: '优化网格设置'",
                "💡 试试说: '对比不同方案'"
            ]
        }
        
        return suggestions.get(stage, suggestions["exploring"])
    
    def _handle_routing(self) -> Dict[str, Any]:
        """
        处理求解器路由请求 - 启动问卷向导
        
        Returns:
            路由问答响应
        """
        self._routing_mode = True
        self.physics_router.reset()
        
        result = self.physics_router.start_routing()
        
        if result["status"] == "next_question":
            question = result["question"]
            options_text = "\n".join([
                f"  {i+1}. {opt['label']}"
                for i, opt in enumerate(question["options"])
            ])
            
            return {
                "type": "routing_question",
                "message": f"📋 {question['question']}\n\n💡 {question['explanation']}\n\n选项：\n{options_text}\n\n请回复选项编号（1-{len(question['options'])}）",
                "dimension": question["dimension"],
                "options": question["options"],
                "progress": result["progress"]
            }
        else:
            self._routing_mode = False
            return {
                "type": "error",
                "message": "启动路由失败"
            }
    
    def _handle_routing_input(self, user_input: str) -> Dict[str, Any]:
        """
        处理路由模式下的用户输入
        
        Args:
            user_input: 用户输入（选项编号或值）
            
        Returns:
            下一个问题或推荐结果
        """
        # 尝试解析用户输入
        answer = self._parse_routing_answer(user_input)
        
        if answer is None:
            return {
                "type": "routing_question",
                "message": "无法识别您的选择，请回复选项编号（如：1、2）",
                "progress": self.physics_router.get_progress()
            }
        
        # 获取当前维度并提交答案
        current_state = self.physics_router.get_current_state()
        dimension = current_state.get("current_dimension")
        
        if not dimension:
            self._routing_mode = False
            return {
                "type": "error",
                "message": "路由状态错误"
            }
        
        result = self.physics_router.answer_question(dimension, answer)
        
        if result["status"] == "next_question":
            question = result["question"]
            options_text = "\n".join([
                f"  {i+1}. {opt['label']}"
                for i, opt in enumerate(question["options"])
            ])
            
            return {
                "type": "routing_question",
                "message": f"📋 {question['question']}\n\n💡 {question['explanation']}\n\n选项：\n{options_text}\n\n请回复选项编号（1-{len(question['options'])}）",
                "dimension": question["dimension"],
                "options": question["options"],
                "progress": result["progress"]
            }
        elif result["status"] == "complete":
            # 路由完成，退出路由模式
            self._routing_mode = False
            recommendation = result["recommendation"]
            
            # 构建推荐信息
            message = f"""✅ 求解器推荐完成！

🔧 推荐求解器：{recommendation['solver']}
📝 {recommendation['reasoning']}

📦 所需配置文件：
  {', '.join(recommendation['required_dicts'])}

🎯 初始场变量：
  {', '.join(recommendation['initial_fields'])}"""
            
            if recommendation['turbulence_model']:
                message += f"\n\n🌊 湍流模型：{recommendation['turbulence_model']}"
            
            if recommendation['warnings']:
                warnings_text = '\n  ⚠️ '.join([''] + recommendation['warnings'])
                message += f"\n\n⚠️ 注意事项：{warnings_text}"
            
            # 将推荐结果保存到当前配置
            if self.current_config is None:
                self.current_config = {}
            self.current_config["solver"] = {
                "name": recommendation['solver'],
                "turbulence_model": recommendation['turbulence_model']
            }
            self.current_config["physics_type"] = "compressible" if recommendation['physics_tags'].get('compressible') else "incompressible"
            
            return {
                "type": "routing_complete",
                "message": message,
                "recommendation": recommendation
            }
        else:
            return {
                "type": "error",
                "message": f"路由处理错误: {result.get('message', '未知错误')}"
            }
    
    def _parse_routing_answer(self, user_input: str) -> Any:
        """
        解析路由问答的用户输入
        
        Args:
            user_input: 用户输入字符串
            
        Returns:
            解析后的答案值，解析失败返回None
        """
        user_input = user_input.strip()
        
        # 获取当前问题
        current_state = self.physics_router.get_current_state()
        dimension = current_state.get("current_dimension")
        
        if not dimension:
            return None
        
        # 尝试解析为数字选项
        try:
            option_index = int(user_input) - 1
            
            # 获取当前问题的选项
            from ..core.physics_router import PhysicsRouter
            router = PhysicsRouter()
            questions = router._get_questions()
            
            for question in questions:
                if question.dimension == dimension:
                    if 0 <= option_index < len(question.options):
                        return question.options[option_index].value
                    break
        except ValueError:
            pass
        
        # 尝试直接匹配选项值
        if user_input.lower() in ["true", "yes", "是", "可压缩"]:
            return True
        if user_input.lower() in ["false", "no", "否", "不可压缩"]:
            return False
        
        # 直接返回字符串值
        return user_input
    
    def _handle_create_case(self, user_input: str) -> Dict[str, Any]:
        """
        处理创建算例请求
            
        流程：
        1. LLM 理解需求生成配置
        2. 本地优化配置
        3. 检查求解器，必要时启动路由
        4. 验证配置
        5. 生成案例文件
        6. 返回可运行提示
        """
            
        # 1. LLM理解需求
        raw_config = self.prompt_engine.natural_language_to_config(user_input)
            
        # 2. 本地优化
        config = self.config_refiner.refine(raw_config)
            
        # 3. 检查是否明确指定了求解器，如果没有则启动路由
        solver_name = config.get("solver", {}).get("name", "")
        if not solver_name or solver_name == "unknown":
            # 未明确指定求解器，启动路由流程
            logger.info("未明确指定求解器，启动PhysicsRouter")
            return self._handle_routing()
            
        # 4. 检查缺失的关键参数
        missing_params = self._check_missing_critical_params(config)
        if missing_params:
            # 有关键参数缺失，返回引导式追问
            hints = "\n".join([f"• {p['name']}：{p['hint']}\n  {p['example']}" for p in missing_params])
            return {
                "type": "clarification_needed",
                "message": f"为了创建合适的算例，我需要了解更多信息：\n\n{hints}",
                "missing_params": missing_params,
                "partial_config": config
            }
            
        # 5. 使用友好验证
        passed, friendly_errors, suggestions = validate_with_friendly_errors(config)
            
        if not passed:
            # 尝试自动修复
            self.error_recovery.set_config(config)
            auto_fixed_config, fix_log = self.error_recovery.try_auto_fix(config, friendly_errors)
            if auto_fixed_config:
                # 自动修复成功，用修复后的配置继续
                config = auto_fixed_config
                # 记录修复日志
                print(f"[ManagerAgent] 自动修复成功: {fix_log}")
            else:
                # 自动修复失败，返回友好错误和修复选项
                return {
                    "type": "validation_error",
                    "message": "配置验证发现以下问题：\n" +
                        "\n".join(f"• {e['message']}" for e in friendly_errors),
                    "errors": friendly_errors,
                    "suggestions": suggestions,
                    "fix_options": self.error_recovery.generate_fix_options(config, friendly_errors),
                    "config": config
                }
            
        # 6. 保存配置
        self.current_config = config
        self.current_case = config.get("task_id", f"case_{int(time.time())}")
            
        # 7. 更新ErrorRecovery的配置
        self.error_recovery.set_config(config)
            
        # 8. 生成案例文件
        case_path = self._generate_case_files()
            
        if case_path:
            # 生成成功
            return {
                "type": "case_created",
                "message": f"✅ 算例创建成功！\n\n" +
                          f"📁 案例路径: {case_path}\n\n" +
                          f"📋 配置摘要:\n{self._summarize_config(config)}\n\n" +
                          f"💡 您可以输入「运行仿真」或「开始计算」来启动仿真。",
                "case_path": str(case_path),
                "config_summary": self._summarize_config(config)
            }
        else:
            # 生成失败，返回计划让用户手动确认
            plan = self._generate_plan("create", config)
            return {
                "type": "plan",
                "message": f"我理解了您的需求，准备创建算例：{self.current_case}\n\n" +
                          f"案例文件生成失败，请确认后重试。",
                "plan": asdict(plan),
                "config_summary": self._summarize_config(config),
                "requires_confirmation": plan.requires_confirmation
            }
        
    def _generate_case_files(self) -> Optional[Path]:
        """
        生成案例文件
            
        Returns:
            案例路径，如果生成失败则返回 None
        """
        if not self.current_config or not self.current_case:
            return None
            
        try:
            # 创建算例目录
            case_path = self.case_manager.create_case(
                self.current_case,
                self.current_config.get("physics_type", "incompressible")
            )
            case_path = Path(case_path)
                
            # 生成所有配置文件
            generator = CaseGenerator(self.current_config)
            generator.generate_all(case_path)
                
            # 保存案例信息
            self.case_manager.update_case_status(
                self.current_case,
                "created",
                self.current_config.get("solver", {}).get("name", "")
            )
                
            logger.info(f"[ManagerAgent] 案例文件生成成功: {case_path}")
            return case_path
                
        except Exception as e:
            logger.error(f"[ManagerAgent] 生成案例文件失败: {e}")
            return None
    
    def _check_missing_critical_params(self, config: dict) -> list:
        """检查配置中缺失的关键参数，返回需要用户补充的信息"""
        missing = []
        
        # 检查几何参数
        geom = config.get("geometry", {}).get("dimensions", {})
        if not geom or all(v in [None, 0, 0.0] for v in geom.values()):
            missing.append({
                "name": "几何尺寸",
                "hint": "请提供计算域的长度、宽度、高度（单位：米）",
                "example": "例如：1m x 1m x 0.1m"
            })
        
        # 检查关键物理参数
        if not config.get("nu"):
            missing.append({
                "name": "流体类型或运动粘度",
                "hint": "请说明模拟什么流体（水/空气/油），或直接给出运动粘度值",
                "example": "例如：模拟水流（nu=1e-6）或空气（nu=1.5e-5）"
            })
        
        return missing
    
    def execute_plan(self, plan_type: str, confirmed: bool = True, max_retries: int = 2) -> ExecutionResult:
        """
        执行计划
        
        Args:
            plan_type: 计划类型
            confirmed: 是否已确认
            max_retries: 失败时最大重试次数
            
        Returns:
            执行结果
        """
        if self.require_confirmation and not confirmed:
            return ExecutionResult(
                success=False,
                message="操作需要用户确认",
                outputs={},
                logs=[]
            )
        
        if plan_type == "create":
            result = self._execute_create()
        elif plan_type == "run":
            result = self._execute_run()
        else:
            return ExecutionResult(
                success=False,
                message=f"未知计划类型: {plan_type}",
                outputs={},
                logs=[]
            )
        
        # 如果失败，尝试自动修复并重试
        retry_count = 0
        while not result.success and retry_count < max_retries:
            retry_count += 1
            fix_result = self.error_recovery.attempt_recovery(result, result.logs)
            if fix_result:
                # 重新执行
                if plan_type == "create":
                    result = self._execute_create()
                else:
                    result = self._execute_run()
            else:
                break
        
        return result
    
    def _execute_create(self) -> ExecutionResult:
        """执行创建算例"""
        logs = []
        
        try:
            # 1. 创建算例目录
            case_path = self.case_manager.create_case(
                self.current_case,
                self.current_config.get("physics_type", "incompressible")
            )
            logs.append(f"创建算例目录: {case_path}")
            
            # 2. 生成所有文件
            generator = CaseGenerator(self.current_config)
            generator.generate_all(case_path)
            logs.append("生成所有配置文件")
            
            # 3. 运行blockMesh
            runner = OpenFOAMRunner(case_path)
            success, log = runner.run_blockmesh()
            logs.append(f"blockMesh: {'成功' if success else '失败'}")
            
            if not success:
                return ExecutionResult(
                    success=False,
                    message="网格生成失败",
                    outputs={"case_path": str(case_path)},
                    logs=logs
                )
            
            # 4. 运行checkMesh
            success, log, metrics = runner.run_checkmesh()
            logs.append(f"checkMesh: {'通过' if success else '警告'}")
            logs.append(f"网格质量: 最大非正交性={metrics.get('non_orthogonality_max', 'N/A')}")
            
            # 更新状态
            self.case_manager.update_case_status(
                self.current_case, 
                "meshed",
                self.current_config.get("solver", {}).get("name", "")
            )
            
            return ExecutionResult(
                success=True,
                message=f"算例 {self.current_case} 创建完成，网格已生成",
                outputs={
                    "case_path": str(case_path),
                    "mesh_metrics": metrics
                },
                logs=logs
            )
            
        except Exception as e:
            logs.append(f"错误: {str(e)}")
            return ExecutionResult(
                success=False,
                message=f"创建失败: {str(e)}",
                outputs={},
                logs=logs
            )
    
    def _execute_run(self) -> ExecutionResult:
        """执行仿真计算"""
        logs = []
        
        if not self.current_case:
            return ExecutionResult(
                success=False,
                message="没有活动的算例",
                outputs={},
                logs=logs
            )
        
        case_path = self.case_manager.get_case(self.current_case)
        if not case_path:
            return ExecutionResult(
                success=False,
                message=f"找不到算例: {self.current_case}",
                outputs={},
                logs=logs
            )
        
        try:
            runner = OpenFOAMRunner(case_path)
            monitor = SolverMonitor(runner)
            
            solver_name = self.current_config.get("solver", {}).get("name", "icoFoam")
            
            logs.append(f"启动求解器: {solver_name}")
            
            # 运行并监控
            final_metrics = None
            for state, metrics in monitor.monitor(solver_name):
                final_metrics = metrics
                
                # 每100步输出一次日志
                if len(monitor.metrics_history) % 100 == 0:
                    logs.append(f"Time={metrics.time:.4f}, Co={metrics.courant_max:.2f}")
                
                # 检测发散
                if state.value == "diverging":
                    logs.append("警告：检测到发散趋势")
                    if self.auto_fix:
                        logs.append("尝试自动修复...")
                        # 这里可以实现自愈逻辑
                
                # 检测完成
                if state.value in ["completed", "converged"]:
                    break
            
            # 获取摘要
            summary = monitor.get_summary()
            
            # 更新状态
            final_status = "converged" if summary.get("final_state") == "converged" else "completed"
            self.case_manager.update_case_status(self.current_case, final_status)
            
            return ExecutionResult(
                success=True,
                message=f"计算完成，最终时间={summary.get('final_time', 'N/A')}",
                outputs=summary,
                logs=logs
            )
            
        except Exception as e:
            logs.append(f"错误: {str(e)}")
            return ExecutionResult(
                success=False,
                message=f"计算失败: {str(e)}",
                outputs={},
                logs=logs
            )
    
    def _generate_plan(self, task_type: str, config: Dict[str, Any]) -> TaskPlan:
        """生成任务计划"""
        
        steps = []
        
        if task_type == "create":
            steps = [
                {"step": 1, "action": "创建算例目录", "target": config.get("task_id")},
                {"step": 2, "action": "生成blockMeshDict", "details": "网格定义"},
                {"step": 3, "action": "生成controlDict", "details": "求解器控制"},
                {"step": 4, "action": "生成初始场", "details": "U, p, T(如果需要)"},
                {"step": 5, "action": "运行blockMesh", "details": "生成网格"},
                {"step": 6, "action": "运行checkMesh", "details": "网格质量检查"}
            ]
        
        return TaskPlan(
            task_id=config.get("task_id", "unknown"),
            description=f"{task_type} task",
            steps=steps,
            requires_confirmation=True,
            estimated_time="1-2分钟"
        )
    
    def _summarize_config(self, config: Dict[str, Any]) -> str:
        """生成配置摘要"""
        physics = config.get("physics_type", "unknown")
        solver = config.get("solver", {}).get("name", "unknown")
        
        geom = config.get("geometry", {})
        dims = geom.get("dimensions", {})
        res = geom.get("mesh_resolution", {})
        
        total_cells = res.get("nx", 1) * res.get("ny", 1) * res.get("nz", 1)
        
        summary = f"""物理类型: {physics}
求解器: {solver}
几何尺寸: {dims.get('L', '?')} x {dims.get('W', '?')} x {dims.get('H', '?')}
网格: {res.get('nx', '?')} x {res.get('ny', '?')} x {res.get('nz', '?')} (共约{total_cells}单元)
运行时间: 0 到 {config.get('solver', {}).get('endTime', '?')} 秒"""
        
        return summary
    
    def _handle_modify_case(self, user_input: str) -> Dict[str, Any]:
        """处理修改算例请求"""
        if not self.current_config:
            return {
                "type": "error",
                "message": "当前没有活动的算例配置。请先创建一个算例。"
            }
        
        # 1. 解析修改意图：哪个参数要改成什么值
        modifications = self.case_modifier.parse_modifications(user_input)
        
        if not modifications:
            return {
                "type": "clarification_needed",
                "message": self.case_modifier.get_modification_hints()
            }
        
        # 2. 应用修改到配置
        new_config = self.case_modifier.apply_modifications(self.current_config, modifications)
        
        # 3. 验证新配置
        passed, errors, suggestions = validate_with_friendly_errors(new_config)
        
        if not passed:
            return {
                "type": "validation_error",
                "message": "修改后的配置存在问题：\n" + 
                           "\n".join(f"• {e['message']}" for e in errors),
                "suggestions": suggestions
            }
        
        # 4. 保存配置，显示变更摘要
        old_config = self.current_config
        self.current_config = new_config
        self.conversation_context["last_config_change"] = modifications
        
        change_summary = self.case_modifier.generate_change_summary(old_config, new_config)
        
        return {
            "type": "modified",
            "message": f"配置已更新：\n{change_summary}",
            "config_summary": self._summarize_config(new_config)
        }
    
    def _handle_run(self) -> Dict[str, Any]:
        """
        处理运行仿真请求 - 端到端仿真流程
        
        流程：
        1. 检查是否有活动算例
        2. 检查执行环境是否可用
        3. 获取案例路径和求解器名称
        4. 调用 run_full_pipeline() 执行仿真
        5. 生成结果可视化
        6. 返回格式化的结果消息
        """
        # 1. 检查是否有活动算例
        if not self.current_case:
            return {
                "type": "error",
                "message": "当前没有活动的算例。请先创建一个算例。"
            }
        
        # 2. 获取案例路径
        case_path = self.case_manager.get_case(self.current_case)
        if not case_path:
            # 尝试从当前配置生成案例
            if self.current_config:
                case_path = self._ensure_case_generated()
                if not case_path:
                    return {
                        "type": "error",
                        "message": f"找不到算例: {self.current_case}，且无法自动生成。"
                    }
            else:
                return {
                    "type": "error",
                    "message": f"找不到算例: {self.current_case}"
                }
        
        case_path = Path(case_path)
        
        # 3. 初始化或更新 OpenFOAMRunner
        if self.runner is None or self._runner_case_path != case_path:
            self.runner = OpenFOAMRunner(case_path)
            self._runner_case_path = case_path
        
        # 4. 检查执行环境是否可用
        if self.runner.execution_mode == "unavailable":
            return {
                "type": "error",
                "message": "OpenFOAM 环境不可用。\n\n" +
                           "请确保以下条件之一满足：\n" +
                           "• Docker 已安装并运行（推荐 Windows 用户）\n" +
                           "• 本地已安装 OpenFOAM 并配置好环境变量"
            }
        
        # 4.5 OpenFOAM v11 兼容性处理
        self._ensure_openfoam_v11_compatibility(case_path)
        
        # 5. 获取求解器名称
        solver_name = self.current_config.get("solver", {}).get("name", "icoFoam")
        if not solver_name or solver_name == "unknown":
            solver_name = "icoFoam"
        
        logger.info(f"[ManagerAgent] 开始运行仿真: {self.current_case}, 求解器: {solver_name}")
        logger.info(f"[ManagerAgent] 执行模式: {self.runner.execution_mode}")
        
        # 6. 执行仿真管线
        try:
            result = self.runner.run_full_pipeline(solver_name)
        except Exception as e:
            logger.error(f"[ManagerAgent] 仿真执行异常: {e}")
            return {
                "type": "error",
                "message": f"仿真执行异常: {str(e)}"
            }
        
        # 7. 格式化结果消息
        if result.get("success", False):
            message = self._format_simulation_success(result, case_path)
            
            # 8. 尝试生成结果可视化
            image_paths = self._generate_result_visualization(case_path)
            if image_paths:
                message += f"\n\n📷 结果可视化已生成"
            
            # 更新状态
            self.case_manager.update_case_status(self.current_case, "completed", solver_name)
            
            return {
                "type": "simulation_complete",
                "message": message,
                "result": result,
                "image_paths": image_paths,
                "case_path": str(case_path)
            }
        else:
            error_msg = result.get("error", "未知错误")
            failed_stages = [s for s in result.get("stages", []) if not s.get("success", False)]
            
            message = f"❌ 仿真运行失败\n\n"
            message += f"执行模式: {result.get('execution_mode', 'unknown')}\n"
            message += f"总耗时: {result.get('total_duration', 0):.1f}秒\n\n"
            
            if failed_stages:
                message += "失败阶段:\n"
                for stage in failed_stages:
                    message += f"  • {stage['name']}: 失败\n"
                    # 添加关键日志摘要
                    log = stage.get('log', '')
                    if log:
                        error_lines = [line for line in log.split('\n') 
                                      if 'error' in line.lower() or 'fatal' in line.lower()]
                        if error_lines:
                            message += f"    错误: {error_lines[0][:100]}\n"
            
            return {
                "type": "simulation_error",
                "message": message,
                "result": result,
                "case_path": str(case_path)
            }
    
    def _ensure_case_generated(self) -> Optional[Path]:
        """
        确保案例文件已生成
        
        Returns:
            案例路径，如果生成失败则返回 None
        """
        if not self.current_config or not self.current_case:
            return None
        
        try:
            # 创建算例目录
            case_path = self.case_manager.create_case(
                self.current_case,
                self.current_config.get("physics_type", "incompressible")
            )
            case_path = Path(case_path)
            
            # 生成所有配置文件
            generator = CaseGenerator(self.current_config)
            generator.generate_all(case_path)
            
            logger.info(f"[ManagerAgent] 自动生成案例文件: {case_path}")
            return case_path
            
        except Exception as e:
            logger.error(f"[ManagerAgent] 生成案例文件失败: {e}")
            return None
    
    def _format_simulation_success(self, result: Dict[str, Any], case_path: Path) -> str:
        """
        格式化仿真成功的消息
        
        Args:
            result: run_full_pipeline 返回的结果字典
            case_path: 案例路径
            
        Returns:
            格式化的用户友好消息
        """
        message = "✅ 仿真运行完成！\n\n"
        message += "📊 运行摘要:\n"
        
        total_duration = result.get("total_duration", 0)
        
        for stage in result.get("stages", []):
            stage_name = stage.get("name", "unknown")
            success = stage.get("success", False)
            duration = stage.get("duration", 0)
            
            status = "成功" if success else "失败"
            message += f"- {stage_name}: {status} ({duration:.1f}秒)\n"
        
        message += f"- 总耗时: {total_duration:.1f}秒\n\n"
        message += f"📁 结果文件已生成在: {case_path}"
        
        return message
    
    def _generate_result_visualization(self, case_path: Path) -> List[str]:
        """
        生成结果可视化图像
        
        Args:
            case_path: 案例路径
            
        Returns:
            生成的图像路径列表
        """
        image_paths = []
        
        try:
            from ..utils.result_visualizer import ResultVisualizer
            
            visualizer = ResultVisualizer(case_path)
            
            # 检查是否有结果数据
            latest_time = visualizer._get_latest_time()
            if latest_time and latest_time != "0":
                # 生成速度场结果图
                u_image = visualizer.create_result_figure(time_step=latest_time, field='U')
                if u_image and u_image.exists():
                    image_paths.append(str(u_image))
                    logger.info(f"[ManagerAgent] 生成速度场可视化: {u_image}")
                
                # 生成压力场结果图
                p_image = visualizer.create_result_figure(time_step=latest_time, field='p')
                if p_image and p_image.exists():
                    image_paths.append(str(p_image))
                    logger.info(f"[ManagerAgent] 生成压力场可视化: {p_image}")
        except ImportError:
            logger.warning("[ManagerAgent] ResultVisualizer 不可用，跳过可视化生成")
        except Exception as e:
            logger.warning(f"[ManagerAgent] 生成结果可视化失败: {e}")
        
        return image_paths
    
    def _ensure_openfoam_v11_compatibility(self, case_path: Path) -> None:
        """
        确保 OpenFOAM v11 兼容性
        
        OpenFOAM v11 的关键变化：
        - transportProperties → physicalProperties
        
        此方法检查并创建兼容的文件链接/副本
        """
        import shutil
        
        constant_dir = case_path / "constant"
        if not constant_dir.exists():
            return
        
        # transportProperties → physicalProperties (OpenFOAM v11)
        transport_file = constant_dir / "transportProperties"
        physical_file = constant_dir / "physicalProperties"
        
        if transport_file.exists() and not physical_file.exists():
            try:
                # 复制文件（Windows 不支持符号链接）
                shutil.copy2(transport_file, physical_file)
                logger.info(f"[ManagerAgent] OpenFOAM v11 兼容: 创建 physicalProperties")
            except Exception as e:
                logger.warning(f"[ManagerAgent] 创建 physicalProperties 失败: {e}")
        
        # 检查其他可能需要兼容的文件
        # turbulenceProperties 在 v11 中保持不变
        # thermophysicalProperties 在 v11 中保持不变
    
    def _handle_check_status(self) -> Dict[str, Any]:
        """处理查看状态请求"""
        if not self.current_case:
            # 列出所有算例
            cases = self.case_manager.list_cases()
            return {
                "type": "status",
                "message": f"当前没有活动算例。所有算例: {', '.join(cases) if cases else '无'}"
            }
        
        info = self.case_manager.get_case_info(self.current_case)
        if info:
            return {
                "type": "status",
                "message": f"当前算例: {info.name}\\n状态: {info.status}\\n求解器: {info.solver}"
            }
        else:
            return {
                "type": "error",
                "message": f"找不到算例信息: {self.current_case}"
            }
    
    def _handle_help(self) -> Dict[str, Any]:
        """处理帮助请求"""
        help_text = """OpenFOAM AI Agent 使用帮助

您可以这样与我交互：

1. 创建算例：
   - "建立一个二维方腔驱动流"
   - "创建一个管道流动仿真，雷诺数1000"
   - "计算方腔内的自然对流"

2. 修改配置：
   - "把网格改成40x40"
   - "时间步长改为0.001"
   - "运动粘度设为1e-6"

3. 运行计算：
   - "开始计算"
   - "运行仿真"

4. 查看状态：
   - "查看状态"
   - "进度如何"

5. 解释概念：
   - "什么是库朗数"
   - "解释icoFoam求解器"

6. 对比方案：
   - "icoFoam和simpleFoam有什么区别"
   - "层流和湍流的区别"

7. 优化建议：
   - "优化当前配置"
   - "如何改进收敛性"

我会将您的自然语言转换为OpenFOAM配置并自动执行。"""
        
        return {
            "type": "help",
            "message": help_text
        }
    
    def _handle_explain(self, user_input: str) -> Dict[str, Any]:
        """处理解释请求"""
        # 尝试从 TeachingEngine 获取解释
        try:
            from ..core.teaching_engine import TeachingEngine
            teacher = TeachingEngine()
            
            # 从输入中提取要解释的概念
            explanation = teacher.explain_parameter(user_input)
            if not explanation and self.current_config:
                explanation = self.prompt_engine.explain_config(self.current_config)
            if not explanation:
                explanation = "请先创建一个算例，或具体说明要了解什么概念。"
            
            return {"type": "explanation", "message": explanation}
        except ImportError:
            # 如果TeachingEngine不可用，使用prompt_engine的mock方法
            if self.current_config and hasattr(self.prompt_engine, '_mock_explain_config'):
                return {
                    "type": "explanation", 
                    "message": self.prompt_engine._mock_explain_config(self.current_config)
                }
            return {
                "type": "explanation", 
                "message": "请先创建一个算例，或具体说明要了解什么CFD概念（如库朗数、雷诺数、边界条件等）。"
            }
    
    def _handle_compare(self, user_input: str) -> Dict[str, Any]:
        """处理对比请求"""
        input_lower = user_input.lower()
        
        # 求解器对比
        if "icofoam" in input_lower and "simplefoam" in input_lower:
            comparison = """icoFoam vs simpleFoam 对比：

icoFoam：
• 瞬态不可压层流求解器
• 基于PISO算法
• 适用于时间相关的流动问题
• 需要较小的时间步长以满足CFL条件

simpleFoam：
• 稳态不可压求解器
• 基于SIMPLE算法
• 适用于稳态流动问题
• 不需要时间步长，使用伪时间推进

选择建议：
• 如果关注流动随时间的变化 → 使用icoFoam
• 如果只需要最终稳态结果 → 使用simpleFoam"""
            return {"type": "comparison", "message": comparison}
        
        # 层流与湍流对比
        if "层流" in user_input or "湍流" in user_input or "laminar" in input_lower or "turbulent" in input_lower:
            comparison = """层流 vs 湍流 对比：

层流（Laminar）：
• 流体分层流动，各层间无混合
• 雷诺数 Re < 2300（管道流动）
• 流动可预测，无涡旋
• 粘性力占主导

湍流（Turbulent）：
• 流体存在不规则涡旋和混合
• 雷诺数 Re > 4000（管道流动）
• 流动随机，需要统计方法描述
• 惯性力占主导

判断方法：
• 计算雷诺数 Re = ρUL/μ
• Re < 2300：层流
• 2300 < Re < 4000：过渡区
• Re > 4000：湍流"""
            return {"type": "comparison", "message": comparison}
        
        # 默认回复
        return {
            "type": "comparison",
            "message": "对比功能：请说明要对比什么。例如：\n" +
                       "• \"icoFoam和simpleFoam有什么区别？\"\n" +
                       "• \"层流和湍流的区别\"\n" +
                       "• \"显式格式和隐式格式的区别\""
        }
    
    def _handle_optimize(self, user_input: str) -> Dict[str, Any]:
        """处理优化请求"""
        if not self.current_config:
            return {"type": "error", "message": "请先创建算例，然后再请求优化建议。"}
        
        # 尝试使用prompt_engine获取建议
        try:
            suggestions = self.prompt_engine.suggest_improvements(self.current_config, "")
            if suggestions and suggestions != ["使用真实API以获取改进建议"]:
                return {
                    "type": "optimization",
                    "message": "优化建议：\n" + "\n".join(f"• {s}" for s in suggestions)
                }
        except Exception as e:
            logger.warning(f"获取LLM优化建议失败: {e}")
        
        # 基于当前配置生成通用优化建议
        config = self.current_config
        suggestions = []
        
        # 网格优化建议
        geom = config.get("geometry", {})
        res = geom.get("mesh_resolution", {})
        if res:
            nx, ny, nz = res.get("nx", 20), res.get("ny", 20), res.get("nz", 1)
            total_cells = nx * ny * max(nz, 1)
            if total_cells < 1000:
                suggestions.append(f"当前网格数{total_cells}较少，建议增加网格以提高精度（推荐至少40x40=1600）")
            elif total_cells > 100000:
                suggestions.append(f"当前网格数{total_cells}较多，计算时间较长，可考虑使用并行计算")
        
        # 时间步长优化建议
        solver = config.get("solver", {})
        delta_t = solver.get("deltaT", 0.01)
        end_time = solver.get("endTime", 1.0)
        solver_name = solver.get("name", "icoFoam")
        
        if "icoFoam" in solver_name:
            # 估算CFL条件
            dims = geom.get("dimensions", {})
            L = dims.get("L", 1.0)
            dx = L / nx if nx > 0 else 0.1
            u_est = 1.0  # 假设特征速度
            courant = u_est * delta_t / dx
            
            if courant > 0.5:
                suggestions.append(f"估计库朗数{courant:.2f}可能过大，建议减小时间步长至{0.5 * dx / u_est:.4f}以下")
            elif courant < 0.05:
                suggestions.append(f"时间步长较小，可能需要较多计算步数（约{int(end_time/delta_t)}步）")
        
        # 求解器选择建议
        physics = config.get("physics_type", "incompressible")
        if physics == "incompressible" and solver_name not in ["icoFoam", "simpleFoam", "pimpleFoam"]:
            suggestions.append(f"当前求解器{solver_name}可能不适合不可压流，推荐使用icoFoam或simpleFoam")
        
        if not suggestions:
            suggestions.append("当前配置已较为合理。如需进一步优化，请提供运行日志以获取更具体的建议。")
        
        return {
            "type": "optimization",
            "message": "优化建议：\n" + "\n".join(f"• {s}" for s in suggestions)
        }


if __name__ == "__main__":
    # 测试ManagerAgent
    print("ManagerAgent 模块测试")
    print("=" * 50)
    
    agent = ManagerAgent()
    
    # 测试意图识别
    test_inputs = [
        "建立一个方腔驱动流",
        "开始计算",
        "查看状态",
        "帮助"
    ]
    
    for user_input in test_inputs:
        print(f"\n用户输入: {user_input}")
        response = agent.process_input(user_input)
        print(f"响应类型: {response['type']}")
        print(f"响应内容: {response['message'][:100]}...")
