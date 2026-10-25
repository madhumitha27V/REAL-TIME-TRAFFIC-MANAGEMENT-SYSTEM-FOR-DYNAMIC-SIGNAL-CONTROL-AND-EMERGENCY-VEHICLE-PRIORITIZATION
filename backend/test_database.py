
from backend.database import get_db_connection

connection = get_db_connection()

try:
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES")

    print("MySQL connected successfully!")
    for table in cursor.fetchall():
        print(table[0])

    cursor.close()
finally:
    connection.close()
