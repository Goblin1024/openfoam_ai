# OpenFOAM AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenFOAM](https://img.shields.io/badge/OpenFOAM-v11-orange.svg)](https://www.openfoam.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**让 CFD 仿真像说话一样简单** 🚀

---

<details>
<summary><b>🌐 Language / 语言</b></summary>

<br>

**English | [中文](README_EN.md)**

<br>

</details>

OpenFOAM AI Agent 是一个基于大语言模型的自动化 CFD（计算流体力学）仿真智能体系统。通过自然语言描述，AI 自动完成从几何建模到结果可视化的全流程。

## 🎯 核心特性

- 🗣️ **自然语言交互**: 用中文或英文描述仿真需求，AI 自动理解并执行
- 🤖 **多智能体架构**: Manager、Critic、Specialist Agents 协同工作
- 🛡️ **防幻觉机制**: 多层验证确保物理合理性和科研级质量
- 🧠 **记忆性建模**: 支持"在上次基础上修改"的智能交互模式
- 🖼️ **多模态输入**: 支持自然语言和几何图像解析
- 🔧 **自愈能力**: 自动检测和修复仿真发散问题
- 📊 **自动后处理**: 生成云图、流线、矢量图等可视化结果

## 🚀 快速开始

### 环境要求

- **Python**: 3.10 或更高版本
- **OpenFOAM**: Foundation v11 或 ESI v2312（可选，用于真实计算）
- **操作系统**: Windows / Linux / macOS

### 安装

#### 方法 1: 本地安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/openfoam-ai.git
cd openfoam-ai

# 安装依赖
pip install -r openfoam_ai/requirements.txt

# 配置环境变量（可选，用于真实 LLM）
cp .env.example .env
# 编辑 .env 添加你的 API 密钥
```

#### 方法 2: Docker 部署（推荐）

```bash
# 使用 Docker Compose
docker-compose -f openfoam_ai/docker/docker-compose.yml up -d

# 查看日志
docker-compose -f openfoam_ai/docker/docker-compose.yml logs -f
```

### 运行

#### 交互模式

```bash
python openfoam_ai/main.py
```

#### 命令行快速创建算例

```bash
python openfoam_ai/main.py --case "建立一个二维方腔驱动流，顶部速度 1m/s，雷诺数 100"
```

#### Web 界面

```bash
python interactive_gui.py
```

然后在浏览器中访问 http://localhost:7860

## 📖 使用示例

### 示例 1: 方腔驱动流

```
👤 > 建立一个二维方腔驱动流，顶部速度 1m/s，雷诺数 100

🤖 我理解了您的需求，准备创建算例：cavity_re100

物理类型：incompressible
求解器：icoFoam
几何尺寸：1.0 x 1.0 x 0.1
网格：50 x 50 x 1 (共约 2500 单元)
运行时间：0 到 2.0 秒

执行计划:
  1. 创建算例目录
  2. 生成 blockMeshDict
  3. 生成 controlDict
  4. 生成初始场
  5. 运行 blockMesh
  6. 运行 checkMesh

确认执行？(y/n): y

结果：✓ 成功
信息：算例 cavity_re100 创建完成，网格已生成
```

### 示例 2: 增量修改

```
👤 > 在上次的基础上加密网格到 80x80

🤖 收到增量修改请求...

变更检测:
  - geometry.mesh_resolution.nx: 50 → 80
  - geometry.mesh_resolution.ny: 50 → 80

确认修改？(y/n): y

结果：✓ 成功
信息：算例已更新，网格重新生成
```

### 示例 3: 后处理可视化

```
👤 > 生成速度云图和流线图

🤖 准备后处理...

生成的文件:
  - result_U_0.png (速度云图)
  - streamlines.png (流线图)

结果：✓ 成功
```

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                  用户交互层 (CLI / Web UI)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                Manager Agent (任务调度)                  │
│     意图识别 → 计划生成 → 执行协调 → 结果汇总            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────┬──────────────────┬───────────────────────┐
│ Preprocessing│    Execution     │   Postprocessing      │
│   Agent     │      Agent       │        Agent          │
│ · 网格生成   │  · 求解器执行     │    · 数据提取         │
│ · 字典生成   │  · 残差监控      │    · 可视化           │
│ · 边界设置   │  · 自愈重启      │    · 报告生成         │
└─────────────┴──────────────────┴───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  OpenFOAM 计算引擎                       │
│        blockMesh / icoFoam / checkMesh / paraView       │
└─────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
openfoam-ai/
├── openfoam_ai/              # 核心代码包
│   ├── agents/               # Agent 模块
│   │   ├── manager_agent.py       # 总控 Agent
│   │   ├── critic_agent.py        # 审查者 Agent
│   │   ├── mesh_quality_agent.py  # 网格质量 Agent
│   │   ├── self_healing_agent.py  # 自愈 Agent
│   │   ├── physics_validation_agent.py  # 物理验证 Agent
│   │   ├── postprocessing_agent.py    # 后处理 Agent
│   │   └── prompt_engine.py          # LLM 接口
│   ├── core/                 # 核心功能
│   │   ├── case_manager.py        # 算例管理
│   │   ├── openfoam_runner.py     # 命令执行
│   │   ├── validators.py          # 物理验证
│   │   └── file_generator.py      # 字典生成
│   ├── memory/               # 记忆管理
│   │   ├── memory_manager.py      # 向量数据库
│   │   └── session_manager.py     # 会话管理
│   ├── ui/                   # 用户界面
│   │   ├── cli_interface.py       # 命令行界面
│   │   └── gradio_interface.py    # Web 界面
│   ├── utils/                # 工具函数
│   ├── config/               # 配置文件
│   ├── docker/               # Docker 配置
│   ├── tests/                # 单元测试
│   ├── main.py               # 主入口
│   └── requirements.txt      # 依赖列表
├── demo_cases/               # 示例算例
├── gui_cases/                # Web 界面算例
├── interactive_gui.py        # Web 界面启动脚本
├── README.md                 # 项目说明
├── LICENSE                   # 许可证
└── .gitignore                # Git 忽略配置
```

## 🔒 防幻觉机制

本项目采用多重机制防止 AI 生成不合理配置：

1. **Pydantic 硬约束**: 所有配置必须通过类型和范围验证
2. **项目宪法**: 强制遵守 `config/system_constitution.yaml` 中的规则
3. **Critic Agent**: 多智能体审查机制（评分系统）
4. **物理验证**: 质量守恒、能量守恒验证
5. **网格质量约束**: 自动检查非正交性、偏斜度、长宽比
6. **库朗数限制**: 自动估计和限制库朗数（CFL 条件）

## 🧪 测试

```bash
# 运行所有测试
pytest openfoam_ai/tests/

# 运行特定测试
pytest openfoam_ai/tests/test_phase1.py -v

# 生成覆盖率报告
pytest --cov=openfoam_ai openfoam_ai/tests/
```

### 测试覆盖率

| 阶段 | 测试数 | 通过数 | 通过率 |
|------|--------|--------|--------|
| 阶段一 | 17 | 17 | 100% |
| 阶段二 | 17 | 17 | 100% |
| 阶段三 | 24 | 24 | 100% |
| 阶段四 | 11 | 11 | 100% |
| **总计** | **52** | **52** | **100%** |

## 📚 API 参考

### 核心模块

#### CaseManager

```python
from openfoam_ai.core import CaseManager

case_manager = CaseManager("./cases")

# 创建算例
case_path = case_manager.create_case("cavity_flow", physics_type="incompressible")

# 列出所有算例
cases = case_manager.list_cases()

# 清理算例
case_manager.cleanup("cavity_flow", keep_results=True)
```

#### OpenFOAMRunner

```python
from openfoam_ai.core import OpenFOAMRunner

runner = OpenFOAMRunner(case_path)

# 运行网格生成
success, message = runner.run_blockmesh()

# 运行求解器
for metrics in runner.run_solver("icoFoam"):
    print(f"Time: {metrics.time}, Courant: {metrics.courant_max}")
```

#### PromptEngine

```python
from openfoam_ai.agents import PromptEngine

# Mock 模式（无需 API 密钥）
engine = PromptEngine(api_key=None)

# 真实 LLM 模式
engine = PromptEngine(api_key="your-api-key", base_url="...")

# 解析自然语言
config = engine.natural_language_to_config("建立方腔驱动流")
```

## 🛣️ 开发路线图

- [x] **阶段一**: 基础设施与 MVP
  - [x] 项目架构搭建
  - [x] CaseManager 实现
  - [x] 字典文件生成器
  - [x] OpenFOAM 命令封装
  
- [x] **阶段二**: AI 自查与自愈能力
  - [x] 网格质量自动修复
  - [x] 求解稳定性监控
  - [x] 发散自愈机制
  - [x] Critic Agent 审查者
  
- [x] **阶段三**: 记忆性建模与交互
  - [x] 向量数据库
  - [x] 算例历史管理
  - [x] 增量修改
  - [x] Web 界面
  
- [x] **阶段四**: 多模态与后处理
  - [x] 几何图像解析
  - [x] 自动绘图
  - [x] 结果解释
  
- [ ] **阶段五**: 高级功能（规划中）
  - [ ] 多相流支持
  - [ ] 传热耦合
  - [ ] 湍流模型
  - [ ] 优化设计

## 🤝 贡献

欢迎贡献代码、报告问题或提出新功能建议！

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/yourusername/openfoam-ai.git
cd openfoam-ai

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -r openfoam_ai/requirements.txt
pip install -e .

# 运行测试
pytest openfoam_ai/tests/
```

### 代码规范

- 遵循 [PEP 8](https://pep8.org/) 代码规范
- 使用 [Black](https://github.com/psf/black) 格式化代码
- 添加适当的类型注解
- 编写单元测试覆盖新功能

## 🔧 故障排除

### 常见错误

1. **SyntaxError: source code string cannot contain null bytes**
   - **原因**: Python 文件包含空字节或 UTF‑16 BOM
   - **解决**: 运行 `python clean.py` 或手动转换文件编码为 UTF‑8

2. **ModuleNotFoundError: No module named 'openai'**
   - **原因**: 未安装 openai 包
   - **解决**: 安装 openai (`pip install openai`) 或使用 Mock 模式（设置`api_key=None`）

3. **FileNotFoundError: [Errno 2] No such file or directory: 'blockMesh'**
   - **原因**: OpenFOAM 环境未正确加载
   - **解决**: 确保 OpenFOAM 已安装并在终端中能直接运行`blockMesh`，或使用 Docker 容器

4. **PydanticValidationError**
   - **原因**: 配置不符合验证规则
   - **解决**: 检查配置参数是否符合宪法规则（见`config/system_constitution.yaml`）

5. **UnicodeEncodeError: 'gbk' codec can't encode character**
   - **原因**: Windows 控制台默认编码为 GBK
   - **解决**: 设置环境变量`PYTHONIOENCODING=utf-8`

### 调试建议

- 启用详细日志：设置环境变量 `LOG_LEVEL=DEBUG`
- 使用 Mock 模式测试配置生成：`PromptEngine(api_key=None)`
- 运行单元测试：`pytest openfoam_ai/tests/`
- 检查算例目录结构：确保`0/`, `constant/`, `system/`目录存在

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) - 详见 LICENSE 文件

## 🙏 致谢

- [OpenFOAM](https://www.openfoam.com/) - 开源 CFD 工具
- [LangChain](https://python.langchain.com/) - LLM 应用框架
- [PyVista](https://docs.pyvista.org/) - 可视化库
- [Gradio](https://gradio.app/) - Web 界面库

## 📧 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 [GitHub Issue](https://github.com/yourusername/openfoam-ai/issues)
- 发送邮件至：your.email@example.com

## 📝 引用

如果您在研究中使用本项目，请引用：

```bibtex
@software{openfoam_ai_agent2026,
  author = {Your Name},
  title = {OpenFOAM AI Agent: LLM-Driven Automated CFD Simulation},
  year = {2026},
  url = {https://github.com/yourusername/openfoam-ai}
}
```

---

**免责声明**: 本工具用于学术研究和工程辅助。仿真结果需经专业人员验证后方可用于实际工程决策。
