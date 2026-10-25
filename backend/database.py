
import os
import mysql.connector
from mysql.connector import Error


def get_db_connection():
    try:
        config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": "defaultdb" if os.getenv("DB_HOST") else "smartflow_ai",
        }

        # Verify Aiven's TLS certificate when a CA certificate is configured.
        ca_path = os.getenv("DB_SSL_CA")
        if os.getenv("DB_HOST") and ca_path:
            config["ssl_ca"] = ca_path
            config["ssl_verify_cert"] = True
            config["ssl_verify_identity"] = True

        connection = mysql.connector.connect(**config)
        return connection

    except Error as error:
        print(f"MySQL connection failed: {error}")
        raise
