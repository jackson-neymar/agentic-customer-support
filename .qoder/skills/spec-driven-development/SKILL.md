---
name: spec-driven-development
description: Use for spec-driven development with AI before software changes: turn vague feature requests, bug reports, refactors, or product changes into clear specs, Given-When-Then scenarios, acceptance criteria, task plans, implementation guardrails, and review checklists. Trigger when the user asks to write a spec, clarify requirements, plan implementation, convert a feature or bug into tasks, or use SDD/spec-first development.
---

# Spec Driven Development

## 核心原则

对任何非琐碎的软件开发任务，先走 Spec-first 工作流。先明确要构建什么、不改变什么、如何验证、还有哪些不确定点，再开始修改代码。

保持务实推进：只追问那些会实质影响实现选择的信息。对于低风险的不确定点，在 Spec 中写明假设，然后继续推进。

## 工作流程

1. **Specify（明确需求）**：先把用户请求转换成具体、可验证的 Spec，再进入实现。
2. **Plan（制定计划）**：把 Spec 拆成有顺序、有依赖、可验证的工作单元。
3. **Implement（执行实现）**：基于已确认的 Spec 做小范围代码修改。如果现有代码与 Spec 冲突，先暂停并说明。
4. **Review（审查验收）**：用测试、静态检查或手工验证，对照验收标准确认行为。

当需要起草完整 Spec、检查 Spec 质量，或复用提示词和清单时，读取 `references/spec-templates.md`。

## Spec 结构

根据任务需要包含以下部分：

- **目标**：用一句话说明要解决的问题或用户价值。
- **范围**：明确哪些行为在范围内，哪些行为不在范围内。
- **角色与权限**：说明用户、角色、授权规则和隐私约束。
- **输入与输出**：参数、格式、校验规则、响应、错误码和状态变化。
- **行为描述**：用 Given-When-Then 描述成功路径、失败路径和边界场景。
- **数据与副作用**：存储字段、迁移、事务、幂等性、并发和外部调用。
- **验收标准**：说明完成后可以观察到什么结果，怎样证明任务完成。
- **测试要求**：列出单元测试、集成测试、回归测试、安全测试或手工检查。
- **待确认问题**：只保留会影响行为、数据、安全或兼容性的未决问题。

## Given-When-Then 写法

行为描述使用以下格式：

```text
Given [前置条件和相关状态]
When [用户动作、系统事件或 API 请求]
Then [可观察的预期结果]
And [重要副作用、错误、状态变化或约束]
```

至少覆盖一个成功路径，并根据风险补充必要的失败路径。优先关注边界值、重复提交、非法输入、权限、超时、第三方失败、并发和数据一致性。

## 任务拆分

按可验证的功能单元拆分任务，而不是按过细的机械改动拆分。

合适的任务单元通常满足：

- 聚焦在一个模块或一条业务链路内。
- 完成后可以通过测试或手工验收验证。
- 输入、输出、回滚或兼容性要求清楚。
- 依赖关系明确，例如先做数据结构，再做服务逻辑，再做 UI。

避免任务大到覆盖整个系统，也避免小到脱离业务上下文。

## 实现守则

编辑代码前，先查看与 Spec 相关的现有代码、测试、约定和数据契约。优先沿用项目已有模式和本地工具函数。

实现过程中：

- 只做 Spec 已确认范围内的修改。
- 不要静默扩大需求。
- 如果 Spec 与现有代码冲突，记录冲突，并选择最小可行路径或向用户确认。
- 除非 Spec 明确允许破坏性变更，否则保持兼容。
- 根据风险和行为影响范围添加或更新测试。

## Review 清单

像审查人工代码一样审查 AI 生成的代码：

- 核对核心行为和验收标准是否符合 Spec。
- 检查边界条件、非法输入、重复提交、并发和超时行为。
- 检查权限、注入风险、敏感信息泄露和隐私约束。
- 检查性能风险，例如 N+1 查询、重复计算、无界循环和不必要的外部调用。
- 检查是否符合现有架构、命名、错误处理、日志和测试风格。
- 移除不必要的依赖、过度抽象和猜测性代码。


