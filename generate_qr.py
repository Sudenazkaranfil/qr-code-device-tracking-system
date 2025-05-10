import qrcode, os

base_url = "https://kuyam-cihaz-takip-sistemi.onrender.com/cihaz"
os.makedirs("qr_codes", exist_ok=True)

# Cihazlar (id) listesi
devices = [{"id": i} for i in range(1, 59)]

# QR kodlarını oluşturma
for device in devices:
    url = f"{base_url}/{device['id']}"  # Her cihaz için URL
    qr = qrcode.make(url)
    qr_filename = f"qr_codes/{device['id']}.png"  # QR dosya ismi sadece device_id olacak
    qr.save(qr_filename)

print("Tüm QR'ler oluşturuldu.")
