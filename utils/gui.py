import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import json5
import threading
import queue
import logging

import utils.static as static
from utils.static import CONFIG_FILE_PATH, STEAM_ACCOUNT_INFO_FILE_PATH, DEFAULT_CONFIG_JSON, DEFAULT_STEAM_ACCOUNT_JSON
from utils.logger import gui_log_queue, setup_gui_logging, logger

# UI Theme Palette
BG_MAIN = "#121214"
BG_CARD = "#1A1A1E"
BG_ENTRY = "#2A2A30"
BORDER_COLOR = "#2C2C35"
FG_PRIMARY = "#E2E2E9"
FG_SECONDARY = "#8E8E9F"
ACCENT_BLUE = "#3A86FF"
ACCENT_GREEN = "#06D6A0"
ACCENT_RED = "#EF476F"
ACCENT_YELLOW = "#FFD166"

class SteamautoGUI:
    def __init__(self, main_runner_func):
        self.main_runner_func = main_runner_func
        self.root = tk.Tk()
        self.root.title("Steamauto 可视化控制台")
        self.root.geometry("1000x680")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)
        
        # Keep track of UI panels
        self.panels = {}
        self.current_panel = None
        self.is_running = False
        self.worker_thread = None
        
        # Load configs
        self.config_data = self.load_json_config(CONFIG_FILE_PATH, DEFAULT_CONFIG_JSON)
        self.account_data = self.load_json_config(STEAM_ACCOUNT_INFO_FILE_PATH, DEFAULT_STEAM_ACCOUNT_JSON)
        
        self.build_ui()
        self.switch_panel("dashboard")
        
        # Start queue listener for logs
        setup_gui_logging()
        static.is_gui_mode = True
        static.no_pause = True  # Prevent terminal inputs
        
        self.poll_logs()
        
    def load_json_config(self, file_path, default_content):
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(default_content)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json5.load(f)
        except Exception as e:
            messagebox.showerror("配置载入错误", f"解析 {os.path.basename(file_path)} 失败！已加载默认模板。")
            return json5.loads(default_content)

    def save_configs(self):
        try:
            self.gather_gui_inputs()
            
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json5.dump(self.config_data, f, indent=2, ensure_ascii=False)
                
            with open(STEAM_ACCOUNT_INFO_FILE_PATH, "w", encoding="utf-8") as f:
                json5.dump(self.account_data, f, indent=2, ensure_ascii=False)
                
            logger.info("系统配置文件保存成功！")
            return True
        except Exception as e:
            messagebox.showerror("保存失败", f"保存配置时发生异常：\n{str(e)}")
            return False

    def build_ui(self):
        # 1. Left Sidebar
        self.sidebar = tk.Frame(self.root, bg=BG_CARD, width=220, bd=0)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # Logo/Title
        title_label = tk.Label(self.sidebar, text="Steamauto", bg=BG_CARD, fg=ACCENT_BLUE, font=("Segoe UI", 18, "bold"))
        title_label.pack(pady=(20, 5))
        sub_label = tk.Label(self.sidebar, text="自动发货与租赁系统", bg=BG_CARD, fg=FG_SECONDARY, font=("Microsoft YaHei", 9))
        sub_label.pack(pady=(0, 20))
        
        # Sidebar Menu Items
        self.menu_buttons = {}
        menu_items = [
            ("dashboard", "📊 控制中心"),
            ("account", "👤 Steam 账号"),
            ("buff", "🔴 网易 BUFF"),
            ("uu", "🟢 悠悠有品"),
            ("eco", "🔵 ECOSteam"),
            ("system", "⚙️ 系统与代理")
        ]
        
        for p_id, text in menu_items:
            btn = tk.Button(
                self.sidebar, text=text, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_ENTRY, 
                activeforeground=FG_PRIMARY, bd=0, relief="flat", font=("Microsoft YaHei", 10),
                anchor="w", padx=20, pady=10, command=lambda p=p_id: self.switch_panel(p)
            )
            btn.pack(fill=tk.X, pady=1)
            self.menu_buttons[p_id] = btn

        # Separator line
        sep = tk.Frame(self.sidebar, bg=BORDER_COLOR, height=1)
        sep.pack(fill=tk.X, pady=20)
        
        # Control Buttons
        self.btn_save = tk.Button(
            self.sidebar, text="💾 保存当前配置", bg=ACCENT_BLUE, fg="white", 
            activebackground="#2563EB", activeforeground="white", bd=0, relief="flat", 
            font=("Microsoft YaHei", 10, "bold"), pady=8, command=self.save_configs
        )
        self.btn_save.pack(fill=tk.X, padx=15, pady=5)
        
        self.btn_toggle = tk.Button(
            self.sidebar, text="🚀 启动自动发货", bg=ACCENT_GREEN, fg="white", 
            activebackground="#059669", activeforeground="white", bd=0, relief="flat", 
            font=("Microsoft YaHei", 10, "bold"), pady=8, command=self.toggle_worker
        )
        self.btn_toggle.pack(fill=tk.X, padx=15, pady=5)
        
        self.status_indicator = tk.Label(self.sidebar, text="● 状态: 未运行", bg=BG_CARD, fg=ACCENT_RED, font=("Microsoft YaHei", 9, "bold"))
        self.status_indicator.pack(side=tk.BOTTOM, pady=20)

        # 2. Right Workspace Frame
        self.workspace = tk.Frame(self.root, bg=BG_MAIN)
        self.workspace.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Sub-frames in workspace
        self.create_dashboard_panel()
        self.create_account_panel()
        self.create_buff_panel()
        self.create_uu_panel()
        self.create_eco_panel()
        self.create_system_panel()

    def switch_panel(self, panel_id):
        if self.current_panel:
            self.current_panel.pack_forget()
            
        # Reset menu active style
        for p, btn in self.menu_buttons.items():
            btn.configure(bg=BG_CARD, fg=FG_PRIMARY)
            
        self.menu_buttons[panel_id].configure(bg=BG_ENTRY, fg=ACCENT_BLUE)
        self.current_panel = self.panels[panel_id]
        self.current_panel.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # ================= PANEL CREATORS =================

    def create_dashboard_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["dashboard"] = panel
        
        header = tk.Label(panel, text="控制中心", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 10))
        
        # Console Log Area Label
        lbl_console = tk.Label(panel, text="实时日志终端 (Real-time Logs):", bg=BG_MAIN, fg=FG_SECONDARY, font=("Microsoft YaHei", 9))
        lbl_console.pack(anchor="w", pady=(0, 5))
        
        # Log Text Box
        log_frame = tk.Frame(panel, bg="#0C0C0D", bd=1, relief="solid", highlightthickness=0)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(
            log_frame, bg="#0C0C0D", fg=FG_PRIMARY, insertbackground=FG_PRIMARY,
            font=("Courier New", 9), relief="flat", wrap="word"
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Define log tags for colors
        self.log_text.tag_config("INFO", foreground="#10B981")
        self.log_text.tag_config("WARNING", foreground="#F59E0B")
        self.log_text.tag_config("ERROR", foreground="#EF4444")
        self.log_text.tag_config("CRITICAL", foreground="#EF4444", background="#3F0000")
        self.log_text.tag_config("DEBUG", foreground="#6B7280")
        
        # Quick actions card
        tips_frame = tk.Frame(panel, bg=BG_CARD, bd=0, padx=15, pady=10)
        tips_frame.pack(fill=tk.X, pady=(15, 0))
        
        tips_label = tk.Label(
            tips_frame, text="💡 温馨提示：如果未配置Steam令牌文件，程序在首次账密登录时会在上方弹出验证码输入窗，请留意悬浮框。",
            bg=BG_CARD, fg=FG_SECONDARY, font=("Microsoft YaHei", 9), anchor="w"
        )
        tips_label.pack(fill=tk.X)

    def create_account_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["account"] = panel
        
        header = tk.Label(panel, text="Steam 账户登录设置", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 20))
        
        form_frame = tk.Frame(panel, bg=BG_CARD, padx=20, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Steam Username
        self.lbl_user = tk.Label(form_frame, text="Steam 用户名", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10))
        self.lbl_user.grid(row=0, column=0, sticky="w", pady=10)
        self.ent_user = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=40)
        self.ent_user.grid(row=0, column=1, padx=20, pady=10, ipady=4)
        self.ent_user.insert(0, self.account_data.get("steam_username", ""))
        
        # Steam Password
        self.lbl_pwd = tk.Label(form_frame, text="Steam 密码", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10))
        self.lbl_pwd.grid(row=1, column=0, sticky="w", pady=10)
        
        pwd_frame = tk.Frame(form_frame, bg=BG_CARD)
        pwd_frame.grid(row=1, column=1, padx=20, pady=10, sticky="w")
        
        self.ent_pwd = tk.Entry(pwd_frame, show="*", bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=40)
        self.ent_pwd.pack(side=tk.LEFT, ipady=4)
        self.ent_pwd.insert(0, self.account_data.get("steam_password", ""))
        
        self.pwd_visible = False
        def toggle_pwd():
            self.pwd_visible = not self.pwd_visible
            self.ent_pwd.config(show="" if self.pwd_visible else "*")
            self.btn_show_pwd.config(text="🙈 隐藏" if self.pwd_visible else "👁 显示")
            
        self.btn_show_pwd = tk.Button(pwd_frame, text="👁 显示", bg=BG_ENTRY, fg=FG_SECONDARY, activebackground=BG_ENTRY, activeforeground=FG_PRIMARY, bd=0, font=("Microsoft YaHei", 9), command=toggle_pwd)
        self.btn_show_pwd.pack(side=tk.LEFT, padx=10)
        
        # shared_secret
        self.lbl_shared = tk.Label(form_frame, text="shared_secret", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10))
        self.lbl_shared.grid(row=2, column=0, sticky="w", pady=10)
        self.ent_shared = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=40)
        self.ent_shared.grid(row=2, column=1, padx=20, pady=10, ipady=4)
        self.ent_shared.insert(0, self.account_data.get("shared_secret", ""))
        
        lbl_shared_desc = tk.Label(form_frame, text="用于自动生成手机验证码的令牌主密钥", bg=BG_CARD, fg=FG_SECONDARY, font=("Microsoft YaHei", 8))
        lbl_shared_desc.grid(row=2, column=2, sticky="w", pady=10)
        
        # identity_secret
        self.lbl_identity = tk.Label(form_frame, text="identity_secret", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10))
        self.lbl_identity.grid(row=3, column=0, sticky="w", pady=10)
        self.ent_identity = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=40)
        self.ent_identity.grid(row=3, column=1, padx=20, pady=10, ipady=4)
        self.ent_identity.insert(0, self.account_data.get("identity_secret", ""))
        
        lbl_identity_desc = tk.Label(form_frame, text="用于自动确认交易报价的二次确认密钥", bg=BG_CARD, fg=FG_SECONDARY, font=("Microsoft YaHei", 8))
        lbl_identity_desc.grid(row=3, column=2, sticky="w", pady=10)

    def create_buff_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["buff"] = panel
        
        header = tk.Label(panel, text="网易 BUFF 自动发货设置", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 20))
        
        form_frame = tk.Frame(panel, bg=BG_CARD, padx=20, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        buff_conf = self.config_data.get("buff_auto_accept_offer", {})
        
        # Enable Switch
        self.var_buff_enable = tk.BooleanVar(value=buff_conf.get("enable", True))
        chk_enable = tk.Checkbutton(
            form_frame, text="启用 BUFF 自动发货报价功能", variable=self.var_buff_enable,
            bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY,
            selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")
        )
        chk_enable.grid(row=0, column=0, columnspan=2, sticky="w", pady=15)
        
        # Interval
        tk.Label(form_frame, text="检查新报价间隔 (秒)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=10)
        self.ent_buff_interval = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_buff_interval.grid(row=1, column=1, sticky="w", padx=20, pady=10, ipady=4)
        self.ent_buff_interval.insert(0, str(buff_conf.get("interval", 300)))
        
        # Dota2 support
        self.var_buff_dota = tk.BooleanVar(value=buff_conf.get("dota2_support", False))
        chk_dota = tk.Checkbutton(
            form_frame, text="开启 Dota2 支持", variable=self.var_buff_dota,
            bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY,
            selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10)
        )
        chk_dota.grid(row=2, column=0, columnspan=2, sticky="w", pady=10)
        
        # Use proxies
        self.var_buff_proxy = tk.BooleanVar(value=buff_conf.get("use_proxies", False))
        chk_proxy = tk.Checkbutton(
            form_frame, text="使用代理连接 BUFF (读取全局代理配置)", variable=self.var_buff_proxy,
            bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY,
            selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10)
        )
        chk_proxy.grid(row=3, column=0, columnspan=2, sticky="w", pady=10)

    def create_uu_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["uu"] = panel
        
        header = tk.Label(panel, text="悠悠有品配置", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 10))
        
        # Tab notebook for UU's multiple features
        uu_notebook = ttk.Notebook(panel)
        uu_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Stylise Notebook
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_CARD, foreground=FG_PRIMARY, borderwidth=0, padding=[15, 6])
        style.map("TNotebook.Tab", background=[("selected", BG_ENTRY)], foreground=[("selected", ACCENT_BLUE)])
        
        # Tab 1: UU Offer
        tab_offer = tk.Frame(uu_notebook, bg=BG_CARD, padx=20, pady=20)
        uu_notebook.add(tab_offer, text=" 📤 自动发货 ")
        uu_offer_conf = self.config_data.get("uu_auto_accept_offer", {})
        
        self.var_uu_offer_enable = tk.BooleanVar(value=uu_offer_conf.get("enable", False))
        tk.Checkbutton(tab_offer, text="启用悠悠有品自动发货功能", variable=self.var_uu_offer_enable, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=10)
        
        tk.Label(tab_offer, text="轮询检查新报价间隔 (秒)：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(10, 2))
        self.ent_uu_offer_int = tk.Entry(tab_offer, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=20)
        self.ent_uu_offer_int.pack(anchor="w", pady=(0, 10), ipady=3)
        self.ent_uu_offer_int.insert(0, str(uu_offer_conf.get("interval", 300)))
        
        self.var_uu_offer_proxy = tk.BooleanVar(value=uu_offer_conf.get("use_proxies", False))
        tk.Checkbutton(tab_offer, text="使用代理连接悠悠有品", variable=self.var_uu_offer_proxy, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10)).pack(anchor="w", pady=10)

        # Tab 2: UU Lease
        tab_lease = tk.Frame(uu_notebook, bg=BG_CARD, padx=20, pady=20)
        uu_notebook.add(tab_lease, text=" 🔑 自动租赁上架 ")
        uu_lease_conf = self.config_data.get("uu_auto_lease_item", {})
        
        self.var_uu_lease_enable = tk.BooleanVar(value=uu_lease_conf.get("enable", False))
        tk.Checkbutton(tab_lease, text="启用悠悠自动租赁上架", variable=self.var_uu_lease_enable, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        
        tk.Label(tab_lease, text="最长租赁天数", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=1, column=0, sticky="w", pady=5)
        self.ent_uu_lease_days = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_lease_days.grid(row=1, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_days.insert(0, str(uu_lease_conf.get("lease_max_days", 60)))
        
        tk.Label(tab_lease, text="最低上架过滤价格 (元)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=2, column=0, sticky="w", pady=5)
        self.ent_uu_lease_price = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_lease_price.grid(row=2, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_price.insert(0, str(uu_lease_conf.get("filter_price", 100)))
        
        tk.Label(tab_lease, text="定时运行时间 (如 17:30)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=3, column=0, sticky="w", pady=5)
        self.ent_uu_lease_time = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_lease_time.grid(row=3, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_time.insert(0, uu_lease_conf.get("run_time", "17:30"))
        
        tk.Label(tab_lease, text="改价轮询间隔 (分钟)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=4, column=0, sticky="w", pady=5)
        self.ent_uu_lease_int = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_lease_int.grid(row=4, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_int.insert(0, str(uu_lease_conf.get("interval", 31)))
        
        tk.Label(tab_lease, text="不出租商品黑名单(逗号隔开)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=5, column=0, sticky="w", pady=5)
        self.ent_uu_lease_black = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=35)
        self.ent_uu_lease_black.grid(row=5, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_black.insert(0, ", ".join(uu_lease_conf.get("filter_name", [])))
        
        self.var_uu_lease_fix = tk.BooleanVar(value=uu_lease_conf.get("enable_fix_lease_ratio", False))
        tk.Checkbutton(tab_lease, text="按现价固定比例设定租金", variable=self.var_uu_lease_fix, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        
        tk.Label(tab_lease, text="固定出租价格比例 (如 0.001)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=7, column=0, sticky="w", pady=5)
        self.ent_uu_lease_ratio = tk.Entry(tab_lease, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_lease_ratio.grid(row=7, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_lease_ratio.insert(0, str(uu_lease_conf.get("fix_lease_ratio", 0.001)))

        # Tab 3: UU Sell
        tab_sell = tk.Frame(uu_notebook, bg=BG_CARD, padx=20, pady=20)
        uu_notebook.add(tab_sell, text=" 🏷️ 自动出售上架 ")
        uu_sell_conf = self.config_data.get("uu_auto_sell_item", {})
        
        self.var_uu_sell_enable = tk.BooleanVar(value=uu_sell_conf.get("enable", False))
        tk.Checkbutton(tab_sell, text="启用自动出售上架配置", variable=self.var_uu_sell_enable, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        
        tk.Label(tab_sell, text="定时运行时间 (如 15:30)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=1, column=0, sticky="w", pady=5)
        self.ent_uu_sell_time = tk.Entry(tab_sell, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_sell_time.grid(row=1, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_sell_time.insert(0, uu_sell_conf.get("run_time", "15:30"))
        
        tk.Label(tab_sell, text="出售请求市场间隔 (分钟)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=2, column=0, sticky="w", pady=5)
        self.ent_uu_sell_req_int = tk.Entry(tab_sell, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_sell_req_int.grid(row=2, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_sell_req_int.insert(0, str(uu_sell_conf.get("sell_interval", 20)))
        
        tk.Label(tab_sell, text="已上架改价轮询间隔 (分钟)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=3, column=0, sticky="w", pady=5)
        self.ent_uu_sell_int = tk.Entry(tab_sell, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_sell_int.grid(row=3, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_sell_int.insert(0, str(uu_sell_conf.get("interval", 51)))
        
        tk.Label(tab_sell, text="最高限制上架价 (0代表无限制)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=4, column=0, sticky="w", pady=5)
        self.ent_uu_sell_max = tk.Entry(tab_sell, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_uu_sell_max.grid(row=4, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_sell_max.insert(0, str(uu_sell_conf.get("max_on_sale_price", 1000)))
        
        tk.Label(tab_sell, text="出售商品名字列表(英文逗号隔开)", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).grid(row=5, column=0, sticky="w", pady=5)
        self.ent_uu_sell_names = tk.Entry(tab_sell, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=35)
        self.ent_uu_sell_names.grid(row=5, column=1, sticky="w", padx=10, pady=5, ipady=3)
        self.ent_uu_sell_names.insert(0, ", ".join(uu_sell_conf.get("name", [])))
        
        self.var_uu_sell_adj = tk.BooleanVar(value=uu_sell_conf.get("use_price_adjustment", True))
        tk.Checkbutton(tab_sell, text="开启自动压价功能 (-0.01)", variable=self.var_uu_sell_adj, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)

    def create_eco_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["eco"] = panel
        
        header = tk.Label(panel, text="ECOSteam.cn 开放平台插件", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 20))
        
        form_frame = tk.Frame(panel, bg=BG_CARD, padx=20, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        eco_conf = self.config_data.get("ecosteam", {})
        
        # Enable Switch
        self.var_eco_enable = tk.BooleanVar(value=eco_conf.get("enable", False))
        chk_enable = tk.Checkbutton(
            form_frame, text="启用 ECOSteam 插件支持", variable=self.var_eco_enable,
            bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY,
            selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")
        )
        chk_enable.grid(row=0, column=0, columnspan=2, sticky="w", pady=10)
        
        # partnerId
        tk.Label(form_frame, text="身份合作 ID (partnerId)：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=8)
        self.ent_eco_partner = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=35)
        self.ent_eco_partner.grid(row=1, column=1, sticky="w", padx=20, pady=8, ipady=3)
        self.ent_eco_partner.insert(0, eco_conf.get("partnerId", ""))
        
        # auto accept interval
        accept_conf = eco_conf.get("auto_accept_offer", {})
        tk.Label(form_frame, text="自动接收报价轮询 (秒)：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10)).grid(row=2, column=0, sticky="w", pady=8)
        self.ent_eco_int = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_eco_int.grid(row=2, column=1, sticky="w", padx=20, pady=8, ipady=3)
        self.ent_eco_int.insert(0, str(accept_conf.get("interval", 30)))
        
        # Sync interval & QPS
        tk.Label(form_frame, text="同步商品价格间隔 (秒)：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 10)).grid(row=3, column=0, sticky="w", pady=8)
        self.ent_eco_sync = tk.Entry(form_frame, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=15)
        self.ent_eco_sync.grid(row=3, column=1, sticky="w", padx=20, pady=8, ipady=3)
        self.ent_eco_sync.insert(0, str(eco_conf.get("sync_interval", 60)))
        
        # Tips / Note
        lbl_notes = tk.Label(
            form_frame, text="⚠️ 提示：ECOSteam 插件需要单独在 config 目录创建 rsakey.txt 填入 RSA 私钥。",
            bg=BG_CARD, fg=ACCENT_YELLOW, font=("Microsoft YaHei", 9), justify=tk.LEFT
        )
        lbl_notes.grid(row=4, column=0, columnspan=2, sticky="w", pady=20)

    def create_system_panel(self):
        panel = tk.Frame(self.workspace, bg=BG_MAIN)
        self.panels["system"] = panel
        
        header = tk.Label(panel, text="系统、网络与通知设置", bg=BG_MAIN, fg=FG_PRIMARY, font=("Microsoft YaHei", 16, "bold"))
        header.pack(anchor="w", pady=(0, 10))
        
        sys_notebook = ttk.Notebook(panel)
        sys_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Proxy & Network
        tab_net = tk.Frame(sys_notebook, bg=BG_CARD, padx=20, pady=20)
        sys_notebook.add(tab_net, text=" 🌐 网络与代理 ")
        
        self.var_ssl_ignore = tk.BooleanVar(value=self.config_data.get("steam_login_ignore_ssl_error", False))
        tk.Checkbutton(tab_net, text="忽略 Steam 登录 SSL 证书验证错误", variable=self.var_ssl_ignore, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=5)
        
        self.var_steam_acc = tk.BooleanVar(value=self.config_data.get("steam_local_accelerate", False))
        tk.Checkbutton(tab_net, text="开启内置本地加速功能 (需配合上述忽略SSL开启)", variable=self.var_steam_acc, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=5)
        
        self.var_use_proxy = tk.BooleanVar(value=self.config_data.get("use_proxies", False))
        tk.Checkbutton(tab_net, text="手动指定 Steam 全局代理", variable=self.var_use_proxy, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=5)
        
        proxies = self.config_data.get("proxies", {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})
        tk.Label(tab_net, text="HTTP 代理地址:", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(10, 2))
        self.ent_proxy_http = tk.Entry(tab_net, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=45)
        self.ent_proxy_http.pack(anchor="w", pady=(0, 5), ipady=3)
        self.ent_proxy_http.insert(0, proxies.get("http", ""))
        
        tk.Label(tab_net, text="HTTPS 代理地址:", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(5, 2))
        self.ent_proxy_https = tk.Entry(tab_net, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=45)
        self.ent_proxy_https.pack(anchor="w", pady=(0, 5), ipady=3)
        self.ent_proxy_https.insert(0, proxies.get("https", ""))

        # Tab 2: Notifications
        tab_notify = tk.Frame(sys_notebook, bg=BG_CARD, padx=20, pady=20)
        sys_notebook.add(tab_notify, text=" 🔔 通知推送 (Apprise) ")
        
        notify_conf = self.config_data.get("notify_service", {})
        
        tk.Label(tab_notify, text="通知服务地址 (Apprise 格式，每行一个)：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(0, 5))
        self.txt_notifiers = tk.Text(tab_notify, bg=BG_ENTRY, fg=FG_PRIMARY, insertbackground=FG_PRIMARY, bd=0, font=("Segoe UI", 9), height=5, width=60)
        self.txt_notifiers.pack(anchor="w", fill=tk.BOTH, expand=True, pady=(0, 10))
        self.txt_notifiers.insert("1.0", "\n".join(notify_conf.get("notifiers", [])))
        
        # Title prefix
        tk.Label(tab_notify, text="自定义通知标题前缀：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(0, 2))
        self.ent_notify_title = tk.Entry(tab_notify, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=30)
        self.ent_notify_title.pack(anchor="w", pady=(0, 10), ipady=3)
        self.ent_notify_title.insert(0, notify_conf.get("custom_title", ""))
        
        self.var_notify_steam = tk.BooleanVar(value=notify_conf.get("include_steam_info", True))
        tk.Checkbutton(tab_notify, text="通知内容包含 Steam 账户敏感细节", variable=self.var_notify_steam, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=5)
        
        # Tab 3: Other settings
        tab_other = tk.Frame(sys_notebook, bg=BG_CARD, padx=20, pady=20)
        sys_notebook.add(tab_other, text=" 📝 运行与日志 ")
        
        # Steam Auto Accept Gift
        gift_conf = self.config_data.get("steam_auto_accept_offer", {})
        self.var_gift_enable = tk.BooleanVar(value=gift_conf.get("enable", True))
        tk.Checkbutton(tab_other, text="开启自动接受 Steam 礼物报价 (绿色安全报价)", variable=self.var_gift_enable, bg=BG_CARD, fg=FG_PRIMARY, activebackground=BG_CARD, activeforeground=FG_PRIMARY, selectcolor=BG_ENTRY, font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=10)
        
        # Log level
        tk.Label(tab_other, text="磁盘日志级别：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(10, 2))
        self.var_log_level = tk.StringVar(value=self.config_data.get("log_level", "debug"))
        cb_log = ttk.Combobox(tab_other, textvariable=self.var_log_level, values=["debug", "info", "warning", "error"])
        cb_log.pack(anchor="w", pady=(0, 10))
        
        # Log retention
        tk.Label(tab_other, text="本地日志保留天数：", bg=BG_CARD, fg=FG_PRIMARY, font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(10, 2))
        self.ent_log_days = tk.Entry(tab_other, bg=BG_ENTRY, fg=FG_PRIMARY, bd=0, font=("Segoe UI", 10), width=10)
        self.ent_log_days.pack(anchor="w", pady=(0, 10), ipady=3)
        self.ent_log_days.insert(0, str(self.config_data.get("log_retention_days", 7)))

    # ================= INPUT GATHERING =================

    def gather_gui_inputs(self):
        # Steam Account settings
        self.account_data["steam_username"] = self.ent_user.get().strip()
        self.account_data["steam_password"] = self.ent_pwd.get().strip()
        self.account_data["shared_secret"] = self.ent_shared.get().strip()
        self.account_data["identity_secret"] = self.ent_identity.get().strip()
        
        # BUFF settings
        if "buff_auto_accept_offer" not in self.config_data:
            self.config_data["buff_auto_accept_offer"] = {}
        self.config_data["buff_auto_accept_offer"]["enable"] = self.var_buff_enable.get()
        try:
            self.config_data["buff_auto_accept_offer"]["interval"] = int(self.ent_buff_interval.get().strip())
        except ValueError:
            pass
        self.config_data["buff_auto_accept_offer"]["dota2_support"] = self.var_buff_dota.get()
        self.config_data["buff_auto_accept_offer"]["use_proxies"] = self.var_buff_proxy.get()
        
        # UU Offer
        if "uu_auto_accept_offer" not in self.config_data:
            self.config_data["uu_auto_accept_offer"] = {}
        self.config_data["uu_auto_accept_offer"]["enable"] = self.var_uu_offer_enable.get()
        try:
            self.config_data["uu_auto_accept_offer"]["interval"] = int(self.ent_uu_offer_int.get().strip())
        except ValueError:
            pass
        self.config_data["uu_auto_accept_offer"]["use_proxies"] = self.var_uu_offer_proxy.get()
        
        # UU Lease
        if "uu_auto_lease_item" not in self.config_data:
            self.config_data["uu_auto_lease_item"] = {}
        self.config_data["uu_auto_lease_item"]["enable"] = self.var_uu_lease_enable.get()
        try:
            self.config_data["uu_auto_lease_item"]["lease_max_days"] = int(self.ent_uu_lease_days.get().strip())
            self.config_data["uu_auto_lease_item"]["filter_price"] = float(self.ent_uu_lease_price.get().strip())
            self.config_data["uu_auto_lease_item"]["interval"] = int(self.ent_uu_lease_int.get().strip())
            self.config_data["uu_auto_lease_item"]["fix_lease_ratio"] = float(self.ent_uu_lease_ratio.get().strip())
        except ValueError:
            pass
        self.config_data["uu_auto_lease_item"]["run_time"] = self.ent_uu_lease_time.get().strip()
        self.config_data["uu_auto_lease_item"]["enable_fix_lease_ratio"] = self.var_uu_lease_fix.get()
        
        black_names = [n.strip() for n in self.ent_uu_lease_black.get().split(",") if n.strip()]
        self.config_data["uu_auto_lease_item"]["filter_name"] = black_names
        
        # UU Sell
        if "uu_auto_sell_item" not in self.config_data:
            self.config_data["uu_auto_sell_item"] = {}
        self.config_data["uu_auto_sell_item"]["enable"] = self.var_uu_sell_enable.get()
        self.config_data["uu_auto_sell_item"]["run_time"] = self.ent_uu_sell_time.get().strip()
        try:
            self.config_data["uu_auto_sell_item"]["sell_interval"] = int(self.ent_uu_sell_req_int.get().strip())
            self.config_data["uu_auto_sell_item"]["interval"] = int(self.ent_uu_sell_int.get().strip())
            self.config_data["uu_auto_sell_item"]["max_on_sale_price"] = float(self.ent_uu_sell_max.get().strip())
        except ValueError:
            pass
        sell_names = [n.strip() for n in self.ent_uu_sell_names.get().split(",") if n.strip()]
        self.config_data["uu_auto_sell_item"]["name"] = sell_names
        self.config_data["uu_auto_sell_item"]["use_price_adjustment"] = self.var_uu_sell_adj.get()
        
        # ECOSteam
        if "ecosteam" not in self.config_data:
            self.config_data["ecosteam"] = {}
        self.config_data["ecosteam"]["enable"] = self.var_eco_enable.get()
        self.config_data["ecosteam"]["partnerId"] = self.ent_eco_partner.get().strip()
        if "auto_accept_offer" not in self.config_data["ecosteam"]:
            self.config_data["ecosteam"]["auto_accept_offer"] = {}
        try:
            self.config_data["ecosteam"]["auto_accept_offer"]["interval"] = int(self.ent_eco_int.get().strip())
            self.config_data["ecosteam"]["sync_interval"] = int(self.ent_eco_sync.get().strip())
        except ValueError:
            pass
            
        # Network & System
        self.config_data["steam_login_ignore_ssl_error"] = self.var_ssl_ignore.get()
        self.config_data["steam_local_accelerate"] = self.var_steam_acc.get()
        self.config_data["use_proxies"] = self.var_use_proxy.get()
        
        if "proxies" not in self.config_data:
            self.config_data["proxies"] = {}
        self.config_data["proxies"]["http"] = self.ent_proxy_http.get().strip()
        self.config_data["proxies"]["https"] = self.ent_proxy_https.get().strip()
        
        # Notifications
        if "notify_service" not in self.config_data:
            self.config_data["notify_service"] = {}
        notifiers = [url.strip() for url in self.txt_notifiers.get("1.0", tk.END).split("\n") if url.strip()]
        self.config_data["notify_service"]["notifiers"] = notifiers
        self.config_data["notify_service"]["custom_title"] = self.ent_notify_title.get().strip()
        self.config_data["notify_service"]["include_steam_info"] = self.var_notify_steam.get()
        
        # Gift
        if "steam_auto_accept_offer" not in self.config_data:
            self.config_data["steam_auto_accept_offer"] = {}
        self.config_data["steam_auto_accept_offer"]["enable"] = self.var_gift_enable.get()
        
        # Others
        self.config_data["log_level"] = self.var_log_level.get()
        try:
            self.config_data["log_retention_days"] = int(self.ent_log_days.get().strip())
        except ValueError:
            pass
            
        # Explicitly disable C5 Game plugins
        if "c5_auto_accept_offer" not in self.config_data:
            self.config_data["c5_auto_accept_offer"] = {}
        self.config_data["c5_auto_accept_offer"]["enable"] = False

    # ================= LOGS TERMINAL =================

    def poll_logs(self):
        try:
            while True:
                lvl, msg = gui_log_queue.get_nowait()
                self.write_to_terminal(lvl, msg)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_logs)

    def write_to_terminal(self, lvl, msg):
        self.log_text.config(state=tk.NORMAL)
        # Append message with corresponding log level style tag
        start_idx = self.log_text.index(tk.END + "-1c")
        self.log_text.insert(tk.END, msg + "\n")
        end_idx = self.log_text.index(tk.END + "-1c")
        
        self.log_text.tag_add(lvl, start_idx, end_idx)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    # ================= BACKGROUND WORKER THREAD =================

    def toggle_worker(self):
        if self.is_running:
            # Tkinter exit or exit application safely
            answer = messagebox.askyesno("停止程序", "确认退出程序并关闭吗？")
            if answer:
                os._exit(0)
            return

        # Save config first
        if not self.save_configs():
            return
            
        # Validate that steam username and password are not empty
        if not self.account_data.get("steam_username") or not self.account_data.get("steam_password"):
            messagebox.showwarning("凭证缺失", "Steam 用户名或密码不可为空，请到「Steam 账号」页面填写并保存！")
            self.switch_panel("account")
            return

        self.is_running = True
        self.btn_toggle.config(text="🛑 停止并关闭", bg=ACCENT_RED, activebackground="#DC2626")
        self.status_indicator.config(text="● 状态: 运行中", fg=ACCENT_GREEN)
        
        # Start core app thread
        self.worker_thread = threading.Thread(target=self.run_background_loop, daemon=True)
        self.worker_thread.start()

    def run_background_loop(self):
        try:
            logger.info("可视化守护挂机线程已启动...")
            self.main_runner_func()
        except Exception as e:
            logger.exception("守护挂机线程因发生致命错误异常退出")
        finally:
            self.is_running = False
            self.root.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        self.btn_toggle.config(text="🚀 启动自动发货", bg=ACCENT_GREEN, activebackground="#059669")
        self.status_indicator.config(text="● 状态: 已停止", fg=ACCENT_RED)
        messagebox.showinfo("运行结束", "挂机主进程已退出。")

    def run(self):
        self.root.mainloop()
