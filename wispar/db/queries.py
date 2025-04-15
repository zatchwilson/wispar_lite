import MySQLdb

db = MySQLdb.connect(host="localhost", user="root", password="password", database="wispar_db")
db_cursor = db.cursor()
db_cursor.execute("describe books;")
results = db_cursor.fetchall()
for result in results:
    print(result)
    print("\n")