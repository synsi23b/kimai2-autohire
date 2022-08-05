import re
import dotenv
import mysql.connector
from mysql.connector import errorcode, MySQLConnection
from pathlib import Path
from datetime import datetime


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


def set_user_alias(user:str, firstname:str, lastname:str):
    name = f"{firstname} {lastname}"
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"UPDATE kimai2_users SET alias = '{name}' WHERE username = '{user}';")
    cnx.commit()


def get_user_mail_alias(user_id):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT email, alias FROM kimai2_users WHERE id = {user_id};")
    mail, alias = next(cur)
    #cur.execute(f"SELECT value FROM kimai2_user_preferences WHERE user_id = {user_id} AND name = 'timezone';")
    #return (mail, alias, next(cur)[0])
    return (mail, alias)


def set_user_salary(user:str, salary:float) -> int:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id FROM kimai2_users WHERE username = '{user}';")
    user_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_user_preferences(user_id, name, value) VALUES({user_id}, 'hourly_rate', '{salary:.2f}');")
    cnx.commit()
    return user_id


def get_project_for_type(usertype:str):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id, customer_id FROM kimai2_projects WHERE name = '{usertype}';")
    return next(cur)


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


def create_private_activity(proj_id:int, acti_name:str, team_id:int, salary:float, hours:float):
    budget = salary * hours
    # round by 5 minute steps
    seconds = (int(hours * 3600) // 300) * 300
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"INSERT INTO kimai2_activities(project_id, name, visible, time_budget, budget, budget_type) VALUES ({proj_id}, '{acti_name}', 1, {seconds}, {budget}, 'month');")
    cnx.commit()
    cur.execute(f"SELECT id FROM kimai2_activities WHERE name = '{acti_name}';")
    acti_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_activities_teams(activity_id, team_id) VALUES ({acti_id}, {team_id});")
    cnx.commit()


def link_team_proj_customer(team_id, proj_id, custom_id):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"INSERT INTO kimai2_customers_teams(customer_id, team_id) VALUES ({custom_id}, {team_id});")
    cur.execute(f"INSERT INTO kimai2_projects_teams(project_id, team_id) VALUES ({proj_id}, {team_id});")
    cnx.commit()


def sum_times_range(user_id:int, start, end) -> float:
    cnx = get_db()
    cur = cnx.cursor()
    querry = f"SELECT SUM(duration) FROM kimai2_timesheet WHERE user = {user_id} AND date_tz between '{start}' AND '{end}';"
    #print(querry)
    cur.execute(querry)
    res = next(cur)[0]
    #print(res)
    return int(res if res is not None else 0)


if __name__ == "__main__":
    pass
    #cn = get_db()
    #create_private_team("bla", 1, "prparke")
    e = datetime.now()
    s = e.replace(month=e.month - 1)
    print(sum_times_range(12, s, e))