# OpenFOAM AI Agent - LLM 配置完成

## 已集成的功能

✅ **支持 7 大国内主流 LLM 提供商：**
1. KIMI (Moonshot AI)
2. DeepSeek
3. 豆包 (ByteDance)
4. GLM (智谱 AI)
5. MiniMax
6. 阿里云百炼 (Qwen)
7. OpenAI

✅ **统一的 API 接口：**
- `llm_adapter.py` - 适配器核心
- `PromptEngineV2` - 支持多模型的提示词引擎
- 自动 fallback 到 Mock 模式

---

## 快速开始

### 1. 选择提供商并申请 API Key

推荐顺序：
1. **KIMI** (https://platform.moonshot.cn) - 中文最强
2. **DeepSeek** (https://platform.deepseek.com) - 性价比最高
3. **GLM** (https://open.bigmodel.cn) - 稳定可靠

### 2. 配置 API Key

**Windows:**
```cmd
set KIMI_API_KEY=sk-your-key-here
```

**Linux/Mac:**
```bash
export KIMI_API_KEY=sk-your-key-here
```

### 3. 测试连接

```bash
python test_llm_connection.py
```

### 4. 启动项目

**自动检测模式：**
```bash
python quick_start.py
```

**指定提供商：**
```bash
python start_with_llm.py --provider kimi
```

**Mock 模式（无需 API Key）：**
```bash
python start_with_llm.py --mock
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `openfoam_ai/core/llm_adapter.py` | LLM 适配器核心，支持7家提供商 |
| `openfoam_ai/agents/prompt_engine_v2.py` | V2版提示词引擎，支持真实LLM |
| `test_llm_connection.py` | API 连接测试工具 |
| `start_with_llm.py` | LLM 模式启动器 |
| `quick_start.py` | 自动检测并启动 |
| `.env.example` | 环境变量模板 |
| `LLM配置指南.md` | 详细配置文档 |

---

## 使用示例

### 示例 1: 使用 KIMI 创建算例

```bash
# 设置 Key
set KIMI_API_KEY=sk-abc123...

# 启动
python quick_start.py

# 输入:
> 创建一个二维方腔驱动流，顶部速度1m/s

# 输出:
[AI] 正在解析您的需求...
[OK] 成功连接到 kimi LLM
[STAT] 方案评分: 78/100
[INFO] 配置摘要:
  算例名称: cavity_flow_001
  物理类型: incompressible
  求解器: icoFoam
  网格分辨率: 40 x 40
[OK] 算例创建成功!
```

### 示例 2: 对比不同 LLM

```bash
# 测试所有配置
python test_llm_connection.py

# 输出示例:
======================================================================
测试结果汇总
======================================================================
kimi           : ✓ 通过
deepseek       : ✓ 通过
glm            : ✗ 失败
...

推荐使用的提供商: kimi, deepseek
```

---

## 注意事项

### API Key 安全
- 不要将 API Key 提交到 Git
- 使用 `.env` 文件并添加到 `.gitignore`
- 定期轮换 API Key

### 成本控制
- 单次配置约消耗 1000-3000 tokens
- KIMI: ~¥0.02-0.05/次
- DeepSeek: ~¥0.005-0.01/次

### 网络要求
- 需要能访问对应 API 域名
- 可能需要配置代理

---

## 故障排除

| 问题 | 解决 |
|------|------|
| API Key 无效 | 检查 Key 是否完整，账户是否有余额 |
| 连接超时 | 检查网络，确认能访问 API 域名 |
| JSON 解析错误 | 尝试更换模型或调整 temperature |

---

## 下一步

1. 申请 API Key (推荐 KIMI 或 DeepSeek)
2. 设置环境变量
3. 运行 `python test_llm_connection.py` 测试
4. 运行 `python quick_start.py` 启动项目
5. 输入自然语言开始建模仿真！

---

## 项目结构

```
openfoam_ai/
├── core/
│   ├── llm_adapter.py          # LLM 适配器 (NEW)
│   └── ...
├── agents/
│   ├── prompt_engine.py         # 原版 (Mock模式)
│   └── prompt_engine_v2.py      # V2版 (支持真实LLM)
└── ...

test_llm_connection.py           # 连接测试
start_with_llm.py                # LLM启动器
quick_start.py                   # 快速启动
LLM配置指南.md                    # 详细文档
```

---

**项目已准备就绪，等待您的 API Key 开始真实 LLM 建模仿真！**
