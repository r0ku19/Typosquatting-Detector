import os

try:
    import mysql.connector as mysql_connector
except ImportError as exc:  # pragma: no cover - seeder needs MySQL connector at runtime.
    raise RuntimeError("mysql-connector-python is required to run the database seeder.") from exc


DB_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "NewPasswordHere")
DB_NAME = os.getenv("MYSQL_DATABASE", "govph_typosquat")


LEGITIMATE_DOMAINS = [
    ("gov.ph", "Government of the Philippines"),
    ("philhealth.gov.ph", "PhilHealth"),
    ("bir.gov.ph", "Bureau of Internal Revenue"),
    ("lto.gov.ph", "Land Transportation Office"),
    ("pnp.gov.ph", "Philippine National Police"),
    ("deped.gov.ph", "Department of Education"),
    ("dfa.gov.ph", "Department of Foreign Affairs"),
    ("dilg.gov.ph", "Department of the Interior and Local Government"),
    ("dict.gov.ph", "Department of Information and Communications Technology"),
    ("neda.gov.ph", "National Economic and Development Authority"),
]


def connect(database=None):
    config = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if database:
        config["database"] = database
    return mysql_connector.connect(**config)


def main():
    root_connection = connect()
    root_cursor = root_connection.cursor()
    root_cursor.execute(
        f"""
        CREATE DATABASE IF NOT EXISTS `{DB_NAME}`
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
        """.strip()
    )
    root_cursor.close()
    root_connection.close()

    connection = connect(DB_NAME)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS legitimate_domains (
            id INT AUTO_INCREMENT PRIMARY KEY,
            domain VARCHAR(255) NOT NULL UNIQUE,
            organization_name VARCHAR(255) NOT NULL,
            active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """.strip()
    )

    insert_sql = """
        INSERT INTO legitimate_domains (domain, organization_name, active)
        VALUES (%s, %s, 1)
        ON DUPLICATE KEY UPDATE
            organization_name = VALUES(organization_name),
            active = VALUES(active)
    """
    cursor.executemany(insert_sql, LEGITIMATE_DOMAINS)
    connection.commit()
    seeded_count = len(LEGITIMATE_DOMAINS)
    cursor.close()
    connection.close()

    print(f"Seeded {seeded_count} legitimate .gov.ph domains into `{DB_NAME}`.")


if __name__ == "__main__":
    main()