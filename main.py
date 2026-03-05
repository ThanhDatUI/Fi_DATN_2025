
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import numpy as np
import pandas as pd
import tflite_runtime.interpreter as tflite
from PIL import Image, ImageEnhance
import os
import time
import board
import busio
import RPi.GPIO as GPIO
import requests
import socket
import smbus2
import joblib
from datetime import datetime
from threading import Thread
from flask import Flask, request
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1115 as ADS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
last_call_time = datetime.min  # thời gian lần gọi gần nhất
def send_emergency_email(subject, body):
    try:
        print("🧪 Gọi hàm gửi email: ", subject)
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()

        print("📧 Đã gửi email:", subject)
    except Exception as e:
        print(f"❌ Gửi email thất bại: {e}")

last_alarm_time = datetime.min  # 🆕 thời điểm báo động cuối
# === Google Sheets Config ===
SPREADSHEET_ID = '1rOX2ULAQ4fAMfDijPcDynpaQx-rwwhKBXyNRi89T58o'
CREDENTIALS_FILE = 'credentials.json'
# ==== email ===
EMAIL_SENDER = "phanthanhdat25082003@gmail.com"
EMAIL_PASSWORD = "qwafdvecgpdnfelj"
EMAIL_RECEIVER = "phanthanhdat0825@gmail.com"
creds = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
sheet_service = build('sheets', 'v4', credentials=creds)

# === GPIO Config ===
BUZZER_PIN = 27
HALL_PIN = 22
GPIO.setmode(GPIO.BCM)
GPIO.setup(HALL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# === ADC for force sensors ===
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
force_top = AnalogIn(ads, ADS.P0)
force_forehead = AnalogIn(ads, ADS.P2)
force_left = AnalogIn(ads, ADS.P1)   # A1 bên trái
force_right = AnalogIn(ads, ADS.P3)  # A3 bên phải
FORCE_THRESHOLD = 2000

# === Load label and TFLite model ===
with open("labelmap.txt", "r") as f:
    labels = f.read().splitlines()

interpreter = tflite.Interpreter(model_path="model.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_height = input_details[0]['shape'][1]
input_width = input_details[0]['shape'][2]

# === Load sklearn model ===
bus = smbus2.SMBus(1)
MPU6050_ADDR = 0x68
model = joblib.load("mpu6050_rf_model.pkl")
ENABLE_FORCE = True
ENABLE_MPU = True
ENABLE_HALL = True

def init_mpu():
    bus.write_byte_data(MPU6050_ADDR, 0x6B, 0)
    time.sleep(0.1)

def read_raw_data(addr):
    high = bus.read_byte_data(MPU6050_ADDR, addr)
    low = bus.read_byte_data(MPU6050_ADDR, addr+1)
    value = ((high << 8) | low)
    if value > 32768:
        value = value - 65536
    return value

def read_mpu6050():
    ax = read_raw_data(0x3B) / 16384.0
    ay = read_raw_data(0x3D) / 16384.0
    az = read_raw_data(0x3F) / 16384.0
    gx = read_raw_data(0x43) / 131.0
    gy = read_raw_data(0x45) / 131.0
    gz = read_raw_data(0x47) / 131.0
    return ax, ay, az, gx, gy, gz

def predict_behavior(ax, ay, az, gx, gy, gz):
    input_data = pd.DataFrame([[ax, ay, az, gx, gy, gz]],
                              columns=["ax", "ay", "az", "gx", "gy", "gz"])
    return model.predict(input_data)[0]

def get_latest_ip():
    try:
        result = sheet_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Main!A2:M"
        ).execute()
        values = result.get('values', [])
        if values:
            return values[-1][1]
    except Exception as e:
        print("❌ Lỗi đọc IP từ Google Sheets:", e)
    return None

def get_pi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Unknown"

        
def append_status_to_sheet(detect1, detect2, detect3, conclusion,
                           accident_flag=0,
                           detection_source='',
                           esp_response='',
                           gps_location='',
                           note=''):
    try:
        current_time = datetime.now().strftime('%H:%M:%S')
        current_date = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        esp_ip = get_latest_ip() or ''
        pi_ip = get_pi_ip()

        body = {
            'values': [[
                current_date, esp_ip, pi_ip, current_time,
                detect1, detect2, detect3, conclusion,
                accident_flag, detection_source, esp_response,
                gps_location, note
            ]]
        }
        sheet_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Main!A2",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        print("✅ Đã ghi trạng thái + tai nạn lên Google Sheets.")
    except Exception as e:
        print("⚠️ Lỗi ghi Google Sheets:", e)


def upload_pi_ip_only():
    try:
        current_date = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        pi_ip = get_pi_ip()

        body = {
            'values': [[
                current_date, pi_ip
            ]]
        }
        sheet_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="RaspberryIP!A1",  # 🚀 Sheet mới tên RaspberryIP
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",  # luôn chèn dòng mới
            body=body
        ).execute()
        print(f"✅ Đã ghi Pi IP lên Sheet RaspberryIP: {pi_ip}")
    except Exception as e:
        print("⚠️ Lỗi khi ghi Pi IP:", e)

def auto_upload_pi_ip():
    upload_pi_ip_only()  # 🚀 Ghi 1 lần duy nhất khi khởi động


def detect_image(image_path):
    img = Image.open(image_path).convert('RGB')
    img = img.rotate(180)
    img = img.resize((input_width, input_height))
    img = ImageEnhance.Sharpness(img).enhance(2)

    input_data = np.expand_dims(np.array(img, dtype=np.uint8), axis=0)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    classes = interpreter.get_tensor(output_details[1]['index'])[0]
    scores = interpreter.get_tensor(output_details[2]['index'])[0]

    for i in range(len(scores)):
        if scores[i] > 0.5:
            label = labels[int(classes[i])]
            print(f"🎯 Phát hiện: {label} ({scores[i]*100:.1f}%)")
            if label in ['person', 'mask', 'glasses']:
                return True
    return False

def play_buzzer():
    print("🔊 Buzzer được kích hoạt")
    try:
        for _ in range(3):
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            time.sleep(0.3)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            time.sleep(0.2)
    except Exception as e:
        print("❌ Lỗi khi phát buzzer:", e)

app = Flask(__name__)

# === Biến lưu trạng thái ===
current_status = {
    "step": "🕹️ Khởi động hệ thống...",
    "progress": 0,
    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "gx": 0.0,
    "ax": 0.0
}


def update_status(step_text, progress_value):
    global current_status
    current_status["step"] = step_text
    current_status["progress"] = progress_value
    current_status["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
from flask import jsonify
@app.route('/status', methods=['GET'])
def get_status():
    return current_status



@app.route('/buzzer', methods=["GET"])
def remote_buzzer():
    Thread(target=play_buzzer).start()
    return "🔔 Buzzer từ HTTP đã chạy!"


@app.route('/api/buzzer', methods=['GET'])
def api_buzzer():
    state = request.args.get('state', 'off')
    print(f"🔔 API Buzzer yêu cầu: {state}")

    if state == 'on':
        Thread(target=play_buzzer).start()
        return "✅ Buzzer ON"
    else:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        return "✅ Buzzer OFF"
    
@app.route('/api/relay', methods=['GET'])
def api_relay():
    state = request.args.get('state', 'off')
    esp32_ip = get_latest_ip()
    if not esp32_ip:
        return "❌ Không có IP ESP32"

    try:
        url = f"http://{esp32_ip}/relay?state={state}"
        print(f"➡️ Forward relay to ESP32: {url}")
        response = requests.get(url, timeout=3)
        return f"✅ ESP32 relay {state} → {response.text}"
    except Exception as e:
        return f"⚠️ Lỗi gửi relay tới ESP32: {str(e)}"

@app.route('/api/sensor_control', methods=['GET'])
def api_sensor_control():
    global ENABLE_FORCE, ENABLE_MPU, ENABLE_HALL

    sensor = request.args.get('sensor', '')
    state = request.args.get('state', 'off')
    enabled = (state == 'on')

    print(f"🔄 Yêu cầu điều khiển sensor: {sensor}, trạng thái: {state}")

    if sensor == 'force':
        ENABLE_FORCE = enabled
        return f"✅ Force sensor set to {state}"
    elif sensor == 'mpu':
        ENABLE_MPU = enabled
        return f"✅ MPU6050 set to {state}"
    elif sensor == 'hall':
        ENABLE_HALL = enabled
        return f"✅ Hall sensor set to {state}"
    else:
        return f"❌ Không rõ sensor: {sensor}"

@app.route('/alert_sw', methods=['POST'])
def alert_sw():
    global current_status, last_call_time

    print("🚨 [ESP32] CẢM BIẾN SW420 + SW520 > 3s → BÁO VỀ PI")
    print(f"🤖 Trạng thái MPU hiện tại: {current_status['step']}")

    if 'fall' in current_status['step']:
        now = datetime.now()
        if (now - last_call_time) > timedelta(seconds=7):
            print("📞 PHÁT HIỆN FALL → GỌI NGƯỢC LẠI ESP32 (alert_mpu)!")
            print("📧 Gửi email cảnh báo ngay lập tức sau khi gửi alert_mpu...")
            send_emergency_email(
                    subject="📞 Goi khan cap",
                    body="Da kich hoat goi khan cap tai vi tri 10.730333,106.697683")
            esp32_ip = get_latest_ip()
            if esp32_ip:
                try:
                    url_alert = f"http://{esp32_ip}/alert_mpu"
                    
                    response = requests.get(url_alert, timeout=5)
                    print(f"📨 ESP32 trả lời: {response.text.strip()}")
                except Exception as e:
                    print(f"⚠️ Lỗi gửi alert_mpu tới ESP32: {e}")
            last_call_time = now
            return "OK - Đã gọi alert_mpu cho ESP32!"
        else:
            print("⏳ ĐANG CHỜ 7 GIÂY... Không gọi lại.")
            return "OK - Đang chờ (không gọi lại)"
    else:
        print("ℹ️ Không phải fall → chưa gọi.")
        return "OK - Chưa gọi (chưa fall)."
@app.route('/api/set_phone', methods=['GET'])
def api_set_phone():
    esp32_ip = get_latest_ip()
    if not esp32_ip:
        return "❌ Không có IP ESP32"

    phone = request.args.get('phone', '')
    if not phone:
        return "❌ Thiếu tham số phone"

    try:
        url = f"http://{esp32_ip}/set_phone?phone={phone}"
        print(f"➡️ Forward set_phone to ESP32: {url}")
        response = requests.get(url, timeout=3)
        return f"✅ ESP32 set_phone → {response.text}"
    except Exception as e:
        return f"⚠️ Lỗi gửi set_phone tới ESP32: {str(e)}"

@app.route('/log_call_done', methods=['POST'])
def log_call_done():
    print("📞 Đã nhận log_call_done từ ESP32")
    # Có thể:
    # - ghi vào Google Sheet
    # - hoặc gọi app incrementCounter('call')
    # - hoặc set biến nhớ
    
    return "OK - Call logged"

@app.route('/api/alert_mpu')
def api_alert_mpu():
    esp32_ip = get_latest_ip()
    if not esp32_ip:
        return "❌ Không có IP ESP32"

    try:
        url_alert = f"http://{esp32_ip}/alert_mpu"
        
        
        print(f"➡️ Gửi alert_mpu tới ESP32: {url_alert}")
        response = requests.get(url_alert, timeout=5)
        return f"✅ ESP32 alert_mpu → {response.text.strip()}"
    except Exception as e:
        return f"⚠️ Lỗi gửi alert_mpu tới ESP32: {e}"

def continuous_mpu_monitor():
    global ENABLE_MPU
    init_mpu()
    while True:
        if not ENABLE_MPU:
            time.sleep(1)
            continue

        ax, ay, az, gx, gy, gz = read_mpu6050()
        result = predict_behavior(ax, ay, az, gx, gy, gz)
        print(f"[MPU6050] 🤖 Dự đoán liên tục: {result}")
        current_status.update({
        "step": f"🤖 Dự đoán: {result}",
        "progress": 6,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "gx": gx,
        "ax": ax,
	"ay": ay,
	"az": az
})
        update_status(f"🤖 Dự đoán: {result}", 6)
        time.sleep(3)
def monitor_force_left_right():
    global ENABLE_FORCE
    while True:
        if not ENABLE_FORCE:
            time.sleep(1)
            continue

        v_left = max(force_left.value - 300000, 0)
        v_right = force_right.value

        if v_left > FORCE_THRESHOLD or v_right > FORCE_THRESHOLD:
            print(f"⚠️ Phat hien luc bat thuong")
            play_buzzer()
            send_emergency_email(
                        subject="📩 Luc bat thuong",
                        body="Luc Bat Thuong Tai Toa Do 10.730333,106.697683")
            # 🆕 Gửi yêu cầu gửi tin nhắn qua ESP32
            esp32_ip = get_latest_ip()
            if esp32_ip:
                try:
                    msg = "Luc Bat Thuong Tai Toa Do 10.730333,106.697683"
                    url_sms = f"http://{esp32_ip}/send_sms?msg={msg}"
                    response = requests.get(url_sms, timeout=5)
                    
                    print(f"📨 Send SMS: {response.text.strip()}")
                except Exception as e:
                    print(f"❌ ERROR SEND SMS to ESP32: {e}")

            append_status_to_sheet(
                1, 1, 1, 1,
                accident_flag=0,
                detection_source='force_sensor',
                gps_location="10.730333, 106.697683",
                note="Lực bất thường trái/phải"
            )
            time.sleep(5)
        time.sleep(0.5)



def continuous_hall_monitor():
    global ENABLE_HALL
    print("✅ QUY TRÌNH HOÀN TẤT. BẮT ĐẦU GIÁM SÁT LIÊN TỤC...")
    last_state = GPIO.LOW
    while True:
        if not ENABLE_HALL:
            time.sleep(1)
            continue

        current_state = GPIO.input(HALL_PIN)
        if current_state == GPIO.LOW and last_state == GPIO.HIGH:
            print("📍 Phát hiện nam châm mới → Kích hoạt buzzer.")
            play_buzzer()
        last_state = current_state
        time.sleep(0.5)

def main_process():
    try:
        print("🕹️ Khởi động hệ thống kiểm tra mũ bảo hiểm...")
        detect1 = detect2 = detect3 = 0

        print("⏳ Đang chờ đủ lực...")
        update_status("⏳ Đang chờ đủ lực...", 1)
        while True:
            if force_top.value > FORCE_THRESHOLD and force_forehead.value > FORCE_THRESHOLD:
                print("✅ Lực đạt yêu cầu.")
                detect1 = 1
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                time.sleep(0.3)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                break
            time.sleep(1)
        
        time.sleep(1)
        print("📸 Chụp ảnh để nhận diện...")
        update_status("📸 Đang nhận diện người đội mũ...", 2)
        while True:
            os.system("libcamera-still -o image.jpg --width 320 --height 240 -n -t 100")
            if detect_image("image.jpg"):
                print("✅ Đã nhận diện có người đội mũ.")
                detect2 = 1
                break
            else:
                print("⛔ Không phát hiện người đội mũ. Chụp lại...")
                time.sleep(2)

        print("⏳ Đang chờ gài quai nón...")
        update_status("⏳ Đang chờ gài quai nón...", 3)
        while True:
            if GPIO.input(HALL_PIN) == GPIO.HIGH:
                print("🟢 Đã gài quai nón.")
                update_status("🟢 Đã gài quai nón, khởi động xe...", 4)
                play_buzzer()
                detect3 = 1
                break
            print("🔴 Chưa gài quai...")
            time.sleep(1)

        esp32_ip = get_latest_ip()
        if esp32_ip:
            try:
                url = f"http://{esp32_ip}/relay?state=on"
                response = requests.get(url, timeout=3)
                print("✅ ESP32 phản hồi:", response.text)
            except Exception as e:
                print("⚠️ Lỗi gửi đến ESP32:", e)

        init_mpu()
        ax, ay, az, gx, gy, gz = read_mpu6050()
        behavior_result = predict_behavior(ax, ay, az, gx, gy, gz)
        print(f"🤖 Hành vi được dự đoán: {behavior_result}")
        update_status(f"🤖 Hành vi: {behavior_result}", 5)

        # abnormal_detected = behavior_result in ["fall", "crash", "abnormal"]
        # if abnormal_detected and esp32_ip:
            
        #     url_alert = f"http://{esp32_ip}/alert_mpu"
        #     try:
        #         response_alert = requests.get(url_alert, timeout=5)
        #         result = response_alert.text.strip()
        #         print(f"📨 ESP32 trả lời: {result}")
        #     except Exception as e:
        #         print("⚠️ ESP32 không phản hồi:", e)
        #         result = "NO_RESPONSE"
        #     print("🚨 Xác nhận tai nạn → xử lý khẩn cấp...")
        #     play_buzzer()
        #     append_status_to_sheet(
        #             detect1, detect2, detect3, 1,
        #             accident_flag=1,
        #             detection_source="MPU6050",
        #             esp_response=result,
        #             gps_location="10.730592740620942, 106.69800229033699",
        #             note="Tăng tốc đột ngột và rung/nghiêng"
        #             )
            
            

        conclusion = 1 if detect1 and detect2 and detect3 else 0
        append_status_to_sheet(detect1, detect2, detect3, conclusion)

        Thread(target=continuous_hall_monitor, daemon=True).start()
        Thread(target=continuous_mpu_monitor, daemon=True).start()
        Thread(target=monitor_force_left_right, daemon=True).start()
        update_status("🤖 Đang giám sát liên tục với MPU6050...", 6)

    except KeyboardInterrupt:
        print("\n⛔ Dừng bằng tay.")
    except KeyboardInterrupt:
        print("\n⛔ Dừng bằng tay.")
        GPIO.cleanup()
        print("🧹 Đã giải phóng GPIO.")

if __name__ == "__main__":
    Thread(target=auto_upload_pi_ip, daemon=True).start()  # 🚀 Ghi IP lên RaspberryIP
    Thread(target=main_process).start()
    app.run(host="0.0.0.0", port=5000)
