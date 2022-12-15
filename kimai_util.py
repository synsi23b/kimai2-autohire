import subprocess
import dotenv
from os import getenv
import db_util
import re
import urllib
import yaml
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import subprocess
from pathlib import Path
import logging
import pytz


UTC = pytz.UTC


dotenv.load_dotenv()


#ADMIN_USER_ID = 1
HOLIDAY_FULLTIME_EMPLOYEE_HOURS = 24 * 8


@dataclass(frozen=True)
class UserType:
    verbose: str
    teams: list
    roles: list


USER_TYPES = {
    "angestellter": UserType("Angestellter", ["LIT"], ["ROLE_USER", "Angestellter"]),
    "student": UserType("Werkstudent", ["Werkstudent"], ["ROLE_USER", "Werkstudent"]),
    "schueler": UserType("Angestellter", ["Schüleraushilfe"], ["ROLE_USER", "Werkstudent"]),
}


def get_console() -> str:
    """
    return path to console binary using standard if not overwritten by env
    """
    path = getenv("KIMAI_CONSOLE_PATH")
    if path is None:
        return "/var/www/kimai2/bin/console"
    return path


def get_kimai_datafolder() -> str:
    return "/var/www/kimai2/var/data"


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


def console_user_create(user, passw, email, roles=["ROLE_USER"]):
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
    if len(roles) == 1:
        res = subprocess.run([cons, "--no-interaction", "kimai:user:create", user, email, roles[0], passw])
    else:
        res = subprocess.run([cons, "--no-interaction", "kimai:user:create", user, email, ",".join(roles), passw])
    res.check_returncode()
    

# def create_activity(usertype:str, user:str, hours:float):
#     proj_id, custom_id = db_util.get_project_for_type(usertype)
#     salary = db_util.get_project_rate(proj_id)
#     user_id = db_util.get_user_id(user)
#     team_name = f"work_{user}"
#     team_id = db_util.create_private_team(team_name, ADMIN_USER_ID, user_id)
#     db_util.create_private_activity(proj_id, team_name, team_id, salary, hours)
#     db_util.link_team_proj_customer(team_id, proj_id, custom_id)


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class Angestellter:
    # dictionary containing kimai configuration values regarding holdiay plugins
    __vacationconfig = None
    # dictionary containing kimai configuration values regarding default working activities per role
    __workingconfig = None

    def __init__(self, row, role):
        self._role = role
        self._id = row[0]
        self._user = row[1]
        self._email = row[2]
        self._alias = row[4]
        self._registration = row[6]
        self._preferences = db_util.get_user_preferences(self._id)
        self._worktime_weekdays = [int(self._preferences[Angestellter.__vacationconfig[f"worktime_{idx}"]]) for idx in range(7)]
        if role != "ROLE_ADMIN":
            self._work_actis = Angestellter.__workingconfig[self._role]["work"]
            self._project = Angestellter.__workingconfig[self._role]["project"]
            self._break_acti = Angestellter.__workingconfig[self._role]["breaktime"]
            self._freeday_acti = Angestellter.__workingconfig[self._role]["freeday"]
            self._noshow_acti = Angestellter.__workingconfig[self._role]["noshow"]
            self._saldo_acti = Angestellter.__workingconfig["saldo_id"]


    @staticmethod
    def populate_configuration():
        if not Angestellter.__vacationconfig:
            Angestellter.__vacationconfig = db_util.get_configuration("vacation", False)
            for idx, day in enumerate(WEEKDAYS):
                Angestellter.__vacationconfig[f"worktime_{idx}"] = Angestellter.__vacationconfig[f"vacation.daily_working_time_meta_name_{day}"]
            Angestellter.__workingconfig = yaml.load(db_util.get_configuration("worktime.fillercfg", True), yaml.Loader)
            

    @staticmethod
    def get_all_active(role:str):
        """
        role: WERKSTUDENT ANGESTELLTER
        """
        Angestellter.populate_configuration()
        return [Angestellter(row, role) for row in db_util.get_user_by_role(role)]


    def get_student_holiday_eligibility(self):
        if self._role != "WERKSTUDENT":
            raise ValueError("Only supposed to be used for studenten!")
        now = datetime.now()
        employeed_days = int((now - self._registration).total_seconds() / 86400)
        weeks = employeed_days / 7
        total_hours = db_util.sum_times_range(self._id, self._registration, now) / 3600
        average_weekly = total_hours / weeks
        holiday_hours = HOLIDAY_FULLTIME_EMPLOYEE_HOURS * average_weekly / 40
        holiday_days = holiday_hours / 8
        holiday_taken = db_util.get_user_holidays_taken(self._id)
        return average_weekly, holiday_days, holiday_taken

    
    def import_holiday_on_day(self, holiday:tuple):
        """
        holiday -> (date, name, state)
        """
        holidate, holiname, holistate = holiday
        # check holiday applies for this users state
        if holistate != self._preferences["public_holiday_state"]:
            return
        # check holiday doesnt exist already
        holitivity = Angestellter.__vacationconfig["vacation.public_holiday_activity"]
        if db_util.check_timesheet_exists(self._id, holidate, holitivity, holiname):
            logging.info(f"User: {self._user} has holiday {holiname} already set, skipping")
            return
        # check user is actualy supposed to work on this day
        # TODO wether or not students will get a time here. maybe always zero hours is best
        workingtime = self._worktime_weekdays[holidate.weekday()]
        #if workingtime == 0: # dont check, insert even 0 duration holidays just for display on the journal
        #    return
        # create start, end, duration
        start = UTC.localize(datetime(holidate.year, holidate.month, holidate.day, 8))
        end = start + timedelta(seconds=workingtime)
        # finaly insert new timesheet
        logging.info(f"Inserting public holiday > {holiday} < for user {self._email}")
        db_util.insert_timesheet(self._id, holitivity, 0, start, end, holiname, 0, True)

    
    def has_not_worked(self, workday:date):
        return db_util.check_timesheet_exists(self._id, workday) == 0


    def fill_missing_workday(self, workday:date):
        if self.has_not_worked(workday):
            dt = datetime(workday.year, workday.month, workday.day)
            start = end = pytz.timezone(self._preferences["timezone"]).localize(dt)
            if self._worktime_weekdays[workday.weekday()] > 0:
                logging.info(f"Insert missing day for user {self._email}")
                db_util.insert_timesheet(self._id, self._noshow_acti, self._project, start, end, "", 0, False)
            else:
                logging.info(f"Insert free day for user {self._email}")
                db_util.insert_timesheet(self._id, self._freeday_acti, self._project, start, end, "", 0, False)


    def _float_to_dt(self, day, value):
        hours = int(value)
        minutes = int(60*(value - hours))
        dt = datetime(day.year, day.month, day.day, hours, minutes)
        #userdt = pytz.timezone(self._preferences["timezone"]).localize(dt)
        return pytz.timezone(self._preferences["timezone"]).localize(dt)

    
    def sum_weekly_time(self, day:date):
        return db_util.sum_times_weeks(self._id, [day] )[0][2]


    def get_registration_date(self):
        return self._registration.date()

    
    def get_first_record_date(self):
        return db_util.get_first_timesheet_date(self._id) 

    
    def receive_admin_mails(self):
        return self._preferences.get("receive_administrativ_mails", 0)
    

    def insert_auto_worktime(self, workday:date):
        # check not worked already that day (this also finds public holidays)
        # make sure its also not the weekend (day 5 or 6)
        if self.has_not_worked(workday) and workday.weekday() not in [5, 6]:
            # compare to the maximum allowed weekly worktime of the fellow
            week_max = int(self._preferences.get("worktime_auto_insert_weekly_max", 0))
            if week_max == 0:
                return
            week_cur = self.sum_weekly_time(workday)
            week_remaining_time = week_max - week_cur
            if week_remaining_time > 0:
                # if there is any time left to insert this week, do the daily maximum or remaining limit
                insertseconds = min(week_remaining_time, int(self._preferences["worktime_auto_insert_daily_max"]))
                start = self._float_to_dt(workday, float(self._preferences["worktime_auto_insert_start_time"]))
                end = start + timedelta(seconds=insertseconds)
                default_work = Angestellter.__workingconfig[self._role]["work"][0]
                default_proj = Angestellter.__workingconfig[self._role]["project"]
                logging.info(f"Autowork: Inserting {insertseconds} seconds autowork for user {self._email}")
                db_util.insert_timesheet(self._id, self._work_actis[0], self._project, start, end, "", 0, False)
            else:
                logging.info(f"Autowork: user {self._email} has filled weekly quota. Doing nothing")

    
    def update_breaktime(self, day):
        # check the total worktime is greater than 6 or 8 hours
        # between 6 and 8 hours, 30 minutes break are neccessairy
        # over 8 hours 1 hour break is neccessairy
        # also calculate the times between individual sheets, if there is a break over 15 minutes, count it towards the forced break time
        sheets = db_util.get_sheets_for_day(self._id, day, self._work_actis)
        total_duration = sum([ts.duration for ts in sheets])
        remaining_time = 0
        if total_duration > (8 * 60 * 60):
            # work over 8:00 hours -> minimum break time 3600s (1h)
            break_times = db_util.calculate_timesheet_break_times(sheets)
            remaining_time = 3600 - break_times
        elif total_duration > (6 * 60 * 60):
            # work between 6:01 and 8:00 hours -> minimum break time 1800s (30min)
            break_times = db_util.calculate_timesheet_break_times(sheets)
            remaining_time = 1800 - break_times
        # get breaksheet if it already exists to update instead of insert
        breaksheet = db_util.get_sheets_for_day(self._id, day, [self._break_acti])
        if breaksheet:
            breaksheet = breaksheet[0]
        if remaining_time > 0:
            # have to insert a break of remaining_time seconds
            if breaksheet and breaksheet.duration == -remaining_time:
                # the current break time is the same as the exisiting one
                return
            # always use UTC 0 hour as start
            # _, break_start = sheets[-1].tzaware_start_end()
            # if break_start.date() != day:
            #     # if appending the break at the end of the working time, make sure it is still the same day
            #     # since it is not possible in this case, append the time at the start of the day
            #     break_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
            break_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
            break_end = break_start + timedelta(seconds=remaining_time)
            total_h = int(total_duration/3600)
            total_min = int(total_duration/60) - (total_h * 60)
            breakinfo = f"{datetime.utcnow():%Y-%m-%d %H:%M}: Arbeit: {total_h}:{total_min} Pausen: {break_times/60:.2f} min"
            if breaksheet:
                logging.info(f"Updating mandatory break for user {self._email} on {day}: {remaining_time} seconds. Worked {total_duration} and took {break_times} break by sign out")
                db_util.update_timesheet_times_description(breaksheet, break_start, break_end, f"{breakinfo}\n{breaksheet.description}")
            else:
                logging.info(f"Inserting mandatory break for user {self._email} on {day}: {remaining_time} seconds. Worked {total_duration} and took {break_times} break by sign out")
                db_util.insert_timesheet(self._id, self._break_acti, self._project, break_start, break_end, breakinfo, 0, True)
        else:
            # dont have to insert a break, check if the breaksheet exists, than delete it
            if breaksheet:
                db_util.timesheet_delete(breaksheet.id)


    def update_saldo(self, day):
        saldo_sheets = db_util.get_all_saldo_sheets(self._id, self._saldo_acti)
        if not saldo_sheets:
            # no saldo present, create from zero until DAY
            start = self.get_first_record_date()
            if start is None:
                return
            start = datetime(start.year, start.month, start.day, tzinfo=UTC)
            db_util.insert_timesheet(self._id, self._saldo_acti, self._project, start, start, f"{datetime.utcnow()}: Startsaldo 0", 0, True)
            self.update_saldo(day)
        else:
            if saldo_sheets[-1].date_tz == day:
                # the newest saldo is on the same day requested for generation, so update its value any changed ones on between
                for a, b in zip(saldo_sheets[:-1], saldo_sheets[1:]):
                    # calculate the time between [a b) and than update b if neccesairy
                    start = a.start
                    td1d = timedelta(days=1)
                    end = b.start - td1d
                    worked_time = db_util.sum_times_range(self._id, start.date(), end.date())
                    has_to_work = 0
                    wtwd = self._worktime_weekdays
                    while start <= end:
                        has_to_work += wtwd[start.weekday()]
                        start += td1d
                    new_saldo = worked_time - has_to_work
                    if b.duration != new_saldo:
                        db_util.update_saldo_duration_description_unsafe(b.id, new_saldo, f"{datetime.utcnow():%Y-%m-%d %H:%M}: {new_saldo/3600:.2f}h\n{b.description}")
            else:
                if saldo_sheets[-1].date_tz < day:
                    # the new saldo request is further in the future compared to the last saldo. 
                    # create a dummy value and than run the function again to re-use same day update
                    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
                    db_util.insert_timesheet(self._id, self._saldo_acti, self._project, start, start, f"", 0, True)
                    self.update_saldo(day)
                elif saldo_sheets[0].date_tz < day:
                    # the new saldo day is somewhere in between the existing saldo_sheets or completely new. search for it
                    notfound = True
                    for sheet in saldo_sheets:
                        if sheet.date_tz == day:
                            notfound = False
                            break
                    if notfound:
                        # not found, so create entry here, than run the whole calculation again until the newest saldo day
                        start = datetime(day.year, day.month, day.day, tzinfo=UTC)
                        db_util.insert_timesheet(self._id, self._saldo_acti, self._project, start, start, f"", 0, True)
                    self.update_saldo(saldo_sheets[0].date_tz)

                


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


def export_invoice(user:str, start:date, end:date, template:str, outpath:str|Path) -> str:
    #   Usage:
    #   kimai:invoice:create [options]

    #   Options:
    #       --user=USER                      The user to be used for generating the invoices
    #       --start[=START]                  Start date (format: 2020-01-01, default: start of the month)
    #       --end[=END]                      End date (format: 2020-01-31, default: end of the month)
    #       --timezone[=TIMEZONE]            Timezone for start and end date query (fallback: users timezone)
    #       --customer[=CUSTOMER]            Comma separated list of customer IDs
    #       --project[=PROJECT]              Comma separated list of project IDs
    #       --by-customer                    If set, one invoice for each active customer in the given timerange is created
    #       --by-project                     If set, one invoice for each active project in the given timerange is created
    #       --set-exported                   Whether the invoice items should be marked as exported
    #       --template[=TEMPLATE]            Invoice template
    #       --template-meta[=TEMPLATE-META]  Fetch invoice template from a meta-field
    #       --search[=SEARCH]                Search term to filter invoice entries
    #       --exported[=EXPORTED]            Exported filter for invoice entries (possible values: exported, all), by default only "not exported" items are fetched
    #       --preview[=PREVIEW]              Absolute path for a rendered preview of the invoice, which will neither be saved nor the items be marked as exported.
    #       --preview-unique                 Adds a unique part to the filename of the generated invoice preview file, so there is no chance that they get overwritten on same project name.
    #./bin/console kimai:invoice:create --user=presley85 --template=myinvoi --exported=all --by-customer
    res = subprocess.run([get_console(), "kimai:invoice:create", f"--user={user}", f"--start={start.strftime('%Y-%m-%d')}", f"--end={end.strftime('%Y-%m-%d')}", f"--template={template}", f"--by-customer", "--exported=all", f"--preview={outpath}"], capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"{res.stderr}\n\n{res.stdout}")
    print(res.stdout)


def export_monthly_journal_student(user:str, start:date, end:date, outpath:Path):
    export_invoice(user, start, end, "journal_student", outpath)
    

if __name__ == "__main__":
    pass
    students = db_util.get_user_by_role("Werk")