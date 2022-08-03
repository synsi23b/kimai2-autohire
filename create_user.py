import random
import string
import kimai_util
import db_util


def create_user(firstname, lastname, email, usertype, salary, monthly_hours):
    usr = (firstname[0] + firstname[-1] + lastname[:5]).lower()
    pwd = "".join(random.choices(string.ascii_letters + string.digits,k=12))
    kimai_util.console_user_create(usr, pwd, email)
    print(usr, pwd)
    db_util.set_user_alias(usr, firstname, lastname)
    kimai_util.create_activity(usertype, usr, salary, monthly_hours)


if __name__ == "__main__":
    create_user("jokk", "parker", "jop@pp.de", "Werkstudent", 15.0, 20.3)
