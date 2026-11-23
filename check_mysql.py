import os
import sys
import dotenv

dotenv.load_dotenv()

try:
    import pymysql
except ImportError:
    print("[ERROR] PyMySQL is not installed. Run: pip install pymysql")
    sys.exit(1)

host = os.getenv('DB_HOST', '127.0.0.1')
port = int(os.getenv('DB_PORT', '3306'))
user = os.getenv('DB_USER', 'root')
password = os.getenv('DB_PASSWORD', '')
db_name = os.getenv('DB_NAME', 'techravisha_db')

print("=" * 60)
print(" TechRavisha MySQL Connection Diagnostic Tool")
print("=" * 60)
print(f"Host:     {host}:{port}")
print(f"User:     {user}")
print(f"Password: {'(blank / empty)' if not password else '********'}")
print(f"Database: {db_name}")
print("-" * 60)

# 1. Try connecting with current credentials
def test_connection(pwd):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=pwd,
            connect_timeout=3
        )
        return conn, None
    except Exception as e:
        return None, e

conn, err = test_connection(password)

if conn:
    print("[SUCCESS] Connected to MySQL successfully with current credentials!")
    with conn.cursor() as cur:
        cur.execute("SHOW DATABASES;")
        databases = [row[0] for row in cur.fetchall()]
        if db_name in databases:
            print(f"[SUCCESS] Database '{db_name}' already exists.")
        else:
            print(f"[INFO] Database '{db_name}' does not exist. Creating it now...")
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print(f"[SUCCESS] Database '{db_name}' created successfully!")
    conn.close()
    print("-" * 60)
    print("Next step: Run the following commands in your terminal:")
    print("  python manage.py migrate")
    print("  python manage.py loaddata initial_data.json")
    print("  python manage.py runserver")
    print("=" * 60)
    sys.exit(0)

# If connection failed with 1045, test common passwords to assist the user
err_code = getattr(err, 'args', [None])[0] if err else None
print(f"[FAILED] Could not connect: {err}")

if err_code == 1045:
    print("\n[INFO] 'Access denied' means MySQL root user requires a password.")
    print("Testing common default passwords...")
    common_passwords = ['root', 'admin', '1234', '123456', '12345678', 'password', 'mysql', 'toor']
    matched_pwd = None
    for trial_pwd in common_passwords:
        test_conn, _ = test_connection(trial_pwd)
        if test_conn:
            matched_pwd = trial_pwd
            test_conn.close()
            break
    
    if matched_pwd:
        print(f"\n>>> [MATCH FOUND!] Your MySQL root password is: '{matched_pwd}'")
        print(f">>> Please update your backend\\.env file:")
        print(f"    DB_PASSWORD={matched_pwd}")
    else:
        print("\n>>> Please set your MySQL root password in 'backend\\.env':")
        print("    DB_PASSWORD=your_actual_mysql_password")
        print("\n(Tip: Agar aap password bhul gaye hain ya bina setup ke turant chalana chahte hain,")
        print(" toh backend\\.env me 'DB_ENGINE=sqlite' set kar ke turant chala sakte hain.)")

print("=" * 60)

