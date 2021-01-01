#!/usr/bin/python
"""Schedule Plex server related Pre-roll Intro videos
A helper script to automate management of Plex pre-rolls.
Define when you want different pre-rolls to play throughout the year.

Ideas include:
- Holiday pre-roll rotations
- Special occasions
- Summer/Winter rotations
- Breaking up the monoteny
- Keeping your family/friends on their toes!

Set it and forget it!

Optional Arguments:
    -h, --help                  show this help message and exit
    -c [], --config-path []     path/to/config.ini file to use 
                                (Optional: uses local/plexapi default path if omitted)
    -s [],--schedule-path []    path/to/preroll_schedules.yaml file to use 
                                (Optional: uses local path if omitted)
    -l [], --logconfig-path []  path/to/logging.conf logging configuration file 
                                (Optional: uses local path if omitted)

Requirements:
- See Requirements.txt for Python modules

Scheduling: 
    Add to system scheduler such as:
    > crontab -e 
    > 0 0 * * * python path/to/schedule_preroll.py >/dev/null 2>&1

Raises:
    FileNotFoundError: [description]
    KeyError: [description]
    ConfigError: [description]
    FileNotFoundError: [description]
"""
import os
import sys
import logging
import logging.config
import requests
import datetime
import yaml
from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import Error as ConfigError
from plexapi.server import PlexServer, CONFIG

# import local modules
import plexutil

logger = logging.getLogger(__name__)

filename = os.path.basename(sys.argv[0])
SCRIPT_NAME = os.path.splitext(filename)[0]

def getArguments():
    """Return command line arguments
    See https://docs.python.org/3/howto/argparse.html

    Returns:
        argparse.Namespace: Namespace object
    """
    description = 'Automate scheduling of pre-roll intros for Plex'
    version = '0.7.0'

    log_default = './logging.conf'
    config_default = './config.ini'
    schedule_default = './preroll_schedules.yaml'
    parser = ArgumentParser(description='{}'.format(description))
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {}'.format(version), help='show the version number and exit')
    parser.add_argument('-l', '--logconfig-path', dest='log_config_file', default=log_default, action='store', help='Path to logging config file. Default: {}'.format(log_default))
    parser.add_argument('-c', '--config-path', dest='config_file', action='store', help='Path to Config.ini to use for Plex Server info. Default: {}'.format(config_default))
    parser.add_argument('-s', '--schedule-path', dest='schedule_file', action='store', help='Path to pre-roll schedule file (YAML) to be use. Default: {}'.format(schedule_default))
    args = parser.parse_args()

    return args

def getYAMLSchema():
    """Return the main schema layout of the preroll_schedules.yaml file

    Returns:
        dict: Dict of main schema items
    """
    schema = {'default': None, 'monthly': None, 'weekly': None, 'date_range': None, 'misc': None}
    return schema

def getWeekRange(year, weeknum):
    """Return the starting/ending date range of a given year/week

    Args:
        year (int): Year to calc range for
        weeknum (int): Month of the year (1-12)

    Returns:
        Date: Start date of the Year/Month
        Date: End date of the Year/Month
    """
    start = datetime.datetime.strptime('{}-W{}-0'.format(year, int(weeknum)-1), "%Y-W%W-%w").date()
    end = start + datetime.timedelta(days=6)

    return start, end

def getMonthRange(year, monthnum):
    """Return the starting/ending date range of a given year/month

    Args:
        year (int): Year to calc range for
        monthnum (int): Month of the year (1-12)

    Returns:
        Date: Start date of the Year/Month
        Date: End date of the Year/Month
    """
    start = datetime.date(year, monthnum, 1)
    next_month = start.replace(day=28) + datetime.timedelta(days=4)
    end = next_month - datetime.timedelta(days=next_month.day)

    return start, end

def getPrerollSchedule(filename=None):
    """Return a listing of defined preroll schedules for searching/use

    Raises:
        FileNotFoundError: If no schedule config file exists

    Returns:
        list: list of schedules (Dict: {Type, StartDate, EndDate, Path})
    """
    default_files = ['preroll_schedules.yaml', 'preroll_schedules.yml']

    schedule_file = None
    if filename != None:
        if os.path.exists(filename):
            schedule_file = filename
        else:
            raise FileNotFoundError('Preroll Schedule file -s "{}" not found'.format(filename))
    else:
        for f in default_files:
            if os.path.exists(f):
                schedule_file = f
                break
    
    # if we still cant find a schedule file, we hae to abort
    if not schedule_file:
        msg = 'No {} Found'.format(' / '.join(default_files))
        logger.critical(msg)
        raise FileNotFoundError(msg)

    with open(schedule_file, 'r') as file:
        #contents = yaml.load(file, Loader=yaml.SafeLoader)
        contents = yaml.load(file, Loader=yaml.FullLoader)

    today = datetime.date.today()
    schedule = []
    for schedule_type in getYAMLSchema():
        if schedule_type == 'weekly':
            try:
                use = contents[schedule_type]['enabled']

                if use:
                    for i in range(1,53):
                        try:
                            path = contents[schedule_type][i]

                            if path:
                                entry = {}
                                start, end = getWeekRange(today.year, i)
                                entry['Type'] = schedule_type
                                entry['StartDate'] = start
                                entry['EndDate'] = end
                                entry['Path'] = path

                                schedule.append(entry)
                        except KeyError as e:
                            # skip KeyError for missing Weeks
                            logger.debug('Key Value not found: "{}"->"{}", skipping week'.format(schedule_type, i))
                            continue
            except KeyError as e:
                logger.error('Key Value not found in "{}" section'.format(schedule_type), exc_info=e)
                raise e
        elif schedule_type == 'monthly':
            try:
                use = contents[schedule_type]['enabled']

                if use:
                    for i in range(1,13):
                        month_abrev = datetime.date(today.year, i, 1).strftime('%b').lower()
                        try:
                            path = contents[schedule_type][month_abrev]    

                            if path:
                                entry = {}
                                start, end = getMonthRange(today.year, i)
                                entry['Type'] = schedule_type
                                entry['StartDate'] = start
                                entry['EndDate'] = end
                                entry['Path'] = path

                                schedule.append(entry)
                        except KeyError as e:
                            # skip KeyError for missing Months
                            logger.warning('Key Value not found: "{}"->"{}", skipping month'.format(schedule_type, month_abrev))
                            continue
            except KeyError as e:
                logger.error('Key Value not found in "{}" section'.format(schedule_type), exc_info=e)
                raise e
        elif schedule_type == 'date_range':
            try:
                use = contents[schedule_type]['enabled']
                if use: 
                    for r in contents[schedule_type]['ranges']:
                        try:
                            path = r['path']

                            if path:
                                entry = {}
                                entry['Type'] = schedule_type
                                entry['StartDate'] = r['start_date']
                                entry['EndDate'] = r['end_date']
                                entry['Path'] = path

                                schedule.append(entry)
                        except KeyError as e:
                            #logger.error('Key Value not found: "{}"'.format(schedule_type), exc_info=e)
                            raise e
            except KeyError as e:
                logger.error('Key Value not found in "{}" section'.format(schedule_type), exc_info=e)
                raise e
        elif schedule_type == 'misc':
            try:
                use = contents[schedule_type]['enabled']
                if use:
                    try:
                        path = contents[schedule_type]['always_use']

                        if path:
                            entry = {}
                            entry['Type'] = schedule_type
                            entry['StartDate'] = datetime.date(today.year, today.month, today.day)
                            entry['EndDate'] = datetime.date(today.year, today.month, today.day)
                            entry['Path'] = path

                            schedule.append(entry)
                    except KeyError as e:
                        #logger.error('Key Value not found: "{}"'.format(schedule_type), exc_info=e)
                        raise e
            except KeyError as e:
                logger.error('Key Value not found in "{}" section'.format(schedule_type), exc_info=e)
                raise e
        elif schedule_type == 'default':
            try:
                use = contents[schedule_type]['enabled']
                if use:
                    try:
                        path = contents[schedule_type]['path']

                        if path:
                            entry = {}
                            entry['Type'] = schedule_type
                            entry['StartDate'] = datetime.date(today.year, today.month, today.day)
                            entry['EndDate'] = datetime.date(today.year, today.month, today.day)
                            entry['Path'] = path

                            schedule.append(entry)
                    except KeyError as e:
                        #logger.error('Key Value not found: "{}"'.format(schedule_type), exc_info=e)
                        raise e
            except KeyError as e:
                logger.error('Key Value not found in "{}" section'.format(schedule_type), exc_info=e)
                raise e

        else:
            continue 

    # Sort list so most recent Ranges appear first
    schedule.sort(reverse=True, key=lambda x:x['StartDate'])

    return schedule

def buildListingString(items, play_all=False):
    """Build the Plex formatted string of preroll paths

    Args:
        items (list): List of preroll video paths to place into a string listing
        play_all (bool, optional): Play all videos. Defaults to False (Random choice)

    Returns:
        string: CSV Listing (, or ;) based on play_all param of preroll video paths
    """
    if play_all:
        # use , to play all entries
        listing = ','.join(items)
    else:
        pass
        #use ; to play random selection
        listing = ';'.join(items)

    return listing

def getPrerollListingString(schedule_file=None):
    """Return listing of preroll videos to be used by Plex

    Returns:
        string: listing of preroll video paths to be used for Extras
    """
    listing = ''
    entries = dict(getYAMLSchema())
    today = datetime.date.today()

    for e in getYAMLSchema():
        entries[e] = [] 

    # the the time series schedule of pre-rolls
    schedule = getPrerollSchedule(schedule_file)

    for entry in schedule:
        if entry['StartDate'] <= today <= entry['EndDate']:
            try:
                entry_type = entry['Type']
            except KeyError:
                continue
            
            path = entry['Path']

            if path:    
                entries[entry_type].append(path)

    # Build the merged output based or order of Priority
    merged_list = []
    if entries['misc']:
        merged_list.extend(entries['misc'])
    if entries['date_range']:
        merged_list.extend(entries['date_range'])
    if entries['weekly'] and not entries['date_range']:
        merged_list.extend(entries['weekly'])
    if entries['monthly'] \
        and not entries['weekly'] and not entries['date_range']:
        merged_list.extend(entries['monthly'])
    if entries['default'] \
        and not entries['monthly'] and not entries['weekly'] and not entries['date_range']:
        merged_list.extend(entries['default'])

    listing = buildListingString(merged_list)

    return listing

def setPrerollList(plex, preroll_listing):
    """Save Plex Preroll info to PlexServer settings

    Args:
        plex (PlexServer): Plex server to update
        preroll_listing (string, list): csv listing or List of preroll paths to save
    """
    # if happend to send in an Iterable List, merge to a string
    if type(preroll_listing) is list:
        preroll_listing = buildListingString(preroll_listing)

    plex.settings.get('cinemaTrailersPrerollID').set(preroll_listing)    
    plex.settings.save()

if __name__ == '__main__':
    args = getArguments()

    log_config = args.log_config_file
    if os.path.exists(log_config):
        logging.config.fileConfig(log_config, disable_existing_loggers=False)
    else:
        logger.warning('Logging Config file "{}" not available')

    cfg = plexutil.getPlexConfig(args.config_file)

    # Initialize Session information
    sess = requests.Session()
    # Ignore verifying the SSL certificate
    sess.verify = False    # '/path/to/certfile'
    # If verify is set to a path of a directory (not a cert file),
    # the directory needs to be processed with the c_rehash utility 
    # from OpenSSL.
    if sess.verify is False:
        # Disable the warning that the request is insecure, we know that...
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        plex = PlexServer(cfg['PLEX_URL'], cfg['PLEX_TOKEN'], session=sess)
    except Exception as e:
        logger.error('Error Connecting to Plex', exc_info=e)
        raise e

    prerolls = getPrerollListingString(args.schedule_file)
    logger.info('Saving Preroll List: "{}"'.format(prerolls))
    setPrerollList(plex, prerolls)