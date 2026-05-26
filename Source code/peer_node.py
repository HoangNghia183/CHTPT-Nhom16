import socket
import json
import threading
import time
import base64
import os

from cryptography.fernet import Fernet

# Key dùng chung cho toàn mạng
SECRET_KEY = b'4wX9p9R2V6D_8jQwV6D_8jQwV6D_8jQwV6D_8jQwV6M='
cipher_suite = Fernet(SECRET_KEY)

class PeerNode:
    def __init__(self, peer_id, my_ip, my_port, tracker_ip, tracker_port=9000, ui_queue=None):
        self.peer_id = peer_id
        self.my_ip = my_ip
        self.my_port = my_port
        self.tracker_ip = tracker_ip
        self.tracker_port = tracker_port
        self.known_peers = {} # Lưu danh bạ online
        self.offline_peers = {} # Lưu danh bạ offline
        self.my_groups = {} # Lưu các nhóm mà peer này tham gia
        self.ui_queue = ui_queue # Hàng đợi giao tiếp với GUI
        self.pending_files = {} # Lưu tạm file_name -> file_path đang chờ gửi

    def display(self, message):
        """Hàm thay thế cho print() để đẩy về GUI hoặc CLI"""
        if self.ui_queue:
            self.ui_queue.put(message)
        else:
            print(message)

    # PHẦN GIAO TIẾP VỚI TRACKER SERVER
    def send_to_tracker(self, packet, wait_for_response=False):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.tracker_ip, self.tracker_port))
            client.sendall((json.dumps(packet) + '\n').encode('utf-8'))
            
            if wait_for_response:
                data = client.recv(16384).decode('utf-8')
                client.close()
                return json.loads(data.strip())
                
            client.close()
        except Exception as e:
            pass
        return None

    def register(self):
        packet = {"action": "REGISTER", "payload": {"peer_id": self.peer_id, "ip": self.my_ip, "port": self.my_port}}
        response = self.send_to_tracker(packet, wait_for_response=True)
        self.display("[+] Đã đăng ký với Tracker Server thành công!")
        if response and response.get("action") == "OFFLINE_MSGS":
            self.display("\n[!] BẠN CÓ TIN NHẮN OFFLINE CHƯA ĐỌC:")
            for msg_data in response["payload"]["messages"]:
                decrypted_msg = cipher_suite.decrypt(msg_data['message'].encode('utf-8')).decode('utf-8')
                self.display(f"[{msg_data['sender']} để lại]: {decrypted_msg}")

    def unregister(self):
        packet = {"action": "LEAVE", "payload": {"peer_id": self.peer_id}}
        self.send_to_tracker(packet)
        self.display("[-] Đã gửi yêu cầu rời mạng sạch sẽ lên Tracker.")

    def get_peers(self, silent=False):
        packet = {"action": "GET_PEERS", "payload": {}}
        response = self.send_to_tracker(packet, wait_for_response=True)
        if response and response.get("action") == "PEER_LIST":
            online = response["payload"]["online"]
            all_registered = response["payload"]["all_registered"]
            
            self.known_peers = online
            # Tính toán danh sách offline
            self.offline_peers = {k: v for k, v in all_registered.items() if k not in online}
            
            if not silent:
                self.display("\n--- Danh sách mạng ---")
                self.display("ONLINE:")
                for pid, info in self.known_peers.items():
                    self.display(f"- {pid} ({info['ip']}:{info['port']})")
                self.display("OFFLINE:")
                for pid, info in self.offline_peers.items():
                    self.display(f"- {pid} ({info['ip']}:{info['port']})")
                self.display("----------------------")

    def heartbeat(self):
        packet = {"action": "PING", "payload": {"peer_id": self.peer_id}}
        while True:
            self.send_to_tracker(packet)
            time.sleep(10)

    # CÁC API NHÓM ĐỘNG TRÊN TRACKER
    def create_group(self, group_id, members):
        # Đảm bảo người tạo nhóm cũng nằm trong danh sách nhóm
        if self.peer_id not in members:
            members.append(self.peer_id)
        packet = {"action": "CREATE_GROUP", "payload": {"group_id": group_id, "members": members}}
        self.send_to_tracker(packet)

    def get_groups(self):
        packet = {"action": "GET_GROUPS", "payload": {"peer_id": self.peer_id}}
        response = self.send_to_tracker(packet, wait_for_response=True)
        if response and response.get("action") == "GROUP_LIST":
            self.my_groups = response["payload"]["groups"]

    def leave_group(self, group_id):
        packet = {"action": "LEAVE_GROUP", "payload": {"group_id": group_id, "peer_id": self.peer_id}}
        self.send_to_tracker(packet)

    # PHẦN LÕI P2P (GIAO TIẾP TRỰC TIẾP)
    def listen_for_peers(self):
        """Luồng Server: Lắng nghe tin nhắn trực tiếp từ các Peer khác"""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((self.my_ip, self.my_port))
        listener.listen(5)
        listener.settimeout(1.0)
        
        while True:
            try:
                conn, addr = listener.accept()
                threading.Thread(target=self.handle_incoming_message, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                break

    def handle_incoming_message(self, conn):
        """Xử lý tin nhắn P2P"""
        try:
            data = b""
            while True:
                chunk = conn.recv(16384)
                if not chunk:
                    break
                data += chunk
                if b'\n' in chunk:
                    break

            if data:
                packet = json.loads(data.decode('utf-8').strip())
                action = packet.get("action")
                payload = packet.get("payload", {})

                # A. Xử lý nhận tin nhắn 1v1
                if action == "CHAT_1V1":
                    sender = payload["sender_id"]
                    encrypted_msg = payload["message"]
                    decrypted_msg = cipher_suite.decrypt(encrypted_msg.encode('utf-8')).decode('utf-8')
                    self.display(f"\n[Tin nhắn từ {sender}]: {decrypted_msg}")
                    
                    ack_packet = {"action": "ACK"}
                    conn.sendall((json.dumps(ack_packet) + '\n').encode('utf-8'))
                
                # B. Xử lý nhận tin nhắn nhóm
                elif action == "CHAT_GROUP":
                    sender = payload["sender_id"]
                    encrypted_msg = payload["message"]
                    decrypted_msg = cipher_suite.decrypt(encrypted_msg.encode('utf-8')).decode('utf-8')
                    self.display(f"\n[Nhóm từ {sender}]: {decrypted_msg}")
                    
                    ack_packet = {"action": "ACK"}
                    conn.sendall((json.dumps(ack_packet) + '\n').encode('utf-8'))
                
                # C. Giao thức xác nhận file: Bước 1 - Nhận yêu cầu gửi file
                elif action == "FILE_REQUEST":
                    sender = payload["sender_id"]
                    filename = payload["filename"]
                    filesize = payload["filesize"]
                    
                    if self.ui_queue:
                        # Đẩy tín hiệu đặc biệt lên GUI xử lý Popup hỏi ý kiến người dùng
                        self.ui_queue.put(("FILE_CONFIRM_REQ", sender, filename, filesize))
                    else:
                        # CLI (Mặc định từ chối khi không có GUI)
                        self.display(f"\n[!] Yêu cầu file từ {sender}: '{filename}' ({filesize} bytes).")
                        self.send_file_confirmation_response(sender, filename, accepted=False)
                
                # C. Giao thức xác nhận file: Bước 2 - Nhận phản hồi đồng ý / từ chối
                elif action == "FILE_RESPONSE":
                    receiver = payload["receiver_id"]
                    filename = payload["filename"]
                    accepted = payload["accepted"]
                    
                    if accepted:
                        self.display(f"\n[Hệ thống] {receiver} đồng ý nhận file '{filename}'. Đang bắt đầu gửi...")
                        if filename in self.pending_files:
                            filepath = self.pending_files[filename]
                            # Bắt đầu truyền dữ liệu thực trên một luồng phụ
                            threading.Thread(target=self.send_file_data, args=(receiver, filepath), daemon=True).start()
                    else:
                        self.display(f"\n[Hệ thống] {receiver} đã TỪ CHỐI nhận file '{filename}'.")
                
                # C. Giao thức xác nhận file: Bước 3 - Nhận dữ liệu file thực tế
                elif action == "FILE_DATA":
                    sender = payload["sender_id"]
                    filename = payload["filename"]
                    file_data_b64 = payload["data"]

                    raw_bytes = base64.b64decode(file_data_b64)
                    save_path = f"recv_{filename}"
                    with open(save_path, "wb") as f:
                        f.write(raw_bytes)

                    self.display(f"\n[Hệ thống] Nhận file thành công: '{save_path}' ({len(raw_bytes)} bytes) từ {sender}.")
                    
                    ack_packet = {"action": "ACK"}
                    conn.sendall((json.dumps(ack_packet) + '\n').encode('utf-8'))
        except Exception as e:
            pass
        finally:
            conn.close()

    # CÁC PHƯƠNG THỨC GỬI TIN NHẮN VÀ TRUYỀN FILE
    def chat_1v1(self, target_peer, message, silent=False):
        """Gửi tin nhắn trực tiếp đến Peer online hoặc lưu offline"""
        encrypted_msg = cipher_suite.encrypt(message.encode('utf-8')).decode('utf-8')

        # 1. Nếu người nhận offline (không có trong danh sách online known_peers)
        if target_peer not in self.known_peers:
            if target_peer not in self.offline_peers:
                self.display(f"[-] Không tìm thấy người dùng '{target_peer}' trong mạng P2P.")
                return

            if not silent:
                self.display(f"[-] {target_peer} hiện đang offline. Kích hoạt Store-and-Forward gửi lên Tracker...")
            
            store_packet = {
                "action": "STORE_MSG",
                "payload": {"target": target_peer, "sender": self.peer_id, "message": encrypted_msg}
            }
            self.send_to_tracker(store_packet)
            if not silent:
                self.display("[+] Đã lưu tin nhắn offline lên Tracker Server thành công.")
            return

        # 2. Nếu người nhận online
        target_ip = self.known_peers[target_peer]["ip"]
        target_port = self.known_peers[target_peer]["port"]
        packet = {"action": "CHAT_1V1", "payload": {"sender_id": self.peer_id, "message": encrypted_msg}}
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0) 
            s.connect((target_ip, target_port))
            s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
            s.recv(1024)
            if not silent:
                self.display(f"[+] Đã gửi trực tiếp tới {target_peer}.")
        except (ConnectionRefusedError, socket.timeout):
            if not silent:
                self.display(f"[-] Lỗi kết nối trực tiếp đến {target_peer}. Kích hoạt Store-and-Forward gửi lên Tracker...")
            store_packet = {
                "action": "STORE_MSG",
                "payload": {"target": target_peer, "sender": self.peer_id, "message": encrypted_msg}
            }
            self.send_to_tracker(store_packet)
            if not silent:
                self.display("[+] Đã lưu tin nhắn offline lên Tracker Server.")
        except Exception as e:
            self.display(f"[-] Lỗi truyền tin: {e}")
        finally:
            s.close()

    def chat_group(self, target_peers, message):
        """Gửi tin nhắn nhóm tới toàn bộ các thành viên trong nhóm"""
        encrypted_msg = cipher_suite.encrypt(message.encode('utf-8')).decode('utf-8')
        
        for target_peer in target_peers:
            target_peer = target_peer.strip()
            if not target_peer or target_peer == self.peer_id:
                continue
                
            # Nếu peer đó online, gửi P2P trực tiếp
            if target_peer in self.known_peers:
                target_ip = self.known_peers[target_peer]["ip"]
                target_port = self.known_peers[target_peer]["port"]
                
                packet = {
                    "action": "CHAT_GROUP",
                    "payload": {
                        "sender_id": self.peer_id,
                        "message": encrypted_msg,
                        "group_members": target_peers
                    }
                }
                
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(3.0)
                    s.connect((target_ip, target_port))
                    s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
                    s.recv(1024)
                except Exception:
                    # Gửi offline nếu gặp lỗi kết nối P2P
                    store_packet = {
                        "action": "STORE_MSG",
                        "payload": {"target": target_peer, "sender": f"{self.peer_id} (Nhóm)", "message": encrypted_msg}
                    }
                    self.send_to_tracker(store_packet)
                finally:
                    s.close()
            else:
                # Nếu peer offline, lưu offline message
                store_packet = {
                    "action": "STORE_MSG",
                    "payload": {"target": target_peer, "sender": f"{self.peer_id} (Nhóm)", "message": encrypted_msg}
                }
                self.send_to_tracker(store_packet)

    # Giao thức truyền file 3 bước bất đồng bộ:
    # Bước 1: Người gửi gửi đề nghị
    def request_send_file(self, target_peer, filepath):
        if not os.path.exists(filepath):
            self.display("[-] File không tồn tại!")
            return
        if target_peer not in self.known_peers:
            self.display(f"[-] {target_peer} không online. Gửi file yêu cầu kết nối trực tiếp.")
            return

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        # Lưu đường dẫn file vào dictionary cục bộ chờ phản hồi
        self.pending_files[filename] = filepath
        
        packet = {
            "action": "FILE_REQUEST",
            "payload": {
                "sender_id": self.peer_id,
                "filename": filename,
                "filesize": filesize
            }
        }
        
        target_ip = self.known_peers[target_peer]["ip"]
        target_port = self.known_peers[target_peer]["port"]
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((target_ip, target_port))
            s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
            self.display(f"[Hệ thống] Đã gửi yêu cầu nhận file '{filename}' tới {target_peer}. Đang đợi đồng ý...")
        except Exception as e:
            self.display(f"[-] Yêu cầu gửi file thất bại: {e}")
        finally:
            s.close()

    # Bước 2: Người nhận gửi phản hồi Đồng ý/Từ chối
    def send_file_confirmation_response(self, sender, filename, accepted):
        if sender not in self.known_peers:
            return
            
        packet = {
            "action": "FILE_RESPONSE",
            "payload": {
                "receiver_id": self.peer_id,
                "filename": filename,
                "accepted": accepted
            }
        }
        
        target_ip = self.known_peers[sender]["ip"]
        target_port = self.known_peers[sender]["port"]
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5.0)
            s.connect((target_ip, target_port))
            s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
        except Exception:
            pass
        finally:
            s.close()

    # Bước 3: Gửi dữ liệu file thực tế khi đối phương đồng ý
    def send_file_data(self, target_peer, filepath):
        if target_peer not in self.known_peers:
            return
            
        try:
            with open(filepath, "rb") as f:
                encoded_data = base64.b64encode(f.read()).decode('utf-8')
            
            filename = os.path.basename(filepath)
            packet = {
                "action": "FILE_DATA",
                "payload": {
                    "sender_id": self.peer_id,
                    "filename": filename,
                    "data": encoded_data
                }
            }
            
            target_ip = self.known_peers[target_peer]["ip"]
            target_port = self.known_peers[target_peer]["port"]
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(20.0) # Đặt timeout lớn hơn cho file dung lượng lớn
            s.connect((target_ip, target_port))
            s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
            s.recv(1024)
            self.display(f"[+] Đã truyền dữ liệu file '{filename}' thành công tới {target_peer}!")
            
            # Xóa khỏi danh sách hàng đợi
            if filename in self.pending_files:
                del self.pending_files[filename]
        except Exception as e:
            self.display(f"[-] Gửi file thực tế thất bại: {e}")
        finally:
            s.close()

if __name__ == "__main__":
    print("[*] Engine PeerNode của Hệ thống P2P Chat. Vui lòng chạy app.py để khởi chạy ứng dụng GUI.")