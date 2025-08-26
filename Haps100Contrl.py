import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import json
import subprocess
import threading
import time
import tempfile
import sys
from queue import Queue
from pathlib import Path

# 用于支持打包资源文件
def get_resource_path(relative_path):
    """获取资源文件的路径，支持开发环境和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹，并将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class HAPSAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPS自动化控制")
        self.root.geometry("1000x600")
        self.root.minsize(800, 500)  # 调整最小尺寸
        
        # 检查并获取默认TCL文件路径
        self.default_tcl_path = get_resource_path("haps_control_default.tcl")
        if not os.path.exists(self.default_tcl_path):
            self.log(f"警告: 未找到默认TCL文件 {self.default_tcl_path}")
        
        # 创建主框架，分为左右两部分
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧主内容区域
        self.left_frame = ttk.Frame(self.main_container)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 右侧日志区域
        self.right_frame = ttk.Frame(self.main_container)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 配置文件路径
        self.config_file = "haps_config.json"
        
        # 默认参数
        self.default_xactorscmd = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\xactorscmd.bat"
        self.default_tcl_script = "tcl\\reset.tcl"
        
        # 初始化配置
        self.config = {
            "base_dir": "", #os.getcwd(),
            "xactorscmd_path": self.default_xactorscmd,
            "load_all_tcl": "tcl\\load_all.tcl",
            "load_master_tcl": "tcl\\load_master.tcl",
            "load_slave_tcl": "tcl\\load_slave.tcl",
            "reset_all_tcl": "tcl\\reset_all.tcl",
            "reset_master_tcl": "tcl\\reset_master.tcl",
            "reset_slave_tcl": "tcl\\reset_slave.tcl",
            "custom_commands": [""]  # 默认至少有一个命令框
        }
        
        # 临时日志存储（在log_text创建前使用）
        self.temp_logs = []
        
        # 命令队列和执行状态 - 用于串行执行
        self.command_queue = Queue()  # 存储待执行的命令
        self.is_processing = False    # 是否正在处理命令队列
        
        # 创建界面元素变量
        self.create_variables()
        
        # 创建界面
        self.create_widgets()
        
        # 加载配置文件（现在log_text已经创建）
        self.load_config()
        # 明确加载自定义命令
        self.load_custom_commands()

    def create_variables(self):
        """提前创建所有需要的变量，避免属性访问错误"""
        self.base_dir_var = tk.StringVar(value=self.config["base_dir"])
        self.xactorscmd_var = tk.StringVar(value=self.config["xactorscmd_path"])
        self.load_all_tcl_var = tk.StringVar(value=self.config["load_all_tcl"])
        self.load_master_tcl_var = tk.StringVar(value=self.config["load_master_tcl"])
        self.load_slave_tcl_var = tk.StringVar(value=self.config["load_slave_tcl"])
        self.reset_all_tcl_var = tk.StringVar(value=self.config["reset_all_tcl"])
        self.reset_master_tcl_var = tk.StringVar(value=self.config["reset_master_tcl"])
        self.reset_slave_tcl_var = tk.StringVar(value=self.config["reset_slave_tcl"])

    def create_widgets(self):
        # 创建标签页控件（放在左侧框架内）
        self.tab_control = ttk.Notebook(self.left_frame)
        self.tab_control.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 界面一：自动化操作
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text="自动化操作")
        
        # 界面二：自定义命令
        self.tab2 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab2, text="自定义命令")
        
        # 初始化左侧内容界面
        self.init_tab1()
        self.init_tab2()
        
        # 初始化右侧日志区域
        self.init_log_area()
        
        # 显示临时日志
        self.flush_temp_logs()

    def init_tab1(self):
        # 使用网格布局的主框架，确保宽度自适应
        main_frame = ttk.Frame(self.tab1, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)  # 第二列可扩展
        
        # 顶部框架：目录选择（第0行）
        ttk.Label(main_frame, text="基础路径:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.base_dir_entry = ttk.Entry(main_frame, textvariable=self.base_dir_var)
        self.base_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        browse_btn = ttk.Button(main_frame, text="浏览...", command=self.browse_base_dir)
        browse_btn.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        
        # 操作按钮区域（第1行）
        btn_frame = ttk.LabelFrame(main_frame, text="操作", padding="10")
        btn_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)
        btn_frame.columnconfigure(0, weight=1)
        
        # 执行状态指示器
        self.status_var = tk.StringVar(value="就绪")
        status_frame = ttk.Frame(btn_frame)
        status_frame.pack(fill=tk.X, pady=5)
        ttk.Label(status_frame, text="执行状态:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # 清空队列按钮
        clear_queue_btn = ttk.Button(status_frame, text="清空队列", command=self.clear_command_queue)
        clear_queue_btn.pack(side=tk.RIGHT, padx=5)
        
        # Load按钮组
        load_frame = ttk.Frame(btn_frame)
        load_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(load_frame, text="Load操作:").pack(side=tk.LEFT, padx=5)
        
        self.load_all_btn = ttk.Button(load_frame, text="Load All", command=lambda: self.queue_command("load_all"))
        self.load_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_master_btn = ttk.Button(load_frame, text="Load Master", command=lambda: self.queue_command("load_master"))
        self.load_master_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_slave_btn = ttk.Button(load_frame, text="Load Slave", command=lambda: self.queue_command("load_slave"))
        self.load_slave_btn.pack(side=tk.LEFT, padx=5)
        
        # Reset按钮组
        reset_frame = ttk.Frame(btn_frame)
        reset_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(reset_frame, text="Reset操作:").pack(side=tk.LEFT, padx=5)
        
        self.reset_all_btn = ttk.Button(reset_frame, text="Reset HAPS", command=lambda: self.queue_command("reset_all"))
        self.reset_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_master_btn = ttk.Button(reset_frame, text="Reset Master", command=lambda: self.queue_command("reset_master"))
        self.reset_master_btn.pack(side=tk.LEFT, padx=5)
        
        self.reset_slave_btn = ttk.Button(reset_frame, text="Reset Slave", command=lambda: self.queue_command("reset_slave"))
        self.reset_slave_btn.pack(side=tk.LEFT, padx=5)
        
        # 配置区域（第2行）
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW, padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)  # 配置区域的第二列可扩展
        
        row = 0  # 配置区域内部的行计数器
        
        # xactorscmd路径配置
        ttk.Label(config_frame, text="xactorscmd路径:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.xactorscmd_entry = ttk.Entry(config_frame, textvariable=self.xactorscmd_var)
        self.xactorscmd_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        browse_xactors_btn = ttk.Button(config_frame, text="浏览...", 
                                      command=lambda: self.browse_file("xactorscmd_path", self.xactorscmd_var, ".bat"))
        browse_xactors_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Load All TCL配置
        ttk.Label(config_frame, text="Load All TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_all_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("load_all_tcl", self.load_all_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # 其他配置项保持不变...
        # Load Master TCL配置
        ttk.Label(config_frame, text="Load Master TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_master_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("load_master_tcl", self.load_master_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Load Slave TCL配置
        ttk.Label(config_frame, text="Load Slave TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_slave_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("load_slave_tcl", self.load_slave_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Reset All TCL配置
        ttk.Label(config_frame, text="Reset All TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_all_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("reset_all_tcl", self.reset_all_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Reset Master TCL配置
        ttk.Label(config_frame, text="Reset Master TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_master_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("reset_master_tcl", self.reset_master_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # Reset Slave TCL配置
        ttk.Label(config_frame, text="Reset Slave TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_slave_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        browse_btn = ttk.Button(config_frame, text="浏览...", 
                              command=lambda: self.browse_file("reset_slave_tcl", self.reset_slave_tcl_var, ".tcl"))
        browse_btn.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        
        # 保存配置按钮
        save_config_btn = ttk.Button(config_frame, text="保存配置", command=self.save_config)
        save_config_btn.grid(row=row, column=0, columnspan=3, pady=10)

    def init_tab2(self):
        """初始化自定义命令页面，将命令框放在最上方"""
        # 使用网格布局的主框架，确保宽度自适应
        main_frame = ttk.Frame(self.tab2, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        
        # 1. 命令框区域（最上方）
        self.commands_frame = ttk.LabelFrame(main_frame, text="自定义命令", padding="10")
        self.commands_frame.grid(row=0, column=0, sticky=tk.NSEW, pady=5)
        main_frame.rowconfigure(0, weight=1)  # 命令框区域可扩展
        self.commands_frame.columnconfigure(0, weight=1)
        
        # 命令框列表
        self.command_entries = []
        
        # 2. 可用参数提示（命令框下方）
        params_frame = ttk.Frame(main_frame)
        params_frame.grid(row=1, column=0, sticky=tk.EW, pady=5)
        
        ttk.Label(params_frame, text="可用参数为: $HAPS_DEVICE $HAPS_SERIAL $HAPS_HANDLE", 
                 foreground="blue").pack(anchor=tk.W)
        
        # 3. 按钮区域（最下方）
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, sticky=tk.EW, pady=5)
        
        add_btn = ttk.Button(btn_frame, text="添加命令框", command=self.add_command_entry)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        remove_btn = ttk.Button(btn_frame, text="删除最后一个", command=self.remove_command_entry)
        remove_btn.pack(side=tk.LEFT, padx=5)
        
        save_cmds_btn = ttk.Button(btn_frame, text="保存命令", command=self.save_custom_commands)
        save_cmds_btn.pack(side=tk.LEFT, padx=5)

    def init_log_area(self):
        """初始化右侧日志区域"""
        log_frame = ttk.LabelFrame(self.right_frame, text="日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 日志控制栏
        log_ctrl_frame = ttk.Frame(log_frame)
        log_ctrl_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 清空日志按钮
        clear_log_btn = ttk.Button(log_ctrl_frame, text="清空日志", command=self.clear_log)
        clear_log_btn.pack(side=tk.RIGHT, padx=5)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

    def load_custom_commands(self):
        """从配置中加载自定义命令，确保在页面初始化时调用"""
        # 清除现有命令框
        for widget in self.commands_frame.winfo_children():
            widget.destroy()
        self.command_entries = []
        
        # 从配置创建命令框
        for i, cmd in enumerate(self.config["custom_commands"]):
            self.add_command_entry(default_text=cmd, update_config=False)
        
        self.log(f"已加载 {len(self.command_entries)} 条自定义命令")

    def browse_file(self, config_key, var, file_extension):
        """浏览选择文件并更新变量"""
        # 确定初始目录
        initial_dir = self.base_dir_var.get()
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
            
        # 根据文件类型设置文件过滤器
        if file_extension == ".tcl":
            file_filter = f"TCL脚本文件 (*{file_extension})|*{file_extension}|所有文件 (*.*)|*.*"
            title = "选择TCL脚本文件"
        elif file_extension == ".bat":
            file_filter = f"批处理文件 (*{file_extension})|*{file_extension}|所有文件 (*.*)|*.*"
            title = "选择批处理文件"
        else:
            file_filter = f"所有文件 (*.*)|*.*"
            title = "选择文件"
            
        # 打开文件选择对话框
        file_path = filedialog.askopenfilename(
            title=title,
            initialdir=initial_dir,
            filetypes=[(file_filter.split("|")[0], file_filter.split("|")[1]),
                      (file_filter.split("|")[2], file_filter.split("|")[3])]
        )
        
        if file_path:
            # 检查是否是相对路径，如果是则转换为相对于基础目录的路径
            base_dir = self.base_dir_var.get()
            if base_dir and os.path.commonprefix([file_path, base_dir]) == base_dir:
                # 计算相对路径
                rel_path = os.path.relpath(file_path, base_dir)
                var.set(rel_path)
                self.config[config_key] = rel_path
                self.log(f"已选择{config_key}文件: {rel_path} (相对路径)")
            else:
                # 使用绝对路径
                var.set(file_path)
                self.config[config_key] = file_path
                self.log(f"已选择{config_key}文件: {file_path} (绝对路径)")

    def create_command_entries(self):
        # 从配置创建命令框
        for i, cmd in enumerate(self.config["custom_commands"]):
            self.add_command_entry(default_text=cmd, update_config=False)

    def add_command_entry(self, default_text="", update_config=True):
        # 获取新行索引
        new_row = len(self.command_entries)
        
        frame = ttk.Frame(self.commands_frame)
        frame.grid(row=new_row, column=0, sticky=tk.EW, pady=2)
        self.commands_frame.rowconfigure(new_row, weight=1)
        
        cmd_var = tk.StringVar(value=default_text)
        entry = ttk.Entry(frame, textvariable=cmd_var)
        entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        exec_btn = ttk.Button(frame, text="执行", 
                            command=lambda var=cmd_var: self.queue_custom_command(var.get()))
        exec_btn.pack(side=tk.LEFT, padx=5)
        
        self.command_entries.append((frame, cmd_var, new_row))
        
        if update_config:
            # 更新配置
            self.config["custom_commands"] = [var.get() for (frame, var, i) in self.command_entries]

    def remove_command_entry(self):
        if len(self.command_entries) > 1:  # 至少保留一个
            frame, var, row = self.command_entries.pop()
            frame.destroy()
            
            # 重新编号剩余的命令框行
            for i, (f, v, r) in enumerate(self.command_entries):
                if r > row:
                    f.grid(row=r-1, column=0, sticky=tk.EW, pady=2)
                    self.command_entries[i] = (f, v, r-1)
            
            # 更新配置
            self.config["custom_commands"] = [var.get() for (frame, var, i) in self.command_entries]

    def save_custom_commands(self):
        # 保存当前命令到配置
        self.config["custom_commands"] = [var.get() for (frame, var, i) in self.command_entries]
        self.save_config()
        messagebox.showinfo("提示", "命令已保存")

    def browse_base_dir(self):
        dir_path = filedialog.askdirectory(title="选择基础目录", initialdir=self.base_dir_var.get())
        if dir_path:
            self.base_dir_var.set(dir_path)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并配置，确保所有必要键存在
                    for key in self.config:
                        if key in loaded_config:
                            self.config[key] = loaded_config[key]
                
                # 更新变量值
                self.base_dir_var.set(self.config["base_dir"])
                self.xactorscmd_var.set(self.config["xactorscmd_path"])
                self.load_all_tcl_var.set(self.config["load_all_tcl"])
                self.load_master_tcl_var.set(self.config["load_master_tcl"])
                self.load_slave_tcl_var.set(self.config["load_slave_tcl"])
                self.reset_all_tcl_var.set(self.config["reset_all_tcl"])
                self.reset_master_tcl_var.set(self.config["reset_master_tcl"])
                self.reset_slave_tcl_var.set(self.config["reset_slave_tcl"])
                
                self.log("配置文件加载成功")
            except Exception as e:
                self.log(f"加载配置文件失败: {str(e)}")
                # 使用默认配置，并尝试创建新的配置文件
                self.save_config()
        else:
            # 配置文件不存在，创建新的
            self.save_config()
            self.log("配置文件不存在，已创建新的配置文件")

    def save_config(self):
        # 从界面更新配置
        self.config["base_dir"] = self.base_dir_var.get()
        self.config["xactorscmd_path"] = self.xactorscmd_var.get()
        self.config["load_all_tcl"] = self.load_all_tcl_var.get()
        self.config["load_master_tcl"] = self.load_master_tcl_var.get()
        self.config["load_slave_tcl"] = self.load_slave_tcl_var.get()
        self.config["reset_all_tcl"] = self.reset_all_tcl_var.get()
        self.config["reset_master_tcl"] = self.reset_master_tcl_var.get()
        self.config["reset_slave_tcl"] = self.reset_slave_tcl_var.get()
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.log("配置已保存")
        except Exception as e:
            error_msg = f"保存配置失败: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("错误", error_msg)

    def log(self, message):
        """在日志框中添加消息"""
        # 如果log_text尚未创建，先存储到临时日志
        if not hasattr(self, 'log_text'):
            self.temp_logs.append(message)
            return
            
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # 滚动到最后
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self):
        """清空日志框内容"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("日志已清空")
    
    def flush_temp_logs(self):
        """显示临时存储的日志"""
        if hasattr(self, 'log_text') and self.temp_logs:
            self.log_text.config(state=tk.NORMAL)
            for message in self.temp_logs:
                timestamp = time.strftime("%H:%M:%S")
                self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.temp_logs = []

    def run_haps_command(self, xactorscmd_path=None, tcl_script=None):
        """
        集成原haps100control.bat的功能
        执行HAPS命令，支持参数传递，未传参时使用默认值
        """
        # 设置默认值
        if xactorscmd_path is None or not xactorscmd_path.strip():
            xactorscmd_path = self.default_xactorscmd
            self.log(f"未指定xactorscmd路径，使用默认值: {xactorscmd_path}")
        
        if tcl_script is None or not tcl_script.strip():
            tcl_script = self.default_tcl_script
            self.log(f"未指定TCL脚本，使用默认值: {tcl_script}")
        
        # 处理路径（转为绝对路径）
        base_dir = self.base_dir_var.get()
        if base_dir and not os.path.isabs(tcl_script):
            tcl_script = os.path.join(base_dir, tcl_script)
        
        # 检查xactorscmd是否存在
        if not os.path.exists(xactorscmd_path):
            error_msg = f"错误：未找到xactorscmd.bat - {xactorscmd_path}"
            self.log(error_msg)
            return False, error_msg, -1
        
        # 检查TCL脚本是否存在
        if not os.path.exists(tcl_script):
            error_msg = f"错误：未找到TCL脚本 - {tcl_script}"
            self.log(error_msg)
            return False, error_msg, -1
        
        try:
            # 创建临时命令文件
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write(f"confprosh {tcl_script}\n")
                f.write("exit\n")
                cmd_file = f.name
            
            self.log(f"创建临时命令文件: {cmd_file}")
            
            # 构建命令
            command = f'"{xactorscmd_path}" < "{cmd_file}"'
            
            # 执行命令
            self.log(f"执行命令: {command}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace"
            )
            
            # 实时输出日志
            for line in process.stdout:
                self.log(line.strip())
            
            # 等待进程完成
            process.wait()
            return_code = process.returncode
            
            # 清理临时文件
            try:
                os.unlink(cmd_file)
                self.log(f"已删除临时命令文件: {cmd_file}")
            except Exception as e:
                self.log(f"删除临时文件失败: {str(e)}")
            
            if return_code == 0:
                return True, "命令执行成功", return_code
            else:
                return False, f"命令执行失败，返回代码: {return_code}", return_code
                
        except Exception as e:
            error_msg = f"执行命令时发生错误: {str(e)}"
            self.log(error_msg)
            return False, error_msg, -1

    def queue_command(self, command_type):
        """将命令加入队列等待执行"""
        # 获取xactorscmd路径
        xactorscmd_path = self.xactorscmd_var.get()
        
        # 获取tcl脚本路径
        tcl_script = ""
        if command_type == "load_all":
            tcl_script = self.load_all_tcl_var.get()
        elif command_type == "load_master":
            tcl_script = self.load_master_tcl_var.get()
        elif command_type == "load_slave":
            tcl_script = self.load_slave_tcl_var.get()
        elif command_type == "reset_all":
            tcl_script = self.reset_all_tcl_var.get()
        elif command_type == "reset_master":
            tcl_script = self.reset_master_tcl_var.get()
        elif command_type == "reset_slave":
            tcl_script = self.reset_slave_tcl_var.get()
        
        # 将命令加入队列
        self.command_queue.put(('preset', command_type, xactorscmd_path, tcl_script))
        self.log(f"命令 '{command_type}' 已加入执行队列，当前队列长度: {self.command_queue.qsize()}")
        
        # 如果当前没有处理命令，开始处理队列
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        # 更新状态
        self.update_status()

    def queue_custom_command(self, command):
        """将自定义命令加入队列等待执行"""
        if not command.strip():
            messagebox.showinfo("提示", "命令不能为空")
            return
        
        # 获取xactorscmd路径
        xactorscmd_path = self.xactorscmd_var.get()
        
        # 将命令加入队列
        self.command_queue.put(('custom', command, xactorscmd_path))
        self.log(f"自定义命令已加入执行队列，当前队列长度: {self.command_queue.qsize()}")
        
        # 如果当前没有处理命令，开始处理队列
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        # 更新状态
        self.update_status()

    def process_command_queue(self):
        """处理命令队列，串行执行所有命令"""
        self.is_processing = True
        self.update_status()
        
        try:
            # 处理队列中的所有命令
            while not self.command_queue.empty():
                # 获取队列中的下一个命令
                command = self.command_queue.get()
                
                try:
                    # 执行预设命令
                    if command[0] == 'preset':
                        _, command_type, xactorscmd_path, tcl_script = command
                        self.log(f"开始执行预设命令: {command_type}")
                        success, msg, return_code = self.run_haps_command(xactorscmd_path, tcl_script)
                        self.log(msg)
                    # 执行自定义命令
                    elif command[0] == 'custom':
                        _, command_text, xactorscmd_path = command
                        self.log(f"开始执行自定义命令: {command_text}")
                        
                        # 使用打包的默认TCL文件
                        default_tcl = self.default_tcl_path
                            
                        if not os.path.exists(default_tcl):
                            error_msg = f"默认TCL文件不存在: {default_tcl}"
                            self.log(error_msg)
                            continue
                            
                        with open(default_tcl, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        
                        # 创建临时文件
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tcl', encoding='utf-8') as f:
                            f.write(content)
                            f.write("\n")  # 确保新命令在新行
                            f.write(command_text)
                            f.write("\n")
                            f.write("cfg_close $HAPS_HANDLE\n")
                            tmp_tcl = f.name
                        
                        self.log(f"已创建临时TCL文件: {tmp_tcl}")
                        
                        # 执行命令
                        success, msg, return_code = self.run_haps_command(xactorscmd_path, tmp_tcl)
                        self.log(msg)
                        
                        # 清理临时TCL文件
                        try:
                            os.unlink(tmp_tcl)
                            self.log(f"已删除临时TCL文件: {tmp_tcl}")
                        except Exception as e:
                            self.log(f"删除临时TCL文件失败: {str(e)}")
                            
                except Exception as e:
                    self.log(f"执行命令时出错: {str(e)}")
                finally:
                    # 标记命令处理完成
                    self.command_queue.task_done()
                    self.update_status()
        
        finally:
            self.is_processing = False
            self.update_status()
            self.log("所有命令执行完毕")

    def clear_command_queue(self):
        """清空命令队列"""
        # 清空队列
        while not self.command_queue.empty():
            self.command_queue.get()
            self.command_queue.task_done()
        
        self.log("命令队列已清空")
        self.update_status()

    def update_status(self):
        """更新执行状态显示"""
        if self.is_processing:
            status = f"执行中 - 队列剩余: {self.command_queue.qsize()}"
            color = "orange"
        else:
            if self.command_queue.qsize() > 0:
                status = f"就绪 - 队列等待: {self.command_queue.qsize()}"
                color = "blue"
            else:
                status = "就绪"
                color = "green"
                
        # 更新状态文本和颜色
        self.status_var.set(status)
        self.status_label.configure(foreground=color)

    def _update_buttons_state(self, state):
        """更新按钮状态"""
        state = tk.NORMAL if state else tk.DISABLED
        
        # 界面一按钮
        self.load_all_btn.config(state=state)
        self.load_master_btn.config(state=state)
        self.load_slave_btn.config(state=state)
        self.reset_all_btn.config(state=state)
        self.reset_master_btn.config(state=state)
        self.reset_slave_btn.config(state=state)
        
        # 界面二按钮
        for frame, var, i in self.command_entries:
            # 找到执行按钮并更新状态
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Button) and widget["text"] == "执行":
                    widget.config(state=state)

if __name__ == "__main__":
    root = tk.Tk()
    app = HAPSAutomationGUI(root)
    root.mainloop()
    