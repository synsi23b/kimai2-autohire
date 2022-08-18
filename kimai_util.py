from http.client import responses
import subprocess
from xmlrpc.client import Boolean
import dotenv
from os import getenv
import db_util
import re
import urllib
import yaml
from datetime import datetime, date

dotenv.load_dotenv()

ADMIN_USER_ID = 1


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


class Worker:
    def __init__(self, id:int, sheets:list):
        self._id = id
        self._sheets = sheets
        mail, alias = db_util.get_user_mail_alias(id)
        self._mail = mail
        self._alias = alias
        # lookup date_tz from sheet-tuple, last item
        self._weeks = db_util.sum_times_weeks(id, [ x[-1] for x in sheets ])
        # sheets are sorted ascending
        self._sum_month = db_util.sum_times_range(id, sheets[0][-1], sheets[-1][-1]) / 3600
        self._budget_month = db_util.get_worker_budget(id)

class AutogenProjekt:
    def __init__(self, id:int, name:str, comment:str):
        self._id = id
        self._name = name
        self._comment = comment
        comment = comment.replace("*generate_sheets*\r\n", "")
        data = yaml.load(comment, yaml.Loader)
        self._max_weekly = float(data["max_weekly"])
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
                return False, resp + f"You are {ovr:.1f} hours over the allowed monthly hours.\nPlease try to fix this issue before the salary reporting date by moving time records into the next month"
        return True, resp

    def is_worker_budget_ok(self, worker:Worker):
        ovr = worker._sum_month - worker._budget_month
        if ovr > 0:
            return False, f"Your contract is for {worker._budget_month:.1f} hours. You worked {ovr:.1f} to much."
        return True, ""

    def is_worker_weeks_ok(self, worker:Worker):
        weeks = []
        weeks_ok = True
        for week in worker._weeks:
            duration = week[2] / 3600
            resp = f"{week[0]} - {week[1]}    {duration:.1f} hours."
            wmax = self._max_weekly
            if self.is_in_season(week[0]):
                wmax = self._max_season
            if duration > wmax:
                weeks_ok = False
                weeks.append((False, resp + f" !!! The maximum during this week is {wmax:.1f} !!!" ))
            else:
                weeks.append((True, resp))
        return weeks_ok, weeks
            

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