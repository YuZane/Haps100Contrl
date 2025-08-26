import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import os
import json
import subprocess
import threading
import time
import tempfile
from queue import Queue
import paramiko  # 需要安装: pip install paramiko
import sys

class HAPSAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPS自动化控制 (支持远程操作)")
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)
        
        # 创建主框架，分为左右两部分
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧主内容区域
        self.left_frame = ttk.Frame(self.main_container)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 右侧日志区域
        self.right_frame = ttk.Frame(self.main_container)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0), ipady=5)
        
        # 配置文件路径
        self.config_file = "haps_config.json"
        
        # 默认参数
        self.default_xactorscmd = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\xactorscmd.bat"
        self.default_tcl_script = "tcl\\reset.tcl"
        
        # 初始化配置，新增远程连接配置
        self.config = {
            "remote_ip": "",
            "remote_port": 22,
            "remote_user": "",
            "remote_password": "",
            "base_dir": "",
            "xactorscmd_path": self.default_xactorscmd,
            "load_all_tcl": "load_all.tcl",
            "load_master_tcl": "load_master.tcl",
            "load_slave_tcl": "load_slave.tcl",
            "reset_all_tcl": "reset_all.tcl",
            "reset_master_tcl": "reset_master.tcl",
            "reset_slave_tcl": "reset_slave.tcl",
            "custom_commands": [""]
        }
        
        # SSH客户端实例
        self.ssh_client = None
        self.ssh_connected = False
        
        # 临时日志存储
        self.temp_logs = []
        
        # 命令队列和执行状态
        self.command_queue = Queue()
        self.is_processing = False
        
        # 创建界面元素变量
        self.create_variables()
        
        # 创建界面
        self.create_widgets()
        
        # 加载配置文件
        self.load_config()

    def create_variables(self):
        """创建所有需要的变量"""
        # 远程连接变量
        self.remote_ip_var = tk.StringVar()
        self.remote_port_var = tk.IntVar(value=22)
        self.remote_user_var = tk.StringVar()
        self.remote_password_var = tk.StringVar()
        
        # 其他配置变量
        self.base_dir_var = tk.StringVar()
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
        
        # 界面一：远程配置与自动化操作
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text="远程操作")
        
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
        # 主框架
        main_frame = ttk.Frame(self.tab1, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)
        
        # 1. 远程连接配置区域
        remote_frame = ttk.LabelFrame(main_frame, text="远程SSH连接配置", padding="10")
        remote_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)
        remote_frame.columnconfigure(1, weight=1)
        
        # 远程连接配置行
        row = 0
        ttk.Label(remote_frame, text="IP地址:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(remote_frame, textvariable=self.remote_ip_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        ttk.Label(remote_frame, text="端口:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(remote_frame, textvariable=self.remote_port_var, width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        
        row += 1
        ttk.Label(remote_frame, text="用户名:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(remote_frame, textvariable=self.remote_user_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        ttk.Label(remote_frame, text="密码:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        pwd_entry = ttk.Entry(remote_frame, textvariable=self.remote_password_var, show="*")
        pwd_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        conn_frame = ttk.Frame(remote_frame)
        conn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        self.connect_btn = ttk.Button(conn_frame, text="连接", command=self.connect_ssh)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = ttk.Button(conn_frame, text="断开连接", command=self.disconnect_ssh, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_conn_btn = ttk.Button(conn_frame, text="保存连接配置", command=self.save_connection_config)
        self.save_conn_btn.pack(side=tk.LEFT, padx=5)
        
        # 连接状态指示
        self.connection_status = ttk.Label(remote_frame, text="未连接", foreground="red")
        self.connection_status.grid(row=row, column=2, padx=5, pady=5)
        
        # 2. 远程路径配置
        path_frame = ttk.LabelFrame(main_frame, text="远程路径配置", padding="10")
        path_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="远程基础路径:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.base_dir_entry = ttk.Entry(path_frame, textvariable=self.base_dir_var)
        self.base_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # 3. 操作按钮区域
        btn_frame = ttk.LabelFrame(main_frame, text="操作", padding="10")
        btn_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)
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
        
        # 4. 远程文件配置区域
        config_frame = ttk.LabelFrame(main_frame, text="远程文件配置", padding="10")
        config_frame.grid(row=3, column=0, columnspan=3, sticky=tk.NSEW, padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # xactorscmd路径配置
        ttk.Label(config_frame, text="xactorscmd路径:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.xactorscmd_entry = ttk.Entry(config_frame, textvariable=self.xactorscmd_var)
        self.xactorscmd_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        # 各种TCL配置...
        ttk.Label(config_frame, text="Load All TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_all_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        ttk.Label(config_frame, text="Load Master TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_master_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        ttk.Label(config_frame, text="Load Slave TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.load_slave_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        ttk.Label(config_frame, text="Reset All TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_all_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        ttk.Label(config_frame, text="Reset Master TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_master_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        ttk.Label(config_frame, text="Reset Slave TCL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(config_frame, textvariable=self.reset_slave_tcl_var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        row += 1
        
        # 保存配置按钮
        save_config_btn = ttk.Button(config_frame, text="保存配置", command=self.save_config)
        save_config_btn.grid(row=row, column=0, columnspan=2, pady=10)

    def init_tab2(self):
        # 主框架
        main_frame = ttk.Frame(self.tab2, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        
        # 命令框区域（最上方）
        self.commands_frame = ttk.LabelFrame(main_frame, text="自定义命令", padding="10")
        self.commands_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        main_frame.rowconfigure(0, weight=1)
        self.commands_frame.columnconfigure(0, weight=1)
        
        # 命令框列表
        self.command_entries = []
        self.create_command_entries()
        
        # 可用参数提示（中间）
        params_frame = ttk.Frame(main_frame)
        params_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(params_frame, text="可用参数为: $HAPS_DEVICE $HAPS_SERIAL $HAPS_HANDLE", 
                 foreground="blue").pack(anchor=tk.W)
        
        # 按钮区域（最下方）
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
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

    def connect_ssh(self):
        """建立SSH连接"""
        # 检查是否已连接
        if self.ssh_connected:
            messagebox.showinfo("提示", "已处于连接状态")
            return
            
        # 获取连接信息
        ip = self.remote_ip_var.get().strip()
        port = self.remote_port_var.get()
        user = self.remote_user_var.get().strip()
        pwd = self.remote_password_var.get().strip()
        
        # 验证输入
        if not ip or not user or not pwd:
            messagebox.showerror("错误", "IP地址、用户名和密码不能为空")
            return
            
        # 尝试连接
        self.log(f"尝试连接到 {ip}:{port} ...")
        
        # 在新线程中执行连接，避免阻塞GUI
        threading.Thread(target=self._ssh_connect_impl, args=(ip, port, user, pwd), daemon=True).start()

    def _ssh_connect_impl(self, ip, port, user, pwd):
        """SSH连接实现"""
        try:
            # 创建SSH客户端
            self.ssh_client = paramiko.SSHClient()
            # 自动接受未知的主机密钥
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接
            self.ssh_client.connect(ip, port, user, pwd, timeout=10)
            
            # 更新连接状态
            self.ssh_connected = True
            self.root.after(0, lambda: self._update_connection_status())
            self.log(f"成功连接到 {ip}:{port}")
            
        except Exception as e:
            self.log(f"SSH连接失败: {str(e)}")
            self.ssh_connected = False
            self.ssh_client = None
            self.root.after(0, lambda: self._update_connection_status())

    def disconnect_ssh(self):
        """断开SSH连接"""
        if self.ssh_connected and self.ssh_client:
            try:
                self.ssh_client.close()
                self.log("已断开SSH连接")
            except Exception as e:
                self.log(f"断开连接时出错: {str(e)}")
            
            self.ssh_connected = False
            self.ssh_client = None
            self._update_connection_status()
        else:
            messagebox.showinfo("提示", "未处于连接状态")

    def _update_connection_status(self):
        """更新连接状态显示"""
        if self.ssh_connected:
            self.connection_status.config(text="已连接", foreground="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
        else:
            self.connection_status.config(text="未连接", foreground="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)

    def save_connection_config(self):
        """保存连接配置"""
        self.config["remote_ip"] = self.remote_ip_var.get()
        self.config["remote_port"] = self.remote_port_var.get()
        self.config["remote_user"] = self.remote_user_var.get()
        self.config["remote_password"] = self.remote_password_var.get()
        
        self.save_config()
        messagebox.showinfo("提示", "连接配置已保存")

    def create_command_entries(self):
        # 清除现有命令框
        for widget in self.commands_frame.winfo_children():
            widget.destroy()
        
        # 创建命令框（从上到下）
        for i, cmd in enumerate(self.config["custom_commands"]):
            frame = ttk.Frame(self.commands_frame)
            frame.grid(row=i, column=0, sticky=tk.EW, pady=2)
            self.commands_frame.rowconfigure(i, weight=1)
            
            cmd_var = tk.StringVar(value=cmd)
            entry = ttk.Entry(frame, textvariable=cmd_var)
            entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            exec_btn = ttk.Button(frame, text="执行", 
                                command=lambda var=cmd_var: self.queue_custom_command(var.get()))
            exec_btn.pack(side=tk.LEFT, padx=5)
            
            self.command_entries.append((frame, cmd_var, i))

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
                self.remote_ip_var.set(self.config["remote_ip"])
                self.remote_port_var.set(self.config["remote_port"])
                self.remote_user_var.set(self.config["remote_user"])
                self.remote_password_var.set(self.config["remote_password"])
                self.base_dir_var.set(self.config["base_dir"])
                self.xactorscmd_var.set(self.config["xactorscmd_path"])
                self.load_all_tcl_var.set(self.config["load_all_tcl"])
                self.load_master_tcl_var.set(self.config["load_master_tcl"])
                self.load_slave_tcl_var.set(self.config["load_slave_tcl"])
                self.reset_all_tcl_var.set(self.config["reset_all_tcl"])
                self.reset_master_tcl_var.set(self.config["reset_master_tcl"])
                self.reset_slave_tcl_var.set(self.config["reset_slave_tcl"])
                
                # 加载自定义命令
                self.create_command_entries()
                
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
        self.config["remote_ip"] = self.remote_ip_var.get()
        self.config["remote_port"] = self.remote_port_var.get()
        self.config["remote_user"] = self.remote_user_var.get()
        self.config["remote_password"] = self.remote_password_var.get()
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
        if not hasattr(self, 'log_text'):
            self.temp_logs.append(message)
            return
            
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
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

    def run_remote_command(self, command):
        """在远程机器上执行命令"""
        if not self.ssh_connected or not self.ssh_client:
            return False, "未建立SSH连接，请先连接", -1
            
        try:
            self.log(f"在远程执行命令: {command}")
            
            # 执行远程命令
            stdin, stdout, stderr = self.ssh_client.exec_command(command, get_pty=True)
            
            # 实时获取输出
            output = []
            error = []
            
            # 读取标准输出
            for line in iter(stdout.readline, ""):
                stripped_line = line.strip()
                output.append(stripped_line)
                self.log(stripped_line)
            
            # 读取错误输出
            for line in iter(stderr.readline, ""):
                stripped_line = line.strip()
                error.append(stripped_line)
                self.log(f"错误: {stripped_line}")
            
            # 获取返回码
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                return True, "命令执行成功", exit_status
            else:
                error_msg = f"命令执行失败，返回代码: {exit_status}"
                return False, error_msg, exit_status
                
        except Exception as e:
            error_msg = f"执行远程命令时出错: {str(e)}"
            self.log(error_msg)
            return False, error_msg, -1

    def run_haps_command(self, xactorscmd_path=None, tcl_script=None):
        """在远程机器上执行HAPS命令"""
        # 设置默认值
        if xactorscmd_path is None or not xactorscmd_path.strip():
            xactorscmd_path = self.default_xactorscmd
            self.log(f"未指定xactorscmd路径，使用默认值: {xactorscmd_path}")
        
        if tcl_script is None or not tcl_script.strip():
            tcl_script = self.default_tcl_script
            self.log(f"未指定TCL脚本，使用默认值: {tcl_script}")
        
        # 处理远程路径
        base_dir = self.base_dir_var.get()
        if base_dir and not tcl_script.startswith(base_dir):
            tcl_script = os.path.join(base_dir, tcl_script).replace("/", "\\")
        
        # 构建完整命令
        # 在远程Windows机器上执行批处理命令
        command = f'{xactorscmd_path} -f {tcl_script}'
        self.log(f"构建HAPS命令: {command}")
        
        # 执行远程命令
        return self.run_remote_command(command)

    def queue_command(self, command_type):
        """将命令加入队列等待执行"""
        if not self.ssh_connected:
            messagebox.showerror("错误", "请先建立SSH连接")
            return
        
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
        if not self.ssh_connected:
            messagebox.showerror("错误", "请先建立SSH连接")
            return
        
        if not command.strip():
            messagebox.showinfo("提示", "命令不能为空")
            return
        
        # 将命令加入队列
        self.command_queue.put(('custom', command))
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
                        _, command_text = command
                        self.log(f"开始执行自定义命令: {command_text}")
                        success, msg, return_code = self.run_remote_command(command_text)
                        self.log(msg)
                        
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

    def on_closing(self):
        """关闭窗口时的处理"""
        if self.ssh_connected and self.ssh_client:
            try:
                self.ssh_client.close()
                self.log("程序退出，已断开SSH连接")
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HAPSAutomationGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)  # 关闭窗口时断开连接
    root.mainloop()
    