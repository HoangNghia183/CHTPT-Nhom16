import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinter import filedialog
import threading
import queue
import os
import sys
from peer_node import PeerNode

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("P2P Chat System - Đăng nhập")
        self.root.geometry("450x350")
        self.root.resizable(False, False)

        # Bảng màu UI
        self.bg_color = "#f4f6f9"
        self.primary_color = "#3b82f6"
        self.success_color = "#10b981"
        self.danger_color = "#ef4444"
        self.text_color = "#1e293b"
        self.sidebar_bg = "#ffffff"
        self.chat_bg = "#ffffff"

        self.root.configure(bg=self.bg_color)
        
        # Khởi tạo Queue
        self.msg_queue = queue.Queue()
        self.node = None
        self.is_logged_in = False

        # Hiển thị màn hình đăng nhập
        self.show_login_screen()

    def show_login_screen(self):
        self.login_frame = tk.Frame(self.root, bg=self.bg_color, padx=30, pady=30)
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        title_lbl = tk.Label(
            self.login_frame, text="HỆ THỐNG P2P CHAT", 
            font=("Segoe UI", 16, "bold"), bg=self.bg_color, fg=self.primary_color
        )
        title_lbl.pack(pady=(0, 20))

        # Tên người dùng
        lbl1 = tk.Label(self.login_frame, text="Tên người dùng (Peer ID):", font=("Segoe UI", 9, "bold"), bg=self.bg_color, fg=self.text_color)
        lbl1.pack(anchor="w", pady=(0, 2))
        self.name_entry = tk.Entry(self.login_frame, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.name_entry.pack(fill=tk.X, pady=(0, 15))
        self.name_entry.focus()

        # Port
        lbl2 = tk.Label(self.login_frame, text="Cổng kết nối (Port của Peer):", font=("Segoe UI", 9, "bold"), bg=self.bg_color, fg=self.text_color)
        lbl2.pack(anchor="w", pady=(0, 2))
        self.port_entry = tk.Entry(self.login_frame, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.port_entry.pack(fill=tk.X, pady=(0, 15))

        # Tracker IP
        lbl3 = tk.Label(self.login_frame, text="Địa chỉ Tracker Server IP:", font=("Segoe UI", 9, "bold"), bg=self.bg_color, fg=self.text_color)
        lbl3.pack(anchor="w", pady=(0, 2))
        self.tracker_entry = tk.Entry(self.login_frame, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.tracker_entry.insert(0, "127.0.0.1")
        self.tracker_entry.pack(fill=tk.X, pady=(0, 20))

        # Nút Đăng nhập
        btn_login = tk.Button(
            self.login_frame, text="ĐĂNG NHẬP & THAM GIA MẠNG", command=self.login_action,
            bg=self.primary_color, fg="white", activebackground="#2563eb",
            activeforeground="white", font=("Segoe UI", 10, "bold"), bd=0, pady=8, cursor="hand2"
        )
        btn_login.pack(fill=tk.X)

    def login_action(self):
        peer_name = self.name_entry.get().strip()
        port_str = self.port_entry.get().strip()
        tracker_ip = self.tracker_entry.get().strip()

        if not peer_name or not port_str or not tracker_ip:
            messagebox.showerror("Lỗi", "Vui lòng nhập đầy đủ thông tin đăng nhập!")
            return

        try:
            port = int(port_str)
            if port < 1024 or port > 65535:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Lỗi", "Cổng kết nối phải là số nguyên nằm trong khoảng [1024 - 65535]!")
            return

        # Khởi tạo PeerNode và chuyển sang giao diện chính
        self.node = PeerNode(
            peer_id=peer_name, my_ip="127.0.0.1", 
            my_port=port, tracker_ip=tracker_ip, 
            ui_queue=self.msg_queue
        )
        
        self.is_logged_in = True
        self.login_frame.destroy()

        # Cấu hình lại cửa sổ chính cho giao diện chat
        self.root.title(f"P2P Chat System - Đang đăng nhập: {peer_name} (Port: {port})")
        self.root.geometry("850x600")
        self.root.minsize(750, 480)
        self.root.resizable(True, True)

        self.setup_ui()
        
        # Đăng ký bắt sự kiện đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bắt đầu các luồng xử lý mạng
        threading.Thread(target=self.node.register, daemon=True).start()
        threading.Thread(target=self.node.heartbeat, daemon=True).start()
        threading.Thread(target=self.node.listen_for_peers, daemon=True).start()
        threading.Thread(target=self.node.get_peers, args=(False,), daemon=True).start()
        threading.Thread(target=self.node.get_groups, daemon=True).start()
        
        # Kích hoạt vòng lặp kiểm tra Queue liên tục
        self.root.after(100, self.process_queue)
        
        # Lên lịch tự động làm mới danh sách peer & nhóm online mỗi 5 giây
        self.root.after(5000, self.auto_refresh_peers)

    def setup_ui(self):
        # Chia layout làm 2 khu vực khung Chat bên trái, Sidebar bên phải
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.bg_color, bd=0, sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # KHUNG TRÁI: Khung Chat và Nhập liệu
        left_frame = tk.Frame(main_pane, bg=self.bg_color)
        main_pane.add(left_frame, stretch="always")

        # Khung hiển thị tin nhắn chat
        self.chat_area = scrolledtext.ScrolledText(
            left_frame, wrap=tk.WORD, state='disabled', 
            bg=self.chat_bg, fg=self.text_color, 
            font=("Segoe UI", 10), bd=1, relief=tk.SOLID
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Khung nhập tin nhắn và người nhận
        input_frame = tk.Frame(left_frame, bg=self.bg_color)
        input_frame.pack(fill=tk.X)

        # Hàng 1: Người nhận
        row1 = tk.Frame(input_frame, bg=self.bg_color)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(
            row1, text="Người nhận:", font=("Segoe UI", 9, "bold"), 
            bg=self.bg_color, fg=self.text_color, width=12, anchor="w"
        ).pack(side=tk.LEFT)
        
        self.target_entry = tk.Entry(row1, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Hướng dẫn gửi tin nhóm
        tk.Label(
            row1, text="(Double-click sidebar để điền nhanh)", font=("Segoe UI", 8, "italic"), 
            bg=self.bg_color, fg="#64748b"
        ).pack(side=tk.LEFT)

        # Hàng 2: Nội dung tin nhắn
        row2 = tk.Frame(input_frame, bg=self.bg_color)
        row2.pack(fill=tk.X, pady=5)
        tk.Label(
            row2, text="Tin nhắn:", font=("Segoe UI", 9, "bold"), 
            bg=self.bg_color, fg=self.text_color, width=12, anchor="w"
        ).pack(side=tk.LEFT)
        
        self.msg_entry = tk.Entry(row2, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.msg_entry.bind("<Return>", lambda event: self.send_message())

        # Hàng 3: Nút gửi tin nhắn và gửi file
        row3 = tk.Frame(input_frame, bg=self.bg_color)
        row3.pack(fill=tk.X, pady=2)

        self.send_btn = tk.Button(
            row3, text="GỬI TIN NHẮN", command=self.send_message, 
            bg=self.primary_color, fg="white", activebackground="#2563eb", 
            activeforeground="white", font=("Segoe UI", 9, "bold"), 
            bd=0, padx=20, pady=6, cursor="hand2"
        )
        self.send_btn.pack(side=tk.LEFT)

        self.file_btn = tk.Button(
            row3, text="YÊU CẦU GỬI FILE", command=self.choose_and_send_file_req, 
            bg=self.success_color, fg="white", activebackground="#059669", 
            activeforeground="white", font=("Segoe UI", 9, "bold"), 
            bd=0, padx=20, pady=6, cursor="hand2"
        )
        self.file_btn.pack(side=tk.LEFT, padx=10)

        # KHUNG PHẢI: Sidebar danh sách Peer và nhóm
        sidebar_frame = tk.Frame(main_pane, bg=self.sidebar_bg, bd=1, relief=tk.SOLID)
        main_pane.add(sidebar_frame, minsize=230)

        # Tiêu đề danh sách Online
        self.online_title = tk.Label(
            sidebar_frame, text="🟢 Peers Online (0)", 
            font=("Segoe UI", 9, "bold"), bg=self.sidebar_bg, fg="#10b981", pady=5
        )
        self.online_title.pack(fill=tk.X)

        # Listbox Online
        self.online_listbox = tk.Listbox(
            sidebar_frame, height=8, font=("Segoe UI", 9), bg=self.sidebar_bg, 
            fg=self.text_color, bd=0, highlightthickness=0, 
            selectbackground="#cbd5e1", selectforeground=self.text_color, activestyle="none"
        )
        self.online_listbox.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.online_listbox.bind("<Double-Button-1>", self.on_online_double_click)

        # Tiêu đề danh sách Offline
        self.offline_title = tk.Label(
            sidebar_frame, text="⚫ Peers Offline (0)", 
            font=("Segoe UI", 9, "bold"), bg=self.sidebar_bg, fg="#64748b", pady=5
        )
        self.offline_title.pack(fill=tk.X)

        # Listbox Offline
        self.offline_listbox = tk.Listbox(
            sidebar_frame, height=6, font=("Segoe UI", 9), bg=self.sidebar_bg, 
            fg="#94a3b8", bd=0, highlightthickness=0, 
            selectbackground="#cbd5e1", selectforeground=self.text_color, activestyle="none"
        )
        self.offline_listbox.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Tiêu đề danh sách Nhóm
        self.group_title = tk.Label(
            sidebar_frame, text="👥 Nhóm của tôi (0)", 
            font=("Segoe UI", 9, "bold"), bg=self.sidebar_bg, fg=self.primary_color, pady=5
        )
        self.group_title.pack(fill=tk.X)

        # Listbox Nhóm
        self.group_listbox = tk.Listbox(
            sidebar_frame, height=6, font=("Segoe UI", 9), bg=self.sidebar_bg, 
            fg=self.text_color, bd=0, highlightthickness=0, 
            selectbackground="#cbd5e1", selectforeground=self.text_color, activestyle="none"
        )
        self.group_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.group_listbox.bind("<Double-Button-1>", self.on_group_double_click)

        # Khung chứa nút tạo/rời nhóm
        group_btn_frame = tk.Frame(sidebar_frame, bg=self.sidebar_bg)
        group_btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(0, 5))

        self.btn_create_grp = tk.Button(
            group_btn_frame, text="Tạo nhóm", command=self.open_create_group_dialog,
            bg=self.primary_color, fg="white", font=("Segoe UI", 8, "bold"),
            bd=0, pady=4, cursor="hand2"
        )
        self.btn_create_grp.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_leave_grp = tk.Button(
            group_btn_frame, text="Rời nhóm", command=self.leave_selected_group,
            bg=self.danger_color, fg="white", font=("Segoe UI", 8, "bold"),
            bd=0, pady=4, cursor="hand2"
        )
        self.btn_leave_grp.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Nút bấm làm mới thủ công ở dưới cùng
        self.refresh_btn = tk.Button(
            sidebar_frame, text="Làm mới danh sách", command=self.manual_refresh,
            bg="#f1f5f9", fg=self.text_color, font=("Segoe UI", 9), 
            bd=0, pady=5, cursor="hand2"
        )
        self.refresh_btn.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

    def process_queue(self):
        """Hàm định kỳ: Đọc dữ liệu từ hàng đợi mạng hiển thị lên giao diện chính"""
        if not self.is_logged_in:
            return

        while not self.msg_queue.empty():
            try:
                data = self.msg_queue.get_nowait()
                if isinstance(data, tuple) and data[0] == "FILE_CONFIRM_REQ":
                    # Xử lý đề nghị nhận file
                    _, sender, filename, filesize = data
                    # Chạy trong luồng UI chính
                    self.handle_file_confirmation_dialog(sender, filename, filesize)
                else:
                    # In tin nhắn chat bình thường
                    self.write_to_chat(data)
            except queue.Empty:
                break
        
        # Tự động đồng bộ các Listbox
        self.update_ui_lists()
        self.root.after(100, self.process_queue)

    def write_to_chat(self, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.yview(tk.END)
        self.chat_area.config(state='disabled')

    def update_ui_lists(self):
        """Đồng bộ trạng thái của cả 3 danh sách bên Sidebar"""
        # 1. Cập nhật Peer Online
        current_online_sel = None
        try:
            if self.online_listbox.curselection():
                current_online_sel = self.online_listbox.get(self.online_listbox.curselection())
        except Exception: pass

        self.online_listbox.delete(0, tk.END)
        online_count = 0
        for pid in sorted(self.node.known_peers.keys()):
            if pid == self.node.peer_id: continue
            self.online_listbox.insert(tk.END, pid)
            online_count += 1
        self.online_title.config(text=f"🟢 Peers Online ({online_count})")
        if current_online_sel:
            for idx, item in enumerate(self.online_listbox.get(0, tk.END)):
                if item == current_online_sel:
                    self.online_listbox.selection_set(idx)
                    break

        # 2. Cập nhật Peer Offline
        self.offline_listbox.delete(0, tk.END)
        offline_count = 0
        for pid in sorted(self.node.offline_peers.keys()):
            if pid == self.node.peer_id: continue
            self.offline_listbox.insert(tk.END, pid)
            offline_count += 1
        self.offline_title.config(text=f"⚫ Peers Offline ({offline_count})")

        # 3. Cập nhật Nhóm
        current_group_sel = None
        try:
            if self.group_listbox.curselection():
                current_group_sel = self.group_listbox.get(self.group_listbox.curselection())
        except Exception: pass

        self.group_listbox.delete(0, tk.END)
        group_count = 0
        for gid in sorted(self.node.my_groups.keys()):
            self.group_listbox.insert(tk.END, gid)
            group_count += 1
        self.group_title.config(text=f"👥 Nhóm của tôi ({group_count})")
        if current_group_sel:
            for idx, item in enumerate(self.group_listbox.get(0, tk.END)):
                if item == current_group_sel:
                    self.group_listbox.selection_set(idx)
                    break

    def on_online_double_click(self, event):
        """Click đúp Online: tự điền hoặc nối thêm tên vào ô Người nhận"""
        try:
            selected_peer = self.online_listbox.get(self.online_listbox.curselection())
            current_target = self.target_entry.get().strip()
            
            if not current_target:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, selected_peer)
            else:
                targets = [t.strip() for t in current_target.split(",") if t.strip()]
                if selected_peer not in targets:
                    targets.append(selected_peer)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, ", ".join(targets))
        except Exception: pass

    def on_group_double_click(self, event):
        """Click đúp Nhóm: Tự điền tất cả thành viên trong nhóm vào mục Người nhận để chat nhóm"""
        try:
            selected_group = self.group_listbox.get(self.group_listbox.curselection())
            if selected_group in self.node.my_groups:
                members = self.node.my_groups[selected_group]
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, ", ".join(members))
        except Exception: pass

    def send_message(self):
        target_str = self.target_entry.get().strip()
        msg = self.msg_entry.get().strip()
        
        if not target_str or not msg:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập người nhận và tin nhắn!")
            return
        
        # Nếu phát hiện có nhiều người nhận
        if "," in target_str:
            targets = [t.strip() for t in target_str.split(",") if t.strip()]
            self.write_to_chat(f"[Tôi -> Nhóm {targets}]: {msg}")
            self.msg_entry.delete(0, tk.END)
            threading.Thread(target=self.node.chat_group, args=(targets, msg), daemon=True).start()
        else:
            self.write_to_chat(f"[Tôi -> {target_str}]: {msg}")
            self.msg_entry.delete(0, tk.END)
            threading.Thread(target=self.node.chat_1v1, args=(target_str, msg), daemon=True).start()

    # Giao thức truyền file 3 bước bất đồng bộ:
    # B1: Người gửi đính kèm file
    def choose_and_send_file_req(self):
        target = self.target_entry.get().strip()
        if not target or "," in target:
            messagebox.showwarning("Cảnh báo", "Gửi file hiện chỉ hỗ trợ 1v1. Vui lòng nhập duy nhất 1 người nhận!")
            return
            
        filepath = filedialog.askopenfilename()
        if filepath:
            filename = os.path.basename(filepath)
            self.write_to_chat(f"[Hệ thống] Đang gửi yêu cầu chuyển file '{filename}' tới {target}...")
            # Gọi API request file
            threading.Thread(target=self.node.request_send_file, args=(target, filepath), daemon=True).start()

    # B2:Người nhận xử lý xác nhận file
    def handle_file_confirmation_dialog(self, sender, filename, filesize):
        ans = messagebox.askyesno(
            "Yêu cầu nhận file", 
            f"Người dùng '{sender}' muốn gửi cho bạn file:\n\n"
            f"Tên file: {filename}\n"
            f"Dung lượng: {filesize} bytes\n\n"
            f"Bạn có đồng ý tải file về máy không?"
        )
        
        if ans:
            self.write_to_chat(f"[Hệ thống] Bạn đã đồng ý nhận file '{filename}'. Đang tải về...")
        else:
            self.write_to_chat(f"[Hệ thống] Bạn đã từ chối nhận file '{filename}'.")

        # Gửi câu trả lời về cho sender qua luồng mạng phụ
        threading.Thread(target=self.node.send_file_confirmation_response, args=(sender, filename, ans), daemon=True).start()

    # Quản lý tạo/rời nhóm
    def open_create_group_dialog(self):
        """Mở popup tạo nhóm nhỏ"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Tạo nhóm mới")
        dialog.geometry("350x220")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.configure(bg=self.bg_color)

        tk.Label(dialog, text="Tên nhóm (Group ID):", font=("Segoe UI", 9, "bold"), bg=self.bg_color, fg=self.text_color).pack(anchor="w", padx=20, pady=(15, 2))
        group_id_entry = tk.Entry(dialog, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        group_id_entry.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(dialog, text="Các thành viên (cách nhau dấu phẩy):", font=("Segoe UI", 9, "bold"), bg=self.bg_color, fg=self.text_color).pack(anchor="w", padx=20, pady=(0, 2))
        members_entry = tk.Entry(dialog, font=("Segoe UI", 10), bd=1, relief=tk.SOLID)
        members_entry.pack(fill=tk.X, padx=20, pady=(0, 20))

        def create_action():
            gid = group_id_entry.get().strip()
            mems_str = members_entry.get().strip()
            if not gid or not mems_str:
                messagebox.showwarning("Cảnh báo", "Vui lòng điền đầy đủ Group ID và thành viên!")
                return
            
            members = [m.strip() for m in mems_str.split(",") if m.strip()]
            
            # Gửi lệnh tạo nhóm
            threading.Thread(target=self.node.create_group, args=(gid, members), daemon=True).start()
            
            # Làm mới danh sách nhóm ngay
            threading.Thread(target=self.node.get_groups, daemon=True).start()
            
            self.write_to_chat(f"[Hệ thống] Đã gửi yêu cầu tạo nhóm '{gid}'...")
            dialog.destroy()

        btn_create = tk.Button(
            dialog, text="XÁC NHẬN TẠO NHÓM", command=create_action,
            bg=self.success_color, fg="white", font=("Segoe UI", 9, "bold"),
            bd=0, pady=6, cursor="hand2"
        )
        btn_create.pack(fill=tk.X, padx=20)

    def leave_selected_group(self):
        try:
            selected_group = self.group_listbox.get(self.group_listbox.curselection())
            ans = messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn rời khỏi nhóm '{selected_group}' không?")
            if ans:
                threading.Thread(target=self.node.leave_group, args=(selected_group,), daemon=True).start()
                self.write_to_chat(f"[Hệ thống] Bạn đã gửi yêu cầu rời nhóm '{selected_group}'...")
                # Lấy lại nhóm ngay
                threading.Thread(target=self.node.get_groups, daemon=True).start()
        except Exception:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 nhóm từ danh sách để rời nhóm!")

    def auto_refresh_peers(self):
        """Cập nhật ngầm tự động mỗi 5s"""
        threading.Thread(target=self.node.get_peers, args=(True,), daemon=True).start()
        threading.Thread(target=self.node.get_groups, daemon=True).start()
        self.root.after(5000, self.auto_refresh_peers)

    def manual_refresh(self):
        """Khi bấm nút làm mới sẽ in danh sách ra màn hình chat"""
        self.write_to_chat("[Hệ thống] Đang làm mới danh sách peer và nhóm...")
        threading.Thread(target=self.node.get_peers, args=(False,), daemon=True).start()
        threading.Thread(target=self.node.get_groups, daemon=True).start()

    def on_closing(self):
        """Bắt sự kiện đóng cửa sổ để hủy đăng ký (LEAVE) sạch sẽ trên Tracker"""
        if self.node:
            try:
                self.node.unregister()
            except Exception: pass
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()