import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import json
import threading
import time
import re
from queue import Queue
import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException

class ScrollableFrame(ttk.Frame):
    """可滚动框架组件"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content_frame = ttk.Frame(self.canvas)
        
        self.content_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_frame, width=e.width)
        )
        
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class HAPSAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HAPS远程自动化控制")
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)
        
        # 配置网格权重，使界面可缩放
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # SSH连接状态
        self.ssh_client = None
        self.ssh_connected = False
        
        # 命令队列和执行状态
        self.command_queue = Queue()
        self.is_processing = False
        
        # ------------------------------ 顶部SSH配置区 ------------------------------
        self.ssh_frame = ttk.LabelFrame(root, text="远程SSH配置", padding="10")
        self.ssh_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=(5, 0))
        self.ssh_frame.grid_columnconfigure(1, weight=1)
        self.ssh_frame.grid_columnconfigure(3, weight=1)
        self.ssh_frame.grid_columnconfigure(5, weight=1)
        self.ssh_frame.grid_columnconfigure(7, weight=1)
        
        # ------------------------------ 下方主内容区 ------------------------------
        self.main_container = ttk.Frame(root)
        self.main_container.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=5)  # 左侧占50%宽度
        self.main_container.grid_columnconfigure(1, weight=5)  # 右侧占50%宽度
        
        # 左侧操作区
        self.left_container = ttk.Frame(self.main_container)
        self.left_container.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 5))
        self.left_container.grid_rowconfigure(0, weight=1)
        self.left_container.grid_columnconfigure(0, weight=1)
        
        # 右侧日志区
        self.right_container = ttk.Frame(self.main_container)
        self.right_container.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 0))
        self.right_container.grid_rowconfigure(0, weight=1)
        self.right_container.grid_columnconfigure(0, weight=1)
        
        # 配置文件路径
        self.config_file = "haps_config.json"
        
        # 默认路径配置
        self.default_haps_control = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\haps100control.bat"
        self.default_xactorscmd = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\xactorscmd.bat"
        
        # 初始化配置
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
        
        # 临时日志存储
        self.temp_logs = []
        
        # 创建界面变量
        self.create_variables()
        
        # 创建界面
        self.create_widgets()
        
        # 加载配置文件
        self.load_config()

    def create_variables(self):
        """创建所有界面变量"""
        # SSH配置变量
        self.ssh_host_var = tk.StringVar()
        self.ssh_port_var = tk.IntVar(value=self.config["ssh_port"])
        self.ssh_user_var = tk.StringVar()
        self.ssh_password_var = tk.StringVar()
        
        # 路径配置变量
        self.base_dir_var = tk.StringVar(value=self.config["base_dir"])
        self.haps_control_var = tk.StringVar(value=self.config["haps_control_path"])
        self.xactorscmd_var = tk.StringVar(value=self.config["xactorscmd_path"])
        self.load_all_tcl_var = tk.StringVar(value=self.config["load_all_tcl"])
        self.load_master_tcl_var = tk.StringVar(value=self.config["load_master_tcl"])
        self.load_slave_tcl_var = tk.StringVar(value=self.config["load_slave_tcl"])
        self.reset_all_tcl_var = tk.StringVar(value=self.config["reset_all_tcl"])
        self.reset_master_tcl_var = tk.StringVar(value=self.config["reset_master_tcl"])
        self.reset_slave_tcl_var = tk.StringVar(value=self.config["reset_slave_tcl"])
        
        # 执行状态变量
        self.exec_status_var = tk.StringVar(value="就绪")

    def create_widgets(self):
        """创建所有界面元素"""
        self.init_ssh_frame()
        self.init_left_operation_area()
        self.init_right_log_area()
        
        # 显示临时日志
        self.flush_temp_logs()

    def init_ssh_frame(self):
        """初始化SSH配置区域"""
        # SSH配置控件
        ttk.Label(self.ssh_frame, text="IP地址:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_host_var).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="端口:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_port_var, width=10).grid(row=0, column=3, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="用户名:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_user_var).grid(row=0, column=5, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="密码:").grid(row=0, column=6, sticky=tk.W, padx=5, pady=5)
        pwd_entry = ttk.Entry(self.ssh_frame, textvariable=self.ssh_password_var, show="*")
        pwd_entry.grid(row=0, column=7, sticky=tk.EW, padx=5, pady=5)
        
        self.ssh_status_var = tk.StringVar(value="未连接")
        self.ssh_status_label = ttk.Label(self.ssh_frame, textvariable=self.ssh_status_var, foreground="red")
        self.ssh_status_label.grid(row=0, column=8, sticky=tk.W, padx=5, pady=5)
        
        self.ssh_btn = ttk.Button(self.ssh_frame, text="连接", command=self.toggle_ssh_connection)
        self.ssh_btn.grid(row=0, column=9, padx=5, pady=5)

    def init_left_operation_area(self):
        """初始化左侧操作区域"""
        # 左侧使用可滚动框架包装
        self.scrollable_left_frame = ScrollableFrame(self.left_container)
        self.scrollable_left_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.left_frame = self.scrollable_left_frame.content_frame
        
        # 标签页控件 - 包含自动化操作和自定义命令
        self.tab_control = ttk.Notebook(self.left_frame)
        self.tab_control.pack(fill=tk.X, expand=False, padx=5, pady=5)
        
        # 自动化操作标签页
        self.tab1_frame = ttk.Frame(self.tab_control)
        self.tab1_scrollable = ScrollableFrame(self.tab1_frame)
        self.tab1_scrollable.pack(fill=tk.BOTH, expand=True)
        self.tab1 = self.tab1_scrollable.content_frame
        self.tab_control.add(self.tab1_frame, text="自动化操作")
        
        # 自定义命令标签页
        self.tab2_frame = ttk.Frame(self.tab_control)
        self.tab2_scrollable = ScrollableFrame(self.tab2_frame)
        self.tab2_scrollable.pack(fill=tk.BOTH, expand=True)
        self.tab2 = self.tab2_scrollable.content_frame
        self.tab_control.add(self.tab2_frame, text="自定义命令")
        
        # 初始化各标签页内容
        self.init_tab1()
        self.init_tab2()

    def init_right_log_area(self):
        """初始化右侧日志区域"""
        self.log_frame = ttk.LabelFrame(self.right_container, text="执行日志", padding="10")
        self.log_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        # 日志控制按钮区
        log_ctrl_frame = ttk.Frame(self.log_frame, height=30)
        log_ctrl_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        log_ctrl_frame.pack_propagate(False)
        
        clear_log_btn = ttk.Button(log_ctrl_frame, text="清空日志", command=self.clear_log)
        clear_log_btn.pack(side=tk.RIGHT, padx=5)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.log_text.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 5))

    def init_tab1(self):
        """初始化自动化操作界面"""
        main_frame = ttk.Frame(self.tab1, padding="10")
        main_frame.pack(fill=tk.X, expand=False)
        
        # 基础路径配置
        ttk.Label(main_frame, text="远程基础路径:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.base_dir_entry = ttk.Entry(main_frame, textvariable=self.base_dir_var)
        self.base_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # 执行状态显示
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        ttk.Label(status_frame, text="执行状态:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, textvariable=self.exec_status_var, foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        clear_queue_btn = ttk.Button(status_frame, text="清空队列", command=self.clear_command_queue)
        clear_queue_btn.pack(side=tk.RIGHT, padx=5)
        
        # 操作按钮区
        btn_frame = ttk.LabelFrame(main_frame, text="HAPS操作", padding="10")
        btn_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
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
        
        # 路径配置区
        config_frame = ttk.LabelFrame(main_frame, text="远程文件配置", padding="10")
        config_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        row = 0
        # haps100control路径
        ttk.Label(config_frame, text="haps100control路径:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.haps_ctrl_entry = ttk.Entry(config_frame, textvariable=self.haps_control_var)
        self.haps_ctrl_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # xactorscmd路径
        ttk.Label(config_frame, text="xactorscmd路径:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.xactorscmd_entry = ttk.Entry(config_frame, textvariable=self.xactorscmd_var)
        self.xactorscmd_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # TCL路径配置
        tcl_configs = [
            ("Load All TCL:", self.load_all_tcl_var),
            ("Load Master TCL:", self.load_master_tcl_var),
            ("Load Slave TCL:", self.load_slave_tcl_var),
            ("Reset All TCL:", self.reset_all_tcl_var),
            ("Reset Master TCL:", self.reset_master_tcl_var),
            ("Reset Slave TCL:", self.reset_slave_tcl_var)
        ]
        for label_text, var in tcl_configs:
            ttk.Label(config_frame, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(config_frame, textvariable=var).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
            row += 1
        
        # 保存配置按钮
        self.save_config_btn = ttk.Button(config_frame, text="保存配置", command=self.save_config)
        self.save_config_btn.grid(row=row, column=0, columnspan=2, pady=10)

    def init_tab2(self):
        """初始化自定义命令界面"""
        main_frame = ttk.Frame(self.tab2, padding="10")
        main_frame.pack(fill=tk.X, expand=False)
        
        # 命令框容器
        self.cmds_frame = ttk.LabelFrame(main_frame, text="自定义远程命令", padding="10")
        self.cmds_frame.pack(fill=tk.X, expand=False, padx=5, pady=(5, 10))
        self.cmds_frame.pack_propagate(False)
        self.cmds_frame.columnconfigure(0, weight=1)
        
        # 参数提示
        tip_frame = ttk.Frame(main_frame)
        tip_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(tip_frame, text="提示：命令将加入队列执行，支持参数 $HAPS_DEVICE $HAPS_SERIAL", foreground="blue").pack(anchor=tk.W)
        
        # 操作按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        self.add_cmd_btn = ttk.Button(btn_frame, text="添加命令框", command=self.add_command_entry)
        self.add_cmd_btn.pack(side=tk.LEFT, padx=5)
        self.del_cmd_btn = ttk.Button(btn_frame, text="删除最后一个", command=self.remove_command_entry)
        self.del_cmd_btn.pack(side=tk.LEFT, padx=5)
        self.save_cmds_btn = ttk.Button(btn_frame, text="保存命令", command=self.save_custom_commands)
        self.save_cmds_btn.pack(side=tk.LEFT, padx=5)
        
        # 命令输入框
        self.cmd_entries = []
        self.create_command_entries()

    # ------------------------------ SSH连接逻辑 ------------------------------
    def toggle_ssh_connection(self):
        if self.ssh_connected:
            self.disconnect_ssh()
        else:
            threading.Thread(target=self.connect_ssh, daemon=True).start()

    def connect_ssh(self):
        try:
            host = self.ssh_host_var.get().strip()
            port = self.ssh_port_var.get() or 22
            user = self.ssh_user_var.get().strip()
            pwd = self.ssh_password_var.get().strip()
            
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
            
            # 处理输出
            output = self.process_data(output_bytes)
            error = self.process_data(error_bytes)
            
            if error:
                self.sync_log(f"连接验证错误: {error}")
                
            if "HAPS_CONNECTED" in output or "484150535f434f4e4e4543544544" in output:
                self.ssh_connected = True
                self.ssh_status_var.set("已连接")
                self.ssh_status_label.configure(foreground="green")
                self.ssh_btn.configure(text="断开")
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

    def disconnect_ssh(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.sync_log("SSH连接已断开")
            except Exception as e:
                self.sync_log(f"断开SSH时出错：{str(e)}")
        
        self.ssh_connected = False
        self.ssh_status_var.set("未连接")
        self.ssh_status_label.configure(foreground="red")
        self.ssh_btn.configure(text="连接")
        self.ssh_client = None

    def check_remote_paths(self):
        """检查远程关键路径"""
        paths = [
            (self.haps_control_var.get(), "haps100control.bat"),
            (self.xactorscmd_var.get(), "xactorscmd.bat"),
            (self.base_dir_var.get(), "基础目录"),
            (os.path.join(self.base_dir_var.get(), "system", "targetsystem.tsd"), "targetsystem.tsd")
        ]
        
        for path, desc in paths:
            if not path:
                continue
            # 处理路径中的反斜杠问题
            path = path.replace("/", "\\")
            cmd = f'if exist "{path}" (echo EXIST) else (echo NOT_EXIST)'
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=5)
                output_bytes = stdout.read()
                error_bytes = stderr.read()
                
                # 处理输出数据
                output = self.process_data(output_bytes)
                error = self.process_data(error_bytes)
                
                if error:
                    self.sync_log(f"[{desc}] 检查错误：{error}")
                elif output == "EXIST" or "4558495354" in output:  # EXIST的十六进制
                    self.sync_log(f"[{desc}] 路径存在：{path}")
                else:
                    self.sync_log(f"[{desc}] 路径不存在：{path}")
                    messagebox.showwarning("路径警告", f"[{desc}] 远程路径不存在：{path}")
            except Exception as e:
                self.sync_log(f"[{desc}] 检查失败：{str(e)}")

    # ------------------------------ 命令执行逻辑 ------------------------------
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
        self.sync_log(f"自定义命令加入队列，当前队列：{self.command_queue.qsize()}")
        
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
                        self.sync_log(f"开始执行自定义命令：{cmd_content}")
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
            # 获取路径参数
            haps_ctrl = self.haps_control_var.get().strip()
            xactorscmd = self.xactorscmd_var.get().strip()
            base_dir = self.base_dir_var.get().strip()
            
            if not haps_ctrl or not xactorscmd:
                raise ValueError("haps100control和xactorscmd路径不能为空")
            
            # 获取TCL脚本路径
            tcl_map = {
                "load_all": self.load_all_tcl_var.get(),
                "load_master": self.load_master_tcl_var.get(),
                "load_slave": self.load_slave_tcl_var.get(),
                "reset_all": self.reset_all_tcl_var.get(),
                "reset_master": self.reset_master_tcl_var.get(),
                "reset_slave": self.reset_slave_tcl_var.get()
            }
            tcl_script = tcl_map[cmd_type].strip()
            
            # 处理TCL路径
            if tcl_script and not tcl_script.startswith(('C:', 'D:', '\\', '/')) and base_dir:
                tcl_script = f"{base_dir}\\{tcl_script}"
            
            if not tcl_script:
                raise ValueError(f"未配置{cmd_type}的TCL脚本路径")
            
            # 构建命令 - 先切换到基础目录再执行
            cmd = f'cd /d "{base_dir}" && call "{haps_ctrl}" "{xactorscmd}" "{tcl_script}"'
            self.sync_log(f"构建HAPS命令：{cmd}")
            
            # 执行命令
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
        """执行远程命令（使用字节流处理）"""
        try:
            # 执行命令
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=300)
            
            # 实时读取输出（使用字节流）
            output = []
            error = []
            
            def read_stream(stream, buffer):
                while True:
                    try:
                        # 读取字节数据
                        data = stream.readline()
                        if not data:
                            break
                        # 处理数据（可能是字节或字符串）
                        processed = self.process_data(data)
                        buffer.append(processed)
                        self.sync_log(f"输出：{processed}")
                    except Exception as e:
                        err_msg = f"[读取错误] {str(e)}"
                        buffer.append(err_msg)
                        self.sync_log(err_msg)
                        break
            
            # 启动线程读取stdout和stderr
            stdout_thread = threading.Thread(target=read_stream, args=(stdout, output), daemon=True)
            stderr_thread = threading.Thread(target=read_stream, args=(stderr, error), daemon=True)
            
            stdout_thread.start()
            stderr_thread.start()
            stdout_thread.join()
            stderr_thread.join()
            
            # 获取返回码
            return_code = stdout.channel.recv_exit_status()
            full_output = "\n".join(output)
            full_error = "\n".join(error)
            
            if return_code == 0:
                return True, f"返回码0，输出：{full_output}", return_code, full_output
            else:
                return False, f"返回码{return_code}，错误：{full_error}", return_code, full_output
                
        except Exception as e:
            return False, str(e), -1, ""

    def process_data(self, data):
        """处理数据，优先GBK编码，确保兼容中文特殊字符"""
        # 如果是字符串，直接返回
        if isinstance(data, str):
            return data.rstrip('\r\n')
            
        # 如果是字节，尝试解码
        if isinstance(data, bytes):
            # 先尝试GBK解码（专门处理中文环境的特殊字符）
            try:
                return data.decode('gbk', errors='replace').rstrip('\r\n')
            except LookupError:  # 当系统不支持GBK编码时
                pass
                
            # 尝试UTF-8解码
            try:
                return data.decode('utf-8', errors='replace').rstrip('\r\n')
            except LookupError:
                pass
                
            # 最后尝试Latin-1解码
            return data.decode('latin-1').rstrip('\r\n')
            
        # 既不是字符串也不是字节
        return str(data)

    # ------------------------------ 自定义命令界面逻辑 ------------------------------
    def create_command_entries(self):
        """创建自定义命令输入框"""
        for widget in self.cmds_frame.winfo_children():
            widget.destroy()
        self.cmd_entries.clear()
        
        # 从配置加载命令
        custom_cmds = self.config.get("custom_commands", [""])
        for cmd in custom_cmds:
            self.add_command_entry(default_text=cmd, update_config=False)
        
        # 确保至少有一个空框体
        if not self.cmd_entries:
            self.add_command_entry(update_config=False)

    def add_command_entry(self, default_text="", update_config=True):
        """添加命令输入框"""
        # 命令行框架
        cmd_frame = ttk.Frame(self.cmds_frame, height=30)
        cmd_frame.pack(fill=tk.X, pady=3)
        cmd_frame.pack_propagate(False)
        
        # 命令输入框
        cmd_var = tk.StringVar(value=default_text)
        cmd_entry = ttk.Entry(cmd_frame, textvariable=cmd_var, width=60)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # 执行按钮
        exec_btn = ttk.Button(
            cmd_frame, 
            text="执行", 
            width=6,
            command=lambda v=cmd_var: self.queue_custom_command(v.get())
        )
        exec_btn.pack(side=tk.LEFT, padx=2)
        
        # 记录命令框
        self.cmd_entries.append((cmd_frame, cmd_var, exec_btn))
        
        # 更新配置
        if update_config:
            self.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]

    def remove_command_entry(self):
        """删除最后一个命令框"""
        if len(self.cmd_entries) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个命令输入框")
            return
        
        cmd_frame, cmd_var, exec_btn = self.cmd_entries.pop()
        cmd_frame.destroy()
        self.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]

    def save_custom_commands(self):
        """保存自定义命令"""
        self.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
        self.save_config()
        messagebox.showinfo("保存成功", "自定义命令已保存")

    # ------------------------------ 工具方法 ------------------------------
    def sync_log(self, message):
        """同步更新日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def flush_temp_logs(self):
        """显示临时日志"""
        if self.temp_logs:
            self.log_text.config(state=tk.NORMAL)
            for msg in self.temp_logs:
                timestamp = time.strftime("%H:%M:%S")
                self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.temp_logs.clear()

    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.sync_log("日志已清空")

    def load_config(self):
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    for key in self.config:
                        if key in loaded_config:
                            self.config[key] = loaded_config[key]
                
                # 更新界面变量
                self.ssh_host_var.set(self.config["ssh_host"])
                self.ssh_port_var.set(self.config["ssh_port"])
                self.ssh_user_var.set(self.config["ssh_user"])
                self.ssh_password_var.set(self.config["ssh_password"])
                self.base_dir_var.set(self.config["base_dir"])
                self.haps_control_var.set(self.config["haps_control_path"])
                self.xactorscmd_var.set(self.config["xactorscmd_path"])
                self.load_all_tcl_var.set(self.config["load_all_tcl"])
                self.load_master_tcl_var.set(self.config["load_master_tcl"])
                self.load_slave_tcl_var.set(self.config["load_slave_tcl"])
                self.reset_all_tcl_var.set(self.config["reset_all_tcl"])
                self.reset_master_tcl_var.set(self.config["reset_master_tcl"])
                self.reset_slave_tcl_var.set(self.config["reset_slave_tcl"])
                
                self.sync_log("配置文件加载成功")
            except Exception as e:
                self.sync_log(f"加载配置失败：{str(e)}")
                self.save_config()
        else:
            self.save_config()
            self.sync_log("配置文件不存在，已创建默认配置")

    def save_config(self):
        """保存配置"""
        self.config["ssh_host"] = self.ssh_host_var.get().strip()
        self.config["ssh_port"] = self.ssh_port_var.get() or 22
        self.config["ssh_user"] = self.ssh_user_var.get().strip()
        self.config["ssh_password"] = self.ssh_password_var.get().strip()
        self.config["base_dir"] = self.base_dir_var.get().strip()
        self.config["haps_control_path"] = self.haps_control_var.get().strip()
        self.config["xactorscmd_path"] = self.xactorscmd_var.get().strip()
        self.config["load_all_tcl"] = self.load_all_tcl_var.get().strip()
        self.config["load_master_tcl"] = self.load_master_tcl_var.get().strip()
        self.config["load_slave_tcl"] = self.load_slave_tcl_var.get().strip()
        self.config["reset_all_tcl"] = self.reset_all_tcl_var.get().strip()
        self.config["reset_master_tcl"] = self.reset_master_tcl_var.get().strip()
        self.config["reset_slave_tcl"] = self.reset_slave_tcl_var.get().strip()
        self.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
        
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
        queue_size = self.command_queue.qsize()
        if self.is_processing:
            self.exec_status_var.set(f"执行中 - 剩余：{queue_size}")
            self.status_label.configure(foreground="orange")
        else:
            if queue_size > 0:
                self.exec_status_var.set(f"就绪 - 等待：{queue_size}")
                self.status_label.configure(foreground="blue")
            else:
                self.exec_status_var.set("就绪")
                self.status_label.configure(foreground="green")

    def clear_command_queue(self):
        """清空命令队列"""
        while not self.command_queue.empty():
            self.command_queue.get()
            self.command_queue.task_done()
        
        self.sync_log("命令队列已清空")
        self.update_exec_status()

# ------------------------------ 程序入口 ------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = HAPSAutomationGUI(root)
    root.mainloop()
    