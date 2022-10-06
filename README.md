# kimai2-autohire

programmed against kimai version 1.21

# setup

## apt

```bash
sudo apt install xvfb firefox
# maybe no libre office. the pdf it makes is not good. Tweak the template file and it might work
# used to make pdfs from the xlsx timesheets instead of convertapi
sudo apt install libreoffice --no-install-recommends  --no-install-suggests
```
## create second database for keeping own records on kimai host

```sql
mysql> create database dbautohire;
mysql> grant all privileges on dbautohire.* to kimai@localhost with grant option;
mysql> flush privileges;
```
create tables in this database:

db_util ->
  - _create_last_generation


## basic setup
1. after cloning into home directory, install requirements in a virtual environment called venv
```bash
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```
2. some information like the database and email information gets read from the kimai env file, so make sure kimai is in the default path */var/www/kimai2* and its environment file is populated
3. setup crontabs to run for a user that can read the kimai env file, for an example see work-life-checker.


## cron entries
```bash
# create worklife report on sundays
45 23 * * 0 lxc exec kimai -- /root/wlifecheck.bash >/dev/null 2>&1 && curl -fsS --retry 3 https://hc-ping.com/secret> /dev/null
# create preliminary timesheet exports on the first wednesday that is on or after the 25th
*/15 * 28-31,1-3 * * lxc exec kimai -- /root/prelim.bash >/dev/null 2>&1 && curl -fsS --retry 3 https://hc-ping.com/secret > /dev/null
# export final timesheet on the first monday noon that is on or after the 3rd
0 4 4 * * /root/export_to_nc.bash >/dev/null 2>&1 && curl -fsS --retry 3 https://hc-ping.com/secret > /dev/null
```


# Work-Life-Checker

The work life checker can calculate the sum of working hours over each week for the last 5 weeks. It counts from Monday to Sunday regardless of the day it is executed, therefore should be ideally run on Sunday night, just before beginning of the next week.

The scripts sends a worktime report to every user checked. If it detects that a user spend 10 hours more than their regular weekly time, it will also send this report to the supervisors.

This is an example integration with the system root crontab, to run the work life balance check every Sunday night at 23:24 of system time.
```bash
24 23 * * 0 sudo -u ubuntu /home/ubuntu/kimai2-autohire/cron/worklife_check.bash
```

To setup the script, copy the file worklife.yaml from the cron folder to the home directory.
```bash
cp kimai2-autohire/cron/worklife.yaml /home/ubuntu/
```
And fill in which users to check and to which supervisors to send mails if an alarm is triggered.
The configuration works like this: 
one entry per line, key-value pairs.

- if the entry is an email-address, it is a supervisor-email that gets send alerts. multiple supervisors can be defined. there is no meaning to the value attached to the supervisor, so just set it to 1 for now.

- if the entry is a number, it is interpreted as the user id from the database to check. the value section is the nominal worktime per week for that user in hours. To get a list of users and ID execute the following sql.
```sql
mysql> USE kimaidb;
mysql> SELECT id, username, alias FROM kimai2_users;
```

# user creation script

creating a user can done via command line arguments and the script `create_user.py`

The arguments to supply are the new Users First and Last name, e-mail address, group name and working hours per month.

The users group name needs to match a Project name in the Kimai instance. From this grouping, the users salary is also retrieved. The salary needs to be set on the project level in Kimai. The group/project will also be used to check for seasonal changes in allowable worktime per month regardless of monthly hours set.

The monthly hours will be used to create a budgeted activity for this user only, but going over budget is acceptable (set in Kimai settings)

Another way to create multiple users at once is to supply a csv file after the flag --file. There is an example file in the files folder.

User creation will trigger an e-mail using the Kimai credentials. The email contains the user manuals and the login credentials.

# create_timesheet_kgl script

the script will take the timesheets of projects marked with \*generate_sheets\* as the first line of their description. Other parts of the description serve as a configuration space using yaml to set the Vorlesungsfreie Zeit or maximum hours per month and week. For example:

```yaml
*generate_sheets*
max_weekly: 40
max_monthly: 0
max_weekly_season: 20
seasons:
 - 14.10.2024 - 14.02.2025
 - 15.04.2024 - 19.07.2024
 - 16.10.2023 - 09.02.2024
 - 11.04.2023 - 14.07.2023
 - 17.10.2022 - 10.02.2023
```

When run, the script will test whether the day is before or past the 15th. and collect the timesheets accordingly. if it is after the 15th, for the current month, before, for the preceding month. When the script is called with the parameter "--preliminary" the timesheets wont be transmitted to KGL, but just to the users to inform them of their current times.

Further checks done by the script:
- warn users with open timesheets that are longer than 12 hours
- warn users about overwork in a week or month
- warn users that have no timesheet at all

The script should be run a lot of times during the end of month period with the preliminary flag to get everyone's timesheets in order. If a user changes something, this change will be detected and they will get another mail after at least 15 minutes have passed since the last change.

Without the preliminary flag, the script should only be run one time sometime at the start of the new month. It will create PDFs of the timesheets using convertapi. These can be uploaded to the Nextcloud and KGL. The upload to KGL is done via selenium and might brake should they change their website. Similarily, convertapi needs a fresh api token every now and than, unless you pay for it.