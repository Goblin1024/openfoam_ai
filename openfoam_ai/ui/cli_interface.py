"""
CLI Interface - 增强版命令行交互界面

支持多轮对话、记忆功能和操作确认
"""

import sys
import json
from typing import Optional, Dict, Any
from pathlib import Path

from ..agents.manager_agent import ManagerAgent
from ..memory.memory_manager import MemoryManager
from ..memory.session_manager import SessionManager


class CLIInterface:
    """
    增强版命令行交互界面
    
    支持多轮对话、记忆功能和操作确认机制
    """
    
    # 终端颜色代码
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m'
    }
    
    def __init__(self,
                 manager_agent: Optional[ManagerAgent] = None,
                 memory_manager: Optional[MemoryManager] = None,
                 session_manager: Optional[SessionManager] = None):
        """
        初始化CLI界面
        
        Args:
            manager_agent: 管理Agent
            memory_manager: 记忆管理器
            session_manager: 会话管理器
        """
        self.manager = manager_agent or ManagerAgent()
        self.memory = memory_manager
        self.session = session_manager or SessionManager()
        
        self.running = False
        
        print(self._colorize("=" * 60, 'cyan'))
        print(self._colorize("     🤖 OpenFOAM AI Agent - 阶段三：记忆性建模", 'bold'))
        print(self._colorize("=" * 60, 'cyan'))
        print(f"\n会话ID: {self.session.session_id}")
        print("输入 'help' 查看帮助，'exit' 退出\n")
    
    def _colorize(self, text: str, color: str) -> str:
        """添加颜色"""
        if sys.platform == 'win32':
            return text  # Windows需要额外处理，这里简化
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def _print_user(self, text: str):
        """打印用户消息"""
        print(f"\n{self._colorize('👤', 'blue')} {text}")
    
    def _print_assistant(self, text: str):
        """打印助手消息"""
        print(f"\n{self._colorize('🤖', 'green')} {text}")
    
    def _print_system(self, text: str):
        """打印系统消息"""
        print(f"\n{self._colorize('ℹ️', 'yellow')} {text}")
    
    def _print_error(self, text: str):
        """打印错误消息"""
        print(f"\n{self._colorize('❌', 'red')} {text}")
    
    def _print_success(self, text: str):
        """打印成功消息"""
        print(f"\n{self._colorize('✅', 'green')} {text}")
    
    def _print_warning(self, text: str):
        """打印警告消息"""
        print(f"\n{self._colorize('⚠️', 'yellow')} {text}")
    
    def run(self) -> None:
        """运行交互循环"""
        self.running = True
        
        # 检查记忆功能
        if self.memory:
            stats = self.memory.get_statistics()
            if stats['total_memories'] > 0:
                self._print_system(f"记忆库中有 {stats['total_memories']} 条历史配置")
        
        while self.running:
            try:
                # 检查是否有待确认操作
                pending = self.session.get_pending_operations()
                if pending:
                    self._handle_pending_operations(pending[0])
                    continue
                
                # 获取用户输入
                user_input = input(f"\n{self._colorize('>', 'cyan')} ").strip()
                
                if not user_input:
                    continue
                
                # 添加到会话
                self.session.add_message("user", user_input)
                
                # 处理命令
                if user_input.lower() in ['exit', 'quit', '退出']:
                    self._exit()
                elif user_input.lower() in ['help', '帮助', '?']:
                    self._show_help()
                elif user_input.lower() == 'status':
                    self._show_status()
                elif user_input.lower().startswith('search '):
                    self._search_memory(user_input[7:])
                elif user_input.lower() == 'history':
                    self._show_history()
                elif user_input.lower() == 'stats':
                    self._show_stats()
                else:
                    self._process_input(user_input)
                
            except KeyboardInterrupt:
                print("\n")
                self._exit()
            except Exception as e:
                self._print_error(f"发生错误: {e}")
    
    def _process_input(self, user_input: str) -> None:
        """处理用户输入"""
        # 先进行相似性检索
        if self.memory:
            similar = self.memory.search_similar(user_input, n_results=2)
            if similar and len(similar) > 0:
                # 提示用户有相似历史
                top_match = similar[0]
                if self._is_similar_enough(user_input, top_match.user_prompt):
                    self._print_system(f"找到相似历史配置: {top_match.case_name}")
        
        # 处理输入
        response = self.manager.process_input(user_input)
        
        response_type = response.get("type", "unknown")
        message = response.get("message", "未知响应")
        
        # 添加到会话
        self.session.add_message("assistant", message, 
                                metadata={"type": response_type})
        
        if response_type == "plan":
            self._print_assistant(message)
            
            # 显示配置摘要
            config_summary = response.get("config_summary", "")
            if config_summary:
                print(f"\n{config_summary}")
            
            # 存储到记忆
            if self.memory and self.manager.current_config:
                self.memory.store_memory(
                    case_name=self.manager.current_case or "unnamed",
                    user_prompt=user_input,
                    config=self.manager.current_config
                )
            
            # 显示执行计划
            plan = response.get("plan", {})
            steps = plan.get("steps", [])
            if steps:
                print("\n执行计划:")
                for step in steps:
                    print(f"  {step['step']}. {step['action']}")
            
            # 创建待确认操作
            op = self.session.create_pending_operation(
                operation_type="create_case",
                description=f"创建算例: {self.manager.current_case}",
                details={
                    "case_name": self.manager.current_case,
                    "estimated_time": plan.get("estimated_time", "unknown")
                }
            )
            
            # 生成确认提示
            confirm_prompt = self.session.generate_confirmation_prompt(op)
            self._print_assistant(confirm_prompt)
        
        elif response_type == "status":
            self._print_assistant(message)
        
        elif response_type == "error":
            self._print_error(message)
        
        else:
            self._print_assistant(message)
    
    def _is_similar_enough(self, query: str, history: str, threshold: float = 0.7) -> bool:
        """简单判断查询是否和历史相似"""
        # 简化版本：检查关键词重叠
        query_words = set(query.lower().split())
        history_words = set(history.lower().split())
        
        if not query_words:
            return False
        
        overlap = len(query_words & history_words)
        similarity = overlap / len(query_words)
        
        return similarity > threshold
    
    def _handle_pending_operations(self, operation) -> None:
        """处理待确认操作"""
        prompt = self._colorize("等待确认 (Y/N): ", 'yellow')
        user_input = input(f"\n{prompt}").strip()
        
        user_input_lower = user_input.lower()
        
        if user_input_lower in ['y', 'yes', '是', '确认']:
            self.session.confirm_operation(operation.operation_id)
            
            # 执行操作
            self._print_system("正在执行...")
            result = self.manager.execute_plan(
                operation.operation_type,
                confirmed=True
            )
            
            if result.success:
                self._print_success(result.message)
                if result.logs:
                    print("\n执行日志:")
                    for log in result.logs[:10]:
                        print(f"  • {log}")
            else:
                self._print_error(result.message)
        
        elif user_input_lower in ['n', 'no', '否', '取消']:
            self.session.reject_operation(operation.operation_id)
            self._print_warning("操作已取消")
        else:
            self._print_error("请输入 Y 确认或 N 取消")
    
    def _show_help(self) -> None:
        """显示帮助信息"""
        help_text = """
可用命令:
  create <描述>   - 创建新算例（例如: create 二维方腔驱动流）
  run            - 运行当前算例
  status         - 查看当前状态
  history        - 显示对话历史
  search <关键词> - 搜索历史配置
  stats          - 显示统计信息
  help           - 显示此帮助
  exit           - 退出程序

自然语言指令示例:
  "建立一个二维方腔驱动流，顶部速度1m/s"
  "在上一次的基础上，将网格加密到40x40"
  "查看当前算例状态"
        """
        print(help_text)
    
    def _show_status(self) -> None:
        """显示当前状态"""
        summary = self.session.get_context_summary()
        
        print(f"\n{'='*40}")
        print("当前状态")
        print(f"{'='*40}")
        print(f"会话ID: {summary['session_id']}")
        print(f"当前算例: {summary['current_case'] or '无'}")
        print(f"对话阶段: {summary['conversation_stage']}")
        print(f"最后意图: {summary['last_intent'] or '无'}")
        print(f"待确认操作: {summary['pending_operations_count']}")
        print(f"总消息数: {summary['total_messages']}")
        print(f"{'='*40}")
    
    def _search_memory(self, query: str) -> None:
        """搜索记忆"""
        if not self.memory:
            self._print_error("记忆功能未启用")
            return
        
        if not query.strip():
            self._print_error("请输入搜索关键词")
            return
        
        results = self.memory.search_similar(query, n_results=3)
        
        if not results:
            self._print_system("未找到相似的历史配置")
            return
        
        print(f"\n{'='*40}")
        print(f"检索结果 (关键词: {query})")
        print(f"{'='*40}")
        
        for i, entry in enumerate(results, 1):
            print(f"\n{i}. {entry.case_name}")
            print(f"   描述: {entry.user_prompt}")
            print(f"   时间: {entry.timestamp}")
            if entry.tags:
                print(f"   标签: {', '.join(entry.tags)}")
    
    def _show_history(self) -> None:
        """显示对话历史"""
        history = self.session.get_conversation_history()
        
        if not history:
            self._print_system("暂无对话历史")
            return
        
        print(f"\n{'='*40}")
        print("对话历史")
        print(f"{'='*40}")
        
        for msg in history:
            role = msg['role']
            content = msg['content']
            timestamp = msg.get('timestamp', '')
            
            if role == 'user':
                print(f"\n{self._colorize('👤', 'blue')} [{timestamp}] {content}")
            elif role == 'assistant':
                print(f"{self._colorize('🤖', 'green')} {content[:100]}...")
    
    def _show_stats(self) -> None:
        """显示统计信息"""
        print(f"\n{'='*40}")
        print("统计信息")
        print(f"{'='*40}")
        
        # 会话统计
        stats = self.session.get_statistics()
        print(f"\n会话统计:")
        print(f"  总消息数: {stats['total_messages']}")
        print(f"  用户消息: {stats['user_messages']}")
        print(f"  助手消息: {stats['assistant_messages']}")
        print(f"  当前算例: {stats['current_case'] or '无'}")
        print(f"  对话阶段: {stats['conversation_stage']}")
        
        # 记忆统计
        if self.memory:
            mem_stats = self.memory.get_statistics()
            print(f"\n记忆库统计:")
            print(f"  总记忆数: {mem_stats['total_memories']}")
            print(f"  唯一算例: {mem_stats['unique_cases']}")
            print(f"  算例列表: {', '.join(mem_stats['case_names'])}")
            print(f"  存储模式: {mem_stats['storage_mode']}")
        
        print(f"\n{'='*40}")
    
    def _exit(self) -> None:
        """退出程序"""
        # 保存会话
        self.session.save()
        
        # 导出记忆
        if self.memory:
            try:
                export_file = self.memory.export_memory()
                self._print_system(f"记忆已导出到: {export_file}")
            except:
                pass
        
        self._print_system("感谢使用，再见！")
        self.running = False


def run_cli(manager_agent: Optional[ManagerAgent] = None,
            memory_manager: Optional[MemoryManager] = None,
            session_manager: Optional[SessionManager] = None) -> None:
    """
    运行CLI界面
    
    Args:
        manager_agent: 管理Agent
        memory_manager: 记忆管理器
        session_manager: 会话管理器
    """
    cli = CLIInterface(
        manager_agent=manager_agent,
        memory_manager=memory_manager,
        session_manager=session_manager
    )
    cli.run()


if __name__ == "__main__":
    run_cli()
