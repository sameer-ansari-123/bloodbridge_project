import mysql.connector
import os

db_config = {
    'host': os.environ.get("MYSQL_HOST", "localhost"),
    'port': int(os.environ.get("MYSQL_PORT", 3306)),
    'user': os.environ.get("MYSQL_USER", "root"),
    'password': os.environ.get("MYSQL_PASSWORD", "Sameer@123"),
    'database': os.environ.get("MYSQL_DATABASE", "bloodbridge_db")
}

def migrate():
    print("Running migration to add latitude and longitude to valid users...")
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("SHOW COLUMNS FROM users LIKE 'latitude'")
        has_lat = cursor.fetchone()
        
        if not has_lat:
            print("Adding columns to `users` table...")
            cursor.execute("ALTER TABLE users ADD COLUMN latitude DECIMAL(10, 8) NULL")
            cursor.execute("ALTER TABLE users ADD COLUMN longitude DECIMAL(11, 8) NULL")
            conn.commit()
            print("Columns added successfully.")
        else:
            print("Columns already exist.")

        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == '__main__':
    migrate()
