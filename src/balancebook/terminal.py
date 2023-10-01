# https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal
class TColors:
    OKGREEN = '\033[32m'
    WARNING = '\033[95m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def fwarning(s):
    return TColors.WARNING + "Warning: " + s + TColors.ENDC

def fok(s):
    return TColors.OKGREEN + s + TColors.ENDC

def ffail(s):
    return TColors.FAIL + "Error: " + s + TColors.ENDC

def fbold(s):
    return TColors.BOLD + s + TColors.ENDC

def funderline(s):
    return TColors.UNDERLINE + s + TColors.ENDC