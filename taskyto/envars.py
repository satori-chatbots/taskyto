import os

DB_PORT = None

try:
    DB_PORT = int(os.getenv("DB_PORT"))
except Exception as e:
    pass

if __name__ == "__main__":
    if DB_PORT:
        print("""Using DB""")
    else:
        print("""Not using DB""")

    print(DB_PORT, type(DB_PORT))

