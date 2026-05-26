import socket
import json
import time
import random
import threading

# Cấu hình Tracker
TRACKER_IP = "127.0.0.1"
TRACKER_PORT = 9000

# Sinh tự động 15 bot giả lập từ Bot_1 đến Bot_15 với các port tương ứng từ 6001 đến 6015
BOT_PEERS = {f"Bot_{i}": {"port": 6000 + i, "online": False} for i in range(1, 16)}

def send_packet(packet):
    """Gửi một gói tin ngắn hạn tới Tracker Server"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((TRACKER_IP, TRACKER_PORT))
        s.sendall((json.dumps(packet) + '\n').encode('utf-8'))
        s.close()
    except Exception:
        pass

def register_bot(bot_name, port):
    """Đăng ký bot lên mạng (Online)"""
    packet = {
        "action": "REGISTER",
        "payload": {
            "peer_id": bot_name,
            "ip": "127.0.0.1",
            "port": port
        }
    }
    send_packet(packet)
    print(f"[ONLINE] {bot_name} (Port: {port}) đã tham gia mạng.")

def leave_bot(bot_name):
    """Gửi gói tin rời mạng chủ động (Offline)"""
    packet = {
        "action": "LEAVE",
        "payload": {
            "peer_id": bot_name
        }
    }
    send_packet(packet)
    print(f"[OFFLINE] {bot_name} đã rời khỏi mạng.")

def ping_active_bots():
    """Luồng ngầm gửi PING định kỳ duy trì trạng thái cho các bot đang Online"""
    while True:
        time.sleep(8)
        for bot_name, info in BOT_PEERS.items():
            if info["online"]:
                packet = {
                    "action": "PING",
                    "payload": {
                        "peer_id": bot_name
                    }
                }
                send_packet(packet)

def main():
    print("=" * 60)
    print("      TRÌNH GIẢ LẬP BIẾN ĐỘNG MẠNG P2P (CHURN SIMULATOR)      ")
    print("=" * 60)
    print(f"[*] Đang kết nối tới Tracker Server tại: {TRACKER_IP}:{TRACKER_PORT}")
    print("[*] Tổng số bot giả lập tự động: 15 bot (Bot_1 đến Bot_15)")
    print("[*] Nhấn Ctrl+C để dừng trình giả lập bất kỳ lúc nào.\n")

    # Khởi chạy luồng gửi PING heartbeat cho các bot đang online
    threading.Thread(target=ping_active_bots, daemon=True).start()

    try:
        # Ban đầu, cho 3 bot online sẵn để làm nền
        initial_bots = ["Bot_1", "Bot_2", "Bot_3"]
        for bname in initial_bots:
            BOT_PEERS[bname]["online"] = True
            register_bot(bname, BOT_PEERS[bname]["port"])
        
        while True:
            # Chờ ngẫu nhiên từ 2 đến 5 giây cho mỗi biến động Churn để tăng tốc độ thay đổi sinh động hơn
            sleep_time = random.uniform(2.0, 5.0)
            time.sleep(sleep_time)

            # Chọn ngẫu nhiên một bot để thay đổi trạng thái
            bot_name = random.choice(list(BOT_PEERS.keys()))
            bot_info = BOT_PEERS[bot_name]

            if bot_info["online"]:
                # Đang online thì cho rời mạng
                bot_info["online"] = False
                leave_bot(bot_name)
            else:
                # Đang offline thì cho lên mạng
                bot_info["online"] = True
                register_bot(bot_name, bot_info["port"])

    except KeyboardInterrupt:
        print("\n\n[!] Đang tắt trình giả lập. Đang gửi yêu cầu rời mạng cho tất cả các bot...")
        for bname, info in BOT_PEERS.items():
            if info["online"]:
                leave_bot(bname)
        print("[*] Đã dọn dẹp sạch sẽ. Trình giả lập kết thúc.")

if __name__ == "__main__":
    main()
