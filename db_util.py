import re
import dotenv
import mysql.connector
from mysql.connector import errorcode, MySQLConnection
from pathlib import Path
from datetime import datetime, date, timedelta
import calendar
import pytz
from dataclasses import dataclass


UTC = pytz.UTC


HOLIDAY_STUDENT_ACTI_ID = 11


envfile = Path(__file__).resolve().parent / ".env"
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


def get_user_by_role(role:str, active=True):
    role = role.upper()
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    if active:
        cur.execute(f"SELECT * FROM kimai2_users WHERE INSTR(roles, '{role}') AND enabled = 1;")
    else:
        cur.execute(f"SELECT * FROM kimai2_users WHERE INSTR(roles, '{role}');")
    return list(cur)


def set_user_alias(user:str, firstname:str, lastname:str):
    name = f"{firstname} {lastname}"
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"UPDATE kimai2_users SET alias = '{name}' WHERE username = '{user}';")
    cnx.commit()


def get_user_id(user:str, is_alias=False) -> int:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    if is_alias:
        cur.execute(f"SELECT id FROM kimai2_users WHERE alias = '{user}';")
    else:
        cur.execute(f"SELECT id FROM kimai2_users WHERE username = '{user}';")
    return next(cur)[0]


def get_user_registration_date(id:int) -> datetime:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT registration_date FROM kimai2_users WHERE id = {id};")
    return next(cur)[0]


def get_user_preferences(id:int) -> dict:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT name, value FROM kimai2_user_preferences WHERE user_id = {id};")
    return dict(cur)


def check_username_free(user:str):
    try:
        uid = get_user_id(user)
        return False
    except StopIteration:
        get_db().close()
        return True


def get_user_mail_alias(user_id):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT email, alias FROM kimai2_users WHERE id = {user_id};")
    mail, alias = next(cur)
    #cur.execute(f"SELECT value FROM kimai2_user_preferences WHERE user_id = {user_id} AND name = 'timezone';")
    #return (mail, alias, next(cur)[0])
    return (mail, alias)


def get_worker_budget(user_id:int) -> float:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT username FROM kimai2_users WHERE id = {user_id};")
    uname = next(cur)[0]
    cur.execute(f"SELECT time_budget FROM kimai2_activities WHERE name = 'work_{uname}';")
    return next(cur)[0]


def set_user_salary(user:str, salary:float) -> int:
    user_id = get_user_id(user)
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"INSERT INTO kimai2_user_preferences(user_id, name, value) VALUES({user_id}, 'hourly_rate', '{salary:.2f}');")
    cnx.commit()
    return user_id


def get_project_for_type(usertype:str):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id, customer_id FROM kimai2_projects WHERE name = '{usertype}';")
    return next(cur)


def get_private_project_activity_for_user(user:int):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT team_id FROM kimai2_users_teams WHERE user_id = {user};")
    team_id = next(cur)[0]
    cur.execute(f"SELECT project_id FROM kimai2_projects_teams WHERE team_id = {team_id};")
    proj_id = next(cur)[0]
    cur.execute(f"SELECT activity_id FROM kimai2_activities_teams WHERE team_id = {team_id};")
    acti_id = next(cur)[0]
    return proj_id, acti_id


def get_project_rate(projid:int) -> float:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT rate FROM kimai2_projects_rates WHERE project_id = {projid};")
    return next(cur)[0]


def create_private_team(team_name:str, leader_id:int, user_id:int) -> int:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"INSERT INTO kimai2_teams(name, color) VALUES('{team_name}', '#73b761');")
    cnx.commit()
    cur.execute(f"SELECT id FROM kimai2_teams WHERE name = '{team_name}';")
    team_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_users_teams(user_id, team_id, teamlead) VALUES ({leader_id}, {team_id}, 1), ({user_id}, {team_id}, 0);")
    cnx.commit()
    return team_id


def user_join_team(user_id:int, team_name:str):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id FROM kimai2_teams WHERE name = '{team_name}';")
    team_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_users_teams(user_id, team_id, teamlead) VALUES ({user_id}, {team_id}, 0);")
    cnx.commit()


def create_user_preference(user_id:int, key:str, value):
    if type(value) != str:
        value = str(value)
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT * FROM kimai2_user_preferences WHERE user_id = {user_id} AND name = '{key}';")
    try:
        next(cur)
        # value already exists, update
        #f"UPDATE kimai2_timesheet SET exported= 1 WHERE id={i};
        cur.execute(f"UPDATE kimai2_user_preferences SET value = '{value}' WHERE user_id = {user_id} AND name = '{key}';")
    except StopIteration:
        cur.execute(f"INSERT INTO kimai2_user_preferences(user_id, name, value) VALUES ({user_id}, '{key}', '{value}');")
    cnx.commit()


def create_private_activity(proj_id:int, acti_name:str, team_id:int, salary:float, hours:float):
    budget = salary * hours
    # round by 5 minute steps
    seconds = (int(hours * 3600) // 300) * 300
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"INSERT INTO kimai2_activities(project_id, name, visible, time_budget, budget, budget_type) VALUES ({proj_id}, '{acti_name}', 1, {seconds}, {budget}, 'month');")
    cnx.commit()
    cur.execute(f"SELECT id FROM kimai2_activities WHERE name = '{acti_name}';")
    acti_id = next(cur)[0]
    cur.execute(f"INSERT INTO kimai2_activities_teams(activity_id, team_id) VALUES ({acti_id}, {team_id});")
    cnx.commit()


def link_team_proj_customer(team_id, proj_id, custom_id):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
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
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT SUM(duration) FROM kimai2_timesheet WHERE user = {user_id} AND date_tz between '{start}' AND '{end}';")
    res = next(cur)[0]
    return int(res if res is not None else 0)


@dataclass
class Timesheet:
    id: int
    user: int
    activity: int
    project: int
    start: datetime
    end: datetime
    duration: int
    description: str
    rate: float
    fixed_rate: float
    hourly_rate: float
    exported: bool
    timezone: str
    internal_rate: float
    billable: bool
    category: str
    modified_at: datetime
    date_tz: date


    def tzaware_start_end(self):
        tz = pytz.timezone(self.timezone)
        s = UTC.localize(self.start)
        e = UTC.localize(self.end)
        return s.astimezone(tz), e.astimezone(tz)


def select_timesheets(where:str, order:str=""):
    """
    order can take the default value (no order)
    or the statement like start_time ASC
    """
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    if order == "":
        cur.execute(f"SELECT * FROM kimai2_timesheet WHERE {where};")
    else:
        cur.execute(f"SELECT * FROM kimai2_timesheet WHERE {where} ORDER BY {order};")
    return [Timesheet(*x) for x in cur]


def get_sheets_for_day(user_id:int, day:date, activities:list[int]) -> list[Timesheet]:
    return select_timesheets(f"user = {user_id} AND date_tz = '{day}' AND end_time IS NOT NULL and activity_id IN ({','.join(activities)})", "start_time ASC")


def calculate_timesheet_break_times(sheets:list[Timesheet]) ->  int:
    """
    calculate break times taken between timesheets according to german law -> A break has a minimum of 15 minutes, else its not a break
    """
    pause = 0
    if len(sheets) > 1:
        pairs = zip(sheets, sheets[1:] + [None])
        for a, b in pairs:
            if b is not None:
                _, a_end = a.tzaware_start_end()
                b_start, _ = b.tzaware_start_end()
                interval = (b_start - a_end).total_seconds()
                if interval >= (15 * 60):
                    pause += interval
    return pause    


def get_student_holidays_taken(user_id:int) -> int:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(("SELECT COUNT(id) AS holidays FROM kimai2_timesheet WHERE "
                f"user = {user_id} AND activity_id = {HOLIDAY_STUDENT_ACTI_ID} "
                f"AND exported = 1;"))
    res = next(cur)[0]
    return int(res if res is not None else 0)


def get_generate_projects() -> list:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id, name, comment FROM kimai2_projects WHERE comment LIKE '%*generate_sheets*%';")
    return list(cur)


def get_sheets_for_project(proj_id, year:int, month:int) -> list:
    start = date(year, month, 1)
    # monthrange returns a tuple (day_of_week, last_day_of_month)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return select_timesheets(f"project_id = {proj_id} AND end_time IS NOT NULL AND date_tz between '{start}' AND '{end}'", "start_time ASC")


def get_team_worker_by_project(proj_id:int) -> list:
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT team_id FROM kimai2_projects_teams WHERE project_id={proj_id};")
    teams = ", ".join([str(c[0]) for c in cur])
    cur.execute(f"SELECT user_id FROM kimai2_users_teams WHERE teamlead=0 AND team_id IN ({teams});")
    users = ", ".join([str(c[0]) for c in cur])
    cur.execute(f"SELECT id, email, alias FROM kimai2_users WHERE enabled=1 AND id IN ({users});")
    return list(cur)


def set_sheets_exported(sheet_ids:list):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    for i in sheet_ids:
        cur.execute(f"UPDATE kimai2_timesheet SET exported= 1 WHERE id={i};")
    cnx.commit()
    

def get_last_edited_sheet(user_id:int, sheet_date:date) -> tuple:
    start = sheet_date.replace(day=1)
    # monthrange returns a tuple (day_of_week, last_day_of_month)
    end = sheet_date.replace(day=calendar.monthrange(sheet_date.year, sheet_date.month)[1])
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id, modified_at FROM kimai2_timesheet WHERE user = {user_id} AND end_time IS NOT NULL AND date_tz between '{start}' AND '{end}' ORDER BY modified_at DESC;")
    return next(cur)


def get_open_sheets(user_id:int, year:int, month:int) -> list:
    start = date(year, month, 1)
    # monthrange returns a tuple (day_of_week, last_day_of_month)
    end = date(year, month, calendar.monthrange(year, month)[1])
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id, start_time, timezone FROM kimai2_timesheet WHERE user = {user_id} AND end_time IS NULL AND date_tz between '{start}' AND '{end}';")
    return list(cur)


def get_tag_id(name:str, create_with_color_if_not_exists:str=""):
    """
    color has to be in the format: #ff0000
    for red for example
    """
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT id FROM kimai2_tags WHERE name = '{name}';")
    tags = list(cur)
    if tags:
        return tags[0][0]
    if create_with_color_if_not_exists:
        cur.execute(f"INSERT INTO kimai2_tags(id, name, color) VALUES(NULL, '{name}', '{create_with_color_if_not_exists}');")
        cnx.commit()
        return get_tag_id(name)
    return 0


def tag_if_not_tagged(sheet:int, tag:int):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT * FROM kimai2_timesheet_tags WHERE timesheet_id = {sheet} AND tag_id = {tag};")
    if not list(cur):
        cur.execute(f"INSERT INTO kimai2_timesheet_tags(timesheet_id, tag_id) VALUES({sheet}, {tag});")
        cnx.commit()


def stop_open_sheets(user_id:int, day:date) -> bool:
    #overrun_start_time = int(get_configuration("timesheet.rules.long_running_duration")) * 60 - 1
    #overrun_start_time = datetime.utcnow() - timedelta(seconds=overrun_start_time)
    stopped = False
    for sheet in select_timesheets(f"user = {user_id} AND end_time IS NULL AND date_tz = '{day}';"):
        stopped = True
        if sheet.description:
            dsc =  f"!! Automatisch gestoppt !!\n{sheet.description}"
        else:
            dsc = "!! Automatisch gestoppt !!"
        usertz = pytz.timezone(sheet.timezone)
        start = UTC.localize(sheet.start).astimezone(usertz)
        end = datetime.utcnow().astimezone(usertz)
        update_timesheet_times_description(sheet, start, end, dsc)
        tag_if_not_tagged(sheet.id, get_tag_id("Autostop", "#ff0000"))
    return stopped


def get_project_by_activity(activity_id):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT project_id FROM kimai2_activities WHERE id = {activity_id};")
    return next(cur)[0]


def is_activity_deduction(activity_id):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT value FROM kimai2_activities_meta WHERE activity_id = {activity_id} AND name ='is_deduction';")
    res = list(cur)
    return res[0] if res else 0


def insert_timesheet(user_id:int, activity_id:int, project_id:int, start:datetime, end:datetime, description:str, hourly_rate:float, exported:bool):
    datetz = start.date()
    timezone = str(start.tzinfo)
    if start.tzinfo is None:
        raise ValueError("Naive datetime object are not supported. This needs propper timezone setting")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    durs = int((end - start).total_seconds())
    if is_activity_deduction(activity_id):
        durs = -durs
    durh = durs / 3600
    rate = hourly_rate * durh
    description = description.replace("'", "_").replace("\"", "_")
    if project_id == 0:
        project_id = get_project_by_activity(activity_id)
        if not project_id:
            raise RuntimeError(f"Timesheet creation failed: Could not find project id for activity {activity_id}")
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    querry = ("INSERT INTO kimai2_timesheet("
    "id, user, activity_id, project_id, start_time, end_time, "
    "duration, description, rate, hourly_rate, exported, "
    "timezone, internal_rate, modified_at, date_tz) "
    f"VALUES (NULL, {user_id}, {activity_id}, {project_id}, '{start}', '{end}', "
    f"{durs}, '{description}', {rate}, {hourly_rate}, {int(exported)}, "
    f"'{timezone}', {rate}, '{datetime.utcnow()}', '{datetz}');")
    cur.execute(querry)
    cnx.commit()


def update_timesheet_times_description(timesheet:Timesheet, start:datetime, end:datetime, description):
    datetz = start.date()
    timezone = str(start.tzinfo)
    if start.tzinfo is None:
        raise ValueError("Naive datetime object are not supported. This needs propper timezone setting")
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    durs = int((end - start).total_seconds())
    if is_activity_deduction(timesheet.activity):
        durs = -durs
    durh = durs / 3600
    if timesheet.hourly_rate:
        hourlyr = timesheet.hourly_rate
    else:
        hourlyr = 0.0
    rate = hourlyr * durh
    description = description.replace("'", "_").replace("\"", "_")
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    querry = ("UPDATE kimai2_timesheet "
    f"SET start_time = '{start}', end_time = '{end}', duration = {durs}, description = '{description}', "
    f"rate = {rate}, hourly_rate = {hourlyr}, timezone = '{timezone}', modified_at = '{datetime.utcnow()}', date_tz = '{datetz}' "
    f"WHERE id = {timesheet.id};")
    cur.execute(querry)
    cnx.commit()


def timesheet_delete(timesheet_id:int):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    cur.execute(f"DELETE FROM kimai2_timesheet WHERE id = {timesheet_id};")
    cnx.commit()


def check_timesheet_exists(user_id:int, date_tz:date, activity_id:int=0, description:str=""):
    cnx = get_db()
    cur = cnx.cursor(buffered=True)
    if activity_id == 0:
        cur.execute(f"SELECT COUNT(id) from kimai2_timesheet WHERE user = {user_id} AND date_tz = '{date_tz}';")
    elif description == "":
        cur.execute(f"SELECT COUNT(id) from kimai2_timesheet WHERE user = {user_id} AND activity_id = {activity_id} AND date_tz = '{date_tz}';")
    else:
        cur.execute(f"SELECT COUNT(id) from kimai2_timesheet WHERE user = {user_id} AND activity_id = {activity_id} AND date_tz = '{date_tz}' AND description LIKE '%{description}%';")
    return next(cur)[0]


def get_holidays(start:date, end:date, state = ""):
    cnx = get_db()
    cur = cnx.cursor()
    if state == "":
        cur.execute(f"SELECT holiday_date, name, state FROM kimai2_ext_public_holidays WHERE holiday_date between '{start}' AND '{end}';")
    else:
        cur.execute(f"SELECT holiday_date, name, state FROM kimai2_ext_public_holidays WHERE holiday_date between '{start}' AND '{end}' AND state = '{state}';")
    return list(cur)


def get_configuration(key:str, key_exact=True):
    cnx = get_db()
    cur = cnx.cursor()
    if key_exact:
        cur.execute(f"SELECT value FROM kimai2_configuration WHERE name = '{key}';")
        return next(cur)[0]
    else:
        cur.execute(f"SELECT name, value FROM kimai2_configuration WHERE name LIKE '%{key}%';")
        return dict(list(cur))
    

def get_generation_cycle_id_dt(user_id:int):
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT timesheet, modified_at FROM last_generated_change WHERE id = {user_id};")
    try:
        tup = next(cur)
    except StopIteration:
        tup = (0, datetime(year=1970, month=1, day=1, hour=0, minute=0))
    return tup


def set_last_generated_sheet(user_id, sheet_id, mod_at):
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
    q= f"INSERT INTO last_generated_change (id, timesheet, modified_at) VALUES({user_id}, {sheet_id}, '{mod_at}') ON DUPLICATE KEY UPDATE timesheet={sheet_id}, modified_at='{mod_at}';"
    cur.execute(q)
    cnx.commit()


def set_missing_sheet_reminder_send(user_id:int, year:int, month:int):
    mod_at = datetime(year, month, 1, 0, 0, 0, 0)
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
    q= f"INSERT INTO last_generated_change (id, timesheet, modified_at) VALUES({user_id}, 0, '{mod_at}') ON DUPLICATE KEY UPDATE timesheet=0, modified_at='{mod_at}';"
    cur.execute(q)
    cnx.commit()


def open_warning_older_than_hours(sheet_id:int, hours:float) -> bool:
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
    cur.execute(f"SELECT warning_time FROM open_sheet_warning WHERE id = {sheet_id};")
    try:
        wt = next(cur)[0]
    except StopIteration:
        return True
    now = datetime.utcnow()
    delt = timedelta(hours=hours)
    return (now - wt) > delt


def set_open_timesheet_warning_send(sheet_id:int):
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
    now = datetime.utcnow()
    cur.execute(f"INSERT INTO open_sheet_warning (id, warning_time) VALUES({sheet_id}, '{now}') ON DUPLICATE KEY UPDATE warning_time='{now}';")
    cnx.commit()


def _create_table_autoid(name:str, fields:list):
    cnx = get_db("dbautohire")
    cur = cnx.cursor(buffered=True)
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


def _create_open_sheet_warning():
    fields = [
        "warning_time DATETIME"
    ]
    _create_table_autoid("open_sheet_warning", fields)


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
    #_create_last_generation_change()
    #print(get_generate_projects())
    # [(20, 'Werkstudent_TUD', '*generate_sheets*\r\nmax_weekly_during: 20\r\nmax_weekly_outside: 40\r\nseasons:\r\n - 14.10.2024:14.02.2025\r\n - 15.04.2024:19.07.2024\r\n - 16.10.2023:09.02.2024\r\n - 11.04.2023:14.07.2023\r\n - 17.10.2022:10.02.2023')]
    #print(get_team_worker_by_project(20))
    _create_open_sheet_warning()
