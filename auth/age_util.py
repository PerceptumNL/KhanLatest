import datetime


def get_age(birthdate, today=None):
    """ Returns the given age for somebody based on their birthdate.

    People born on leap-days are considered to celebrate birthdays on March 1
    of non-leap years.

    """

    if today is None:
        today = datetime.date.today()

    # Check if the birthday has happened this year.
    try:
        birthday = birthdate.replace(year=today.year)
    except ValueError:
        # The user must have been born on a leap day, and this year is not leap
        birthday = birthdate.replace(year=today.year, month=3, day=1)

    if birthday > today:
        return today.year - birthdate.year - 1
    else:
        return today.year - birthdate.year
