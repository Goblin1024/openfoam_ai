# 配置真实的 OpenAI LLM

## 1. 获取 API Key

访问 https://platform.openai.com/api-keys 创建 API Key

## 2. 配置方式（三选一）

### 方式一：环境变量（推荐）
```bash
# Windows
set OPENAI_API_KEY=your_api_key_here

# Linux/Mac
export OPENAI_API_KEY=your_api_key_here
```

### 方式二：创建 .env 文件
在项目根目录创建 `.env` 文件：
```
OPENAI_API_KEY=your_api_key_here
```

### 方式三：代码中传入
```python
from prompt_engine import PromptEngine

engine = PromptEngine(api_key="your_api_key_here")
config = engine.natural_language_to_config("创建一个方腔驱动流")
```

## 3. 验证配置

运行以下测试：
```python
from prompt_engine import PromptEngine

engine = PromptEngine()
print(f"Mock模式: {engine.mock_mode}")  # 应输出 False

config = engine.natural_language_to_config("创建一个方腔驱动流")
print(config)  # 将看到真实的LLM生成的配置
```

## 4. 注意事项

### 成本考虑
- GPT-4 API 调用会产生费用
- 每个配置生成大约需要 1000-2000 tokens
- 建议先用 Mock 模式开发测试，最后用真实 LLM 验证

### 网络要求
- 需要能访问 OpenAI API（api.openai.com）
- 可能需要配置代理

### 模型选择
默认使用 gpt-4，可以在初始化时指定其他模型：
```python
engine = PromptEngine(
    api_key="your_key",
    model="gpt-3.5-turbo"  # 更便宜但能力较弱
)
```

## 5. 当前的局限性

即使配置了真实 LLM，项目仍存在以下局限：

1. **OpenFOAM 执行**：需要本地安装 OpenFOAM 才能实际运行仿真
2. **后处理可视化**：需要安装 PyVista 才能生成真实图像
3. **ChromaDB**：记忆功能默认使用 Mock 模式，需要安装 chromadb 包才能真实存储

## 6. 真实的项目完成度评估

| 功能模块 | 代码完成度 | 真实运行要求 |
|---------|-----------|-------------|
| PromptEngine | 100% | 需要 OpenAI API Key |
| CaseManager | 100% | 无需额外依赖 |
| MeshQualityAgent | 100% | 需要 OpenFOAM 安装 |
| SelfHealingAgent | 100% | 需要 OpenFOAM 安装 |
| CriticAgent | 100% | 可选：真实 LLM 审查 |
| MemoryManager | 100% | 可选：ChromaDB 安装 |
| PostProcessingAgent | 100% | 可选：PyVista 安装 |

**结论**：项目架构完整，但要完整运行需要配置外部依赖。
