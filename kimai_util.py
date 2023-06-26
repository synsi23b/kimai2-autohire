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
MANUAL_BREAK_ID = 27


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
        self._worktime_weekdays = [int(self._preferences.get(Angestellter.__vacationconfig[f"worktime_{idx}"], 0)) for idx in range(7)]
        if role != "ROLE_ADMIN":
            self._work_actis = Angestellter.__workingconfig[self._role]["work"]
            self._project = Angestellter.__workingconfig[self._role]["project"]
            self._break_acti = Angestellter.__workingconfig[self._role]["breaktime"]
            self._freeday_acti = Angestellter.__workingconfig[self._role]["freeday"]
            self._noshow_acti = Angestellter.__workingconfig[self._role]["noshow"]
            self._flex_acti = Angestellter.__workingconfig["flex_id"]


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
        # check user is actualy supposed to work on this day and insert the specific working time
        # but only for fixed employees and not students
        if self._role == "ANGESTELLTER":
            workingtime = self._worktime_weekdays[holidate.weekday()]
        else:
            workingtime = 0
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
            start = end = datetime(workday.year, workday.month, workday.day, tzinfo=UTC)
            #start = end = pytz.timezone(self._preferences["timezone"]).localize(dt)
            if self._worktime_weekdays[workday.weekday()] > 0:
                logging.info(f"Insert missing day for user {self._email}")
                db_util.insert_timesheet(self._id, self._noshow_acti, self._project, start, end, "", 0, False)
            else:
                logging.info(f"Insert free day for user {self._email}")
                db_util.insert_timesheet(self._id, self._freeday_acti, self._project, start, end, "", 0, False)

    
    def fill_missing_freeday(self, workday:date):
        if self.has_not_worked(workday):
            start = end = datetime(workday.year, workday.month, workday.day, tzinfo=UTC)
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
        # https://www.arbeitsrechte.de/pausenregelung/
        # check the total worktime is within the german laws
        # between 6 and 9 hours, 30 minutes break are neccessairy
        # over 9 hours at least 45 Minutes
        # also calculate the times between individual sheets, if there is a break over 15 minutes, count it towards the forced break time
        sheets = db_util.get_sheets_for_day(self._id, day, self._work_actis)
        total_duration = sum([ts.duration for ts in sheets])
        required_break = 0
        break_taken = 0
        breaklist = []
        if total_duration != 0:
            if total_duration > (6 * 60 * 60):
                required_break = 30 * 60
            if total_duration > (9 * 60 * 60):
                required_break = 45 * 60
            break_taken, breaklist = db_util.calculate_timesheet_break_times(sheets)
        remaining_time = required_break - break_taken
        if remaining_time < 0:
            remaining_time = 0
        # create data for the break sheet, create a breaksheet for every day, even if its zero in duration, unless there was no work
        break_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        break_end = break_start + timedelta(seconds=remaining_time)
        # get breaksheet if it already exists to update instead of insert
        breaksheet = db_util.get_sheets_for_day(self._id, day, [self._break_acti, MANUAL_BREAK_ID])
        if not breaksheet and total_duration > 0:
            db_util.insert_timesheet(self._id, self._break_acti, self._project, break_start, break_end, "", 0, False)
            breaksheet = db_util.get_sheets_for_day(self._id, day, [self._break_acti])
        # delete breaksheets that are too much, we only need one
        elif len(breaksheet) > 1:
            for s in breaksheet[1:]:
                db_util.timesheet_delete(s.id)
        # resolve breaksheet list to actual sheet
        if not breaksheet:
            return
        breaksheet = breaksheet[0]
        # check if the person has working time at all for the day, only create a breaksheet in those cases
        if total_duration == 0:
            db_util.timesheet_delete(breaksheet.id)
        else:
            # update the existing timesheet with the calculation we did just now
            total_h = int(total_duration/3600)
            total_min = int(total_duration/60) - (total_h * 60)
            if total_min < 10:
                total_min = f"0{total_min}"
            breakinfo = f"Generated at {datetime.utcnow():%Y-%m-%d %H:%M}; Working time {total_h}:{total_min} -> {int(required_break/60)} min break"
            breaklist = "\n".join(breaklist)
            if breaklist:
                breakinfo = f"{breakinfo}\n{breaklist}"
            logging.info(f"Updating break for user {self._email} on {day}: {remaining_time} seconds. {breakinfo}")
            db_util.update_timesheet_times_description(breaksheet, break_start, break_end, f"{breakinfo}\n{breaksheet.description}")


    def update_flextime(self, day):
        flex_sheets = db_util.get_all_flex_sheets(self._id, self._flex_acti)
        if not flex_sheets:
            logging.info(f"Creating flextime start for user {self._email} -> {self._worktime_weekdays}")
            # no flex present, create from zero until DAY
            start = self.get_first_record_date()
            if start is None:
                return
            start = datetime(start.year, start.month, start.day, tzinfo=UTC)
            flexdesc = db_util.generate_flex_description(0, self._worktime_weekdays)
            db_util.insert_timesheet(self._id, self._flex_acti, self._project, start, start, flexdesc, 0, True)
            self.update_flextime(day)
        else:
            if flex_sheets[-1].date_tz == day:
                # the newest flex is on the same day requested for generation, so update its value any changed ones on between
                for a, b in zip(flex_sheets[:-1], flex_sheets[1:]):
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
                    new_flex = worked_time - has_to_work
                    bflex = int(b.description.split(",")[0])
                    if bflex != new_flex:
                        flexentry = db_util.generate_flex_description(new_flex, wtwd)
                        logging.info(f"Update old flextime for user {self._email} -> ID {b.id} DATE {b.date_tz} FROM {b.description} TO {flexentry}")
                        db_util.update_flex_description(b.id, flexentry)
            else:
                if flex_sheets[-1].date_tz < day:
                    # the new flex request is further in the future compared to the last flex. 
                    # create a dummy value and than run the function again to re-use same day update
                    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
                    flexdesc = db_util.generate_flex_description(0, self._worktime_weekdays)
                    logging.info(f"Insert new flextime for user {self._email} ->  DATE {start} DESC {flexdesc}")
                    db_util.insert_timesheet(self._id, self._flex_acti, self._project, start, start, flexdesc, 0, True)
                    self.update_flextime(day)
                elif flex_sheets[0].date_tz < day:
                    # the new flex day is somewhere in between the existing flex_sheets or completely new. search for it
                    notfound = True
                    for sheet in flex_sheets:
                        if sheet.date_tz == day:
                            notfound = False
                            break
                    if notfound:
                        # not found, so create entry here, than run the whole calculation again until the newest flex day
                        start = datetime(day.year, day.month, day.day, tzinfo=UTC)
                        flexdesc = db_util.generate_flex_description(0, self._worktime_weekdays)
                        logging.info(f"Insert new flextime for user {self._email} ->  DATE {start} DESC {flexdesc}")
                        db_util.insert_timesheet(self._id, self._flex_acti, self._project, start, start, flexdesc, 0, True)
                    self.update_flextime(flex_sheets[0].date_tz)

    def export_monthly_journal(self, start:date, end:date, outfolder:Path):
        res = []
        if db_util.check_timesheet_exists_range(self._id, start, end) > 0:
            res = export_invoice(self._user, start, end, "monatsjournal", outfolder)
        return res


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


def export_invoice(user:str, start:date, end:date, template:str, outfolder:Path) -> str:
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
    res = subprocess.run([get_console(), "kimai:invoice:create", f"--user={user}", f"--start={start.strftime('%Y-%m-%d')}", f"--end={end.strftime('%Y-%m-%d')}", f"--template={template}", f"--by-customer", "--exported=all", f"--preview={str(outfolder)}", "--preview-unique"], capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"{res.stderr}\n\n{res.stdout}")
    output = str(res.stdout, "utf-8")
    logging.info(output)
    filelist = re.findall("\|\s(.+?\.pdf)\s\|", output)
    for f in filelist:
        logging.info(f)
    return filelist
    

if __name__ == "__main__":
    pass
    students = db_util.get_user_by_role("Werk")