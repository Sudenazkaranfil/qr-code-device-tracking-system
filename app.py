from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()  # .env dosyasını yükle

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "varsayilan_gizli_anahtar")  # .env'den al, yoksa yedek

# Veritabanı bağlantısı
def get_connection():
    return psycopg2.connect(os.getenv("DB_URL"), sslmode="require")

# Ana sayfa: Admin giriş formu
@app.route("/")
def home():
    return render_template("index.html")

# Admin giriş POST işlemi
@app.route("/admin_login", methods=["POST"])
def admin_login():
    email = request.form.get("email")
    password = request.form.get("password")

    if email.lower() == os.getenv("ADMIN_EMAIL").lower() and password == os.getenv("ADMIN_PASSWORD"):
        session["admin"] = True
        return redirect(url_for("admin_panel"))
    else:
        return render_template("index.html", login_error="❌ Giriş başarısız.")

# Admin paneli (korumalı)
@app.route("/admin")
def admin_panel():
    if not session.get("admin"):
        flash("Önce giriş yapmalısınız.", "warning")
        return redirect(url_for("home"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, device_id, usage_start, usage_end FROM device_tracking ORDER BY usage_start DESC")
    kayitlar = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_panel.html", kayitlar=kayitlar)

# Admin çıkış
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Başarıyla çıkış yapıldı.", "success")
    return redirect(url_for("home"))

def send_admin_email(email, device_name):
    admin_email = os.getenv("ADMIN_EMAIL")
    from_email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    subject = f"Cihaz Girişi: {device_name}"
    body = f"{email} kullanıcısı şu cihaza giriş yaptı: {device_name}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = admin_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(os.getenv("EMAIL_HOST"), int(os.getenv("EMAIL_PORT"))) as server:
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
        print("📨 Admin'e e-posta gönderildi.")
    except Exception as e:
        print(f"❌ E-posta gönderilemedi: {e}")

@app.route("/cihaz/<int:device_id>", methods=["GET", "POST"])
def device_entry(device_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Cihaz adı sorgulaması
    cursor.execute("SELECT device_name FROM devices WHERE device_id = %s", (device_id,))
    device = cursor.fetchone()
    device_name = device[0] if device else "Tanımsız Cihaz"

    if request.method == "POST":
        email = request.form["email"]

        # Kullanıcıyı bul
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result:
            user_id = result[0]
        else:
            cursor.close()
            conn.close()
            return render_template("device_entry.html", device_id=device_id, device_name=device_name, error="❌ Böyle bir kullanıcı bulunamadı.")

        # Cihazda aktif bir kullanıcı olup olmadığını kontrol et
        cursor.execute("""
            SELECT id, user_id, email FROM device_tracking
            WHERE CAST(device_id AS INTEGER) = %s AND usage_end IS NULL
            ORDER BY usage_start DESC LIMIT 1
        """, (device_id,))
        ongoing = cursor.fetchone()

        if ongoing:
            # Eğer aynı kullanıcı ise çıkış yapılacak
            if ongoing[1] == user_id:
                cursor.execute("""
                    UPDATE device_tracking
                    SET usage_end = %s
                    WHERE id = %s
                """, (datetime.now(), ongoing[0]))
                conn.commit()

                # Mail gönder (çıkış)
                send_admin_email(email, device_name + " cihazından ÇIKIŞ yapıldı.")
                message = "Çıkış yapıldı."

            else:
                # Önceki kullanıcıyı çıkart
                cursor.execute("""
                    UPDATE device_tracking
                    SET usage_end = %s
                    WHERE id = %s
                """, (datetime.now(), ongoing[0]))

                # Yeni kullanıcıyı kaydet
                cursor.execute("""
                    INSERT INTO device_tracking (user_id, device_id, usage_start, email)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, device_id, datetime.now(), email))
                conn.commit()

                send_admin_email(email, device_name + " cihazına GİRİŞ yapıldı. (önceki kullanıcı çıkış yaptı)")
                message = "Başka bir kullanıcı çıkış yaptı ve yeni giriş kaydedildi."

        else:
            # Eğer aktif kullanıcı yoksa direkt yeni giriş
            cursor.execute("""
                INSERT INTO device_tracking (user_id, device_id, usage_start, email)
                VALUES (%s, %s, %s, %s)
            """, (user_id, device_id, datetime.now(), email))
            conn.commit()

            send_admin_email(email, device_name + " cihazına GİRİŞ yapıldı.")
            message = "Yeni giriş kaydedildi."

        cursor.close()
        conn.close()

        return render_template("thanks.html", email=email, message=message, device_id=device_id)

    cursor.close()
    conn.close()
    return render_template("device_entry.html", device_id=device_id, device_name=device_name)

# UptimeRobot kontrolü için sağlık rotası (isteğe bağlı)
@app.route("/ping")
def ping():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))  # Render'da port dinamik olabilir
    app.run(debug=True, port=port, host="0.0.0.0")
