import subprocess
import dotenv
from os import getenv
import db_util
import re
import urllib
import yaml
from datetime import datetime, date, timedelta

dotenv.load_dotenv()

ADMIN_USER_ID = 1
HOLIDAY_FULLTIME_EMPLOYEE_HOURS = 24 * 8


def get_console():
    """
    return path to console binary using standard if not overwritten by env
    """
    path = getenv("KIMAI_BINARY_PATH")
    if path is None:
        return "/var/www/kimai2/bin/console"
    return path


def get_email_credentials():
    """
    return a tuple containing sender-address, password, server-address and port of the email string in the env file
    """
    url = dotenv.get_key("/var/www/kimai2/.env", "MAILER_URL")
    mtc = re.match(r'smtp:\/\/(.+?):(.+?)\@(.+?):(\d+?)\?.+', url)
    sender = urllib.parse.unquote(mtc.group(1))
    passw = urllib.parse.unquote(mtc.group(2))
    host = urllib.parse.unquote(mtc.group(3))
    port = mtc.group(4)
    return (sender, passw, host, int(port))


def console_user_create(user, passw, email):
    """
    Usage:
        kimai:user:create <username> <email> [<role> [<password>]]
        kimai:create-user

    Arguments:
    username              A name for the new user (must be unique)
    email                 Email address of the new user (must be unique)
    role                  A comma separated list of user roles, e.g. "ROLE_USER,ROLE_ADMIN" [default: "ROLE_USER"]
    password              Password for the new user (requested if not provided)
    """
    cons = get_console()
    res = subprocess.run([cons, "--no-interaction", "kimai:user:create", user, email, "ROLE_USER", passw])
    res.check_returncode()
    

def create_activity(usertype:str, user:str, hours:float):
    proj_id, custom_id = db_util.get_project_for_type(usertype)
    salary = db_util.get_project_rate(proj_id)
    user_id = db_util.get_user_id(user)
    team_name = f"work_{user}"
    team_id = db_util.create_private_team(team_name, ADMIN_USER_ID, user_id)
    db_util.create_private_activity(proj_id, team_name, team_id, salary, hours)
    db_util.link_team_proj_customer(team_id, proj_id, custom_id)


class Werkstudent:
    def __init__(self, row):
        self._id = row[0]
        self._user = row[1]
        self._email = row[2]
        self._alias = row[4]
        self._registration = row[6]
        self._preferences = db_util.get_user_preferences(self._id)

    @staticmethod
    def get_all_active():
        return [Werkstudent(row) for row in db_util.get_user_by_role("WERKSTUDENT")]

    def get_holiday_eligibility(self):
        now = datetime.now()
        employeed_days = int((now - self._registration).total_seconds() / 86400)
        weeks = employeed_days / 7
        total_hours = db_util.sum_times_range(self._id, self._registration, now) / 3600
        average_weekly = total_hours / weeks
        holiday_hours = HOLIDAY_FULLTIME_EMPLOYEE_HOURS * average_weekly / 40
        holiday_days = holiday_hours / 8
        holiday_taken = db_util.get_user_holidays_taken(self._id)
        return average_weekly, holiday_days, holiday_taken


class Worker:
    def __init__(self, id:int, sheets:list):
        self._id = id
        self._sheets = sheets
        mail, alias = db_util.get_user_mail_alias(id)
        self._mail = mail
        self._alias = alias
        self._registration = db_util.get_user_registration_date(id)
        # lookup date_tz from sheet-tuple, last item
        self._weeks = db_util.sum_times_weeks(id, [ x[-1] for x in sheets ])
        # sheets are sorted ascending
        self._sum_month = db_util.sum_times_range(id, sheets[0][-1], sheets[-1][-1]) / 3600
        self._budget_month = db_util.get_worker_budget(id)
        self._last_changed_sheet = db_util.get_last_edited_sheet(id, sheets[0][-1])
        self._last_generated_change = db_util.get_generation_cycle_id_dt(id)
        self._preferences = db_util.get_user_preferences(id)

    def mark_sheets_exported(self):
        db_util.set_sheets_exported([s[0] for s in self._sheets])

    def was_changed_since_last_gen(self) -> bool:
        return self._last_changed_sheet != self._last_generated_change

    def last_change_older_than_minutes(self, min:int) -> bool:
        now = datetime.utcnow()
        delt = timedelta(seconds=min*60)
        return (now - self._last_changed_sheet[1]) > delt

    def set_last_generation_sheet(self):
        db_util.set_last_generated_sheet(self._id, *self._last_changed_sheet)

    def get_open_sheets(self, year, month):
        return db_util.get_open_sheets(self._id, year, month)

    def get_work_days(self) -> int:
        return int((datetime.now() - self._registration).total_seconds() / 86400)

    def get_holiday_eligibility(self):
        now = datetime.now()
        employeed_days = int((now - self._registration).total_seconds() / 86400)
        weeks = employeed_days / 7
        total_hours = db_util.sum_times_range(self._id, self._registration, now) / 3600
        average_weekly = total_hours / weeks
        holiday_hours = HOLIDAY_FULLTIME_EMPLOYEE_HOURS * average_weekly / 40
        holiday_days = holiday_hours / 8
        holiday_taken = db_util.get_user_holidays_taken(self._id)
        return average_weekly, holiday_days, holiday_taken


class AutogenProjekt:
    def __init__(self, id:int, name:str, comment:str):
        self._id = id
        self._name = name
        self._comment = comment
        comment = comment.replace("*generate_sheets*\r\n", "")
        data = yaml.load(comment, yaml.Loader)
        self._max_weekly = float(data.get("max_weekly", 24.0 * 7))
        self._max_monthly = float(data.get("max_monthly", 0.0))
        self._max_season = float(data.get("max_weekly_season", 0.0))
        self._seasons = []
        seasons = data.get("seasons", False)
        if self._max_season != 0.0 and seasons:
            for dates in seasons:
                ses = dates.split(" - ")
                self._seasons.append((
                    datetime.strptime(ses[0], "%d.%m.%Y").date(), 
                    datetime.strptime(ses[1], "%d.%m.%Y").date()
                ))
        self._seasons.sort()

    def is_in_season(self, dt:date) -> bool:
        if self._seasons:
            for start, end in self._seasons:
                if start <= dt and dt <= end:
                    return True
        return False

    def get_workers(self, year:int, month:int) -> list:
        sheets = db_util.get_sheets_for_project(self._id, year, month)
        by_worker = {}
        for sheet in sheets:
            wid = sheet[1]
            if wid in by_worker:
                by_worker[wid].append(sheet)
            else:
                by_worker[wid] = [sheet]
        workers = []
        for k, v in by_worker.items():
            workers.append(Worker(k, v))
        return workers

    def is_worker_month_ok(self, worker:Worker):
        resp = f"Your total worktime for this month is {worker._sum_month:.1f} hours. \n"
        if self._max_monthly != 0.0:
            if worker._sum_month > self._max_monthly:
                ovr = worker._sum_month - self._max_monthly
                return False, resp + f"You are {ovr:.2f} hours over the allowed monthly hours.\nPlease try to fix this issue before the salary reporting date by moving time records into the next month"
        return True, resp

    def is_worker_budget_ok(self, worker:Worker):
        ovr = worker._sum_month - worker._budget_month
        if ovr > 0:
            return False, f"Your contract is for {worker._budget_month:.2f} hours. You worked {ovr:.2f} to much."
        return True, ""

    def is_worker_weeks_ok(self, worker:Worker):
        weeks = []
        weeks_ok = True
        for week in worker._weeks:
            duration = week[2] / 3600
            resp = f"{week[0]} - {week[1]}    {duration:.2f} hours."
            wmax = self._max_weekly
            if self.is_in_season(week[0]):
                wmax = self._max_season
            if duration > wmax:
                weeks_ok = False
                weeks.append((False, resp + f" !!! The maximum during this week is {wmax:.2f} !!!" ))
            else:
                weeks.append((True, resp))
        return weeks_ok, weeks

    def is_days_ok(self, worker:Worker):
        days =[]
        for she in worker._sheets:
            # check if the duration of a single entry is greater than 11 hours
            if she[6] > (11 * 60 * 60):
                days.append(str(she[-1]))
        if len(days) == 0:
            return True, ""
        prt = "\n - ".join(days)
        return False, f"!! There are entries with a length greater than 11 hours, are you sure this is correct?\n\nThese are the days on which this occured:{prt}\n\n\n"
            

def get_gen_projects():
    return [AutogenProjekt(*x) for x in db_util.get_generate_projects()]


if __name__ == "__main__":
    pass
    #tup = get_email_credentials()
    proj = get_gen_projects()[0]
    wrk = proj.get_workers(2022, 8)[0]
    for s in wrk._sheets:
        print(s)
    #week = proj.is_worker_weeks_ok(wrk)
    #month = proj.is_worker_month_ok(wrk)

    #print(week)

    pass