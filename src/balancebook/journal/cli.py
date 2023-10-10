import argparse
from balancebook.__about__ import __version__
from balancebook.errors import catch_and_log
from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal

parser = argparse.ArgumentParser(
          prog='balancebook', 
          description='Balance book, plain text budgeting')
parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
parser.add_argument('-f', '--configfile', metavar='CONFIGFILE', type=str, dest='config_file',
                    help='Configuration file to use', default='journal/balancebook.yaml')

subparsers = parser.add_subparsers(help='sub-command help', dest='command')

verify_parser = subparsers.add_parser('verify', help='Verify the journal')


parser.add_argument('configfile', metavar='CONFIGFILE', type=str)

@catch_and_log
def main():
    args = parser.parse_args()

    if args.command == 'verify':
        journal = get_journal(args.configfile)
        journal.load()
        journal.verify_balances()
    else:
        parser.print_help()
  
def get_journal(config_file):
    config = load_config(config_file)
    return Journal(config)