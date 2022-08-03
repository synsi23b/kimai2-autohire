import subprocess
from dotenv import load_dotenv
from os import getenv

load_dotenv()


def get_console():
    """
    return path to console binary using standard if not overwritten by env
    """
    path = getenv("KIMAI_BINARY_PATH")
    if path is None:
        return "/var/www/kimai2/bin/console"
    return path


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
    res = subprocess.run([cons, "--no-interaction", "kiami:user:create", user, email, "ROLE_USER", passw])
    res.check_returncode()