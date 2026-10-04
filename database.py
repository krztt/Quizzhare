import sqlite3
from contextlib import contextmanager

DB_PATH = "local_reviewer.db"


@contextmanager
def _connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database():
    """Creates the necessary tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for organizational folders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table for individual quizzes or PDF reviewers linked to a course
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            title TEXT NOT NULL,
            material_type TEXT NOT NULL, -- 'quiz' or 'pdf'
            file_path TEXT, -- Null if it's a built-in quiz, populated if it's a local PDF
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    ''')

    conn.commit()
    conn.close()


def create_course(course_name):
    with _connection() as conn:
        cursor = conn.execute(
            "INSERT INTO courses (course_name) VALUES (?)",
            (course_name.strip(),),
        )
        return cursor.lastrowid


def get_courses():
    with _connection() as conn:
        return conn.execute(
            "SELECT id, course_name, created_at FROM courses ORDER BY course_name"
        ).fetchall()


def rename_course(course_id, course_name):
    with _connection() as conn:
        cursor = conn.execute(
            "UPDATE courses SET course_name = ? WHERE id = ?",
            (course_name.strip(), course_id),
        )
        return cursor.rowcount > 0


def delete_course(course_id):
    with _connection() as conn:
        conn.execute("DELETE FROM materials WHERE course_id = ?", (course_id,))
        cursor = conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        return cursor.rowcount > 0


def add_material(course_id, title, material_type, file_path):
    with _connection() as conn:
        conn.execute(
            "INSERT INTO materials (course_id, title, material_type, file_path) "
            "VALUES (?, ?, ?, ?)",
            (course_id, title, material_type, file_path),
        )


def update_material(material_id, title):
    with _connection() as conn:
        cursor = conn.execute(
            "UPDATE materials SET title = ? WHERE id = ?",
            (title.strip(), material_id),
        )
        return cursor.rowcount > 0


def delete_material(material_id):
    with _connection() as conn:
        cursor = conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        return cursor.rowcount > 0


def get_materials(course_id=None):
    query = "SELECT id, course_id, title, material_type, file_path FROM materials"
    params = ()
    if course_id is not None:
        query += " WHERE course_id = ?"
        params = (course_id,)
    query += " ORDER BY id DESC"
    with _connection() as conn:
        return conn.execute(query, params).fetchall()

if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")