from werkzeug.security import check_password_hash, generate_password_hash

# Constant-time-ish login: always run a hash check, even for unknown users.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method="pbkdf2:sha256:1000")


def create_user(conn, username, password, role, department, method="scrypt") -> bool:
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return False
    conn.execute(
        "INSERT INTO users (username, password_hash, role, department) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password, method=method), role, department),
    )
    return True


def authenticate(conn, username, password):
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username or "",)).fetchone()
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password or "")
    return row if (row and ok) else None
