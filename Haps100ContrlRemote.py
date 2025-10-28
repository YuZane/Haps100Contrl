import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os
import json
import threading
import time
from queue import Queue
import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException

class ScrollableFrame(ttk.Frame):
    """可滚动框架组件"""
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

class RemoteFileBrowser(tk.Toplevel):
    """远程文件浏览器对话框 - 增加手动输入路径和回退上级目录功能"""
    def __init__(self, parent, ssh_client, initial_dir="/"):
        super().__init__(parent)
        self.parent = parent
        self.ssh_client = ssh_client
        self.current_dir = initial_dir
        self.selected_path = None
        
        self.title("浏览远程文件")
        self.geometry("700x500")
        self.minsize(600, 400)
        
        # 创建UI
        self.create_widgets()
        
        # 加载初始目录
        self.load_directory_contents()
        
        # 模态窗口
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)
    
    def create_widgets(self):
        """创建远程文件浏览器界面控件"""
        # 路径导航区
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 回退按钮
        self.back_btn = ttk.Button(nav_frame, text="上级目录", command=self.navigate_up)
        self.back_btn.pack(side=tk.LEFT, padx=5)
        
        # 路径输入框
        ttk.Label(nav_frame, text="路径:").pack(side=tk.LEFT, padx=5)
        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        self.path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.path_entry.bind("<Return>", lambda e: self.navigate_to_path())
        
        # 转到按钮
        self.go_btn = ttk.Button(nav_frame, text="转到", command=self.navigate_to_path)
        self.go_btn.pack(side=tk.LEFT, padx=5)
        
        # 文件列表
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 列表视图
        columns = ("name", "type")
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        self.file_tree.heading("name", text="名称")
        self.file_tree.heading("type", text="类型")
        self.file_tree.column("name", width=300)
        self.file_tree.column("type", width=100)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件
        self.file_tree.bind("<Double-1>", self.on_item_double_click)
        
        # 按钮区
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="选择", command=self.on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)
    
    def navigate_up(self):
        """导航到上级目录"""
        if self.current_dir in ["/", "", "\\", "."]:
            return
            
        # 处理Windows路径
        if "\\" in self.current_dir:
            parent_dir = os.path.dirname(self.current_dir.rstrip("\\"))
            if not parent_dir:  # 如果是根目录
                parent_dir = self.current_dir.split("\\")[0] + "\\"
        # 处理Unix路径
        elif "/" in self.current_dir:
            parent_dir = os.path.dirname(self.current_dir.rstrip("/"))
            if not parent_dir:  # 如果是根目录
                parent_dir = "/"
        else:
            parent_dir = ""
            
        self.current_dir = parent_dir
        self.load_directory_contents()
    
    def navigate_to_path(self):
        """导航到输入框中的路径"""
        path = self.path_var.get().strip()
        if not path:
            return
            
        # 检查路径是否存在且是目录
        cmd = f'if exist "{path}" (if exist "{path}\\*" (echo DIR_EXIST) else (echo FILE_EXIST)) else (echo NOT_EXIST)'
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
            output_bytes = stdout.read()
            error_bytes = stderr.read()
            
            error = self.process_data(error_bytes)
            if error:
                raise Exception(f"检查路径错误：{error}")
            
            output = self.process_data(output_bytes).strip()
            
            if output == "DIR_EXIST" or "4449525f4558495354" in output:  # DIR_EXIST的十六进制
                self.current_dir = path
                self.load_directory_contents()
            elif output == "FILE_EXIST":
                # 如果是文件，导航到它所在的目录
                dir_path = os.path.dirname(path)
                self.current_dir = dir_path
                self.load_directory_contents()
                # 尝试选中该文件
                file_name = os.path.basename(path)
                for item in self.file_tree.get_children():
                    if self.file_tree.item(item, "values")[0] == file_name:
                        self.file_tree.selection_set(item)
                        self.file_tree.see(item)
                        break
            else:
                messagebox.showerror("错误", f"路径不存在：{path}")
                
        except Exception as e:
            messagebox.showerror("错误", f"导航失败：{str(e)}")
    
    def load_directory_contents(self):
        """加载目录内容"""
        # 清空现有内容
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        self.path_var.set(self.current_dir)
        
        try:
            # 执行dir命令获取目录内容（只显示名称）
            cmd = f'dir /b /ad "{self.current_dir}"'  # 列出目录
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
            dirs_bytes = stdout.read()
            error_bytes = stderr.read()
            
            error = self.process_data(error_bytes)
            if error:
                # 尝试处理访问权限问题
                if "拒绝访问" in error:
                    self.sync_log(f"没有权限访问目录：{self.current_dir}")
                    messagebox.showwarning("权限不足", f"没有权限访问目录：{self.current_dir}")
                    return
                else:
                    raise Exception(f"读取目录错误：{error}")
            
            # 处理目录
            dirs = self.process_data(dirs_bytes).split('\r\n')
            dirs = [d for d in dirs if d.strip()]
            
            for dir_name in dirs:
                self.file_tree.insert("", tk.END, values=(dir_name, "目录"))
            
            # 列出文件
            cmd = f'dir /b /a-d "{self.current_dir}"'  # 列出文件
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
            files_bytes = stdout.read()
            error_bytes = stderr.read()
            
            error = self.process_data(error_bytes)
            if error:
                raise Exception(f"读取文件错误：{error}")
            
            # 处理文件
            files = self.process_data(files_bytes).split('\r\n')
            files = [f for f in files if f.strip()]
            
            for file_name in files:
                self.file_tree.insert("", tk.END, values=(file_name, "文件"))
                
        except Exception as e:
            print()
            # messagebox.showerror("错误", f"加载目录失败：{str(e)}")
    
    def on_item_double_click(self, event):
        """双击项目处理"""
        selection = self.file_tree.selection()
        if not selection:
            return
            
        item = selection[0]
        item_name = self.file_tree.item(item, "values")[0]
        item_type = self.file_tree.item(item, "values")[1]
        
        if item_type == "目录":
            # 进入子目录
            if self.current_dir.endswith(('\\', '/')):
                new_dir = f"{self.current_dir}{item_name}"
            else:
                new_dir = f"{self.current_dir}\\{item_name}"
            self.current_dir = new_dir
            self.load_directory_contents()
    
    def on_select(self):
        """选择文件或目录"""
        selection = self.file_tree.selection()
        if not selection:
            # 如果没有选择任何项，使用当前目录
            self.selected_path = self.current_dir
            self.destroy()
            return
            
        item = selection[0]
        item_name = self.file_tree.item(item, "values")[0]
        item_type = self.file_tree.item(item, "values")[1]
        
        if self.current_dir.endswith(('\\', '/')):
            full_path = f"{self.current_dir}{item_name}"
        else:
            full_path = f"{self.current_dir}\\{item_name}"
            
        self.selected_path = full_path
        self.destroy()
    
    def on_cancel(self):
        """取消选择"""
        self.selected_path = None
        self.destroy()
    
    def process_data(self, data):
        """处理数据编码"""
        if isinstance(data, str):
            return data
            
        if isinstance(data, bytes):
            try:
                return data.decode('gbk', errors='replace')
            except:
                return data.decode('utf-8', errors='replace')
            
        return str(data)
    
    def sync_log(self, message):
        """同步日志到主窗口"""
        if hasattr(self.parent, 'sync_log'):
            self.parent.sync_log(message)
        else:
            print(message)

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
        self.app.root.bind("<<ModeChanged>>", self.update_mode_visibility)

        # 初始化时强制更新模式可见性
        self.update_mode_visibility(None)
        
    def create_widgets(self):
        """创建SSH配置界面控件"""
        row = 0
        
        # 模式选择
        mode_frame = ttk.LabelFrame(self.content_frame, text="运行模式", padding="10")
        mode_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        row += 1
        
        self.mode_var = tk.StringVar(value="local")  # local或ssh
        
        ttk.Radiobutton(mode_frame, text="本地模式", variable=self.mode_var, 
                      value="local", command=self.on_mode_changed).pack(side=tk.LEFT, padx=15)
        ttk.Radiobutton(mode_frame, text="SSH远程模式", variable=self.mode_var, 
                      value="ssh", command=self.on_mode_changed).pack(side=tk.LEFT, padx=15)
        
        # SSH配置控件
        self.ssh_frame = ttk.LabelFrame(self.content_frame, text="SSH配置", padding="10")
        self.ssh_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        row += 1
        
        ssh_row = 0
        ttk.Label(self.ssh_frame, text="IP地址:").grid(row=ssh_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_host_var = tk.StringVar()
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_host_var).grid(row=ssh_row, column=1, sticky=tk.EW, padx=8, pady=8)
        ssh_row += 1
        
        ttk.Label(self.ssh_frame, text="端口:").grid(row=ssh_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_port_var = tk.IntVar(value=22)
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_port_var, width=10).grid(row=ssh_row, column=1, sticky=tk.W, padx=8, pady=8)
        ssh_row += 1
        
        ttk.Label(self.ssh_frame, text="用户名:").grid(row=ssh_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_user_var = tk.StringVar()
        ttk.Entry(self.ssh_frame, textvariable=self.ssh_user_var).grid(row=ssh_row, column=1, sticky=tk.EW, padx=8, pady=8)
        ssh_row += 1
        
        ttk.Label(self.ssh_frame, text="密码:").grid(row=ssh_row, column=0, sticky=tk.W, padx=8, pady=8)
        self.ssh_password_var = tk.StringVar()
        pwd_entry = ttk.Entry(self.ssh_frame, textvariable=self.ssh_password_var, show="*")
        pwd_entry.grid(row=ssh_row, column=1, sticky=tk.EW, padx=8, pady=8)
        ssh_row += 1
        
        # 连接状态
        status_frame = ttk.Frame(self.content_frame)
        status_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1
        
        self.ssh_status_var = tk.StringVar(value="未连接")
        self.ssh_status_label = ttk.Label(status_frame, textvariable=self.ssh_status_var, foreground="red")
        self.ssh_status_label.pack(side=tk.LEFT, padx=5)
        
        # 按钮区
        btn_frame = ttk.Frame(self.content_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)
        row += 1
        
        self.ssh_btn = ttk.Button(btn_frame, text="连接", command=self.toggle_ssh_connection)
        self.ssh_btn.pack(side=tk.LEFT, padx=8)
        
        save_btn = ttk.Button(btn_frame, text="保存配置", command=self.save_config)
        save_btn.pack(side=tk.RIGHT, padx=8)
        
        # 初始更新可见性
        self.update_mode_visibility(None)
        
    def on_mode_changed(self):
        """模式改变时触发"""
        mode = self.mode_var.get()
        self.app.config["mode"] = mode
        self.app.save_config()
        self.update_mode_visibility(None)
        self.app.root.event_generate("<<ModeChanged>>", when="tail")
        
    def update_mode_visibility(self, event):
        """根据模式更新控件可见性"""
        mode = self.mode_var.get()
        if mode == "ssh":
            self.ssh_frame.grid()
            self.ssh_btn.config(state=tk.NORMAL)
        else:
            self.ssh_frame.grid_remove()
            self.ssh_btn.config(state=tk.DISABLED)
            # 如果之前处于连接状态，断开连接
            if self.app.ssh_connected:
                self.app.disconnect_ssh()
        
    def load_config(self):
        """加载SSH配置"""
        # 加载模式配置
        self.mode_var.set(self.app.config.get("mode", "local"))
        
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
        self.app.config["mode"] = self.mode_var.get()
        self.app.save_config()
        # messagebox.showinfo("成功", "配置已保存")
        
    def toggle_ssh_connection(self):
        """切换SSH连接状态"""
        if self.app.ssh_connected:
            self.app.disconnect_ssh()
        else:
            # 更新配置后再连接
            # self.save_config()
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
    """常规操作面板"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent
        
        # 创建可滚动框架
        self.scrollable_frame = ScrollableFrame(self)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame = self.scrollable_frame.content_frame
        
        # 创建内部容器
        self.inner_frame = ttk.Frame(self.content_frame)
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.inner_frame.columnconfigure(1, weight=1)
        
        # 创建控件
        self.create_widgets()
        
        # 加载配置
        self.load_config()
        
        # 绑定状态更新事件
        self.app.root.bind("<<ExecutionStatusChanged>>", self.update_exec_status)
        self.app.root.bind("<<ModeChanged>>", self.update_mode_visibility)
        
        # 强制更新滚动区域
        self.scrollable_frame.force_update()
        
    def create_widgets(self):
        """创建常规操作界面控件"""
        row = 0
        
        # Bitfile路径配置
        path_frame = ttk.Frame(self.inner_frame)
        path_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="Bitfile路径:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=0)
        self.base_dir_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.base_dir_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=0)
        self.browse_base_dir_btn = ttk.Button(path_frame, text="浏览...", width=8,
                                           command=lambda: self.browse_path(self.base_dir_var, is_directory=True))
        self.browse_base_dir_btn.grid(row=0, column=2, padx=8, pady=0)
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
        config_frame = ttk.LabelFrame(self.inner_frame, text="文件配置", padding="10")
        config_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        config_frame.columnconfigure(1, weight=1)
        row += 1
        
        config_row = 0
        # xactorscmd路径
        xactor_frame = ttk.Frame(config_frame)
        xactor_frame.grid(row=config_row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        xactor_frame.columnconfigure(1, weight=1)
        
        ttk.Label(xactor_frame, text="xactorscmd路径:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=0)
        self.xactorscmd_var = tk.StringVar()
        ttk.Entry(xactor_frame, textvariable=self.xactorscmd_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=0)
        self.browse_xactor_btn = ttk.Button(xactor_frame, text="浏览...", width=8,
                                         command=lambda: self.browse_path(self.xactorscmd_var, file_ext=".bat"))
        self.browse_xactor_btn.grid(row=0, column=2, padx=8, pady=0)

        config_row += 1
        # haps100control路径
        haps_frame = ttk.Frame(config_frame)
        haps_frame.grid(row=config_row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        haps_frame.columnconfigure(1, weight=1)
        
        ttk.Label(haps_frame, text="haps100control路径:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=0)
        self.haps_control_var = tk.StringVar()
        ttk.Entry(haps_frame, textvariable=self.haps_control_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=0)
        self.browse_haps_btn = ttk.Button(haps_frame, text="浏览...", width=8,
                                       command=lambda: self.browse_path(self.haps_control_var, file_ext=".bat"))
        self.browse_haps_btn.grid(row=0, column=2, padx=8, pady=0)
        

        config_row += 1
        
        # TCL路径配置
        self.tcl_vars = {}
        self.tcl_buttons = {}
        tcl_configs = [
            ("Load All TCL:", "load_all_tcl"),
            ("Load Master TCL:", "load_master_tcl"),
            ("Load Slave TCL:", "load_slave_tcl"),
            ("Reset All TCL:", "reset_all_tcl"),
            ("Reset Master TCL:", "reset_master_tcl"),
            ("Reset Slave TCL:", "reset_slave_tcl")
        ]
        for label_text, key in tcl_configs:
            tcl_frame = ttk.Frame(config_frame)
            tcl_frame.grid(row=config_row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
            tcl_frame.columnconfigure(1, weight=1)
            
            ttk.Label(tcl_frame, text=label_text).grid(row=0, column=0, sticky=tk.W, padx=8, pady=0)
            self.tcl_vars[key] = tk.StringVar()
            ttk.Entry(tcl_frame, textvariable=self.tcl_vars[key]).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=0)
            self.tcl_buttons[key] = ttk.Button(tcl_frame, text="浏览...", width=8,
                                           command=lambda k=key: self.browse_path(self.tcl_vars[k], file_ext=".tcl"))
            self.tcl_buttons[key].grid(row=0, column=2, padx=8, pady=0)
            config_row += 1
        
        # 保存配置按钮
        save_btn = ttk.Button(config_frame, text="保存配置", command=self.save_config)
        save_btn.grid(row=config_row, column=0, columnspan=2, pady=12)
        config_row += 1
        
        # 添加额外空白区域确保滚动条能显示
        for i in range(5):
            ttk.Label(self.inner_frame, text="").grid(row=row, column=0, pady=10)
            row += 1
        
        # 强制更新滚动区域
        self.scrollable_frame.force_update()
        
    def browse_path(self, var, is_directory=False, file_ext=""):
        """浏览选择路径并自动保存配置"""
        mode = self.app.config.get("mode", "local")
        
        if mode == "local":
            # 本地文件选择
            if is_directory:
                path = filedialog.askdirectory()
            else:
                if file_ext == ".tcl":
                    path = filedialog.askopenfilename(
                        filetypes=[("TCL文件", "*.tcl"), ("所有文件", "*.*")]
                    )
                elif file_ext == ".bat":
                    path = filedialog.askopenfilename(
                        filetypes=[("批处理文件", "*.bat"), ("所有文件", "*.*")]
                    )
                else:
                    path = filedialog.askopenfilename()
            
            if path:
                var.set(path)
                self.save_config()  # 自动保存配置
        else:
            # SSH模式下的远程文件选择
            if not self.app.ssh_connected:
                messagebox.showwarning("未连接", "请先建立SSH连接")
                return
                
            try:
                # 获取当前路径作为初始目录
                current_path = var.get().strip()
                initial_dir = os.path.dirname(current_path) if current_path else self.app.config.get("base_dir", "")
                
                # 打开远程文件浏览器
                browser = RemoteFileBrowser(self.parent, self.app.ssh_client, initial_dir)
                if browser.selected_path:
                    var.set(browser.selected_path)
                    self.save_config()  # 自动保存配置
            except Exception as e:
                messagebox.showerror("错误", f"浏览远程文件失败：{str(e)}")
        
    def update_mode_visibility(self, event):
        """根据模式更新控件状态"""
        mode = self.app.config.get("mode", "local")
        # 在两种模式下都显示浏览按钮，只是功能不同
        pass
        
    def load_config(self):
        """加载常规操作配置"""
        self.base_dir_var.set(self.app.config["base_dir"])
        self.haps_control_var.set(self.app.config["haps_control_path"])
        self.xactorscmd_var.set(self.app.config["xactorscmd_path"])
        
        for key, var in self.tcl_vars.items():
            if key in self.app.config:
                var.set(self.app.config[key])
                
        self.update_exec_status(None)
        
    def save_config(self):
        """保存常规操作配置"""
        self.app.config["base_dir"] = self.base_dir_var.get().strip()
        self.app.config["haps_control_path"] = self.haps_control_var.get().strip()
        self.app.config["xactorscmd_path"] = self.xactorscmd_var.get().strip()
        
        for key, var in self.tcl_vars.items():
            self.app.config[key] = var.get().strip()
            
        self.app.save_config()
        # messagebox.showinfo("成功", "自动化配置已保存")
        
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
        self.scrollable_frame = ScrollableFrame(self)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.content_frame = self.scrollable_frame.content_frame
        
        # 创建内部容器
        self.inner_frame = ttk.Frame(self.content_frame)
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.inner_frame.columnconfigure(1, weight=1)
        
        # 创建控件
        self.create_widgets()
        
        # 加载命令
        self.create_command_entries()
        
        # 强制更新滚动区域
        self.scrollable_frame.force_update()
        
    def create_widgets(self):
        """创建自定义命令界面控件"""
        row = 0
        
        # 默认TCL文件路径配置
        tcl_frame = ttk.Frame(self.inner_frame)
        tcl_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=8)
        tcl_frame.columnconfigure(1, weight=1)
        
        ttk.Label(tcl_frame, text="haps_control_default.tcl路径:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=0)
        self.default_tcl_var = tk.StringVar()
        ttk.Entry(tcl_frame, textvariable=self.default_tcl_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=0)
        self.browse_default_tcl_btn = ttk.Button(tcl_frame, text="浏览...", width=8,
                                              command=lambda: self.browse_path(self.default_tcl_var, file_ext=".tcl"))
        self.browse_default_tcl_btn.grid(row=0, column=2, padx=8, pady=0)
        row += 1
        
        # 命令框容器
        self.cmds_frame = ttk.LabelFrame(self.inner_frame, text="自定义远程命令", padding="10")
        self.cmds_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=(8, 12))
        row += 1
        
        # 参数提示
        tip_frame = ttk.Frame(self.inner_frame)
        tip_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        ttk.Label(tip_frame, text="提示：命令将添加到临时TCL文件执行，支持参数:\n$HAPS_DEVICE、$HAPS_SERIAL、$HAPS_HANDLE。\n如：\n\tcfg_reset_set $HAPS_HANDLE FB1.uA 0\n\tcfg_reset_set $HAPS_HANDLE FB1.uA 1\n\tcfg_scan", foreground="blue").pack(anchor=tk.W)
        row += 1
        
        # 操作按钮区
        btn_frame = ttk.Frame(self.inner_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 12))
        ttk.Button(btn_frame, text="添加命令框", command=self.add_command_entry).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="删除最后一个", command=self.remove_command_entry).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="保存命令", command=self.save_custom_commands).pack(side=tk.LEFT, padx=8)
        row += 1
        
        # 添加额外空白区域确保滚动条能显示
        for i in range(3):
            ttk.Label(self.inner_frame, text="").grid(row=row, column=0, pady=10)
            row += 1

    def save_default_tcl_path(self):
        """单独保存默认TCL路径配置"""
        self.app.config["default_tcl_path"] = self.default_tcl_var.get().strip()
        self.app.save_config()

    def browse_path(self, var, file_ext=""):
        """浏览选择路径并自动保存配置"""
        mode = self.app.config.get("mode", "local")
        
        if mode == "local":
            # 本地文件选择
            if file_ext == ".tcl":
                path = filedialog.askopenfilename(
                    filetypes=[("TCL文件", "*.tcl"), ("所有文件", "*.*")]
                )
            else:
                path = filedialog.askopenfilename()
            
            if path:
                var.set(path)
                self.save_default_tcl_path()  # 新增一个保存默认TCL路径的方法
        else:
            # SSH模式下的远程文件选择
            if not self.app.ssh_connected:
                messagebox.showwarning("未连接", "请先建立SSH连接")
                return
                
            try:
                # 获取当前路径作为初始目录
                current_path = var.get().strip()
                initial_dir = os.path.dirname(current_path) if current_path else self.app.config.get("base_dir", "")
                
                # 打开远程文件浏览器
                browser = RemoteFileBrowser(self.parent, self.app.ssh_client, initial_dir)
                if browser.selected_path:
                    var.set(browser.selected_path)
                    self.save_default_tcl_path()  # 自动保存配置
            except Exception as e:
                messagebox.showerror("错误", f"浏览远程文件失败：{str(e)}")

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
        
        # 加载默认TCL路径配置
        self.default_tcl_var.set(self.app.config.get("default_tcl_path", "tcl\\haps_control_default.tcl"))
        
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
            self.save_custom_commands()  # 同时保存默认TCL路径
            self.update_layout()

    def remove_command_entry(self):
        """删除最后一个命令框"""
        if len(self.cmd_entries) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个命令输入框")
            return
        
        cmd_frame, cmd_var, exec_btn = self.cmd_entries.pop()
        cmd_frame.destroy()
        self.save_custom_commands()  # 同时保存默认TCL路径
        self.update_layout()

    def save_custom_commands(self):
        """保存自定义命令和默认TCL路径配置"""
        # 保存自定义命令
        self.app.config["custom_commands"] = [v.get().strip() for (f, v, b) in self.cmd_entries]
        # 保存默认TCL路径
        self.app.config["default_tcl_path"] = self.default_tcl_var.get().strip()
        self.app.save_config()
        
    def update_layout(self):
        """更新布局并强制刷新滚动区域"""
        self.cmds_frame.update_idletasks()
        self.scrollable_frame.force_update()

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
        self.default_xactorscmd = "C:\\Synopsys\\protocomp-rtV-2024.09\\bin\\xactorscmd.bat"
        
        self.config = {
            "mode": "local",  # 模式配置 local/ssh
            "ssh_host": "192.168.1.1",
            "ssh_port": 22,
            "ssh_user": "admin",
            "ssh_password": "",
            "base_dir": "D:\\zxl_haps12\\mc8860\\mc20l\\mc20l_haps100_va_v2024",
            "xactorscmd_path": self.default_xactorscmd,
            "haps_control_path": "tcl\\haps100control.bat",
            "load_all_tcl": "tcl\\load.tcl",
            "load_master_tcl": "tcl\\load_master.tcl",
            "load_slave_tcl": "tcl\\load_slave.tcl",
            "reset_all_tcl": "tcl\\reset.tcl",
            "reset_master_tcl": "tcl\\reset_master.tcl",
            "reset_slave_tcl": "tcl\\reset_slave.tcl",
            "custom_commands": [""],
            "default_tcl_path": "tcl\\haps_control_default.tcl"
        }
        
        # 加载配置
        self.load_config()
        
        # SSH连接状态
        self.ssh_client = None
        self.ssh_connected = False
        
        # 命令队列和执行状态
        self.command_queue = Queue()
        self.is_processing = False
        
        # 主窗口布局
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
        self.automation_panel = AutomationPanel(self.notebook, self)
        self.ssh_panel = SSHConfigPanel(self.notebook, self)
        self.custom_commands_panel = CustomCommandsPanel(self.notebook, self)
        
        # 添加到标签页
        self.notebook.add(self.automation_panel, text="常规操作")
        self.notebook.add(self.ssh_panel, text="连接配置")
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
        self.status_bar = ttk.Label(root, text="就绪 - 本地模式", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 5))
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 初始更新状态栏
        self.update_status_bar()

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
                self.update_status_bar()
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
        self.update_status_bar()
        self.ssh_client = None
        self.root.event_generate("<<SSHStatusChanged>>", when="tail")

    def check_remote_paths(self):
        """检查远程关键路径 - 优化Bitfile路径判断逻辑"""
        base_dir = self.config.get("base_dir", "").strip()
        
        # 1. 检查Bitfile路径（只需要是目录即可）
        if base_dir:
            self.check_path(base_dir, "基础目录", is_directory=True)
        
        # 2. 检查其他文件路径
        file_paths = [
            (self.config["haps_control_path"], "haps100control.bat", False),
            (self.config["xactorscmd_path"], "xactorscmd.bat", False),
            (os.path.join(base_dir, "system", "targetsystem.tsd") if base_dir else "system\\targetsystem.tsd", "targetsystem.tsd", False),
            (self.get_full_default_tcl_path(), "haps_control_default.tcl", False)
        ]
        
        # 检查TCL脚本路径
        tcl_paths = [
            (self.config["load_all_tcl"], "Load All TCL", False),
            (self.config["load_master_tcl"], "Load Master TCL", False),
            (self.config["load_slave_tcl"], "Load Slave TCL", False),
            (self.config["reset_all_tcl"], "Reset All TCL", False),
            (self.config["reset_master_tcl"], "Reset Master TCL", False),
            (self.config["reset_slave_tcl"], "Reset Slave TCL", False)
        ]
        
        file_paths.extend(tcl_paths)
        
        # 检查所有文件路径
        for path, desc, is_dir in file_paths:
            if not path:
                continue
                
            # 先检查原始路径
            found, full_path = self.check_path(path, desc, is_dir, return_full_path=True)
            
            # 如果没找到，尝试用Bitfile路径拼接
            if not found and base_dir and not os.path.isabs(path):
                combined_path = os.path.join(base_dir, path).replace("/", "\\")
                self.sync_log(f"尝试Bitfile路径拼接：{combined_path}")
                self.check_path(combined_path, f"{desc} (Bitfile路径拼接)", is_dir)

    def check_path(self, path, description, is_directory=False, return_full_path=False):
        """检查路径是否存在"""
        try:
            # 处理路径格式
            path = path.replace("/", "\\")
            
            # 构建检查命令
            if is_directory:
                # 目录检查：存在且是目录
                cmd = f'if exist "{path}" (if exist "{path}\\*" (echo DIR_EXIST) else (echo NOT_DIR)) else (echo NOT_EXIST)'
            else:
                # 文件检查：存在且是文件
                cmd = f'if exist "{path}" (if not exist "{path}\\*" (echo FILE_EXIST) else (echo IS_DIR)) else (echo NOT_EXIST)'
            
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=10)
            output_bytes = stdout.read()
            error_bytes = stderr.read()
            
            output = self.process_data(output_bytes).strip()
            error = self.process_data(error_bytes)
            
            if error:
                self.sync_log(f"[{description}] 检查错误：{error}")
                return (False, path) if return_full_path else False
            
            # 处理检查结果
            if is_directory:
                if output == "DIR_EXIST" or "4449525f4558495354" in output:  # DIR_EXIST的十六进制
                    self.sync_log(f"[{description}] 目录存在：{path}")
                    return (True, path) if return_full_path else True
                elif output == "NOT_DIR":
                    self.sync_log(f"[{description}] 路径存在但不是目录：{path}")
                    return (False, path) if return_full_path else False
                else:
                    self.sync_log(f"[{description}] 目录不存在：{path}")
                    return (False, path) if return_full_path else False
            else:
                if output == "FILE_EXIST" or "46494C455F4558495354" in output:  # FILE_EXIST的十六进制
                    self.sync_log(f"[{description}] 文件存在：{path}")
                    return (True, path) if return_full_path else True
                elif output == "IS_DIR":
                    self.sync_log(f"[{description}] 路径存在但不是文件：{path}")
                    return (False, path) if return_full_path else False
                else:
                    self.sync_log(f"[{description}] 文件不存在：{path}")
                    return (False, path) if return_full_path else False
                    
        except Exception as e:
            self.sync_log(f"[{description}] 检查失败：{str(e)}")
            return (False, path) if return_full_path else False

    # 命令执行逻辑
    def queue_command(self, cmd_type):
        """将预设命令加入队列"""
        mode = self.config.get("mode", "local")
        
        if mode == "ssh" and not self.ssh_connected:
            messagebox.showerror("未连接", "请先建立SSH连接")
            return
        
        self.command_queue.put(('preset', cmd_type))
        self.sync_log(f"预设命令[{cmd_type}]加入队列，当前队列：{self.command_queue.qsize()}")
        
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        self.update_exec_status()

    def queue_custom_command(self, cmd_text):
        """将自定义命令加入队列"""
        mode = self.config.get("mode", "local")
        
        if mode == "ssh" and not self.ssh_connected:
            messagebox.showerror("未连接", "请先建立SSH连接")
            return
        
        cmd_text = cmd_text.strip()
        if not cmd_text:
            messagebox.showwarning("命令为空", "请输入有效的命令")
            return
        
        self.command_queue.put(('custom', cmd_text))
        self.sync_log(f"自定义命令加入队列：{cmd_text}")
        
        if not self.is_processing:
            threading.Thread(target=self.process_command_queue, daemon=True).start()
        
        self.update_exec_status()

    def process_command_queue(self, *args):
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
                        self.run_custom_tcl_command(cmd_content)
                except Exception as e:
                    self.sync_log(f"命令执行异常：{str(e)}")
                finally:
                    self.command_queue.task_done()
                    self.update_exec_status()
        finally:
            self.is_processing = False
            self.update_exec_status()
            self.sync_log("队列所有命令执行完毕")

    def get_full_default_tcl_path(self):
        """获取完整的默认TCL文件路径"""
        default_tcl_path = self.config.get("default_tcl_path", "tcl\\haps_control_default.tcl").strip()
        base_dir = self.config.get("base_dir", "").strip()
        
        # 检查是否为绝对路径
        if os.path.isabs(default_tcl_path) or (len(default_tcl_path) > 1 and default_tcl_path[1] == ':'):
            return default_tcl_path
        # 否则拼接Bitfile路径
        if base_dir:
            return os.path.join(base_dir, default_tcl_path).replace("/", "\\")
        return default_tcl_path

    def generate_temp_tcl_file(self, custom_command):
        """生成临时TCL文件"""
        try:
            # 1. 获取路径信息
            default_tcl_path = self.get_full_default_tcl_path()
            base_dir = self.config.get("base_dir", "").strip()
            temp_tcl_path = os.path.join(base_dir, "haps_control_tmp.tcl").replace("/", "\\") if base_dir else "haps_control_tmp.tcl"
            
            self.sync_log(f"默认TCL路径：{default_tcl_path}")
            self.sync_log(f"临时TCL路径：{temp_tcl_path}")
            
            # 2. 读取默认TCL文件内容
            self.sync_log("读取默认TCL文件内容...")
            
            mode = self.config.get("mode", "local")
            if mode == "local":
                # 本地模式：直接读取文件
                with open(default_tcl_path, 'r', encoding='utf-8', errors='replace') as f:
                    default_content = f.read()
            else:
                # SSH模式：通过命令读取
                # 先检查文件是否存在，如果不存在尝试用Bitfile路径拼接
                file_exists, full_path = self.check_path(default_tcl_path, "默认TCL文件", False, True)
                
                if not file_exists and base_dir and not os.path.isabs(default_tcl_path):
                    self.sync_log(f"默认TCL文件不存在，尝试Bitfile路径拼接...")
                    default_tcl_path = os.path.join(base_dir, default_tcl_path).replace("/", "\\")
                    file_exists, full_path = self.check_path(default_tcl_path, "默认TCL文件(拼接后)", False, True)
                
                if not file_exists:
                    raise Exception(f"默认TCL文件不存在：{default_tcl_path}")
                
                cat_cmd = f'type "{full_path}"'  # Windows系统使用type命令
                stdin, stdout, stderr = self.ssh_client.exec_command(cat_cmd, timeout=30)
                default_content_bytes = stdout.read()
                error_bytes = stderr.read()
                
                error = self.process_data(error_bytes)
                if error:
                    raise Exception(f"读取默认TCL文件错误：{error}")
                
                # 处理内容编码
                try:
                    default_content = default_content_bytes.decode('gbk', errors='replace')
                except:
                    default_content = default_content_bytes.decode('utf-8', errors='replace')
            
            # 3. 构建临时文件内容
            temp_content = f"{default_content}\n"  # 默认内容
            temp_content += f"{custom_command}\n"  # 自定义命令
            temp_content += "cfg_close $HAPS_HANDLE\n"  # 关闭句柄命令
            
            # 4. 写入临时文件
            self.sync_log("生成临时TCL文件...")
            if mode == "local":
                # 本地模式：直接写入文件
                with open(temp_tcl_path, 'w', encoding='utf-8') as f:
                    f.write(temp_content)
            else:
                # SSH模式：使用SFTP写入
                sftp = self.ssh_client.open_sftp()
                
                # 确保目录存在
                temp_dir = os.path.dirname(temp_tcl_path)
                if temp_dir:
                    try:
                        sftp.stat(temp_dir)
                    except FileNotFoundError:
                        self.sync_log(f"创建目录：{temp_dir}")
                        # 递归创建目录的函数
                        def mkdir_p(sftp, remote_directory):
                            if remote_directory == '/':
                                sftp.chdir('/')
                                return
                            if remote_directory == '':
                                return
                            try:
                                sftp.stat(remote_directory)
                            except FileNotFoundError:
                                dirname, basename = os.path.split(remote_directory.rstrip('/'))
                                mkdir_p(sftp, dirname)
                                sftp.mkdir(basename)
                                sftp.chdir(basename)
                                return
                        mkdir_p(sftp, temp_dir)
                
                # 写入文件内容
                with sftp.file(temp_tcl_path, 'w') as f:
                    # 确保使用正确的换行符
                    f.write(temp_content.replace('\n', '\r\n'))
                
                sftp.close()
            
            self.sync_log(f"临时TCL文件生成成功：{temp_tcl_path}")
            return temp_tcl_path
            
        except Exception as e:
            self.sync_log(f"生成临时TCL文件失败：{str(e)}")
            raise

    def run_custom_tcl_command(self, custom_command):
        """执行自定义命令"""
        try:
            # 1. 验证必要路径配置
            haps_ctrl = self.config["haps_control_path"]
            xactorscmd = self.config["xactorscmd_path"]
            base_dir = self.config.get("base_dir", "").strip()
            
            if not haps_ctrl or not xactorscmd:
                raise ValueError("haps100control和xactorscmd路径不能为空")
            
            # 处理haps_control路径
            resolved_haps = self.resolve_path(haps_ctrl, base_dir)
            # 处理xactorscmd路径
            resolved_xactor = self.resolve_path(xactorscmd, base_dir)
            
            # 2. 生成临时TCL文件
            temp_tcl_path = self.generate_temp_tcl_file(custom_command)
            
            # 3. 构建执行命令
            mode = self.config.get("mode", "local")
            
            # 构建命令
            if base_dir:
                cmd = f'cd /d "{base_dir}" && call "{resolved_haps}" "{resolved_xactor}" "{temp_tcl_path}"'
            else:
                cmd = f'call "{resolved_haps}" "{resolved_xactor}" "{temp_tcl_path}"'
            
            self.sync_log(f"执行命令：{cmd}")
            
            # 4. 执行命令
            if mode == "local":
                # 本地模式：使用subprocess执行
                import subprocess
                import shlex
                
                try:
                    # 执行命令
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='gbk',
                        errors='replace'
                    )
                    
                    # 实时输出
                    for line in process.stdout:
                        self.sync_log(f"输出：{line.rstrip()}")
                    
                    # 等待完成
                    return_code = process.wait()
                    
                    if return_code == 0:
                        self.sync_log(f"自定义命令执行成功，返回码：{return_code}")
                        return True, f"返回码{return_code}"
                    else:
                        self.sync_log(f"自定义命令执行失败，返回码：{return_code}")
                        return False, f"返回码{return_code}"
                        
                except Exception as e:
                    return False, str(e)
            else:
                # SSH模式：使用SSH执行
                success, msg = self.run_remote_command(cmd)[:2]
                if success:
                    self.sync_log(f"自定义命令执行成功：{msg}")
                else:
                    self.sync_log(f"自定义命令执行失败：{msg}")
                    messagebox.showerror("执行失败", f"自定义命令失败：{msg}")
                return success, msg
                
        except ValueError as e:
            self.sync_log(f"参数错误：{str(e)}")
            messagebox.showerror("参数错误", str(e))
            return False, str(e)
        except Exception as e:
            self.sync_log(f"自定义命令执行异常：{str(e)}")
            messagebox.showerror("执行异常", str(e))
            return False, str(e)

    def run_haps_command(self, cmd_type):
        """执行HAPS预设命令"""
        try:
            haps_ctrl = self.config["haps_control_path"]
            xactorscmd = self.config["xactorscmd_path"]
            base_dir = self.config["base_dir"]
            mode = self.config.get("mode", "local")
            
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
            
            # 处理路径：先检查原始路径，找不到则尝试用Bitfile路径拼接
            resolved_tcl = self.resolve_path(tcl_script, base_dir)
            if not resolved_tcl:
                raise ValueError(f"找不到{cmd_type}的TCL脚本：{tcl_script}")
            
            # 处理haps_control路径
            resolved_haps = self.resolve_path(haps_ctrl, base_dir)
            # 处理xactorscmd路径
            resolved_xactor = self.resolve_path(xactorscmd, base_dir)
            
            # 构建命令
            if base_dir:
                cmd = f'cd /d "{base_dir}" && call "{resolved_haps}" "{resolved_xactor}" "{resolved_tcl}"'
            else:
                cmd = f'call "{resolved_haps}" "{resolved_xactor}" "{resolved_tcl}"'
            
            self.sync_log(f"构建命令：{cmd}")
            
            # 执行命令
            if mode == "local":
                # 本地模式：使用subprocess执行
                import subprocess
                
                try:
                    # 执行命令
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='gbk',
                        errors='replace'
                    )
                    
                    # 实时输出
                    for line in process.stdout:
                        self.sync_log(f"输出：{line.rstrip()}")
                    
                    # 等待完成
                    return_code = process.wait()
                    
                    if return_code == 0:
                        self.sync_log(f"预设命令[{cmd_type}]执行成功，返回码：{return_code}")
                        return True, f"返回码{return_code}"
                    else:
                        self.sync_log(f"预设命令[{cmd_type}]执行失败，返回码：{return_code}")
                        messagebox.showerror("执行失败", f"{cmd_type}命令失败，返回码：{return_code}")
                        return False, f"返回码{return_code}"
                        
                except Exception as e:
                    error_msg = str(e)
                    self.sync_log(f"预设命令[{cmd_type}]执行异常：{error_msg}")
                    messagebox.showerror("执行异常", error_msg)
                    return False, error_msg
            else:
                # SSH模式：使用SSH执行
                success, msg = self.run_remote_command(cmd)[:2]
                if success:
                    self.sync_log(f"预设命令[{cmd_type}]执行成功：{msg}")
                else:
                    self.sync_log(f"预设命令[{cmd_type}]执行失败：{msg}")
                    messagebox.showerror("执行失败", f"{cmd_type}命令失败：{msg}")
                return success, msg
                
        except ValueError as e:
            self.sync_log(f"参数错误：{str(e)}")
            messagebox.showerror("参数错误", str(e))
            return False, str(e)
        except Exception as e:
            self.sync_log(f"HAPS命令执行异常：{str(e)}")
            messagebox.showerror("执行异常", str(e))
            return False, str(e)

    def resolve_path(self, path, base_dir):
        """解析路径：如果路径不存在，尝试用Bitfile路径拼接"""
        if not path:
            return None
            
        mode = self.config.get("mode", "local")
        resolved_path = path
        
        # 检查路径是否存在
        if mode == "local":
            # 本地模式检查
            if not os.path.exists(resolved_path):
                # 尝试用Bitfile路径拼接
                if base_dir and not os.path.isabs(resolved_path):
                    combined_path = os.path.join(base_dir, resolved_path)
                    if os.path.exists(combined_path):
                        self.sync_log(f"路径不存在，使用Bitfile路径拼接：{combined_path}")
                        resolved_path = combined_path
                    else:
                        self.sync_log(f"路径不存在：{resolved_path} 和 {combined_path}")
                        return None
                else:
                    self.sync_log(f"路径不存在：{resolved_path}")
                    return None
        else:
            # SSH模式检查
            if not self.ssh_connected:
                return resolved_path
                
            # 先检查原始路径
            exists, full_path = self.check_path(resolved_path, "路径解析", False, True)
            
            # 如果不存在，尝试用Bitfile路径拼接
            if not exists and base_dir and not os.path.isabs(resolved_path):
                combined_path = os.path.join(base_dir, resolved_path).replace("/", "\\")
                exists, full_path = self.check_path(combined_path, "路径解析(拼接后)", False, True)
                if exists:
                    self.sync_log(f"路径不存在，使用Bitfile路径拼接：{combined_path}")
                    resolved_path = combined_path
                else:
                    self.sync_log(f"路径不存在：{resolved_path} 和 {combined_path}")
                    return None
            elif not exists:
                self.sync_log(f"路径不存在：{resolved_path}")
                return None
                
        return resolved_path

    def run_remote_command(self, cmd):
        """执行远程命令（SSH模式）"""
        try:
            # 执行命令时指定终端类型，避免某些服务器默认编码问题
            channel = self.ssh_client.get_transport().open_session()
            channel.set_combine_stderr(True)  # 合并stderr到stdout
            channel.exec_command(cmd)
            
            output = []
            
            # 直接读取原始字节流，使用GBK解码
            def read_stream():
                while True:
                    data = channel.recv(1024)
                    if not data:
                        break
                    # 强制使用GBK解码
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
        """处理数据编码"""
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
        self.update_status_bar()

    def update_status_bar(self):
        """更新状态栏"""
        mode = self.config.get("mode", "local")
        if mode == "ssh":
            if self.ssh_connected:
                self.status_bar.config(text=f"SSH已连接 - {self.config['ssh_host']}")
            else:
                self.status_bar.config(text="SSH未连接")
        else:
            if self.is_processing:
                queue_size = self.command_queue.qsize()
                self.status_bar.config(text=f"本地模式 - 执行中，剩余：{queue_size}")
            else:
                self.status_bar.config(text="本地模式 - 就绪")

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
