import cv2
import numpy as np
import socket
import struct
import pyautogui
import time

TCP_PORT = 8889
SENSITIVITY = 2.0
SMOOTHING = 0.7
MIN_HAND_AREA = 4000
SKIN_LOWER = np.array([0, 40, 60])
SKIN_UPPER = np.array([20, 150, 255])

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', TCP_PORT))
server.listen(1)
print("Waiting for ESP32...")
conn, addr = server.accept()
print("Connected")

prev_center = None
smooth_x = 0.0
smooth_y = 0.0

while True:
    try:
        sz = conn.recv(4)
        if len(sz) < 4:
            continue
        fsize = struct.unpack('<I', sz)[0]
        if fsize > 100000 or fsize < 100:
            continue
        jpeg = b''
        while len(jpeg) < fsize:
            chunk = conn.recv(min(65535, fsize - len(jpeg)))
            if not chunk:
                break
            jpeg += chunk
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, SKIN_LOWER, SKIN_UPPER)
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.erode(mask, kernel, 1)
        mask = cv2.dilate(mask, kernel, 2)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if cnts:
            hand = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(hand) >= MIN_HAND_AREA:
                M = cv2.moments(hand)
                if M["m00"] != 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                    # Преобразуем в обычные int (скаляры)
                    cx = int(cx)
                    cy = int(cy)
                    cv2.drawContours(frame, [hand], -1, (0,255,0), 2)
                    cv2.circle(frame, (cx, cy), 10, (0,0,255), -1)
                    
                    if prev_center is not None:
                        dx = (cx - prev_center[0]) * SENSITIVITY
                        dy = (cy - prev_center[1]) * SENSITIVITY
                        dx = max(-20, min(20, dx))
                        dy = max(-20, min(20, dy))
                        smooth_x = SMOOTHING * smooth_x + (1 - SMOOTHING) * dx
                        smooth_y = SMOOTHING * smooth_y + (1 - SMOOTHING) * dy
                        move_x = int(smooth_x)
                        move_y = int(smooth_y)
                        if move_x != 0 or move_y != 0:
                            pyautogui.move(move_x, move_y)
                            print(f"Move: {move_x}, {move_y}")
                    prev_center = (cx, cy)
                    cv2.putText(frame, "TRACKING", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                else:
                    prev_center = None
                    smooth_x = smooth_y = 0
                    cv2.putText(frame, "NO HAND", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
            else:
                prev_center = None
                smooth_x = smooth_y = 0
                cv2.putText(frame, "NO HAND", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        else:
            prev_center = None
            smooth_x = smooth_y = 0
            cv2.putText(frame, "NO HAND", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        
        cv2.imshow("Hand Tracking (Palm Center)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

cv2.destroyAllWindows()
conn.close()
server.close()
