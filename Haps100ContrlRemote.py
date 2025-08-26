import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import json
import threading
import time
from queue import Queue
import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException

class ScrollableFrame(ttk.Frame):
    """可滚动框架组件 - 彻底修复滚动条不显示问题"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # 创建画布和滚动条
        self.canvas = tk.Canvas(self, highlightthickness=0)
        
        # 垂直滚动条
        self.vscrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscrollbar.set)
        
        # 内容框架
        self.content_frame = ttk.Frame(self.canvas)
        
        # 绑定内容框架大小变化事件
        self.content_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # 创建窗口
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        # 绑定画布大小变化事件
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_frame, width=e.width)
        )
        
        # 绑定鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # 布局
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscrollbar.pack(side="right", fill="y")
        
        # 强制更新布局
        self.update_idletasks()

    def _on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def force_update(self):
        """强制更新滚动区域"""
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

class SSHConfigPanel(ttk.Frame):
    """SSH配置面板"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent
        
        # 创建主框架
        self.main_frame = ScrollableFrame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame = self.main_frame.content_frame
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame.columnconfigure(1, weight=1)
        
        # 创建控件
        self.create_widgets()
        
        # 加载配置
        self.load_config()
        
        # 绑定连接状态更新事件
        self.app.root.bind("<<SSHStatusChanged>>", self.update_ssh_status)
        
    def create_widgets(self):
        """创建SSH配置界面控件"""
        # SSH配置控件
        ttk.Label(self.content_frame, text="IP地址:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_host_var = tk.StringVar()
        ttk.Entry(self.content_frame, textvariable=self.ssh_host_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=8)
        
        ttk.Label(self.content_frame, text="端口:").grid(row=1, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_port_var = tk.IntVar(value=22)
        ttk.Entry(self.content_frame, textvariable=self.ssh_port_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=8, pady=8)
        
        ttk.Label(self.content_frame, text="用户名:").grid(row=2, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_user_var = tk.StringVar()
        ttk.Entry(self.content_frame, textvariable=self.ssh_user_var).grid(row=2, column=1, sticky=tk.EW, padx=8, pady=8)
        
        ttk.Label(self.content_frame, text="密码:").grid(row=3, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_password_var = tk.StringVar()
        pwd_entry = ttk.Entry(self.content_frame, textvariable=self.ssh_password_var, show="*")
        pwd_entry.grid(row=3, column=1, sticky=tk.EW, padx=8, pady=8)
        
        # 连接状态
        status_frame = ttk.Frame(self.content_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        self.ssh_status_var = tk.StringVar(value="未连接")
        self.ssh_status_label = ttk.Label(status_frame, textvariable=self.ssh_status_var, foreground="red")
        self.ssh_status_label.pack(side=tk.LEFT, padx=5)
        
        # 按钮区
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        self.ssh_btn = ttk.Button(btn_frame, text="连接", command=self.toggle_ssh_connection)
        self.ssh_btn.pack(side=tk.LEFT, padx=8)
        
        save_btn = ttk.Button(btn_frame, text="保存配置", command=self.save_config)
        save_btn.pack(side=tk.RIGHT, padx=8)
        
    def load_config(self):
        """加载SSH配置"""
        self.ssh_host_var.set(self.app.config["ssh_host"])
        self.ssh_port_var.set(self.app.config["ssh_port"])
        self.ssh_user_var.set(self.app.config["ssh_user"])
        self.ssh_password_var.set(self.app.config["ssh_password"])
        self.update_ssh_status(None)
        
    def save_config(self):
        """保存SSH配置"""
        self.app.config["ssh_host"] = self.ssh_host_var.get().strip()
        self.app.config["ssh_port"] = self.ssh_port_var.get() or 22
        self.app.config["ssh_user"] = self.ssh_user_var.get().strip()
        self.app.config["ssh_password"] = self.ssh_password_var.get().strip()
        self.app.save_config()
        messagebox.showinfo("成功", "SSH配置已保存")
        
    def toggle_ssh_connection(self):
        """切换SSH连接状态"""
        if self.app.ssh_connected:
            self.app.disconnect_ssh()
        else:
            # 更新配置后再连接
            self.save_config()
            threading.Thread(target=self.app.connect_ssh, daemon=True).start()
            
    def update_ssh_status(self, event):
        """更新SSH连接状态显示"""
        if self.app.ssh_connected:
            self.ssh_status_var.set("已连接")
            self.ssh_status_label.configure(foreground="green")
            self.ssh_btn.configure(text="断开")
        else:
            self.ssh_status_var.set("未连接")
            self.ssh_status_label.configure(foreground="red")
            self.ssh_btn.configure(text="连接")

class AutomationPanel(ttk.Frame):
    """自动化操作面板 - 彻底修复滚动条问题"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent
        
        # 创建可滚动框架
        self.scrollable_frame = ScrollableFrame(self)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame = self.scrollable_frame.content_frame
        
        # 创建内部容器，确保内容足够长以触发滚动条
        self.inner_frame = ttk.Frame(self.content_frame)
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.inner_frame.columnconfigure(1, weight=1)
        
        # 创建控件
        self.create_widgets()
        
        # 加载配置
        self.load_config()
        
        # 绑定状态更新事件
        self.app.root.bind("<<ExecutionStatusChanged>>", self.update_exec_status)
        
        # 强制更新滚动区域
        self.scrollable_frame.force_update()
        
    def create_widgets(self):
        """创建自动化操作界面控件"""
        row = 0
        
        # 基础路径配置
        ttk.Label(self.inner_frame, text="远程基础路径:").grid(row=row, column=0, sticky=tk.W, padx=8, pady=8)
        self.base_dir_var = tk.StringVar()
        self.base_dir_entry = ttk.Entry(self.inner_frame, textvariable=self.base_dir_var)
        self.base_dir_entry.grid(row=row, column=1, sticky=tk.EW, padx=8, pady=8)
        row += 1
        
        # 执行状态显示
        status_frame = ttk.Frame(self.inner_frame)
        status_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        ttk.Label(status_frame, text="执行状态:").pack(side=tk.LEFT, padx=5)
        self.exec_status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(status_frame, textvariable=self.exec_status_var, foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        clear_queue_btn = ttk.Button(status_frame, text="清空队列", command=self.app.clear_command_queue)
        clear_queue_btn.pack(side=tk.RIGHT, padx=5)
        row += 1
        
        # 操作按钮区
        btn_frame = ttk.LabelFrame(self.inner_frame, text="HAPS操作", padding="10")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        row += 1
        
        # Load按钮组
        load_frame = ttk.Frame(btn_frame)
        load_frame.pack(fill=tk.X, pady=8)
        ttk.Label(load_frame, text="Load操作:").pack(side=tk.LEFT, padx=8)
        ttk.Button(load_frame, text="Load All", command=lambda: self.app.queue_command("load_all")).pack(side=tk.LEFT, padx=8)
        ttk.Button(load_frame, text="Load Master", command=lambda: self.app.queue_command("load_master")).pack(side=tk.LEFT, padx=8)
        ttk.Button(load_frame, text="Load Slave", command=lambda: self.app.queue_command("load_slave")).pack(side=tk.LEFT, padx=8)
        
        # Reset按钮组
        reset_frame = ttk.Frame(btn_frame)
        reset_frame.pack(fill=tk.X, pady=8)
        ttk.Label(reset_frame, text="Reset操作:").pack(side=tk.LEFT, padx=8)
        ttk.Button(reset_frame, text="Reset HAPS", command=lambda: self.app.queue_command("reset_all")).pack(side=tk.LEFT, padx=8)
        ttk.Button(reset_frame, text="Reset Master", command=lambda: self.app.queue_command("reset_master")).pack(side=tk.LEFT, padx=8)
        ttk.Button(reset_frame, text="Reset Slave", command=lambda: self.app.queue_command("reset_slave")).pack(side=tk.LEFT, padx=8)
        
        # 路径配置区
        config_frame = ttk.LabelFrame(self.inner_frame, text="远程文件配置", padding="10")
        config_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        config_frame.columnconfigure(1, weight=1)
        row += 1
        
        config_row = 0
        # haps100control路径
        ttk.Label(config_frame, text="haps100control路径:").grid(row=config_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.haps_control_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.haps_control_var).grid(row=config_row, column=1, sticky=tk.EW, padx=8, pady=8)
        config_row += 1
        
        # xactorscmd路径
        ttk.Label(config_frame, text="xactorscmd路径:").grid(row=config_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.xactorscmd_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.xactorscmd_var).grid(row=config_row, column=1, sticky=tk.EW, padx=8, pady=8)
        config_row += 1
        
        # TCL路径配置
        self.tcl_vars = {}
        tcl_configs = [
            ("Load All TCL:", "load_all_tcl"),
            ("Load Master TCL:", "load_master_tcl"),
            ("Load Slave TCL:", "load_slave_tcl"),
            ("Reset All TCL:", "reset_all_tcl"),
            ("Reset Master TCL:", "reset_master_tcl"),
            ("Reset Slave TCL:", "reset_slave_tcl")
        ]
        for label_text, key in tcl_configs:
            self.tcl_vars[key] = tk.StringVar()
            ttk.Label(config_frame, text=label_text).grid(row=config_row, column=0, sticky=tk.W, padx=8, pady=8)
            ttk.Entry(config_frame, textvariable=self.tcl_vars[key]).grid(row=config_row, column=1, sticky=tk.EW, padx=8, pady=8)
            config_row += 1
        
        # 保存配置按钮
        save_btn = ttk.Button(config_frame, text="保存配置", command=self.save_config)
        save_btn.grid(row=config_row, column=0, columnspan=2, pady=12)
        config_row += 1
        
        # 添加额外空白区域确保滚动条能显示
        for i in range(5):  # 添加5行空白，确保内容足够长
            ttk.Label(self.inner_frame, text="").grid(row=row, column=0, pady=10)
            row += 1
        
        # 强制更新滚动区域
        self.scrollable_frame.force_update()
        
    def load_config(self):
        """加载自动化操作配置"""
        self.base_dir_var.set(self.app.config["base_dir"])
        self.haps_control_var.set(self.app.config["haps_control_path"])
        self.xactorscmd_var.set(self.app.config["xactorscmd_path"])
        
        for key, var in self.tcl_vars.items():
            if key in self.app.config:
                var.set(self.app.config[key])
                
        self.update_exec_status(None)
        
    def save_config(self):
        """保存自动化操作配置"""
        self.app.config["base_dir"] = self.base_dir_var.get().strip()
        self.app.config["haps_control_path"] = self.haps_control_var.get().strip()
        self.app.config["xactorscmd_path"] = self.xactorscmd_var.get().strip()
        
        for key, var in self.tcl_vars.items():
            self.app.config[key] = var.get().strip()
            
        self.app.save_config()
        messagebox.showinfo("成功", "自动化配置已保存")
        
    def update_exec_status(self, event):
        """更新执行状态显示"""
        queue_size = self.app.command_queue.qsize()
        
        if self.app.is_processing:
            self.exec_status_var.set(f"执行中 - 剩余：{queue_size}")
            self.status_label.configure(foreground="orange")
        elif queue_size > 0:
            self.exec_status_var.set(f"就绪 - 等待：{queue_size}")
            self.status_label.configure(foreground="blue")
        else:
            self.exec_status_var.set("就绪")
            self.status_label.configure(foreground="green")

class CustomCommandsPanel(ttk.Frame):
    """自定义命令面板"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent
        self.cmd_entries = []
        
        # 创建可滚动框架
        self.main_frame = ScrollableFrame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame = self.main_frame.content_frame
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建控件
        self.create_widgets()
        
        # 加载命令
        self.create_command_entries()
        
    def create_widgets(self):
        """创建自定义命令界面控件"""
        # 命令框容器
        self.cmds_frame = ttk.LabelFrame(self.content_frame, text="自定义远程命令", padding="10")
        self.cmds_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 12))
        self.cmds_frame.columnconfigure(0, weight=1)
        
        # 参数提示
        tip_frame = ttk.Frame(self.content_frame)
        tip_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(tip_frame, text="提示：命令将加入队列执行，支持参数 $HAPS_DEVICE $HAPS_SERIAL", foreground="blue").pack(anchor=tk.W)
        
        # 操作按钮区
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(btn_frame, text="添加命令框", command=self.add_command_entry).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="删除最后一个", command=self.remove_command_entry).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="保存命令", command=self.save_custom_commands).pack(side=tk.LEFT, padx=8)
        
    def create_command_entries(self):
        """创建自定义命令输入框"""
        # 清空现有框体
        for widget in self.cmds_frame.winfo_children():
            widget.destroy()
        self.cmd_entries.clear()
        
        # 从配置加载命令
        custom_cmds = self.app.config.get("custom_commands", [""])
        for cmd in custom_cmds:
            self.add_command_entry(default_text=cmd, update_config=False)
        
        # 确保至少有一个空框体
        if not self.cmd_entries:
            self.add_command_entry(update_config=False)
            
        self.update_layout()

    def add_command_entry(self, default_text="", update_config=True):
        """添加命令输入框"""
        # 命令行框架
        cmd_frame = ttk.Frame(self.cmds_frame, height=35)
        cmd_frame.pack(fill=tk.X, pady=5)
        cmd_frame.pack_propagate(False)
        
        # 命令输入框
        cmd_var = tk.StringVar(value=default_text)
        cmd_entry = ttk.Entry(cmd_frame, textvariable=cmd_var)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 执行按钮
        exec_btn = ttk.Button(
            cmd_frame, 
            text="执行", 
            width=6,
            command=lambda v=cmd_var: self.app.queue_custom_command(v.get())
        )
        exec_btn.pack(side=tk.LEFT, padx=5)
        
        # 记录命令框
        self.cmd_entries.append((cmd_frame, cmd_var, exec_btn))
        
        # 更新配置
        if update_config:
            self.app.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
            self.update_layout()

    def remove_command_entry(self):
        """删除最后一个命令框"""
        if len(self.cmd_entries) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个命令输入框")
            return
        
        cmd_frame, cmd_var, exec_btn = self.cmd_entries.pop()
        cmd_frame.destroy()
        self.app.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
        self.update_layout()

    def save_custom_commands(self):
        """保存自定义命令"""
        self.app.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
        self.app.save_config()
        messagebox.showinfo("保存成功", "自定义命令已保存")
        
    def update_layout(self):
        """更新布局"""
        self.cmds_frame.update_idletasks()
        self.main_frame.force_update()

class HAPSAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPS远程自动化控制中心")
        self.root.geometry("1200x600")
        self.root.minsize(1000, 500)
        
        # 先初始化日志相关属性
        self._log_update_timer = None
        self._pending_logs = []
        self._log_updating = False
        self._freeze_ui = False
        
        # 配置相关初始化
        self.config_file = "haps_config.json"
        self.default_haps_control = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\haps100control.bat"
        self.default_xactorscmd = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\xactorscmd.bat"
        
        self.config = {
            "ssh_host": "192.168.1.1",
            "ssh_port": 22,
            "ssh_user": "admin",
            "ssh_password": "",
            "base_dir": "D:\\zxl_haps12\\mc8860\\mc20l\\mc20l_haps100_va_v2024",
            "haps_control_path": self.default_haps_control,
            "xactorscmd_path": self.default_xactorscmd,
            "load_all_tcl": "tcl\\load_all.tcl",
            "load_master_tcl": "tcl\\load_master.tcl",
            "load_slave_tcl": "tcl\\load_slave.tcl",
            "reset_all_tcl": "tcl\\reset_all.tcl",
            "reset_master_tcl": "tcl\\reset_master.tcl",
            "reset_slave_tcl": "tcl\\reset_slave.tcl",
            "custom_commands": [""]
        }
        
        # 加载配置
        self.load_config()
        
        # SSH连接状态
        self.ssh_client = None
        self.ssh_connected = False
        
        # 命令队列和执行状态
        self.command_queue = Queue()
        self.is_processing = False
        
        # 主窗口布局 - 修复日志框面积过大问题
        # 调整比例为5:1，操作区更大，日志区更小
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=5)  # 操作区占5/6
        self.root.grid_columnconfigure(1, weight=1)  # 日志区占1/6
        
        # 左侧操作区
        self.operation_frame = ttk.Frame(root)
        self.operation_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)
        
        # 标签页控件
        self.notebook = ttk.Notebook(self.operation_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建三个功能面板
        self.ssh_panel = SSHConfigPanel(self.notebook, self)
        self.automation_panel = AutomationPanel(self.notebook, self)
        self.custom_commands_panel = CustomCommandsPanel(self.notebook, self)
        
        # 添加到标签页
        self.notebook.add(self.ssh_panel, text="SSH配置")
        self.notebook.add(self.automation_panel, text="自动化操作")
        self.notebook.add(self.custom_commands_panel, text="自定义命令")
        
        # 右侧日志区
        self.log_frame = ttk.LabelFrame(root, text="执行日志", padding="12")
        self.log_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        # 日志控制按钮区
        log_ctrl_frame = ttk.Frame(self.log_frame, height=30)
        log_ctrl_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        log_ctrl_frame.grid_propagate(False)
        
        clear_log_btn = ttk.Button(log_ctrl_frame, text="清空日志", command=self.clear_log)
        clear_log_btn.pack(side=tk.RIGHT, padx=5)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 9),
            state=tk.DISABLED,
            padx=8,
            pady=8
        )
        self.log_text.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 5))
        
        # 底部状态栏
        self.status_bar = ttk.Label(root, text="SSH未连接", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 5))
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # SSH连接逻辑
    def connect_ssh(self):
        try:
            host = self.config["ssh_host"]
            port = self.config["ssh_port"]
            user = self.config["ssh_user"]
            pwd = self.config["ssh_password"]
            
            if not host or not user:
                self.sync_log("SSH连接失败：IP地址和用户名不能为空")
                messagebox.showerror("参数错误", "IP地址和用户名不能为空")
                return
            
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.sync_log(f"正在连接SSH：{host}:{port}")
            
            self.ssh_client.connect(
                hostname=host,
                port=port,
                username=user,
                password=pwd,
                timeout=15,
                allow_agent=False,
                look_for_keys=False
            )
            
            # 验证连接
            stdin, stdout, stderr = self.ssh_client.exec_command("echo HAPS_CONNECTED", timeout=5)
            output_bytes = stdout.read()
            error_bytes = stderr.read()
            
            output = self.process_data(output_bytes)
            error = self.process_data(error_bytes)
            
            if error:
                self.sync_log(f"连接验证错误: {error}")
                
            if "HAPS_CONNECTED" in output or "484150535f434f4e4e4543544544" in output:
                self.ssh_connected = True
                self.status_bar.config(text=f"SSH已连接: {host}")
                self.sync_log(f"SSH连接成功：{host}:{port}")
                self.check_remote_paths()
            else:
                raise Exception(f"连接验证失败，响应：{output}")
                
        except AuthenticationException:
            self.sync_log("SSH认证失败：用户名或密码错误")
            messagebox.showerror("认证失败", "用户名或密码错误")
        except SSHException as e:
            self.sync_log(f"SSH协议错误：{str(e)}")
            messagebox.showerror("SSH错误", f"协议错误：{str(e)}")
        except Exception as e:
            self.sync_log(f"SSH连接失败：{str(e)}")
            messagebox.showerror("连接失败", f"无法连接：{str(e)}")
        finally:
            if not self.ssh_connected:
                self.ssh_client = None
                
            self.root.event_generate("<<SSHStatusChanged>>", when="tail")

    def disconnect_ssh(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.sync_log("SSH连接已断开")
            except Exception as e:
                self.sync_log(f"断开SSH时出错：{str(e)}")
        
        self.ssh_connected = False
        self.status_bar.config(text="SSH未连接")
        self.ssh_client = None
        self.root.event_generate("<<SSHStatusChanged>>", when="tail")

    def check_remote_paths(self):
        """检查远程关键路径"""
        paths = [
            (self.config["haps_control_path"], "haps100control.bat"),
            (self.config["xactorscmd_path"], "xactorscmd.bat"),
            (self.config["base_dir"], "基础目录"),
            (os.path.join(self.config["base_dir"], "system", "targetsystem.tsd"), "targetsystem.tsd")
        ]
        
        for path, desc in paths:
            if not path:
                continue
            path = path.replace("/", "\\")
            cmd = f'if exist "{path}" (echo EXIST) else (echo NOT_EXIST)'
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=5)
                output_bytes = stdout.read()
                error_bytes = stderr.read()
                
                output = self.process_data(output_bytes)
                error = self.process_data(error_bytes)
                
                if error:
                    self.sync_log(f"[{desc}] 检查错误：{error}")
                elif output == "EXIST" or "4558495354" in output:
                    self.sync_log(f"[{desc}] 路径存在：{path}")
                else:
                    self.sync_log(f"[{desc}] 路径不存在：{path}")
                    messagebox.showwarning("路径警告", f"[{desc}] 远程路径不存在：{path}")
            except Exception as e:
                self.sync_log(f"[{desc}] 检查失败：{str(e)}")

    # 命令执行逻辑 - 彻底修复编码错误
    def queue_command(self, cmd_type):
        """将命令加入队列"""
        if not self.ssh_connected:
            messagebox.showerror("未连接", "请先建立SSH连接")
            return
        
        self.command_queue.put(('preset', cmd_type))
        self.sync_log(f"命令[{cmd_type}]加入队列，当前队列：{self.command_queue.qsize()}")
        
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        self.update_exec_status()

    def queue_custom_command(self, cmd_text):
        """自定义命令加入队列"""
        if not self.ssh_connected:
            messagebox.showerror("未连接", "请先建立SSH连接")
            return
        
        cmd_text = cmd_text.strip()
        if not cmd_text:
            messagebox.showwarning("命令为空", "请输入有效的命令")
            return
        
        self.command_queue.put(('custom', cmd_text))
        self.sync_log(f"开始执行自定义命令：{cmd_text}")
        
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        self.update_exec_status()

    def process_command_queue(self):
        """处理命令队列"""
        self.is_processing = True
        self.update_exec_status()
        
        try:
            while not self.command_queue.empty():
                cmd_type, cmd_content = self.command_queue.get()
                try:
                    if cmd_type == 'preset':
                        self.sync_log(f"开始执行预设命令：{cmd_content}")
                        self.run_haps_command(cmd_content)
                    elif cmd_type == 'custom':
                        self.run_remote_command(cmd_content)
                except Exception as e:
                    self.sync_log(f"命令执行异常：{str(e)}")
                finally:
                    self.command_queue.task_done()
                    self.update_exec_status()
        finally:
            self.is_processing = False
            self.update_exec_status()
            self.sync_log("队列所有命令执行完毕")

    def run_haps_command(self, cmd_type):
        """执行HAPS命令"""
        try:
            haps_ctrl = self.config["haps_control_path"]
            xactorscmd = self.config["xactorscmd_path"]
            base_dir = self.config["base_dir"]
            
            if not haps_ctrl or not xactorscmd:
                raise ValueError("haps100control和xactorscmd路径不能为空")
            
            tcl_map = {
                "load_all": self.config["load_all_tcl"],
                "load_master": self.config["load_master_tcl"],
                "load_slave": self.config["load_slave_tcl"],
                "reset_all": self.config["reset_all_tcl"],
                "reset_master": self.config["reset_master_tcl"],
                "reset_slave": self.config["reset_slave_tcl"]
            }
            tcl_script = tcl_map[cmd_type]
            
            if tcl_script and not tcl_script.startswith(('C:', 'D:', '\\', '/')) and base_dir:
                tcl_script = f"{base_dir}\\{tcl_script}"
            
            if not tcl_script:
                raise ValueError(f"未配置{cmd_type}的TCL脚本路径")
            
            cmd = f'cd /d "{base_dir}" && call "{haps_ctrl}" "{xactorscmd}" "{tcl_script}"'
            self.sync_log(f"构建HAPS命令：{cmd}")
            
            success, msg = self.run_remote_command(cmd)[:2]
            if success:
                self.sync_log(f"预设命令[{cmd_type}]执行成功：{msg}")
            else:
                self.sync_log(f"预设命令[{cmd_type}]执行失败：{msg}")
                messagebox.showerror("执行失败", f"{cmd_type}命令失败：{msg}")
                
        except ValueError as e:
            self.sync_log(f"参数错误：{str(e)}")
            messagebox.showerror("参数错误", str(e))
        except Exception as e:
            self.sync_log(f"HAPS命令执行异常：{str(e)}")
            messagebox.showerror("执行异常", str(e))

    def run_remote_command(self, cmd):
        """执行远程命令（完全重构编码处理）"""
        try:
            # 执行命令时指定终端类型，避免某些服务器默认编码问题
            channel = self.ssh_client.get_transport().open_session()
            channel.set_combine_stderr(True)  # 合并stderr到stdout
            channel.exec_command(cmd)
            
            output = []
            error = []
            
            # 直接读取原始字节流，不进行解码
            def read_stream():
                while True:
                    data = channel.recv(1024)
                    if not data:
                        break
                    # 直接使用GBK解码，不尝试其他编码
                    try:
                        processed = data.decode('gbk', errors='replace')
                    except:
                        processed = data.decode('latin-1')
                    output.append(processed)
                    self.sync_log(f"输出：{processed.rstrip('\r\n')}")
            
            # 启动线程读取流
            read_thread = threading.Thread(target=read_stream, daemon=True)
            read_thread.start()
            read_thread.join()
            
            # 等待命令完成
            return_code = channel.recv_exit_status()
            full_output = "".join(output)
            
            if return_code == 0:
                return True, f"返回码0，输出：{full_output}", return_code, full_output
            else:
                return False, f"返回码{return_code}，错误：{full_output}", return_code, full_output
                
        except Exception as e:
            return False, str(e), -1, ""

    def process_data(self, data):
        """处理数据，强制使用GBK编码解决中文问题"""
        # 此方法现在主要用于其他地方的数据处理
        if isinstance(data, str):
            return data.rstrip('\r\n')
            
        if isinstance(data, bytes):
            # 强制使用GBK解码
            try:
                return data.decode('gbk', errors='replace').rstrip('\r\n')
            except:
                return data.decode('latin-1').rstrip('\r\n')
            
        return str(data)

    # 工具方法
    def sync_log(self, message):
        """同步更新日志"""
        if self._freeze_ui:
            return
            
        self._pending_logs.append(message)
        
        if not self._log_update_timer and not self._log_updating:
            self._log_update_timer = self.root.after(150, self._flush_logs)
    
    def _flush_logs(self):
        """批量刷新日志到UI"""
        self._log_updating = True
        
        try:
            if not self._pending_logs:
                return
                
            self.log_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            for message in self._pending_logs:
                self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            self._pending_logs = []
        finally:
            self._log_update_timer = None
            self._log_updating = False

    def clear_log(self):
        """清空日志"""
        self._freeze_ui = True
        
        try:
            if self._log_update_timer:
                self.root.after_cancel(self._log_update_timer)
                self._log_update_timer = None
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            self.log_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] 日志已清空\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            self._pending_logs = []
        finally:
            self._freeze_ui = False

    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)
                        for key in self.config:
                            if key in loaded_config:
                                self.config[key] = loaded_config[key]
                    
                    self.sync_log("配置文件加载成功")
                except Exception as e:
                    self.sync_log(f"加载配置失败：{str(e)}")
                    self.save_config()
            else:
                self.save_config()
                self.sync_log("配置文件不存在，已创建默认配置")
        finally:
            pass

    def save_config(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.sync_log("配置已保存")
        except Exception as e:
            error_msg = f"保存配置失败：{str(e)}"
            self.sync_log(error_msg)
            messagebox.showerror("保存失败", error_msg)

    def update_exec_status(self):
        """更新执行状态"""
        self.root.event_generate("<<ExecutionStatusChanged>>", when="tail")

    def clear_command_queue(self):
        """清空命令队列"""
        try:
            while not self.command_queue.empty():
                self.command_queue.get()
                self.command_queue.task_done()
            
            self.log_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] 命令队列已清空\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
            self.is_processing = False
            self.update_exec_status()
        finally:
            pass
            
    def on_close(self):
        """关闭主窗口时的处理"""
        if self.ssh_connected:
            self.disconnect_ssh()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HAPSAutomationGUI(root)
    root.mainloop()
