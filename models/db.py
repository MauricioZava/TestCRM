import os
import sqlite3

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db")


def get_conn():
    return sqlite3.connect(DB_NAME)
