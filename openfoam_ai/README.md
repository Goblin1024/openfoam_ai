# OpenFOAM AI Agent

基于大语言模型的自动化CFD仿真智能体系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenFOAM](https://img.shields.io/badge/OpenFOAM-v11-orange.svg)](https://www.openfoam.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🎯 项目愿景

让CFD仿真像说话一样简单。通过自然语言描述，AI自动完成：
- 几何建模与网格生成
- 求解器配置与边界条件设置
- 计算执行与实时监控
- 结果后处理与可视化

## 🚀 快速开始

### 环境要求

- Python 3.10+
- OpenFOAM (Foundation v11 或 ESI v2312)
- (可选) OpenAI API Key

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/openfoam-ai.git
cd openfoam-ai

# 安装依赖
pip install -r requirements.txt

# 或使用Docker
docker-compose -f docker/docker-compose.yml up -d
```

### 运行

```bash
# 交互模式
python main.py

# 演示模式
python main.py --demo

# 快速创建算例
python main.py --case "建立一个二维方腔驱动流"
```

## 📖 使用示例

### 示例1: 方腔驱动流

```
👤 > 建立一个二维方腔驱动流，顶部速度1m/s，雷诺数100

🤖 我理解了您的需求，准备创建算例：cavity_re100

物理类型: incompressible
求解器: icoFoam
几何尺寸: 1.0 x 1.0 x 0.1
网格: 50 x 50 x 1 (共约2500单元)
运行时间: 0 到 2.0 秒

执行计划:
  1. 创建算例目录
  2. 生成blockMeshDict
  3. 生成controlDict
  4. 生成初始场
  5. 运行blockMesh
  6. 运行checkMesh

确认执行? (y/n): y

结果: ✓ 成功
信息: 算例 cavity_re100 创建完成，网格已生成
```

### 示例2: 查看状态

```
👤 > 查看状态

🤖 当前算例: cavity_re100
状态: meshed
求解器: icoFoam
```

### 示例3: 运行计算

```
👤 > 开始计算

🤖 准备运行求解器 icoFoam

确认开始计算? (y/n): y

结果: ✓ 成功
信息: 计算完成，最终时间=2.0
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户交互层 (main.py / Gradio UI)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Manager Agent (任务调度)                        │
│   意图识别 → 计划生成 → 执行协调 → 结果汇总                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────┬──────────────────┬──────────────────────────────┐
│  Preprocessing  │    Execution     │      Postprocessing          │
│     Agent       │      Agent       │          Agent               │
│  · 网格生成      │   · 求解器执行    │      · 数据提取              │
│  · 字典生成      │   · 残差监控      │      · 可视化                │
│  · 边界设置      │   · 自愈重启      │      · 报告生成              │
└─────────────────┴──────────────────┴──────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      OpenFOAM 计算引擎                           │
│              blockMesh / icoFoam / checkMesh / paraView          │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
openfoam_ai/
├── agents/                    # Agent模块
│   ├── manager_agent.py       # 总控Agent
│   └── prompt_engine.py       # LLM接口
├── core/                      # 核心功能
│   ├── case_manager.py        # 算例管理
│   ├── file_generator.py      # 字典生成
│   ├── openfoam_runner.py     # 命令执行
│   └── validators.py          # 物理验证
├── models/                    # 物理模型
├── memory/                    # 记忆管理
├── config/                    # 配置文件
│   └── system_constitution.yaml  # 项目宪法
├── docker/                    # Docker配置
├── tests/                     # 测试
├── main.py                    # 主入口
└── requirements.txt           # 依赖
```

## 🔒 防幻觉机制

本项目采用多重机制防止AI生成不合理配置：

1. **Pydantic硬约束**: 所有配置必须通过类型和范围验证
2. **项目宪法**: 强制遵守`config/system_constitution.yaml`中的规则
3. **Critic Agent**: 多智能体审查机制（阶段二）
4. **物理验证**: 质量/能量守恒验证

## 📚 API参考

### 核心模块

#### `CaseManager`
- **位置**: `openfoam_ai/core/case_manager.py`
- **功能**: 管理OpenFOAM算例目录结构，包括创建、复制、清理、删除。
- **主要方法**:
  - `create_case(case_name, physics_type) -> Path`
  - `copy_template(template_path, case_name) -> Path`
  - `list_cases() -> List[str]`
  - `cleanup(case_name, keep_results=False)`
  - `delete_case(case_name)`

#### `OpenFOAMRunner`
- **位置**: `openfoam_ai/core/openfoam_runner.py`
- **功能**: 封装OpenFOAM命令执行（blockMesh、checkMesh、求解器），提供实时监控和日志解析。
- **主要方法**:
  - `run_blockmesh() -> (bool, str)`
  - `run_checkmesh() -> (bool, str, dict)`
  - `run_solver(solver_name, callback) -> Iterator[SolverMetrics]`
  - `stop_solver()`

#### `PhysicsValidator`
- **位置**: `openfoam_ai/core/validators.py`
- **功能**: 验证物理配置的合理性，集成宪法规则，确保CFL条件、网格分辨率、禁止组合等。
- **主要方法**:
  - `validate_mass_conservation()`
  - `validate_energy_conservation()`
  - `validate_boundary_compatibility()`

#### `PromptEngine`
- **位置**: `openfoam_ai/agents/prompt_engine.py`
- **功能**: 将自然语言转换为仿真配置，支持Mock模式（无API密钥）和真实LLM模式。
- **主要方法**:
  - `natural_language_to_config(user_input) -> dict`
  - `explain_config(config) -> str`
  - `suggest_improvements(config, feedback) -> list`

### 配置验证

所有配置都通过Pydantic模型验证，定义在`validators.py`中：
- `MeshConfig`: 网格配置
- `SolverConfig`: 求解器配置
- `BoundaryCondition`: 边界条件
- `SimulationConfig`: 完整仿真配置

## 🛠️ 故障排除

### 常见错误

1. **SyntaxError: source code string cannot contain null bytes**
   - **原因**: Python文件包含空字节或UTF‑16 BOM。
   - **解决**: 运行清理脚本 `python clean.py` 或手动转换文件编码为UTF‑8。

2. **ModuleNotFoundError: No module named 'openai'**
   - **原因**: 未安装openai包，但项目尝试导入。
   - **解决**: 安装openai (`pip install openai`) 或使用Mock模式（设置`api_key=None`）。

3. **FileNotFoundError: [Errno 2] No such file or directory: 'blockMesh'**
   - **原因**: OpenFOAM环境未正确加载或PATH未设置。
   - **解决**: 确保OpenFOAM已安装并在终端中能直接运行`blockMesh`。在Docker容器内运行项目。

4. **PydanticValidationError: ...**
   - **原因**: 配置不符合验证规则。
   - **解决**: 检查配置参数是否符合宪法规则（见`config/system_constitution.yaml`）。

5. **UnicodeEncodeError: 'gbk' codec can't encode character ...**
   - **原因**: Windows控制台默认编码为GBK，无法打印某些Unicode字符。
   - **解决**: 忽略此错误，或设置环境变量`PYTHONIOENCODING=utf-8`。

### 调试建议

- 启用详细日志：设置环境变量 `LOG_LEVEL=DEBUG`。
- 使用Mock模式测试配置生成：`PromptEngine(api_key=None)`。
- 运行单元测试：`pytest openfoam_ai/tests/`。
- 检查算例目录结构：确保`0/`, `constant/`, `system/`目录存在。

## 🛣️ 开发路线图

- [x] **阶段一**: 基础设施与MVP
  - [x] 项目架构搭建
  - [x] CaseManager实现
  - [x] 字典文件生成器
  - [x] OpenFOAM命令封装
  
- [ ] **阶段二**: AI自查能力
  - [ ] 网格质量自动修复
  - [ ] 求解稳定性监控
  - [ ] 发散自愈机制
  
- [ ] **阶段三**: 记忆性建模
  - [ ] 向量数据库
  - [ ] 算例历史管理
  - [ ] 增量修改
  
- [ ] **阶段四**: 多模态与后处理
  - [ ] 几何图像解析
  - [ ] 自动绘图
  - [ ] 结果解释

## 🤝 贡献

欢迎贡献代码、报告问题或提出新功能建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [OpenFOAM](https://www.openfoam.com/) - 开源CFD工具
- [LangChain](https://python.langchain.com/) - LLM应用框架
- [PyVista](https://docs.pyvista.org/) - 可视化库

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 [GitHub Issue](https://github.com/yourusername/openfoam-ai/issues)
- 发送邮件至: your.email@example.com

---

**免责声明**: 本工具用于学术研究和工程辅助。仿真结果需经专业人员验证后方可用于实际工程决策。
