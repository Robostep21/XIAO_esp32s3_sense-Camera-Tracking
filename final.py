import cv2
import numpy as np
import socket
import struct
import pyautogui
import time

# ====================== НАСТРОЙКИ ======================
TCP_PORT = 8889

SENSITIVITY = 2.0
SMOOTHING = 0.7
MIN_HAND_AREA = 4000

# Цвет кожи по умолчанию (HSV)
SKIN_LOWER_DEFAULT = np.array([0, 30, 60])
SKIN_UPPER_DEFAULT = np.array([20, 150, 255])
SKIN_LOWER = SKIN_LOWER_DEFAULT.copy()
SKIN_UPPER = SKIN_UPPER_DEFAULT.copy()

# Фильтры
FILTER_GRAY = False
FILTER_INVERT = False
FILTER_CONTRAST = False
FILTER_BLUR = False
FILTER_BINARY = False

# Отображение маски
SHOW_MASK = False

print("========================================")
print("Hand Skeleton Mouse + Filters")
print("Controls:")
print("  g - Grayscale     i - Invert")
print("  c - Contrast      b - Blur")
print("  t - Binary        r - Reset filters")
print("  m - Show/hide skin mask")
print("  k - Calibrate skin (place hand in green rect)")
print("  d - Reset skin to default")
print("  +/- - Sensitivity  q - Quit")
print("========================================")
print("Waiting for ESP32...")

# ====================== TCP ======================
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', TCP_PORT))
server.listen(1)

conn, addr = server.accept()
print(f"Connected to {addr}\n")

prev_finger_pos = None
smoothed_x = 0
smoothed_y = 0

def apply_filters(img):
    result = img.copy()
    if FILTER_GRAY:
        result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    if FILTER_CONTRAST:
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    if FILTER_BLUR:
        result = cv2.GaussianBlur(result, (5,5), 0)
    if FILTER_INVERT:
        result = cv2.bitwise_not(result)
    if FILTER_BINARY:
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    return result

def find_hand_and_skeleton(frame, return_mask=False):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, SKIN_LOWER, SKIN_UPPER)
    
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=2)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return (None, mask) if return_mask else None
    
    hand = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(hand)
    if area < MIN_HAND_AREA:
        return (None, mask) if return_mask else None
    
    cv2.drawContours(frame, [hand], -1, (0,255,0), 2)
    
    # Центр ладони
    M = cv2.moments(hand)
    if M["m00"] == 0:
        return (None, mask) if return_mask else None
    palm_x = int(M["m10"] / M["m00"])
    palm_y = int(M["m01"] / M["m00"])
    cv2.circle(frame, (palm_x, palm_y), 8, (255,0,0), -1)
    
    # Все точки контура
    points = hand.squeeze()
    if points.ndim == 1:
        return (None, mask) if return_mask else None
    
    # Расстояния от центра
    dx_pts = points[:,0] - palm_x
    dy_pts = points[:,1] - palm_y
    distances = np.sqrt(dx_pts**2 + dy_pts**2)
    
    # Сглаживание для поиска локальных максимумов
    window = 7
    smoothed = np.convolve(distances, np.ones(window)/window, mode='same')
    
    # Локальные максимумы
    peaks = []
    for i in range(window, len(smoothed)-window):
        if smoothed[i] >= np.max(smoothed[i-window:i+window+1]):
            peaks.append(i)
    
    # Сортируем по убыванию расстояния
    peaks.sort(key=lambda i: smoothed[i], reverse=True)
    
    fingertips = []
    for idx in peaks:
        pt = tuple(points[idx])
        dy = pt[1] - palm_y
        dx = pt[0] - palm_x
        
        # Условия для отсева запястья:
        # 1. Точка должна быть выше центра (палец вверх) – если рука вертикально
        if dy > 5:   # точка ниже центра ладони – скорее запястье или основание
            continue
        # 2. Палец должен быть направлен больше вверх, чем вбок
        if abs(dx) > abs(dy) + 15:
            continue
        
        # Группировка близких точек
        if not any(np.hypot(pt[0]-f[0], pt[1]-f[1]) < 20 for f in fingertips):
            fingertips.append(pt)
        if len(fingertips) >= 5:
            break
    
    if not fingertips:
        return (None, mask) if return_mask else None
    
    # Сортируем по Y (самый верхний – указательный)
    fingertips = sorted(fingertips, key=lambda p: p[1])
    index_finger = fingertips[0]
    
    # Рисуем кончики пальцев и скелет
    for i, tip in enumerate(fingertips):
        cv2.circle(frame, tip, 8, (0,255,255), -1)
        if i == 0:
            cv2.circle(frame, tip, 12, (255,0,255), -1)
    for tip in fingertips:
        cv2.line(frame, (palm_x, palm_y), tip, (0,255,0), 2)
    
    return (index_finger, mask) if return_mask else index_finger

# ====================== ОСНОВНОЙ ЦИКЛ ======================
while True:
    try:
        size_data = conn.recv(4)
        if len(size_data) < 4:
            continue
        frame_size = struct.unpack('<I', size_data)[0]
        if frame_size > 100000 or frame_size < 100:
            continue
        jpeg_data = b''
        while len(jpeg_data) < frame_size:
            chunk = conn.recv(min(65535, frame_size - len(jpeg_data)))
            if not chunk:
                break
            jpeg_data += chunk
        frame = cv2.imdecode(np.frombuffer(jpeg_data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        
        filtered_frame = apply_filters(frame)
        result = find_hand_and_skeleton(filtered_frame, return_mask=SHOW_MASK)
        if SHOW_MASK:
            finger_pos, mask = result
        else:
            finger_pos = result
            mask = None
        
        if finger_pos is not None:
            if prev_finger_pos is not None:
                dx = (finger_pos[0] - prev_finger_pos[0]) * SENSITIVITY
                dy = (finger_pos[1] - prev_finger_pos[1]) * SENSITIVITY
                dx = max(-20, min(20, dx))
                dy = max(-20, min(20, dy))
                smoothed_x = SMOOTHING * smoothed_x + (1 - SMOOTHING) * dx
                smoothed_y = SMOOTHING * smoothed_y + (1 - SMOOTHING) * dy
                move_x, move_y = int(smoothed_x), int(smoothed_y)
                if move_x != 0 or move_y != 0:
                    pyautogui.move(move_x, move_y)
            prev_finger_pos = finger_pos
            cv2.putText(filtered_frame, "HAND DETECTED", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        else:
            if prev_finger_pos is not None:
                print("Hand lost")
                prev_finger_pos = None
                smoothed_x = smoothed_y = 0
            cv2.putText(filtered_frame, "NO HAND", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        
        # Отображение информации
        filters_status = [name for name, flag in [("GRAY",FILTER_GRAY),("INV",FILTER_INVERT),
                         ("CONTRAST",FILTER_CONTRAST),("BLUR",FILTER_BLUR),("BINARY",FILTER_BINARY)] if flag]
        status_text = " | ".join(filters_status) if filters_status else "NO FILTERS"
        cv2.putText(filtered_frame, f"Filters: {status_text}", (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
        cv2.putText(filtered_frame, f"Sensitivity: {SENSITIVITY:.1f}", (10,85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
        cv2.putText(filtered_frame, f"Skin H: {SKIN_LOWER[0]}-{SKIN_UPPER[0]}", (10,110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
        
        # Показываем маску, если включена
        if SHOW_MASK and mask is not None:
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            mask_resized = cv2.resize(mask_bgr, (filtered_frame.shape[1]//3, filtered_frame.shape[0]//3))
            filtered_frame[0:mask_resized.shape[0], filtered_frame.shape[1]-mask_resized.shape[1]:] = mask_resized
        
        cv2.imshow("Hand Skeleton + Filters", filtered_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('+') or key == ord('='):
            SENSITIVITY = min(10.0, SENSITIVITY+0.5)
            print(f"Sensitivity: {SENSITIVITY}")
        elif key == ord('-') or key == ord('_'):
            SENSITIVITY = max(0.5, SENSITIVITY-0.5)
            print(f"Sensitivity: {SENSITIVITY}")
        elif key == ord('g'):
            FILTER_GRAY = not FILTER_GRAY
        elif key == ord('i'):
            FILTER_INVERT = not FILTER_INVERT
        elif key == ord('c'):
            FILTER_CONTRAST = not FILTER_CONTRAST
        elif key == ord('b'):
            FILTER_BLUR = not FILTER_BLUR
        elif key == ord('t'):
            FILTER_BINARY = not FILTER_BINARY
        elif key == ord('r'):
            FILTER_GRAY = FILTER_INVERT = FILTER_CONTRAST = FILTER_BLUR = FILTER_BINARY = False
            print("All filters reset")
        elif key == ord('m'):
            SHOW_MASK = not SHOW_MASK
            print(f"Show mask: {SHOW_MASK}")
        elif key == ord('d'):
            SKIN_LOWER = SKIN_LOWER_DEFAULT.copy()
            SKIN_UPPER = SKIN_UPPER_DEFAULT.copy()
            print(f"Skin reset to default: lower={SKIN_LOWER}, upper={SKIN_UPPER}")
        elif key == ord('k'):
            print("\n=== SKIN CALIBRATION ===")
            print("Place your hand in the green rectangle and press SPACE")
            h, w = frame.shape[:2]
            roi_x, roi_y = w//2-100, h//2-100
            roi_w, roi_h = 200, 200
            temp_frame = frame.copy()
            cv2.rectangle(temp_frame, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (0,255,0), 2)
            cv2.imshow("Calibration - press SPACE", temp_frame)
            cv2.waitKey(0)
            roi = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mean_h = np.mean(hsv_roi[:,:,0])
            mean_s = np.mean(hsv_roi[:,:,1])
            mean_v = np.mean(hsv_roi[:,:,2])
            new_lower = np.array([max(0, mean_h-10), max(30, mean_s-40), max(60, mean_v-40)])
            new_upper = np.array([min(180, mean_h+10), min(255, mean_s+40), min(255, mean_v+40)])
            # Проверка: создаём маску по новым границам на ROI
            test_mask = cv2.inRange(hsv_roi, new_lower, new_upper)
            if np.sum(test_mask) < 500:
                print("Calibration failed: new skin range does not detect hand. Keeping previous values.")
            else:
                SKIN_LOWER = new_lower
                SKIN_UPPER = new_upper
                print(f"Skin calibrated: lower={SKIN_LOWER}, upper={SKIN_UPPER}")
            cv2.destroyWindow("Calibration - press SPACE")
    
    except Exception as e:
        print(f"Error: {e}")

cv2.destroyAllWindows()
conn.close()
server.close()
print("\nDone.")
