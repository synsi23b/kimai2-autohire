import re
import dotenv
import mysql.connector
from mysql.connector import errorcode, MySQLConnection
from pathlib import Path


envfile = Path(".env")
if envfile.is_file():
    env = dotenv.dotenv_values(envfile)
else:
    env = dotenv.dotenv_values("/var/www/kimai2/.env")


CNX = None


def get_db() -> MySQLConnection:
    global CNX
    if CNX:
        if CNX.is_connected():
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


def set_user_salary(user:str, salary:float) -> int:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id FROM kimai2_users WHERE username = '{user}';")
    user_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_user_preferences(user_id, name, value) VALUES({user_id}, 'hourly_rate', '{salary:.2f}');")
    cnx.commit()
    return user_id


def create_private_team(team_name:str, leader_id:int, user_id:int) -> int:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"INSERT INTO kimai2_teams(name, color) VALUES('{team_name}', '#73b761');")
    cnx.commit()
    cur.execute(f"SELECT id FROM kimai2_teams WHERE name = '{team_name}';")
    team_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_users_teams(user_id, team_id, teamlead) VALUES ({leader_id}, {team_id}, 1), ({user_id}, {team_id}, 0);")
    cnx.commit()
    return team_id


def create_private_activity(acti_name:str, team_id:int, budget:float):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"INSERT INTO kimai2_activities(name, visible, budget, budget_type) VALUES ('{acti_name}', 1, {budget}, 'month');")
    cnx.commit()
    cur.execute(f"SELECT id FROM kimai2_activities WHERE name = '{acti_name}';")
    acti_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_activities_teams(activity_id, team_id) VALUES ({acti_id}, {team_id});")
    cnx.commit()

if __name__ == "__main__":
    pass
    #cn = get_db()
    #create_private_team("bla", 1, "prparke")