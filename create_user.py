import random
import string
import kimai_util


def create_user(firstname, lastname, email, type, salary):
    usr = (firstname[0] + firstname[-1] + lastname[:5]).lower()
    pwd = "".join(random.choices(string.ascii_letters + string.digits,k=12))
    kimai_util.console_user_create(usr, pwd, email)


if __name__ == "__main__":
    create_user("peter", "parker", "pp@pp.de", "Werkstudent", 15.0)
