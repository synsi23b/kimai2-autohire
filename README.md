# kimai2-autohire

programmed against kimai version 1.21

# setup

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
30 6 25-31 * 3 lxc exec kimai -- /root/prelim.bash >/dev/null 2>&1 && curl -fsS --retry 3 https://hc-ping.com/secret > /dev/null
# export final timesheet on the first monday noon that is on or after the 3rd
0 10 3-9 * 1 /root/export_to_nc.bash >/dev/null 2>&1 && curl -fsS --retry 3 https://hc-ping.com/secret > /dev/null
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

The monthly hours will be used to create a budgeted activity for this user only, but going over budget is acceptable (set in kimai settings)

Another way to create multiple users at once is to supply a csv file after the flag --file. There is an example file in the files folder.

User creation will trigger an e-mail using the kimai credentials. The email contains the user manuals and the login credentials.