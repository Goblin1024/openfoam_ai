# 免费/低成本 LLM 推荐

## 1. DeepSeek（推荐，价格便宜）

**价格：**
- 输入：¥0.001/1K tokens
- 输出：¥0.002/1K tokens
- 单次配置成本：约 ¥0.005-0.01

**申请：** https://platform.deepseek.com
- 新用户可能有免费额度
- 充值门槛低

## 2. 阿里云百炼（新用户免费额度）

**价格：**
- qwen-turbo：¥0.003/1K tokens
- qwen-max：¥0.02/1K tokens

**申请：** https://bailian.console.aliyun.com
- 新用户通常有免费试用额度
- 阿里云账户通用

## 3. GLM（智谱 AI）

**价格：**
- glm-4-flash：¥0.001/1K tokens（最便宜）
- glm-4：¥0.01/1K tokens

**申请：** https://open.bigmodel.cn
- 新用户有免费额度
- 充值方便

## 4. 继续使用 Mock 模式

如果暂时不想申请 API Key，可以继续使用 **Mock 模式**：

```bash
python demo_mock_simulation.py
```

功能完整，只是使用预定义模板而非真实 LLM。

---

## 快速配置示例

### DeepSeek 配置

```bash
# 1. 访问 https://platform.deepseek.com 申请 API Key
# 2. 设置环境变量
set DEEPSEEK_API_KEY=sk-your-deepseek-key

# 3. 测试
python test_llm_connection.py

# 4. 启动
python start_with_llm.py --provider deepseek
```

### 阿里云百炼配置

```bash
# 1. 访问 https://bailian.console.aliyun.com
# 2. 设置环境变量
set ALIYUN_API_KEY=sk-your-aliyun-key

# 3. 启动
python start_with_llm.py --provider aliyun
```
