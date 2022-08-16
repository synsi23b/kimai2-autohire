import subprocess
import dotenv
from os import getenv
import db_util
import re
import urllib

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


if __name__ == "__main__":
    pass
    tup = get_email_credentials()