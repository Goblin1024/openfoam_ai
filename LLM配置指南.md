# OpenFOAM AI Agent - LLM 配置指南

## 支持的 LLM 提供商

项目已集成以下国内主流大模型，支持自然语言建模仿真：

| 提供商 | 推荐模型 | 特点 | 申请地址 |
|--------|---------|------|---------|
| **KIMI** (Moonshot) | kimi-k2 | 中文理解强，上下文长 | https://platform.moonshot.cn |
| **DeepSeek** | deepseek-chat | 代码能力强，性价比高 | https://platform.deepseek.com |
| **豆包** (字节) | doubao-pro | 多模态能力强 | https://www.volcengine.com/product/doubao |
| **GLM** (智谱) | glm-4 | 中文优化好 | https://open.bigmodel.cn |
| **MiniMax** | abab6.5 | 响应速度快 | https://www.minimaxi.com |
| **阿里云百炼** | qwen-max | 稳定可靠 | https://bailian.console.aliyun.com |

---

## 快速配置步骤

### 步骤 1: 申请 API Key

选择一个提供商，访问对应网站申请 API Key。

### 步骤 2: 配置环境变量

**Windows (CMD):**
```cmd
set KIMI_API_KEY=sk-your-key-here
set DEFAULT_LLM_PROVIDER=kimi
```

**Windows (PowerShell):**
```powershell
$env:KIMI_API_KEY="sk-your-key-here"
$env:DEFAULT_LLM_PROVIDER="kimi"
```

**Linux/Mac:**
```bash
export KIMI_API_KEY=sk-your-key-here
export DEFAULT_LLM_PROVIDER=kimi
```

### 步骤 3: 测试连接

```bash
python test_llm_connection.py
```

### 步骤 4: 启动项目

```bash
python start_with_llm.py
```

---

## 配置方式详解

### 方式一：环境变量（推荐）

设置以下环境变量之一：

```bash
# KIMI (推荐)
export KIMI_API_KEY=sk-your-key

# DeepSeek
export DEEPSEEK_API_KEY=sk-your-key

# 豆包
export DOUBAO_API_KEY=sk-your-key

# GLM
export GLM_API_KEY=your-key

# MiniMax
export MINIMAX_API_KEY=your-key

# 阿里云
export ALIYUN_API_KEY=sk-your-key

# 设置默认提供商
export DEFAULT_LLM_PROVIDER=kimi
```

### 方式二：.env 文件

在项目根目录创建 `.env` 文件：

```
DEFAULT_LLM_PROVIDER=kimi
KIMI_API_KEY=sk-your-key-here
```

安装 python-dotenv:
```bash
pip install python-dotenv
```

### 方式三：命令行参数

```bash
# 指定提供商
python start_with_llm.py --provider deepseek

# 直接传入 API Key
python start_with_llm.py --provider kimi --api-key sk-xxx

# 指定模型
python start_with_llm.py --provider aliyun --model qwen-max
```

---

## 各提供商详细配置

### KIMI (Moonshot AI)

**推荐模型：**
- `kimi-k2` (最新，128K上下文)
- `moonshot-v1-128k` (长文本)

**申请步骤：**
1. 访问 https://platform.moonshot.cn
2. 注册账号
3. 创建 API Key
4. 复制 Key 到环境变量

**测试：**
```bash
set KIMI_API_KEY=sk-your-key
python test_llm_connection.py
```

---

### DeepSeek

**推荐模型：**
- `deepseek-chat` (通用对话)
- `deepseek-coder` (代码优化)

**特点：**
- 价格便宜
- 代码生成能力强
- 支持长上下文

**申请：** https://platform.deepseek.com

---

### 豆包 (ByteDance)

**推荐模型：**
- `doubao-pro-128k` (专业版)
- `doubao-vision-pro-32k` (多模态)

**注意：** 豆包通过阿里云百炼平台接入

**申请：** https://www.volcengine.com/product/doubao

---

### GLM (智谱 AI)

**推荐模型：**
- `glm-4` (旗舰版)
- `glm-4-plus` (增强版)
- `glm-4v` (多模态)

**申请：** https://open.bigmodel.cn

---

### MiniMax

**推荐模型：**
- `abab6.5-chat` (最新版)

**申请：** https://www.minimaxi.com

---

### 阿里云百炼

**推荐模型：**
- `qwen-max` (通义千问Max)
- `qwen-vl-max` (多模态)

**申请：** https://bailian.console.aliyun.com

---

## 使用示例

### 示例 1: 使用 KIMI

```bash
# 设置环境变量
set KIMI_API_KEY=sk-abc123...
set DEFAULT_LLM_PROVIDER=kimi

# 启动
python start_with_llm.py

# 输入自然语言
> 创建一个二维方腔驱动流，顶部速度1m/s

[AI] 正在解析您的需求...
[OK] 成功连接到 kimi LLM
[STAT] 方案评分: 78/100
[INFO] 审查结论: CONDITIONAL
[INFO] 配置摘要:
  物理类型: incompressible
  求解器: icoFoam
  网格分辨率: 40 x 40
```

### 示例 2: 使用 DeepSeek

```bash
python start_with_llm.py --provider deepseek --api-key sk-xxx
```

### 示例 3: 对比测试

```bash
# 测试所有配置的提供商
python test_llm_connection.py
```

---

## 故障排除

### 问题 1: API Key 无效

**现象：**
```
[ERR] API 调用失败: Invalid API Key
```

**解决：**
1. 检查 Key 是否复制完整
2. 确认 Key 是否已激活
3. 检查账户余额是否充足

### 问题 2: 网络连接失败

**现象：**
```
[ERR] Connection timeout
```

**解决：**
1. 检查网络连接
2. 确认能访问对应 API 域名
3. 如需代理，设置 HTTPS_PROXY

### 问题 3: JSON 解析错误

**现象：**
```
[ERR] JSON解析错误
```

**解决：**
1. 某些模型可能不严格遵循 JSON 格式
2. 尝试更换模型
3. 使用 Mock 模式测试框架

---

## 成本估算

| 提供商 | 输入价格 | 输出价格 | 单次配置成本 |
|--------|---------|---------|-------------|
| KIMI | ¥0.012/1K tokens | ¥0.012/1K tokens | ~¥0.02-0.05 |
| DeepSeek | ¥0.001/1K tokens | ¥0.002/1K tokens | ~¥0.005-0.01 |
| GLM-4 | ¥0.01/1K tokens | ¥0.01/1K tokens | ~¥0.02-0.05 |

**注：** 单次配置约消耗 1000-3000 tokens

---

## 推荐配置

### 开发测试阶段
- **使用 Mock 模式** - 免费，无需 API Key
- 验证代码框架和功能逻辑

### 生产使用阶段
- **推荐 KIMI** - 中文理解好，上下文长
- **备选 DeepSeek** - 价格便宜，性价比高

---

## 下一步

配置完成后，运行：

```bash
# 测试 LLM 连接
python test_llm_connection.py

# 启动交互式建模仿真
python start_with_llm.py

# 或带参数启动
python start_with_llm.py --provider kimi
```

享受自然语言建模仿真吧！
