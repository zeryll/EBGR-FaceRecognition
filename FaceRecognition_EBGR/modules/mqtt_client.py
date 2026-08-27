import paho.mqtt.client as mqtt
import json
import threading

# Konfigurasi Broker MQTT Publik (Sebagai simulasi Server E-BGR)
# Di dunia nyata nanti bisa diganti dengan IP lokal server E-BGR, misal: "192.168.1.10"
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_CHECKIN = "ebgr/tamu/checkin"
MQTT_TOPIC_CHECKOUT = "ebgr/tamu/checkout"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Berhasil terhubung ke Broker E-BGR!")
    else:
        print(f"[MQTT ERROR] Gagal terhubung, return code {rc}")

def send_message_async(topic, payload_dict):
    """Fungsi internal untuk mengirim pesan di background thread"""
    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Konversi dictionary ke JSON string
        payload_json = json.dumps(payload_dict)
        
        # Publish ke topik
        client.publish(topic, payload_json)
        print(f"\n[MQTT SEND] Topik: {topic} | Payload: {payload_json}")
        
        client.disconnect()
    except Exception as e:
        print(f"[MQTT EXCEPTION] Gagal mengirim data: {e}")

def publish_checkin(id_tamu, nama):
    """
    Kirim notifikasi check-in ke E-BGR.
    Berjalan secara asinkron agar tidak membuat aplikasi GUI (Tkinter) macet (lag).
    """
    payload = {
        "id_tamu": id_tamu,
        "nama": nama,
        "event": "check-in",
        "status": "success",
        "timestamp": "CURRENT_TIMESTAMP" # Di dunia nyata ambil datetime.now()
    }
    # Gunakan thread agar tidak blocking UI
    thread = threading.Thread(target=send_message_async, args=(MQTT_TOPIC_CHECKIN, payload))
    thread.daemon = True
    thread.start()

def publish_checkout(id_tamu, nama):
    """
    Kirim notifikasi check-out ke E-BGR.
    """
    payload = {
        "id_tamu": id_tamu,
        "nama": nama,
        "event": "check-out",
        "status": "success",
        "timestamp": "CURRENT_TIMESTAMP"
    }
    thread = threading.Thread(target=send_message_async, args=(MQTT_TOPIC_CHECKOUT, payload))
    thread.daemon = True
    thread.start()
