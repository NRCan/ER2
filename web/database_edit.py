import sqlite3
from werkzeug.security import generate_password_hash
import random
import string
import csv

def randomStringDigits(stringLength=6):
    """Generate a random string of letters and digits """
    lettersAndDigits = string.ascii_letters + string.digits
    return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))

conn = sqlite3.connect("er2.sqlite", detect_types=sqlite3.PARSE_DECLTYPES)

cur = conn.cursor()

def createUsers(usernames):
    credentials = {}
    for username in usernames:
        password = randomStringDigits(8)
        cur.execute(
            "INSERT INTO user (username, password, admin) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), None),
        )
        credentials[username] = password
        conn.commit()
    with open('credentials.csv', 'w') as f:
        for key in credentials.keys():
            f.write("%s,%s\n"%(key,credentials[key]))

def deleteUsers(id_list):
    sql = "DELETE FROM user WHERE id IN ({})".format(", ".join("?" * len(id_list)))
    cur.execute(sql, id_list)
    conn.commit()
    updateSequence()


def updateSequence():
    sql = 'UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM user) WHERE name="user"'
    cur.execute(sql)
    conn.commit()


# createUsers(usernames)


# id_list = (range(2,41))
# deleteUsers(id_list)

cur.execute("SELECT * FROM user")
rows = cur.fetchall()
for row in rows:
    print(row)