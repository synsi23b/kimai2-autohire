import re
import dotenv
import mysql.connector
from mysql.connector import errorcode
from pathlib import Path


envfile = Path(".env")
env = dotenv.dotenv_values(envfile)

CNX = None

def get_db():
    global CNX
    if CNX:
        return CNX
    dbstring = env["DATABASE_URL"]
    mtc = re.match(r'mysql:\/\/(.+?):(.+?)@(.+?):(\d+)\/(.+?)\?.+', dbstring)
    config = {
        "user": mtc.group(1),
        "password": mtc.group(2),
        "host": mtc.group(3),
        "port": mtc.group(4),
        "database": mtc.group(5),
    }
    try:
        cnx = mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    else:
        CNX = cnx
        return cnx


if __name__ == "__main__":
    cn = get_db()