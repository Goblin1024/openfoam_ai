# 变更日志

本文件记录 OpenFOAM AI Agent 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### Added
- 初始发布版本
- 完整的 AI 驱动 CFD 仿真工作流
- 多智能体架构（Manager、Critic、Specialist Agents）
- 自然语言解析和配置生成
- 网格质量自动检查和修复
- 求解稳定性监控和自愈机制
- 记忆性建模系统（向量数据库）
- 几何图像解析功能
- 自动后处理和可视化
- Web 界面（Gradio）
- 命令行界面
- Docker 容器化部署支持

### Changed
- 无

### Deprecated
- 无

### Removed
- 无

### Fixed
- 无

### Security
- 无

---

## [0.1.0] - 2026-03-29

### Added

#### 阶段一：基础设施与 MVP
- **CaseManager**: 算例目录管理
  - 创建标准 OpenFOAM 算例目录结构
  - 算例状态跟踪
  - 内置方腔驱动流模板
  - 元数据管理
  
- **PromptEngine**: 自然语言解析
  - 支持中文和英文输入
  - Mock 模式（无需 API 密钥）
  - 多物理类型支持
  
- **ConfigRefiner**: 配置优化器
  - 网格分辨率自动优化
  - 时间步长调整
  - 物理参数验证
  
- **OpenFOAMRunner**: 命令执行器
  - blockMesh、checkMesh 封装
  - 求解器执行和监控
  - 日志捕获和解析
  
- **Validators**: 物理验证器
  - Pydantic 硬约束验证
  - 库朗数限制
  - 网格分辨率检查

#### 阶段二：AI 自查与自愈能力
- **MeshQualityAgent**: 网格质量自查
  - 质量等级评估
  - 非正交性、偏斜度、长宽比检查
  - 自动修复策略
  
- **SelfHealingAgent**: 求解稳定性监控
  - 实时求解器监控
  - 发散类型检测
  - 自动修复策略
  - 智能重启机制
  
- **CriticAgent**: 审查者 Agent
  - 基于宪法规则的方案审查
  - 评分系统（0-100 分）
  - 问题分级（critical/major/minor）
  - 改进建议生成
  
- **PhysicsValidationAgent**: 物理一致性校验
  - 质量守恒验证
  - 能量守恒验证
  - 收敛性检查
  - y+ 值检查

#### 阶段三：记忆性建模与交互
- **MemoryManager**: 记忆管理
  - ChromaDB 向量数据库集成
  - 算例配置向量化存储
  - 相似性检索
  
- **ConfigurationDiffer**: 配置差异分析
  - 深度字典差异比较
  - 增量更新
  - 变更摘要生成
  
- **SessionManager**: 会话管理
  - 多轮对话历史记录
  - 上下文追踪
  - 待确认操作队列
  
- **UI 界面**
  - Gradio Web 界面
  - 增强版 CLI Interface

#### 阶段四：多模态与后处理
- **GeometryImageParser**: 几何图像解析
  - 图像解析（Mock 模式和 Vision API）
  - 几何特征提取
  - 边界条件推断
  
- **PostProcessingAgent**: 后处理与自动绘图
  - 自然语言绘图需求解析
  - PyVista 脚本自动生成
  - 多种绘图类型支持
  - 多输出格式

#### 文档和测试
- 完整的 README 文档
- API 参考文档
- 开发指南
- 单元测试（52 个测试，100% 通过率）
- 示例算例

### Changed
- 优化了自然语言解析算法
- 改进了网格质量评估逻辑
- 提升了自愈机制响应速度

### Fixed
- 修复了 Windows 平台编码问题
- 修复了 Mock 模式下的兼容性问题
- 修复了会话持久化的边界情况

### Security
- 添加环境变量配置支持
- 敏感信息隔离（.env 文件）

---

## 版本说明

### 版本号规则

- **主版本号（Major）**: 不兼容的 API 修改
- **次版本号（Minor）**: 向下兼容的功能性新增
- **修订号（Patch）**: 向下兼容的问题修正

### 发布周期

- 主版本：每 6 个月
- 次版本：每月
- 修订版：按需

---

## 贡献者

感谢所有为这个项目做出贡献的开发者！

[完整贡献者列表](https://github.com/yourusername/openfoam-ai/graphs/contributors)

---

## 相关链接

- [GitHub Releases](https://github.com/yourusername/openfoam-ai/releases)
- [Issue Tracker](https://github.com/yourusername/openfoam-ai/issues)
- [项目主页](https://github.com/yourusername/openfoam-ai)
