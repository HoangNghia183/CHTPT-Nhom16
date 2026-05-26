import socket
import threading
import json
import time

# Lưu trữ danh sách mạng. 
# online_peers: {"A": {"ip": "192.168.1.5", "port": 5001, "last_ping": 1625...}}
online_peers = {}
# all_registered_peers: {"A": {"ip": "192.168.1.5", "port": 5001}}
all_registered_peers = {}
# groups: {"StudyGroup": ["A", "BV"]}
groups = {}

offline_messages = {}
TIMEOUT_SECONDS = 15  # Nếu sau 15s không nhận được PING, coi như Peer đã offline

def handle_client(conn, addr):
    """Hàm chạy trên một luồng riêng cho mỗi kết nối từ Peer"""
    print(f"[+] Kết nối mới từ {addr}")
    try:
        while True:
            # Đọc dữ liệu từ socket
            data = conn.recv(4096).decode('utf-8')
            if not data:
                break # Client đã ngắt kết nối
                
            messages = data.strip().split('\n')
            for msg in messages:
                if not msg: continue
                packet = json.loads(msg)
                action = packet.get("action")
                payload = packet.get("payload", {})
                
                # 1. Xử lý Đăng ký
                if action == "REGISTER":
                    peer_id = payload["peer_id"]
                    online_peers[peer_id] = {
                        "ip": payload["ip"],
                        "port": payload["port"],
                        "last_ping": time.time()
                    }
                    all_registered_peers[peer_id] = {
                        "ip": payload["ip"],
                        "port": payload["port"]
                    }
                    print(f"[REGISTER] {peer_id} tham gia mạng từ {payload['ip']}:{payload['port']}")

                    if peer_id in offline_messages and len(offline_messages[peer_id]) > 0:
                        print(f"[*] Đang đẩy tin nhắn offline về cho {peer_id}")
                        response = {
                            "action": "OFFLINE_MSGS",
                            "payload": {"messages": offline_messages[peer_id]}
                        }
                        conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                        del offline_messages[peer_id]
                
                # Xử lý rời mạng chủ động
                elif action == "LEAVE":
                    peer_id = payload["peer_id"]
                    if peer_id in online_peers:
                        print(f"[OFFLINE] {peer_id} chủ động rời mạng.")
                        del online_peers[peer_id]
                
                # 2. Xử lý Yêu cầu danh sách peer
                elif action == "GET_PEERS":
                    clean_online = {k: {"ip": v["ip"], "port": v["port"]} for k, v in online_peers.items()}
                    response = {
                        "action": "PEER_LIST",
                        "payload": {
                            "online": clean_online,
                            "all_registered": all_registered_peers
                        }
                    }
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                
                # 3. Xử lý Heartbeat (PING)
                elif action == "PING":
                    peer_id = payload["peer_id"]
                    if peer_id in online_peers:
                        online_peers[peer_id]["last_ping"] = time.time()

                # 4. Nhận tin nhắn lưu tạm (STORE-AND-FORWARD)
                elif action == "STORE_MSG":
                    target = payload["target"]
                    if target not in offline_messages:
                        offline_messages[target] = []
                    offline_messages[target].append({
                        "sender": payload["sender"],
                        "message": payload["message"]
                    })
                    print(f"[*] Đã lưu tạm tin nhắn từ {payload['sender']} gửi cho {target}.")
                
                # 5. Xử lý Tạo Nhóm
                elif action == "CREATE_GROUP":
                    group_id = payload["group_id"]
                    members = payload["members"]
                    groups[group_id] = list(set(members))
                    print(f"[GROUP] Tạo nhóm mới '{group_id}' với các thành viên: {members}")
                    response = {"action": "GROUP_STATUS", "payload": {"status": "SUCCESS", "group_id": group_id}}
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))

                # 6. Xử lý lấy danh sách nhóm của Peer
                elif action == "GET_GROUPS":
                    peer_id = payload["peer_id"]
                    peer_groups = {gid: mems for gid, mems in groups.items() if peer_id in mems}
                    response = {
                        "action": "GROUP_LIST",
                        "payload": {"groups": peer_groups}
                    }
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))

                # 7. Xử lý rời nhóm
                elif action == "LEAVE_GROUP":
                    group_id = payload["group_id"]
                    peer_id = payload["peer_id"]
                    if group_id in groups:
                        if peer_id in groups[group_id]:
                            groups[group_id].remove(peer_id)
                            print(f"[GROUP] {peer_id} đã rời khỏi nhóm '{group_id}'.")
                            
                            # Nếu không còn ai trong nhóm, xóa nhóm hoàn toàn
                            if len(groups[group_id]) == 0:
                                print(f"[GROUP] Nhóm '{group_id}' trống. Đang xóa nhóm.")
                                del groups[group_id]
                                
                    response = {"action": "GROUP_STATUS", "payload": {"status": "SUCCESS", "group_id": group_id}}
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                        
    except Exception as e:
        pass
    finally:
        conn.close()

def cleanup_offline_peers():
    """Luồng chạy ngầm để xóa các Peer rớt mạng"""
    while True:
        time.sleep(5) # Kiểm tra mỗi 5 giây
        current_time = time.time()
        offline_peers = [peer_id for peer_id, info in online_peers.items() 
                         if current_time - info["last_ping"] > TIMEOUT_SECONDS]
        
        for peer_id in offline_peers:
            print(f"[OFFLINE] {peer_id} đã rớt mạng (Timeout).")
            del online_peers[peer_id]

def start_server(host="0.0.0.0", port=9000):
    cleanup_thread = threading.Thread(target=cleanup_offline_peers, daemon=True)
    cleanup_thread.start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    
    server.settimeout(1.0) 
    
    print(f"[*] Tracker Server đang lắng nghe tại {host}:{port}...")

    try:
        while True:
            try:
                conn, addr = server.accept()
                thread = threading.Thread(target=handle_client, args=(conn, addr))
                thread.start()
            except socket.timeout:
                continue 
                
    except KeyboardInterrupt:
        print("\n[!] Nhận lệnh ngắt từ bàn phím. Đang tắt Server...")
    finally:
        server.close()
        print("[*] Server đã tắt an toàn.")

if __name__ == "__main__":
    start_server()