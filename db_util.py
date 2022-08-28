from codecs import getdecoder
import re
from xmlrpc.client import DateTime
import dotenv
import mysql.connector
from mysql.connector import errorcode, MySQLConnection
from pathlib import Path
from datetime import datetime, date, timedelta
import calendar


envfile = Path(".env")
if envfile.is_file():
    env = dotenv.dotenv_values(envfile)
else:
    env = dotenv.dotenv_values("/var/www/kimai2/.env")


CNX = {}


def get_db(override_dbname="") -> MySQLConnection:
    dbstring = env["DATABASE_URL"]
    mtc = re.match(r'mysql:\/\/(.+?):(.+?)@(.+?):(\d+)\/(.+?)\?.+', dbstring)
    config = {
        "user": mtc.group(1),
        "password": mtc.group(2),
        "host": mtc.group(3),
        "port": mtc.group(4),
        "database": mtc.group(5),
    }
    if override_dbname != "":
        config["database"] = override_dbname
        dbname = override_dbname
    else:
        dbname = config["database"]

    if CNX.get(dbname, None):
        if CNX[dbname].is_connected():
            return CNX[dbname]

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
        CNX[dbname] = cnx
        return cnx


def set_user_alias(user:str, firstname:str, lastname:str):
    name = f"{firstname} {lastname}"
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"UPDATE kimai2_users SET alias = '{name}' WHERE username = '{user}';")
    cnx.commit()


def get_user_id(user:str) -> int:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id FROM kimai2_users WHERE username = '{user}';")
    return next(cur)[0]


def check_username_free(user:str):
    try:
        uid = get_user_id(user)
        return False
    except StopIteration:
        return True


def get_user_mail_alias(user_id):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT email, alias FROM kimai2_users WHERE id = {user_id};")
    mail, alias = next(cur)
    #cur.execute(f"SELECT value FROM kimai2_user_preferences WHERE user_id = {user_id} AND name = 'timezone';")
    #return (mail, alias, next(cur)[0])
    return (mail, alias)


def get_worker_budget(user_id:int) -> float:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT username FROM kimai2_users WHERE id = {user_id};")
    uname = next(cur)[0]
    cur.execute(f"SELECT time_budget FROM kimai2_activities WHERE name = 'work_{uname}';")
    return next(cur)[0]


def set_user_salary(user:str, salary:float) -> int:
    user_id = get_user_id(user)
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"INSERT INTO kimai2_user_preferences(user_id, name, value) VALUES({user_id}, 'hourly_rate', '{salary:.2f}');")
    cnx.commit()
    return user_id


def get_project_for_type(usertype:str):
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id, customer_id FROM kimai2_projects WHERE name = '{usertype}';")
    return next(cur)


def get_project_rate(projid:int) -> float:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT rate FROM kimai2_projects_rates WHERE project_id = {projid};")
    return next(cur)[0]


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


def sum_times_weeks(user_id:int, dates:list) -> list:
    weeks = {}
    for d in dates:
        monday = d - timedelta(days=d.weekday())
        if monday not in weeks:
            sunday = monday + timedelta(days=6)
            val = sum_times_range(user_id, monday, sunday)
            weeks[monday] = (monday, sunday, val)
    return list(weeks.values())


def sum_times_range(user_id:int, start, end) -> float:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT SUM(duration) FROM kimai2_timesheet WHERE user = {user_id} AND date_tz between '{start}' AND '{end}';")
    res = next(cur)[0]
    return int(res if res is not None else 0)


def get_generate_projects() -> list:
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id, name, comment FROM kimai2_projects WHERE comment LIKE '%*generate_sheets*%';")
    return list(cur)


def get_sheets_for_project(proj_id, year:int, month:int) -> list:
    start = date(year, month, 1)
    # monthrange returns a tuple (day_of_week, last_day_of_month)
    end = date(year, month, calendar.monthrange(year, month)[1])
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT * FROM kimai2_timesheet WHERE project_id = {proj_id} AND date_tz between '{start}' AND '{end}' ORDER BY start_time ASC;")
    return list(cur)


def set_sheets_exported(sheet_ids:list):
    cnx = get_db()
    cur = cnx.cursor()
    for i in sheet_ids:
        cur.execute(f"UPDATE kimai2_timesheet SET exported= 1 WHERE id={i};")
    cnx.commit()
    

def get_last_edited_sheet(user_id:int, sheet_date:date) -> tuple:
    start = sheet_date.replace(day=1)
    # monthrange returns a tuple (day_of_week, last_day_of_month)
    end = sheet_date.replace(day= calendar.monthrange(sheet_date.year, sheet_date.month)[1])
    cnx = get_db()
    cur = cnx.cursor()
    cur.execute(f"SELECT id, modified_at FROM timesheets WHERE user = {user_id} AND date_tz between '{start}' AND '{end}' ORDER BY modified_at DESC;")
    return next(cur)


def get_generation_cycle_id_dt(user_id:int):
    cnx = get_db("dbautohire")
    cur = cnx.cursor()
    cur.execute(f"SELECT timesheet, modified_at FROM last_generated_change WHERE id = {user_id};")
    try:
        tup = next(cur)
    except StopIteration:
        tup = (0, datetime(year=1970, month=1, day=1, hour=0, minute=0))
    return tup


def set_last_generated_sheet(user_id, sheet_id, mod_at):
    cnx = get_db("dbautohire")
    cur = cnx.cursor()
    q= f"INSERT INTO last_generated_change (id, timesheet, modified_at) VALUES({user_id}, {sheet_id}, {mod_at}) ON DUPLICATE KEY UPDATE timesheet={sheet_id}, modified_at={mod_at}"
    cur.execute(q)
    cnx.commit()


def _create_table_autoid(name:str, fields:list):
    cnx = get_db("dbautohire")
    cur = cnx.cursor()
    expand_fields = ',\n'.join([" "+f for f in fields])
    querry = f"CREATE TABLE {name} (\n id INT NOT NULL,\n{expand_fields},\n PRIMARY KEY (id)\n);"
    res = input(f"\n\n{querry}\n\n Execute querry? [y/n]")
    if res == "y":
        print("commiting")
        cur.execute(querry)
        cnx.commit()
    else:
        print("Abroted")


def _create_season():
    fields = [
        "name VARCHAR(255)",
        "proj_id INT",
        "max_hours DOUBLE",
        "start DATE",
        "end DATE"
    ]
    _create_table_autoid("seasons", fields)


def _create_last_generation_change():
    fields = [
        "timesheet INT",
        "modified_at DATETIME"
    ]
    _create_table_autoid("last_generated_change", fields)


#def _create_user_season():
# dont need this table, just alwayrs reference timeshit->proj_id->season
#    fields = [
#        "user_id INT",
#        "season_id INT"
#    ]
#    _create_table_autoid("users_seasons", fields)


if __name__ == "__main__":
    pass
    #cn = get_db()
    #create_private_team("bla", 1, "prparke")
    #e = datetime.now()
    #s = e.replace(month=e.month - 1)
    #print(sum_times_range(12, s, e))
    #_create_season()
    #_create_user_season()
    #print(get_generate_projects())
    # [(20, 'Werkstudent_TUD', '*generate_sheets*\r\nmax_weekly_during: 20\r\nmax_weekly_outside: 40\r\nseasons:\r\n - 14.10.2024:14.02.2025\r\n - 15.04.2024:19.07.2024\r\n - 16.10.2023:09.02.2024\r\n - 11.04.2023:14.07.2023\r\n - 17.10.2022:10.02.2023')]
