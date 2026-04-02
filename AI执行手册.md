# OpenFOAM-AI Agent 项目执行手册

> **文档用途**: 本手册供AI助手读取，用于指导项目开发的具体实施步骤
> **版本**: v1.0
> **更新日期**: 2024年

---

## 📋 项目概述

### 项目名称
**OpenFOAM-AI Agent：基于大语言模型的自动化CFD仿真智能体系统**

### 项目愿景
构建一个具备**自主前处理、求解计算、后处理及记忆交互能力**的多智能体系统，让科研人员通过自然语言（或图像）即可驱动OpenFOAM完成复杂流体力学仿真。

### 核心价值
| 维度 | 价值 |
|------|------|
| **降本增效** | 将OpenFOAM陡峭的学习曲线降至"零门槛" |
| **知识沉淀** | 通过记忆性建模，沉淀仿真参数和修正过程 |
| **社区影响力** | 填补硬核科学计算Agent的蓝海市场 |

### 技术架构
```
┌─────────────────────────────────────────────────────────────────┐
│                      用户交互层 (User Interface)                   │
│         自然语言输入 / 几何示意图 / 多轮对话确认                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    交互与记忆总控 Agent                            │
│   任务解析 → JSON结构化 → 项目日志管理 → 状态机维护                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────┬──────────────────┬──────────────────────────────┐
│  前处理 Agent    │   求解执行 Agent  │      后处理 Agent            │
│  · 网格生成      │   · 字典配置      │      · 数据提取              │
│  · 边界划分      │   · 求解器调用    │      · 自动绘图              │
│  · 几何解析      │   · 残差监控      │      · 物理校验              │
│                 │   · 自愈重启      │                             │
└─────────────────┴──────────────────┴──────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      OpenFOAM 计算引擎                           │
│              blockMesh / icoFoam / checkMesh 等                  │
└─────────────────────────────────────────────────────────────────┘
```

### 核心技术栈
- **开发环境**: VS Code + Git/GitHub
- **核心语言**: Python 3.10+
- **底层引擎**: OpenFOAM (Foundation v11 / ESI v2312)
- **AI 框架**: LangChain / AutoGen
- **记忆存储**: ChromaDB / FAISS
- **后处理**: PyVista / ParaView Python API
- **容器化**: Docker / WSL2

---

## 🗺️ 详细执行路线

---

## 阶段一：基础设施搭建与MVP实现（第1-4周）

**阶段目标**: 打通"LLM → Python脚本 → OpenFOAM执行 → 结果提取"的单向数据流

### Week 1: 环境容器化与项目初始化

#### 任务清单
- [ ] 创建项目目录结构
- [ ] 编写Dockerfile集成OpenFOAM+Python
- [ ] 开发CaseManager核心类

#### 目录结构要求
```
openfoam_ai/
├── agents/                    # 各Agent模块
│   ├── __init__.py
│   ├── manager_agent.py       # 交互与记忆总控
│   ├── preprocessing_agent.py # 前处理Agent
│   ├── execution_agent.py     # 求解执行Agent
│   └── postprocessing_agent.py# 后处理Agent
├── core/                      # 核心基础设施
│   ├── __init__.py
│   ├── case_manager.py        # 算例目录管理
│   ├── file_generator.py      # 字典文件生成
│   └── validators.py          # 物理约束校验器
├── models/                    # 物理模型定义
│   ├── __init__.py
│   ├── base_model.py          # 基类
│   ├── incompressible.py      # 不可压流
│   └── heat_transfer.py       # 传热模型
├── memory/                    # 记忆管理
│   ├── __init__.py
│   └── memory_manager.py      # 日志与状态管理
├── config/                    # 配置文件
│   ├── system_constitution.yaml  # 项目宪法
│   └── prompts/               # Prompt模板
├── tests/                     # 测试用例
├── docker/                    # Docker配置
├── requirements.txt
└── main.py                    # 主入口
```

#### 代码参考：CaseManager类
```python
import os
import shutil
from pathlib import Path
from typing import Optional

class CaseManager:
    """OpenFOAM算例目录管理器"""
    
    def __init__(self, base_path: str = "./cases"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_case(self, case_name: str) -> Path:
        """创建标准OpenFOAM算例目录结构"""
        case_path = self.base_path / case_name
        
        # 创建标准目录
        dirs = ["0", "constant", "system", "logs"]
        for d in dirs:
            (case_path / d).mkdir(parents=True, exist_ok=True)
        
        return case_path
    
    def copy_template(self, template_path: str, case_name: str) -> Path:
        """从模板复制算例"""
        src = Path(template_path)
        dst = self.base_path / case_name
        
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        
        return dst
    
    def cleanup(self, case_name: str, keep_results: bool = False):
        """清理算例文件"""
        case_path = self.base_path / case_name
        
        if not keep_results:
            # 删除时间步目录
            for item in case_path.iterdir():
                if item.is_dir() and item.name[0].isdigit():
                    shutil.rmtree(item)
        
        # 清理日志
        log_dir = case_path / "logs"
        if log_dir.exists():
            for log in log_dir.glob("*.log"):
                log.unlink()
```

#### Docker配置参考
```dockerfile
# docker/Dockerfile
FROM opencfd/openfoam-default:2312

USER root

# 安装Python 3.10+
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /workspace

# 复制依赖并安装
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . /workspace/openfoam_ai

ENV PYTHONPATH=/workspace/openfoam_ai:$PYTHONPATH
ENV PATH=/usr/local/bin:$PATH

CMD ["/bin/bash"]
```

---

### Week 2: 基础解析器开发

#### 任务清单
- [ ] 设计JSON任务描述协议
- [ ] 开发LLM接口封装
- [ ] 实现字典文件生成器

#### JSON协议规范
```json
{
  "task_id": "cavity_flow_001",
  "physics_type": "incompressible",
  "geometry": {
    "type": "2D_cavity",
    "dimensions": {"L": 1.0, "W": 1.0, "H": 0.1},
    "mesh_resolution": {"nx": 100, "ny": 100}
  },
  "boundary_conditions": {
    "movingWall": {"type": "fixedValue", "value": [1, 0, 0]},
    "fixedWalls": {"type": "noSlip"}
  },
  "solver": {
    "name": "icoFoam",
    "endTime": 10.0,
    "deltaT": 0.005
  }
}
```

#### 代码参考：PromptEngine
```python
import json
from typing import Dict, Any
import openai

class PromptEngine:
    """LLM提示词引擎"""
    
    SYSTEM_PROMPT_TEMPLATE = """你是一位专业的OpenFOAM CFD工程师。
    将用户的自然语言描述转换为结构化的JSON配置。
    
    可用物理类型：incompressible, compressible, heatTransfer, multiphase
    可用求解器：icoFoam, simpleFoam, buoyantBoussinesqPimpleFoam
    
    输出必须是有效的JSON格式，不要包含任何解释文字。"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def natural_language_to_json(self, user_input: str) -> Dict[str, Any]:
        """将自然语言转换为JSON配置"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": user_input}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
```

#### 代码参考：BlockMeshDictGenerator
```python
from pathlib import Path
from typing import Dict, Any

class BlockMeshDictGenerator:
    """blockMeshDict文件生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.geometry = config.get("geometry", {})
    
    def generate(self) -> str:
        """生成blockMeshDict内容"""
        
        dims = self.geometry.get("dimensions", {})
        res = self.geometry.get("mesh_resolution", {})
        
        L = dims.get("L", 1.0)
        W = dims.get("W", 1.0)
        H = dims.get("H", 0.1)
        nx = res.get("nx", 20)
        ny = res.get("ny", 20)
        nz = res.get("nz", 1)
        
        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

scale   1;

vertices
(
    (0 0 0)
    ({L} 0 0)
    ({L} {W} 0)
    (0 {W} 0)
    (0 0 {H})
    ({L} 0 {H})
    ({L} {W} {H})
    (0 {W} {H})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    movingWall
    {{
        type wall;
        faces
        (
            (3 7 6 2)
        );
    }}
    fixedWalls
    {{
        type wall;
        faces
        (
            (0 4 7 3)
            (2 6 5 1)
            (1 5 4 0)
        );
    }}
    frontAndBack
    {{
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);

// ************************************************************************* //
"""
        return content
    
    def write(self, case_path: Path):
        """写入system/blockMeshDict"""
        system_dir = case_path / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        
        (system_dir / "blockMeshDict").write_text(self.generate())
```

---

### Week 3: 执行与通信模块

#### 任务清单
- [ ] 封装OpenFOAM命令执行
- [ ] 实现日志实时捕获
- [ ] 开发残差/库朗数解析器

#### 代码参考：OpenFOAMRunner
```python
import subprocess
import re
from pathlib import Path
from typing import Tuple, Iterator, Optional
import time

class OpenFOAMRunner:
    """OpenFOAM命令执行器"""
    
    def __init__(self, case_path: Path):
        self.case_path = Path(case_path)
        self.log_dir = self.case_path / "logs"
        self.log_dir.mkdir(exist_ok=True)
    
    def run_blockmesh(self) -> Tuple[bool, str]:
        """执行blockMesh"""
        return self._run_command("blockMesh", "blockMesh.log")
    
    def run_checkmesh(self) -> Tuple[bool, str, dict]:
        """执行checkMesh并解析结果"""
        success, log = self._run_command("checkMesh", "checkMesh.log")
        metrics = self._parse_checkmesh_log(log) if success else {}
        return success, log, metrics
    
    def run_solver(self, solver_name: str) -> Iterator[str]:
        """执行求解器，实时输出日志"""
        log_file = self.log_dir / f"{solver_name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        
        process = subprocess.Popen(
            [solver_name],
            cwd=self.case_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        with open(log_file, 'w') as f:
            for line in process.stdout:
                f.write(line)
                f.flush()
                yield line.strip()
        
        process.wait()
    
    def _run_command(self, cmd: str, log_name: str) -> Tuple[bool, str]:
        """执行单条命令"""
        log_file = self.log_dir / log_name
        
        result = subprocess.run(
            [cmd],
            cwd=self.case_path,
            capture_output=True,
            text=True
        )
        
        log_content = result.stdout + "\\n" + result.stderr
        log_file.write_text(log_content)
        
        return result.returncode == 0, log_content
    
    def _parse_checkmesh_log(self, log: str) -> dict:
        """解析checkMesh日志提取关键指标"""
        metrics = {}
        
        # 提取非正交性
        non_ortho = re.search(r'Non-orthogonality.*?Max = ([\\d.]+)', log, re.DOTALL)
        if non_ortho:
            metrics['non_orthogonality_max'] = float(non_ortho.group(1))
        
        # 提取网格检查失败数
        failed = re.search(r'Failed (\\d+) mesh', log)
        if failed:
            metrics['failed_checks'] = int(failed.group(1))
        
        return metrics
    
    def get_latest_timestep(self) -> Optional[float]:
        """获取最新的时间步目录"""
        timesteps = []
        for item in self.case_path.iterdir():
            if item.is_dir():
                try:
                    timesteps.append(float(item.name))
                except ValueError:
                    continue
        return max(timesteps) if timesteps else None
```

---

### Week 4: MVP验证与文档

#### 任务清单
- [ ] 运行3个经典算例验证
- [ ] 编写README和API文档
- [ ] 阶段复盘与代码重构

#### MVP验证算例
| 算例 | 描述 | 验证目标 |
|------|------|---------|
| cavity | 方腔驱动流 | 基础流程验证 |
| pitzDaily | 突扩管流动 | 稍复杂几何 |
| heatCavity | 方腔自然对流 | 引入传热 |

---

## 阶段二：AI自查与自愈能力（第5-8周）

**阶段目标**: 赋予系统纠错与参数动态调整能力

### Week 5: 网格质量自查Agent

#### 任务清单
- [ ] 实现checkMesh日志深度解析
- [ ] 开发网格修正策略
- [ ] 集成自动/人工确认机制

#### 代码参考：MeshQualityChecker
```python
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MeshQualityReport:
    passed: bool
    non_orthogonality_max: float
    skewness_max: float
    aspect_ratio_max: float
    failed_checks: int
    recommendations: List[str]

class MeshQualityChecker:
    """网格质量检查器"""
    
    THRESHOLDS = {
        'non_orthogonality_warn': 70,
        'non_orthogonality_fail': 85,
        'skewness_warn': 4,
        'aspect_ratio_warn': 100
    }
    
    def check(self, case_path: Path) -> MeshQualityReport:
        """执行网格质量检查"""
        runner = OpenFOAMRunner(case_path)
        success, log, metrics = runner.run_checkmesh()
        
        recommendations = []
        
        # 分析非正交性
        non_ortho = metrics.get('non_orthogonality_max', 0)
        if non_ortho > self.THRESHOLDS['non_orthogonality_fail']:
            recommendations.append(f"非正交性{non_ortho}过高，建议增加非正交修正器或调整网格")
        elif non_ortho > self.THRESHOLDS['non_orthogonality_warn']:
            recommendations.append(f"非正交性{non_ortho}偏高，建议检查网格质量")
        
        passed = metrics.get('failed_checks', 1) == 0
        
        return MeshQualityReport(
            passed=passed,
            non_orthogonality_max=non_ortho,
            skewness_max=metrics.get('skewness_max', 0),
            aspect_ratio_max=metrics.get('aspect_ratio_max', 0),
            failed_checks=metrics.get('failed_checks', 0),
            recommendations=recommendations
        )
```

---

### Week 6-7: 求解稳定性监控Agent

#### 任务清单
- [ ] 实现实时日志监控
- [ ] 开发发散检测算法
- [ ] 实现自愈重启逻辑

#### 代码参考：SolverMonitor
```python
import time
from collections import deque
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum

class SolverState(Enum):
    RUNNING = "running"
    CONVERGED = "converged"
    DIVERGING = "diverging"
    STALLED = "stalled"
    ERROR = "error"

@dataclass
class SolverMetrics:
    time: float
    courant_mean: float
    courant_max: float
    residuals: Dict[str, float]

class SolverMonitor:
    """求解器实时监控器"""
    
    def __init__(self, callback: Optional[Callable] = None):
        self.metrics_history = deque(maxlen=100)
        self.callback = callback
        self.state = SolverState.RUNNING
        
        # 阈值配置
        self.courant_max_limit = 1.0
        self.divergence_threshold = 1e0
        self.stall_threshold = 100  # 步数
    
    def parse_log_line(self, line: str) -> Optional[SolverMetrics]:
        """解析单行日志"""
        # 解析时间
        time_match = re.search(r'Time = ([\\d.]+)', line)
        if time_match:
            self.current_time = float(time_match.group(1))
            return None
        
        # 解析库朗数
        courant_match = re.search(r'Courant Number mean: ([\\d.]+) max: ([\\d.]+)', line)
        if courant_match:
            return SolverMetrics(
                time=getattr(self, 'current_time', 0),
                courant_mean=float(courant_match.group(1)),
                courant_max=float(courant_match.group(2)),
                residuals={}
            )
        
        # 解析残差
        residual_pattern = r'Solving for (\\w+), Initial residual = ([\\de-.]+)'
        residuals = dict(re.findall(residual_pattern, line))
        if residuals:
            return SolverMetrics(
                time=getattr(self, 'current_time', 0),
                courant_mean=0,
                courant_max=0,
                residuals={k: float(v) for k, v in residuals.items()}
            )
        
        return None
    
    def check_state(self, metrics: SolverMetrics) -> SolverState:
        """检查求解器状态"""
        self.metrics_history.append(metrics)
        
        # 检查库朗数
        if metrics.courant_max > self.courant_max_limit:
            return SolverState.DIVERGING
        
        # 检查残差发散
        if len(self.metrics_history) >= 5:
            recent = list(self.metrics_history)[-5:]
            for var in recent[-1].residuals:
                values = [m.residuals.get(var, 0) for m in recent if var in m.residuals]
                if len(values) >= 3 and all(v > self.divergence_threshold for v in values[-3:]):
                    return SolverState.DIVERGING
        
        return SolverState.RUNNING
```

#### 代码参考：SelfHealingController
```python
class SelfHealingController:
    """自愈控制器"""
    
    def __init__(self, case_path: Path):
        self.case_path = Path(case_path)
        self.healing_attempts = 0
        self.max_attempts = 3
    
    def on_divergence_detected(self, monitor: SolverMonitor) -> bool:
        """处理发散情况"""
        if self.healing_attempts >= self.max_attempts:
            print("达到最大自愈尝试次数，停止计算")
            return False
        
        self.healing_attempts += 1
        
        # 获取最新时间步
        latest_time = self._get_latest_timestep()
        if latest_time is None:
            return False
        
        # 读取当前配置
        control_dict = self._read_control_dict()
        
        # 判断问题类型并采取策略
        last_metrics = list(monitor.metrics_history)[-1] if monitor.metrics_history else None
        
        if last_metrics and last_metrics.courant_max > 1.0:
            # 库朗数过高，减小时间步
            new_deltaT = control_dict.get('deltaT', 0.01) * 0.5
            control_dict['deltaT'] = new_deltaT
            control_dict['startFrom'] = 'latestTime'
            print(f"库朗数过高，减小deltaT至{new_deltaT}")
        
        else:
            # 残差发散，减小松弛因子
            fv_solution = self._read_fv_solution()
            for field in ['U', 'p']:
                if field in fv_solution.get('relaxationFactors', {}):
                    old_factor = fv_solution['relaxationFactors'][field]
                    fv_solution['relaxationFactors'][field] = old_factor * 0.8
            self._write_fv_solution(fv_solution)
            print("残差发散，减小松弛因子")
        
        # 保存修改后的配置
        self._write_control_dict(control_dict)
        
        return True
    
    def _get_latest_timestep(self) -> Optional[float]:
        """获取最新时间步"""
        timesteps = []
        for item in self.case_path.iterdir():
            if item.is_dir():
                try:
                    timesteps.append(float(item.name))
                except ValueError:
                    continue
        return max(timesteps) if timesteps else None
```

---

### Week 8: 物理一致性校验

#### 任务清单
- [ ] 实现质量守恒校验
- [ ] 实现能量守恒校验
- [ ] 开发边界条件兼容性检查

#### 代码参考：PhysicsValidator
```python
class PhysicsValidator:
    """物理一致性校验器"""
    
    TOLERANCE = 0.001  # 0.1%
    
    def validate_mass_conservation(self, case_path: Path) -> Tuple[bool, float]:
        """验证质量守恒（进出口流量差）"""
        # 使用foamDictionary或自定义解析提取流量
        inlet_flux = self._get_boundary_flux(case_path, "inlet")
        outlet_flux = self._get_boundary_flux(case_path, "outlet")
        
        if abs(inlet_flux) < 1e-10:
            return False, float('inf')
        
        error = abs(inlet_flux - outlet_flux) / abs(inlet_flux)
        passed = error < self.TOLERANCE
        
        return passed, error
    
    def validate_energy_conservation(self, case_path: Path) -> Tuple[bool, float]:
        """验证能量守恒"""
        # 提取热流数据
        heat_in = self._get_boundary_heat_flux(case_path, "inlet")
        heat_out = self._get_boundary_heat_flux(case_path, "outlet")
        heat_wall = self._get_boundary_heat_flux(case_path, "wall")
        
        total = heat_in + heat_out + heat_wall
        reference = max(abs(heat_in), abs(heat_out), 1e-10)
        
        error = abs(total) / reference
        passed = error < self.TOLERANCE
        
        return passed, error
    
    def validate_boundary_compatibility(self, bc_config: Dict) -> List[str]:
        """检查边界条件物理兼容性"""
        errors = []
        
        # 检查压力-速度耦合
        has_pressure_inlet = any(
            bc.get('type') == 'totalPressure' 
            for bc in bc_config.values()
        )
        has_velocity_inlet = any(
            bc.get('type') == 'fixedValue' and 'U' in str(bc)
            for bc in bc_config.values()
        )
        
        if has_pressure_inlet and has_velocity_inlet:
            errors.append("警告：同时指定压力入口和速度入口可能导致过约束")
        
        return errors
```

---

## 阶段三：记忆性建模与充分交互（第9-12周）

**阶段目标**: 实现模型可修改性，建立科研级交互体验

### Week 9-10: 状态机与记忆管理

#### 任务清单
- [ ] 搭建ChromaDB向量数据库
- [ ] 开发MemoryManager类
- [ ] 实现差异化更新机制

#### 代码参考：MemoryManager
```python
import chromadb
from chromadb.config import Settings
import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class CaseRecord:
    case_id: str
    config: Dict[str, Any]
    description: str
    timestamp: str
    success: bool
    tags: List[str]

class MemoryManager:
    """算例记忆管理器"""
    
    def __init__(self, db_path: str = "./memory/chroma.db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("cases")
    
    def store_case(self, record: CaseRecord):
        """存储算例配置"""
        case_json = json.dumps(record.config, sort_keys=True)
        embedding_id = hashlib.md5(case_json.encode()).hexdigest()
        
        self.collection.add(
            ids=[record.case_id],
            embeddings=[self._compute_embedding(record.config)],
            metadatas=[{
                "description": record.description,
                "timestamp": record.timestamp,
                "success": record.success,
                "tags": json.dumps(record.tags)
            }],
            documents=[case_json]
        )
    
    def retrieve_similar(self, query_config: Dict[str, Any], n: int = 3) -> List[CaseRecord]:
        """相似性检索历史算例"""
        query_embedding = self._compute_embedding(query_config)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n
        )
        
        records = []
        for i in range(len(results['ids'][0])):
            record = CaseRecord(
                case_id=results['ids'][0][i],
                config=json.loads(results['documents'][0][i]),
                description=results['metadatas'][0][i]['description'],
                timestamp=results['metadatas'][0][i]['timestamp'],
                success=results['metadatas'][0][i]['success'],
                tags=json.loads(results['metadatas'][0][i]['tags'])
            )
            records.append(record)
        
        return records
    
    def _compute_embedding(self, config: Dict[str, Any]) -> List[float]:
        """计算配置的简单嵌入向量（可使用sentence-transformer替代）"""
        # 简化实现：将关键参数编码为向量
        embedding = []
        
        # 几何参数
        dims = config.get('geometry', {}).get('dimensions', {})
        embedding.extend([dims.get('L', 0), dims.get('W', 0), dims.get('H', 0)])
        
        # 网格参数
        res = config.get('geometry', {}).get('mesh_resolution', {})
        embedding.extend([res.get('nx', 0), res.get('ny', 0)])
        
        # 求解器参数
        solver = config.get('solver', {})
        embedding.extend([solver.get('endTime', 0), solver.get('deltaT', 0)])
        
        return embedding
    
    def compute_diff(self, old_config: Dict, new_config: Dict) -> Dict[str, Any]:
        """计算配置差异"""
        diff = {}
        
        for key in new_config:
            if key not in old_config:
                diff[key] = {"action": "added", "value": new_config[key]}
            elif old_config[key] != new_config[key]:
                if isinstance(new_config[key], dict):
                    nested_diff = self.compute_diff(old_config[key], new_config[key])
                    if nested_diff:
                        diff[key] = {"action": "modified", "diff": nested_diff}
                else:
                    diff[key] = {
                        "action": "modified",
                        "old": old_config[key],
                        "new": new_config[key]
                    }
        
        return diff
```

#### 代码参考：CaseStateMachine
```python
from enum import Enum, auto
from typing import Dict, Any, Optional
from dataclasses import dataclass

class CaseState(Enum):
    INIT = auto()
    PREPROCESSING = auto()
    MESHED = auto()
    SOLVING = auto()
    CONVERGED = auto()
    DIVERGED = auto()
    POSTPROCESSED = auto()

@dataclass
class StateTransition:
    from_state: CaseState
    to_state: CaseState
    event: str
    timestamp: str

class CaseStateMachine:
    """算例状态机"""
    
    VALID_TRANSITIONS = {
        CaseState.INIT: [CaseState.PREPROCESSING],
        CaseState.PREPROCESSING: [CaseState.MESHED, CaseState.INIT],
        CaseState.MESHED: [CaseState.SOLVING, CaseState.PREPROCESSING],
        CaseState.SOLVING: [CaseState.CONVERGED, CaseState.DIVERGED, CaseState.MESHED],
        CaseState.CONVERGED: [CaseState.POSTPROCESSED, CaseState.SOLVING],
        CaseState.DIVERGED: [CaseState.SOLVING, CaseState.MESHED, CaseState.PREPROCESSING],
        CaseState.POSTPROCESSED: [CaseState.CONVERGED]
    }
    
    def __init__(self):
        self.state = CaseState.INIT
        self.history: List[StateTransition] = []
        self.config_snapshot: Dict[str, Any] = {}
    
    def transition(self, event: str, new_state: CaseState) -> bool:
        """执行状态转换"""
        if new_state not in self.VALID_TRANSITIONS.get(self.state, []):
            return False
        
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            event=event,
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        self.history.append(transition)
        self.state = new_state
        
        return True
    
    def save_config_snapshot(self, config: Dict[str, Any]):
        """保存配置快照"""
        self.config_snapshot = json.loads(json.dumps(config))
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置快照"""
        return self.config_snapshot.copy()
```

---

### Week 11-12: 交互式对话UI

#### 任务清单
- [ ] 搭建Gradio界面
- [ ] 实现多轮对话逻辑
- [ ] 开发执行计划确认机制

#### 代码参考：Gradio UI
```python
import gradio as gr
import json

class OpenFOAMUI:
    """OpenFOAM AI交互界面"""
    
    def __init__(self, agent_system):
        self.agent = agent_system
        self.pending_action = None
    
    def create_interface(self):
        """创建Gradio界面"""
        
        with gr.Blocks(title="OpenFOAM AI Agent") as demo:
            gr.Markdown("# OpenFOAM AI 仿真助手")
            gr.Markdown("通过自然语言描述您的CFD仿真需求")
            
            with gr.Row():
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(height=400)
                    msg = gr.Textbox(
                        placeholder="描述您的仿真需求...",
                        label="输入"
                    )
                    
                    with gr.Row():
                        submit_btn = gr.Button("发送", variant="primary")
                        clear_btn = gr.Button("清空对话")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 执行确认")
                    plan_display = gr.JSON(label="执行计划")
                    confirm_btn = gr.Button("确认执行", visible=False)
                    cancel_btn = gr.Button("取消", visible=False)
                    
                    gr.Markdown("### 系统状态")
                    status_display = gr.Textbox(label="当前状态", interactive=False)
            
            # 事件绑定
            submit_btn.click(
                self.process_message,
                inputs=[msg, chatbot],
                outputs=[chatbot, plan_display, confirm_btn, cancel_btn, msg]
            )
            
            confirm_btn.click(
                self.execute_plan,
                inputs=[chatbot],
                outputs=[chatbot, status_display]
            )
            
            cancel_btn.click(
                self.cancel_plan,
                outputs=[plan_display, confirm_btn, cancel_btn]
            )
        
        return demo
    
    def process_message(self, message, history):
        """处理用户消息"""
        if not message:
            return history, None, gr.update(visible=False), gr.update(visible=False), ""
        
        # 调用Agent生成执行计划
        plan = self.agent.generate_plan(message)
        
        history.append([message, f"我计划执行以下操作：\\n{json.dumps(plan, indent=2, ensure_ascii=False)}\\n\\n请确认是否执行？"])
        
        self.pending_action = plan
        
        return (
            history,
            plan,
            gr.update(visible=True),
            gr.update(visible=True),
            ""
        )
    
    def execute_plan(self, history):
        """执行计划"""
        if not self.pending_action:
            return history, "无待执行计划"
        
        # 执行操作
        result = self.agent.execute(self.pending_action)
        
        history.append([None, f"执行结果：{result}"])
        self.pending_action = None
        
        return history, "执行完成"
    
    def cancel_plan(self):
        """取消计划"""
        self.pending_action = None
        return None, gr.update(visible=False), gr.update(visible=False)

# 启动
if __name__ == "__main__":
    # 初始化Agent系统
    agent = ManagerAgent()  # 假设已实现
    
    ui = OpenFOAMUI(agent)
    demo = ui.create_interface()
    demo.launch(share=True)
```

---

## 阶段四：多模态解析与科研级后处理（第13-16周）

**阶段目标**: 支持几何示意图输入，实现自动化科研级图表生成

### Week 13-14: 视觉模型接入

#### 任务清单
- [ ] 集成多模态LLM API
- [ ] 开发图像解析模块
- [ ] 实现几何参数提取

#### 代码参考：GeometryImageParser
```python
import base64
from typing import Dict, Any, Optional
import openai

class GeometryImageParser:
    """几何图像解析器"""
    
    SYSTEM_PROMPT = """你是一位CAD工程师。分析提供的几何示意图，提取以下信息：
    1. 几何形状类型（矩形、圆形、管道等）
    2. 尺寸参数（长、宽、高、直径等）
    3. 入口和出口位置
    4. 特殊特征（障碍物、弯头等）
    
    输出JSON格式：
    {
        "shape_type": "rectangle",
        "dimensions": {"L": 2.0, "W": 1.0, "H": 0.1},
        "inlet": {"position": "left", "type": "velocity_inlet"},
        "outlet": {"position": "right", "type": "pressure_outlet"},
        "features": []
    }"""
    
    def __init__(self, api_key: str, model: str = "gpt-4-vision-preview"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def parse_sketch(self, image_path: str) -> Dict[str, Any]:
        """解析手绘几何示意图"""
        
        # 读取并编码图片
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请分析这张几何示意图，提取关键参数。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        
        return json.loads(response.choices[0].message.content)
    
    def parse_literature_figure(self, image_path: str, context: str = "") -> Dict[str, Any]:
        """解析文献中的几何图"""
        
        prompt = f"""这是一张来自文献的几何示意图。
        {f"上下文信息：{context}" if context else ""}
        
        请仔细分析并提取：
        1. 所有标注的尺寸参数和数值
        2. 坐标系方向和单位
        3. 边界条件标识（如有标注）
        
        如有模糊之处，请在"uncertainties"字段中说明。"""
        
        # 实现类似parse_sketch的逻辑...
        pass
```

---

### Week 15-16: 自动化绘图Agent

#### 任务清单
- [ ] 开发PyVista脚本生成器
- [ ] 实现自然语言到绘图指令转换
- [ ] 集成图表美化与导出

#### 代码参考：PlotScriptGenerator
```python
from typing import Literal
from pathlib import Path

class PlotScriptGenerator:
    """绘图脚本生成器"""
    
    def generate_slice_plot(
        self,
        case_path: str,
        field: str,
        plane: Literal['x', 'y', 'z'],
        position: float,
        output_path: str,
        colormap: str = "coolwarm",
        title: str = ""
    ) -> str:
        """生成截面云图脚本"""
        
        script = f'''#!/usr/bin/env python3
import pyvista as pv
import numpy as np

# 读取OpenFOAM算例
reader = pv.OpenFOAMReader("{case_path}")
reader.set_active_time_value(reader.time_values[-1])  # 最新时间步

# 获取内部网格
mesh = reader.read()
internal_mesh = mesh["internalMesh"]

# 创建截面
normal = {{'x': [1, 0, 0], 'y': [0, 1, 0], 'z': [0, 0, 1]}}["{plane}"]
origin = [0, 0, 0]
origin[{{'x': 0, 'y': 1, 'z': 2}}["{plane}"]] = {position}

slice_mesh = internal_mesh.slice(normal=normal, origin=origin)

# 绘图
plotter = pv.Plotter(off_screen=True)
plotter.add_mesh(
    slice_mesh,
    scalars="{field}",
    cmap="{colormap}",
    show_edges=False,
    lighting=False
)
plotter.add_scalar_bar(title="{field}")
plotter.add_title("{title or field + ' Distribution'}")

# 保存
plotter.screenshot("{output_path}", transparent_background=True)
print(f"图像已保存至: {output_path}")
'''
        return script
    
    def generate_profile_plot(
        self,
        case_path: str,
        field: str,
        sample_line: dict,
        output_path: str
    ) -> str:
        """生成沿线的参数分布图脚本"""
        
        script = f'''#!/usr/bin/env python3
import pyvista as pv
import matplotlib.pyplot as plt
import numpy as np

# 读取算例
reader = pv.OpenFOAMReader("{case_path}")
reader.set_active_time_value(reader.time_values[-1])
mesh = reader.read()["internalMesh"]

# 定义采样线
start_point = {sample_line['start']}
end_point = {sample_line['end']}

# 采样
line = mesh.sample_over_line(start_point, end_point, resolution=100)

# 提取数据
field_data = line["{field}"]
arc_length = line["Distance"]

# 绘图
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(arc_length, field_data, 'b-', linewidth=2)
ax.set_xlabel('Distance [m]', fontsize=12)
ax.set_ylabel('{field}', fontsize=12)
ax.set_title('{field} Profile', fontsize=14)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("{output_path}", dpi=300, bbox_inches='tight')
print(f"图表已保存至: {output_path}")
'''
        return script
    
    def generate_streamline_plot(
        self,
        case_path: str,
        seed_surface: dict,
        output_path: str
    ) -> str:
        """生成流线图脚本"""
        
        script = f'''#!/usr/bin/env python3
import pyvista as pv

# 读取算例
reader = pv.OpenFOAMReader("{case_path}")
reader.set_active_time_value(reader.time_values[-1])
mesh = reader.read()["internalMesh"]

# 创建种子点
seed = pv.Line(
    {seed_surface['start']},
    {seed_surface['end']},
    resolution={seed_surface.get('resolution', 20)}
)

# 生成流线
streamlines = mesh.streamlines_from_source(
    seed,
    vectors="U",
    integration_direction="both",
    max_time=100.0
)

# 绘图
plotter = pv.Plotter(off_screen=True)
plotter.add_mesh(mesh.opacity(0.3), color="w")
plotter.add_mesh(streamlines.tubes(radius=0.01), scalars="U", cmap="viridis")
plotter.add_scalar_bar(title="Velocity [m/s]")
plotter.camera_position = "iso"

plotter.screenshot("{output_path}", transparent_background=True)
print(f"流线图已保存至: {output_path}")
'''
        return script
    
    def write_and_execute(self, script: str, script_path: str):
        """写入并执行脚本"""
        Path(script_path).write_text(script)
        
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0, result.stdout + result.stderr
```

---

## 🔒 防幻觉机制实施规范

### 1. Pydantic Guardrails（必实现）

```python
from pydantic import BaseModel, validator, Field, root_validator
from typing import Literal

class SimulationConfig(BaseModel):
    """仿真配置模型 - 带硬约束验证"""
    
    physics_type: Literal["incompressible", "compressible", "heatTransfer"]
    delta_t: float = Field(..., gt=0, lt=1, description="时间步长必须为正且小于1")
    end_time: float = Field(..., gt=0, description="结束时间必须为正")
    
    # 网格参数
    nx: int = Field(..., ge=10, le=1000, description="x方向网格数10-1000")
    ny: int = Field(..., ge=10, le=1000, description="y方向网格数10-1000")
    
    @validator('delta_t')
    def validate_delta_t(cls, v, values):
        """验证时间步长合理性"""
        if 'end_time' in values and v > values['end_time'] * 0.1:
            raise ValueError('时间步长过大，建议不超过结束时间的10%')
        return v
    
    @root_validator
    def validate_courant_condition(cls, values):
        """验证库朗数条件"""
        # 简化的库朗数估计
        delta_t = values.get('delta_t', 0)
        nx = values.get('nx', 100)
        
        # 假设特征速度1m/s，特征长度1m
        dx = 1.0 / nx
        estimated_co = 1.0 * delta_t / dx
        
        if estimated_co > 1.0:
            raise ValueError(f'估计库朗数{estimated_co:.2f}过大，建议减小时间步长或增加网格')
        
        return values
    
    @validator('physics_type')
    def validate_physics_combination(cls, v, values):
        """验证物理场组合合理性"""
        # 可以添加更复杂的物理约束
        return v
```

### 2. Critic Agent 实现

```python
class CriticAgent:
    """审查者Agent - 严格把关方案质量"""
    
    SYSTEM_PROMPT = """你是一位极其严苛的工程热物理教授，拥有30年CFD经验。
    
    你的任务是对CFD仿真方案进行严格审查。审查标准：
    
    1. 【强制性】严禁使用过度简化的二维粗网格代替三维真实网格进行最终测试
    2. 【强制性】网格分辨率必须足以捕捉关键物理现象（边界层、分离点等）
    3. 【强制性】所有对流传热测试必须验证能量守恒，误差不得超过0.1%
    4. 【强制性】湍流模型选择必须与流动状态匹配
    5. 【建议性】求解器参数应保守设置，优先保证收敛性
    
    输出格式：
    - 如果方案合格：返回"APPROVE"并简要说明理由
    - 如果方案不合格：返回"REJECT"并列出所有问题及修改建议
    
    记住：你的职责是"挑刺"，宁可过度严格也绝不让次品通过！"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
    
    def review(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """审查方案"""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"请审查以下CFD方案：\\n{json.dumps(proposal, indent=2, ensure_ascii=False)}"}
            ]
        )
        
        review_text = response.choices[0].message.content
        
        return {
            "approved": "APPROVE" in review_text.upper(),
            "feedback": review_text,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
```

### 3. 项目宪法配置文件

```yaml
# config/system_constitution.yaml
Core_Directives:
  - "严禁使用过度简化的二维粗网格代替三维真实网格进行最终测试"
  - "所有对流传热测试必须验证能量守恒，进出口热量误差不得超过 0.1%"
  - "涉及参数反演或敏感性分析时，必须提供残差收敛至 1e-6 以下的证明"
  - "边界层网格必须满足所选湍流模型的 y+ 要求"
  - "瞬态计算必须验证时间步长独立性"

Mesh_Standards:
  min_cells_2d: 10000
  min_cells_3d: 100000
  max_aspect_ratio: 100
  max_non_orthogonality: 70
  y_plus_target_wall_function: [30, 300]
  y_plus_target_resolved: [0, 5]

Solver_Standards:
  min_convergence_residual: 1e-6
  max_courant_explicit: 0.5
  max_courant_implicit: 5.0
  relaxation_factor_min: 0.1
  relaxation_factor_max: 0.9

Validation_Requirements:
  mass_conservation_tolerance: 0.001
  energy_conservation_tolerance: 0.001
  force_balance_tolerance: 0.01
```

---

## 📊 里程碑检查点

| 阶段 | 里程碑 | 验收标准 | 检查日期 |
|------|--------|---------|---------|
| 阶段一结束 | MVP可用 | 3个经典算例端到端自动运行成功 | Week 4 |
| 阶段二结束 | 自愈能力 | 故意引入错误参数，系统能自动检测并修复 | Week 8 |
| 阶段三结束 | 记忆交互 | 支持"在上次模型基础上修改"的会话流程 | Week 12 |
| 阶段四结束 | 开源发布 | GitHub仓库公开，CI/CD通过，文档完整 | Week 16 |

---

## ⚠️ 风险管理清单

| 风险 | 应对方案 | 负责模块 |
|------|---------|---------|
| API调用成本高 | 本地正则提取关键指标，仅摘要传入LLM | execution_agent |
| LLM幻觉导致物理违背 | Pydantic硬约束 + Critic审查 + 项目宪法 | validators.py |
| 复杂几何处理困难 | 阶段一聚焦简单几何，逐步引入snappyHexMesh | preprocessing_agent |
| 文件管理混乱 | 自动清理机制 + 版本控制 | case_manager.py |

---

## 🛠️ 开发规范

### 代码风格
- 使用 Black 进行代码格式化
- 所有函数必须有类型注解
- 复杂逻辑必须添加注释

### 文档要求
- 每个类必须有Docstring
- 每个公开方法必须有参数说明
- 新增功能必须更新本文档

### 测试要求
- 核心功能必须有单元测试（pytest）
- 每个阶段结束必须有集成测试
- 使用 GitHub Actions 自动化测试

---

## 📚 参考资源

- OpenFOAM官方文档: https://www.openfoam.com/documentation
- PyVista文档: https://docs.pyvista.org/
- LangChain文档: https://python.langchain.com/
- ChromaDB文档: https://docs.trychroma.com/

---

**本文档为AI执行参考，人类开发者可基于此进行监督与调整。**
