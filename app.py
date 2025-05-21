from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükler

app = Flask(__name__)

# Veritabanı bağlantısı
def get_connection():
    return psycopg2.connect(os.getenv("DB_URL"), sslmode="require")
    
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/admin")
def admin_panel():
    if not session.get("admin"):
        flash("Önce giriş yapmalısınız.", "warning")
        return redirect(url_for("home"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, cihaz_id, usage_start, usage_end FROM device_tracking ORDER BY usage_start DESC")
    kayitlar = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_panel.html", kayitlar=kayitlar)
@app.route("/admin_login", methods=["POST"])
def admin_login():
    email = request.form.get("email")
    password = request.form.get("password")

    if email.lower() == os.getenv("ADMIN_EMAIL").lower() and password == os.getenv("ADMIN_PASSWORD"):
        session["admin"] = True
        return redirect(url_for("admin_panel"))

    else:
        return render_template("index.html", login_error="❌ Giriş başarısız.")

@app.route("/cihaz/<int:device_id>", methods=["GET", "POST"])
def device_entry(device_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Cihaz adı sorgulaması
    cursor.execute("SELECT device_name FROM devices WHERE device_id = %s", (device_id,))
    device = cursor.fetchone()

    device_name = None
    if device:
        device_name = device[0]

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
            SELECT id, user_id FROM device_tracking
            WHERE CAST(device_id AS INTEGER) = %s AND usage_end IS NULL
            ORDER BY usage_start DESC LIMIT 1
        """, (device_id,))

        ongoing = cursor.fetchone()

        if ongoing:
            if ongoing[1] == user_id:
                # Aynı kullanıcı tekrar okuttuğunda, çıkış yapılacak ama giriş kaydı oluşturulmayacak
                cursor.execute("""
                    UPDATE device_tracking
                    SET usage_end = %s
                    WHERE id = %s
                """, (datetime.now(), ongoing[0]))
                message = "Çıkış yapıldı."
            else:
                # Farklı bir kullanıcı okuduysa, önceki kullanıcıyı çıkartıp yeni kullanıcıyı kaydedelim
                cursor.execute("""
                    UPDATE device_tracking
                    SET usage_end = %s
                    WHERE id = %s
                """, (datetime.now(), ongoing[0]))
                # Yeni kullanıcıyı giriş kaydediyoruz
                cursor.execute("""
                    INSERT INTO device_tracking (user_id, device_id, usage_start, email)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, device_id, datetime.now(), email))
                message = "Başka bir kullanıcı çıkış yaptı ve yeni giriş kaydedildi."
        else:
            # Eğer aktif bir kullanıcı yoksa, direkt yeni kullanıcı kaydedeceğiz
            cursor.execute("""
                INSERT INTO device_tracking (user_id, device_id, usage_start, email)
                VALUES (%s, %s, %s, %s)
            """, (user_id, device_id, datetime.now(), email))
            message = "Yeni giriş kaydedildi."

        conn.commit()
        cursor.close()
        conn.close()

        return render_template("thanks.html", email=email, message=message, device_name=device_name, device_id=device_id)

    cursor.close()
    conn.close()
    # device_id'yi string'e dönüştürme
    device_id = str(device_id)
    return render_template("device_entry.html", device_id=device_id, device_name=device_name)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))  # Render'da port dinamik olabilir
    app.run(debug=True, port=port, host="0.0.0.0")

