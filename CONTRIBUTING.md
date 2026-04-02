# 贡献指南

感谢您对 OpenFOAM AI Agent 项目的关注！我们欢迎各种形式的贡献，包括代码、文档、测试、问题报告和功能建议。

## 📑 目录

- [行为准则](#行为准则)
- [贡献方式](#贡献方式)
- [开发环境搭建](#开发环境搭建)
- [代码规范](#代码规范)
- [提交流程](#提交流程)
- [测试要求](#测试要求)
- [常见问题](#常见问题)

## 行为准则

本项目采用 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。请保持友好、尊重和专业的交流氛围。

## 贡献方式

### 1. 报告问题

发现 Bug 或有功能建议？请创建 [Issue](https://github.com/yourusername/openfoam-ai/issues)：

**Bug 报告应包含：**
- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（Python 版本、操作系统、OpenFOAM 版本）
- 错误日志或截图

**功能建议应包含：**
- 功能描述
- 使用场景
- 预期效果
- 可能的实现思路（可选）

### 2. 提交代码

#### 适合新手的任务

查看标记为 [`good first issue`](https://github.com/yourusername/openfoam-ai/labels/good%20first%20issue) 的问题，这些任务适合第一次贡献者：

- 文档改进
- 添加单元测试
- 代码注释完善
- 简单的 Bug 修复

#### 代码贡献流程

1. **Fork 仓库**
   - 点击 GitHub 页面右上角的 "Fork" 按钮

2. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/openfoam-ai.git
   cd openfoam-ai
   ```

3. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```
   
   分支命名规范：
   - `feature/xxx`: 新功能
   - `bugfix/xxx`: Bug 修复
   - `docs/xxx`: 文档更新
   - `test/xxx`: 测试相关
   - `refactor/xxx`: 代码重构

4. **进行修改**
   - 编写代码
   - 添加测试
   - 更新文档

5. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Commit message 规范遵循 [Conventional Commits](https://www.conventionalcommits.org/)：
   - `feat`: 新功能
   - `fix`: Bug 修复
   - `docs`: 文档更新
   - `style`: 代码格式调整
   - `refactor`: 代码重构
   - `test`: 测试相关
   - `chore`: 构建/工具相关

6. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   - 在 GitHub 上点击 "New Pull Request"
   - 填写 PR 描述模板
   - 等待代码审查

## 开发环境搭建

### 1. 基础环境

```bash
# Python 3.10+
python --version

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. 安装依赖

```bash
# 安装开发和测试依赖
pip install -r openfoam_ai/requirements.txt
pip install -e .

# 开发工具
pip install black mypy pytest pytest-cov
```

### 3. 验证安装

```bash
# 运行测试
pytest openfoam_ai/tests/

# 代码格式化检查
black --check openfoam_ai/

# 类型检查
mypy openfoam_ai/
```

## 代码规范

### Python 代码风格

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用 [Black](https://github.com/psf/black) 格式化代码
- 行宽限制：88 字符（Black 默认）
- 缩进：4 个空格

### 格式化代码

```bash
# 自动格式化
black openfoam_ai/

# 检查格式
black --check openfoam_ai/
```

### 类型注解

所有公共函数和类方法应添加类型注解：

```python
from typing import Dict, List, Optional
from pydantic import BaseModel

class SimulationConfig(BaseModel):
    """仿真配置模型"""
    
    physics_type: str
    solver_name: str
    mesh_resolution: List[int]
    
    def get_solver_path(self) -> str:
        """获取求解器路径"""
        return f"/solvers/{self.solver_name}"

def create_case(
    name: str,
    physics_type: str,
    template: Optional[str] = None
) -> Dict[str, str]:
    """创建算例"""
    ...
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def validate_mesh(config: MeshConfig) -> ValidationResult:
    """
    验证网格质量
    
    Args:
        config: 网格配置对象
        
    Returns:
        ValidationResult: 包含验证结果和错误信息
        
    Raises:
        ValidationError: 当网格质量不满足要求时
    """
    ...
```

## 提交流程

### Pull Request 模板

创建 PR 时，请填写以下信息：

```markdown
## 问题链接
Fixes #123

## 变更描述
简要描述此 PR 的目的

## 变更类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 代码重构
- [ ] 测试更新

## 测试
- [ ] 已添加单元测试
- [ ] 所有测试通过
- [ ] 已更新集成测试

## 检查清单
- [ ] 代码遵循 PEP 8 规范
- [ ] 已运行 Black 格式化
- [ ] 已添加类型注解
- [ ] 已更新文档
- [ ] 无新的警告信息
```

### 代码审查

所有 PR 需要经过至少一位维护者的审查：

**审查要点：**
- 代码质量
- 测试覆盖
- 文档完整性
- 向后兼容性
- 性能影响

### 合并策略

- 使用 **Squash and Merge** 保持提交历史简洁
- 确保 CI 测试全部通过
- 解决所有审查意见

## 测试要求

### 单元测试

新功能必须包含单元测试：

```python
# openfoam_ai/tests/test_new_feature.py

import pytest
from openfoam_ai.core import NewFeature

class TestNewFeature:
    """新功能测试类"""
    
    def test_basic_functionality(self):
        """测试基本功能"""
        feature = NewFeature()
        result = feature.run()
        assert result is not None
    
    def test_edge_case(self):
        """测试边界情况"""
        feature = NewFeature()
        with pytest.raises(ValueError):
            feature.run(invalid_input)
```

### 运行测试

```bash
# 运行所有测试
pytest openfoam_ai/tests/

# 运行特定测试文件
pytest openfoam_ai/tests/test_phase1.py

# 运行特定测试函数
pytest openfoam_ai/tests/test_phase1.py::test_case_manager -v

# 生成覆盖率报告
pytest --cov=openfoam_ai --cov-report=html openfoam_ai/tests/
```

### 测试覆盖率

目标覆盖率：
- 核心模块：>80%
- 新增代码：>90%

## 文档贡献

### 文档结构

```
docs/
├── zh/           # 中文文档
├── en/           # 英文文档
└── api/          # API 文档
```

### 文档格式

- 使用 Markdown 格式
- 代码示例需可运行
- 包含必要的截图和图表

### 构建文档

```bash
# 安装文档工具
pip install mkdocs mkdocs-material

# 本地预览
mkdocs serve

# 构建静态文件
mkdocs build
```

## 常见问题

### Q: 我没有 OpenFOAM 环境，可以贡献代码吗？

A: 可以！您可以：
- 贡献文档
- 编写单元测试（使用 Mock）
- 改进 UI/UX
- 优化代码结构

### Q: 如何测试需要 OpenFOAM 的功能？

A: 使用 Docker 容器：
```bash
docker-compose -f openfoam_ai/docker/docker-compose.yml up -d
```

### Q: PR 多久会被审查？

A: 通常在 1-2 周内。如果超过 2 周没有回应，可以在 Issue 中 @maintainer。

### Q: 可以同时提交多个 PR 吗？

A: 建议一次只关注一个功能或修复，这样更容易审查和合并。

## 联系方式

- GitHub Issues: [提问](https://github.com/yourusername/openfoam-ai/issues)
- 邮箱：your.email@example.com
- 讨论区：[GitHub Discussions](https://github.com/yourusername/openfoam-ai/discussions)

## 致谢

感谢所有为这个项目做出贡献的开发者！

---

再次感谢您的贡献！🎉
