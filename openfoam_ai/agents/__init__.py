"""
OpenFOAM AI Agents
包含PromptEngine、ManagerAgent等智能体模块。

阶段二新增模块：
- MeshQualityChecker: 网格质量自查Agent (Week 5)
- SelfHealingController: 求解稳定性监控与自愈Agent (Week 6-7)
- PhysicsConsistencyValidator: 物理一致性校验Agent (Week 8)
- CriticAgent: 审查者Agent (Week 8)

阶段三模块（位于memory/目录）：
- MemoryManager: 记忆管理模块 (Week 9-10)
- SessionManager: 会话管理模块 (Week 11-12)

阶段四新增模块：
- GeometryImageParser: 几何图像解析Agent (Week 13-14)
- PostProcessingAgent: 后处理与绘图Agent (Week 15-16)

使用方式:
    from openfoam_ai.agents import ManagerAgent
    from openfoam_ai.memory import MemoryManager, SessionManager
    from openfoam_ai.agents import GeometryImageParser, PostProcessingAgent
"""

# 处理导入问题
try:
    # 正常导入（作为包的一部分）
    from .prompt_engine import PromptEngine, ConfigRefiner
    from .manager_agent import ManagerAgent, TaskPlan, ExecutionResult
    
    # ManagerAgent拆分模块
    from .intent_resolver import IntentResolver
    from .case_modifier import CaseModifier
    from .error_recovery import ErrorRecovery
    
    # 阶段二模块
    from .mesh_quality_agent import (
        MeshQualityChecker, 
        MeshQualityReport, 
        MeshQualityLevel,
        MeshAutoFixer
    )
    from .self_healing_agent import (
        SolverStabilityMonitor,
        SelfHealingController,
        SmartSolverRunner,
        DivergenceEvent,
        DivergenceType,
        HealingAction
    )
    from .physics_validation_agent import (
        PhysicsConsistencyValidator,
        PostProcessDataExtractor,
        ValidationResult,
        ValidationType
    )
    from .critic_agent import (
        CriticAgent,
        ConstitutionChecker,
        ReviewReport,
        ReviewIssue,
        ReviewVerdict
    )
    
    # 阶段四模块
    from .geometry_image_agent import (
        GeometryImageParser,
        GeometryFeatures,
        GeometryType,
        BoundaryType,
        create_geometry_parser
    )
    
    # 阶段四模块
    from .postprocessing_agent import (
        PostProcessingAgent,
        PlotType,
        OutputFormat,
        PlotRequest,
        PlotResult,
        create_postprocessing_agent
    )
except ImportError:
    # 作为脚本直接运行时
    import sys
    from pathlib import Path
    agents_dir = Path(__file__).parent
    sys.path.insert(0, str(agents_dir))
    sys.path.insert(0, str(agents_dir.parent / "core"))
    
    from prompt_engine import PromptEngine, ConfigRefiner
    from manager_agent import ManagerAgent, TaskPlan, ExecutionResult
    
    # ManagerAgent拆分模块
    from intent_resolver import IntentResolver
    from case_modifier import CaseModifier
    from error_recovery import ErrorRecovery
    
    from mesh_quality_agent import (
        MeshQualityChecker, 
        MeshQualityReport, 
        MeshQualityLevel,
        MeshAutoFixer
    )
    from self_healing_agent import (
        SolverStabilityMonitor,
        SelfHealingController,
        SmartSolverRunner,
        DivergenceEvent,
        DivergenceType,
        HealingAction
    )
    from physics_validation_agent import (
        PhysicsConsistencyValidator,
        PostProcessDataExtractor,
        ValidationResult,
        ValidationType
    )
    from critic_agent import (
        CriticAgent,
        ConstitutionChecker,
        ReviewReport,
        ReviewIssue,
        ReviewVerdict
    )
    
    from geometry_image_agent import (
        GeometryImageParser,
        GeometryFeatures,
        GeometryType,
        BoundaryType,
        create_geometry_parser
    )
    
    from postprocessing_agent import (
        PostProcessingAgent,
        PlotType,
        OutputFormat,
        PlotRequest,
        PlotResult,
        create_postprocessing_agent
    )

__all__ = [
    # 阶段一
    'PromptEngine',
    'ConfigRefiner',
    'ManagerAgent',
    'TaskPlan',
    'ExecutionResult',
    
    # ManagerAgent拆分模块
    'IntentResolver',
    'CaseModifier',
    'ErrorRecovery',
    
    # 阶段二 - 网格质量
    'MeshQualityChecker',
    'MeshQualityReport',
    'MeshQualityLevel',
    'MeshAutoFixer',
    
    # 阶段二 - 自愈控制
    'SolverStabilityMonitor',
    'SelfHealingController',
    'SmartSolverRunner',
    'DivergenceEvent',
    'DivergenceType',
    'HealingAction',
    
    # 阶段二 - 物理校验
    'PhysicsConsistencyValidator',
    'PostProcessDataExtractor',
    'ValidationResult',
    'ValidationType',
    
    # 阶段二 - 审查者
    'CriticAgent',
    'ConstitutionChecker',
    'ReviewReport',
    'ReviewIssue',
    'ReviewVerdict',
    
    # 阶段四 - 视觉模型
    'GeometryImageParser',
    'GeometryFeatures',
    'GeometryType',
    'BoundaryType',
    'create_geometry_parser',
    
    # 阶段四 - 后处理
    'PostProcessingAgent',
    'PlotType',
    'OutputFormat',
    'PlotRequest',
    'PlotResult',
    'create_postprocessing_agent',
]
