import os
import mysql.connector
import random

db_config = {
    'host': os.environ.get("MYSQL_HOST", "localhost"),
    'port': int(os.environ.get("MYSQL_PORT", 3306)),
    'user': os.environ.get("MYSQL_USER", "root"),
    'password': os.environ.get("MYSQL_PASSWORD", "Sameer@123"),
    'database': os.environ.get("MYSQL_DATABASE", "bloodbridge_db")
}

def seed_locations():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM users WHERE latitude IS NULL OR longitude IS NULL")
        users = cursor.fetchall()
        
        if not users:
            print("All users already have coordinates!")
            return
            
        print(f"Adding mock coordinates to {len(users)} users...")
        
        # New York base coordinates roughly
        base_lat = 40.7128
        base_lng = -74.0060
        
        for user in users:
            # Random offset roughly within 10-20km
            lat = base_lat + random.uniform(-0.1, 0.1)
            lng = base_lng + random.uniform(-0.1, 0.1)
            
            cursor.execute("UPDATE users SET latitude = %s, longitude = %s WHERE id = %s", 
                           (lat, lng, user['id']))
        
        conn.commit()
        conn.close()
        print("Mock coordinates added! Refresh the map to see the donors.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    seed_locations()
