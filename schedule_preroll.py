#!/usr/bin/python
"""Schedule Plex server related Pre-roll Intro videos
A helper script to automate management of Plex pre-rolls.
Define when you want different pre-rolls to play throughout the year.

Set it and forget it!

Optional Arguments:
  -h, --help            show this help message and exit
  -v, --version         show the version number and exit
  -lc LOG_CONFIG_FILE, --logconfig-path LOG_CONFIG_FILE
                        Path to logging config file. 
                        [Default: ./logging.conf]
  -c CONFIG_FILE, --config-path CONFIG_FILE
                        Path to Config.ini to use for Plex Server info. 
                        [Default: ./config.ini]
  -s SCHEDULE_FILE, --schedule-path SCHEDULE_FILE
                        Path to pre-roll schedule file (YAML) to be use. 
                        [Default: ./preroll_schedules.yaml]

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
import requests
from datetime import datetime, date, timedelta
import yaml
from typing import NamedTuple, Union, Optional, Tuple, List, Dict
from argparse import Namespace, ArgumentParser
from configparser import ConfigParser
from configparser import Error as ConfigError
from plexapi.server import PlexServer, CONFIG

# import local util modules
import plexutil

logger = logging.getLogger(__name__)

filename = os.path.basename(sys.argv[0])
SCRIPT_NAME = os.path.splitext(filename)[0]

class ScheduleEntry(NamedTuple):
    type: str
    startdate: datetime
    enddate: datetime
    force: bool
    path: str

ScheduleType = Dict[str, List[ScheduleEntry]]

def arguments() -> Namespace:
    """Setup and Return command line arguments
    See https://docs.python.org/3/howto/argparse.html

    Returns:
        argparse.Namespace: Namespace object
    """
    description = 'Automate scheduling of pre-roll intros for Plex'
    version = '0.10.1'

    config_default = './config.ini'
    log_config_default = './logging.conf'
    schedule_default = './preroll_schedules.yaml'
    parser = ArgumentParser(description='{}'.format(description))
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {}'.format(version), 
                        help='show the version number and exit'
                        )
    parser.add_argument('-lc', '--logconfig-file', 
                        dest='log_config_file', action='store',
                        default=log_config_default,  
                        help='Path to logging config file. [Default: {}]' \
                                .format(log_config_default)
                        )
    parser.add_argument('-t', '--test-run', 
                        dest='do_test_run', action='store_true',
                        default=False,
                        help='Perform a test run, display output but dont save'
                        )
    parser.add_argument('-c', '--config-file', 
                        dest='config_file', action='store', 
                        help='Path to Config.ini to use for Plex Server info. [Default: {}]' \
                                .format(config_default)
                        )
    parser.add_argument('-s', '--schedule-file', 
                        dest='schedule_file', action='store', 
                        help='Path to pre-roll schedule file (YAML) to be use. [Default: {}]' \
                                .format(schedule_default)
                        )
    args = parser.parse_args()

    return args

def schedule_types() -> ScheduleType:
    """Return the main types of schedules to be used for storage processing

    Returns:
        ScheduleType: Dict of main schema items
    """
    schema : ScheduleType = {
                'default': [],
                'monthly': [],
                'weekly': [],
                'date_range': [],
                'misc': []
            }
    return schema

def week_range(year:int, weeknum:int) -> Tuple[datetime, datetime]:
    """Return the starting/ending date range of a given year/week

    Args:
        year (int):     Year to calc range for
        weeknum (int):  Month of the year (1-12)

    Returns:
        DateTime: Start date of the Year/Month
        DateTime: End date of the Year/Month
    """
    start = datetime.strptime('{}-W{}-0'.format(year, int(weeknum)-1), 
                                        "%Y-W%W-%w").date()
    end = start + timedelta(days=6)

    start = datetime.combine(start, datetime.min.time())
    end = datetime.combine(end, datetime.max.time())

    return (start, end)

def month_range(year:int, monthnum:int) -> Tuple[datetime, datetime]:
    """Return the starting/ending date range of a given year/month

    Args:
        year (int):     Year to calc range for
        monthnum (int): Month of the year (1-12)

    Returns:
        DateTime: Start date of the Year/Month
        DateTime: End date of the Year/Month
    """
    start = date(year, monthnum, 1)
    next_month = start.replace(day=28) + timedelta(days=4)
    end = next_month - timedelta(days=next_month.day)

    start = datetime.combine(start, datetime.min.time())
    end = datetime.combine(end, datetime.max.time())

    return (start, end)

def duration_seconds(start:Union[date,datetime], end:Union[date,datetime]) -> float:
    """Return length of time between two date/datetime in seconds

    Args:
        start (date/datetime): [description]
        end (date/datetime): [description]

    Returns:
        float: Length in time seconds
    """
    if not isinstance(start, datetime):
        start = datetime.combine(start, datetime.min.time())
    if not isinstance(end, datetime):
        end = datetime.combine(end, datetime.max.time())

    delta = end - start
    
    logger.debug('duration_second[] Start: {} End: {} Duration: {}'.format(start, 
                                                                        end, 
                                                                        delta.total_seconds()
                                                                    ))
    return delta.total_seconds()

def make_datetime(value: Union[str, date, datetime], lowtime: bool=True) -> datetime:
    """Returns a DateTime object with a calculated Time component if none provided
      converts: 
      * Date to DateTime, with a Time of Midnight 00:00 or 11:59 pm
      * String to DateTime, with a Time as defined in the string

    Args:
        value (Union[str, date, datetime]): Input value to convert to a DateTime object
        lowtime (bool, optional): Calculate time to be midnight (True) or 11:59 PM (False). 
                                    Defaults to True.

    Raises:
        TypeError: Unknown type to calculate

    Returns:
        datetime: DateTime object with time component set if none provided
    """
    today = date.today()
    now = datetime.now()
    dt_val = datetime(today.year, today.month, today.day, 0,0,0)

    # append the low or high time of the day
    if lowtime:
        time = datetime.min.time()
    else:
        time = datetime.max.time()

    # determine how to translate the input value
    if isinstance(value, datetime):
        dt_val = value
    elif isinstance(value, date):
        dt_val = datetime.combine(value, time)
    elif isinstance(value, str):
        try:
            # Expect format of DateType string to be (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
            # allow 'xx' to denote 'every' similar to Cron "*"
            msg = 'Translating string value="{}" to datetime (LowTime={})'.format(value, 
                                                                                lowtime)
            logger.debug(msg)

            # default to today and the time period (low/high)
            year, month, day = today.year, today.month, today.day
            hour, minute, second = time.hour, time.minute, time.second

            # start parsing the Time out, for later additional processing
            dateparts = value.lower().split('-')

            year = today.year if dateparts[0] == 'xxxx' else int(dateparts[0])
            month = today.month if dateparts[1] == 'xx' else int(dateparts[1]) 

            dateparts_day = dateparts[2].split(' ')

            day = today.day if dateparts_day[0] == 'xx' else int(dateparts_day[0]) 

            # attempt to parse out Time components
            if len(dateparts_day) > 1:
                timeparts = dateparts_day[1].split(':')
                if len(timeparts) > 1:
                    hour = now.hour if timeparts[0] == 'xx' else int(timeparts[0]) 
                    minute = now.minute if timeparts[1] == 'xx' else int(timeparts[1]) 
                    second = now.second + 1 if timeparts[2] == 'xx' else int(timeparts[2]) 

            dt_val = datetime(year, month, day, hour, minute, second)
            logger.debug('Datetime-> "{}"'.format(dt_val))
        except Exception as e:
            msg = 'Unable to parse date string "{}"'.format(value)
            logger.error(msg, exc_info=e)
            raise
    else:
        msg = 'UnknownType: Unable to parse date string "{}" for type "{}"'.format(value, 
                                                                                type(value)
                                                                            )
        logger.error(msg)
        raise TypeError(msg)

    return dt_val

def preroll_schedule(schedule_file: Optional[str]=None) -> List[ScheduleEntry]:
    """Return a listing of defined preroll schedules for searching/use

    Args:
        schedule_file (str): path/to/schedule_preroll.yaml style config file (YAML Format)

    Raises:
        FileNotFoundError: If no schedule config file exists

    Returns:
        list: list of ScheduleEntries
    """
    default_files = ['preroll_schedules.yaml', 'preroll_schedules.yml']

    filename = None
    if schedule_file != '' and schedule_file != None:
        if os.path.exists(str(schedule_file)):
            filename = schedule_file
        else:
            msg = 'Pre-roll Schedule file "{}" not found'.format(schedule_file)
            raise FileNotFoundError(msg)
    else:
        for f in default_files:
            if os.path.exists(f):
                filename = f
                break
    
    # if we still cant find a schedule file, we abort
    if not filename:
        msg = 'Missing schedule file: "{}"'.format('" / "'.join(default_files))
        logger.critical(msg)
        raise FileNotFoundError(msg)

    with open(filename, 'r') as file:
        contents = yaml.load(file, Loader=yaml.SafeLoader)

    today = date.today()
    schedule : List[ScheduleEntry] = []
    for schedule_section in schedule_types():
        if schedule_section == 'weekly':
            try:
                use = contents[schedule_section]['enabled']

                if use:
                    for i in range(1,53):
                        try:
                            path = contents[schedule_section][i]

                            if path:
                                start, end = week_range(today.year, i)
  
                                entry = ScheduleEntry(type=schedule_section,
                                                    force=False,
                                                    startdate=start,
                                                    enddate=end,
                                                    path=path)

                                schedule.append(entry)
                        except KeyError as ke:
                            # skip KeyError for missing Weeks
                            msg = 'Key Value not found: "{}"->"{}", skipping week'.format(schedule_section, 
                                                                                        i)
                            logger.debug(msg)
                            pass
            except KeyError as ke:
                msg = 'Key Value not found in "{}" section'.format(schedule_section)
                logger.error(msg, exc_info=ke)
                raise
        elif schedule_section == 'monthly':
            try:
                use = contents[schedule_section]['enabled']

                if use:
                    for i in range(1,13):
                        month_abrev = date(today.year, i, 1).strftime('%b').lower()
                        try:
                            path = contents[schedule_section][month_abrev]    

                            if path:
                                start, end = month_range(today.year, i)

                                entry = ScheduleEntry(type=schedule_section,
                                                    force=False,
                                                    startdate=start,
                                                    enddate=end,
                                                    path=path)

                                schedule.append(entry)
                        except KeyError as ke:
                            # skip KeyError for missing Months
                            msg = 'Key Value not found: "{}"->"{}", skipping month'.format(schedule_section, 
                                                                                            month_abrev)
                            logger.warning(msg)
                            pass
            except KeyError as ke:
                msg = 'Key Value not found in "{}" section'.format(schedule_section)
                logger.error(msg, exc_info=ke)
                raise
        elif schedule_section == 'date_range':
            try:
                use = contents[schedule_section]['enabled']
                if use: 
                    for r in contents[schedule_section]['ranges']:
                        try:
                            path = r['path']

                            if path:
                                try:
                                    force = r['force']
                                except KeyError as ke:
                                    # special case Optional, ignore
                                    force = False
                                    pass
                                
                                start = make_datetime(r['start_date'], lowtime=True)
                                end = make_datetime(r['end_date'], lowtime=False)

                                entry = ScheduleEntry(type=schedule_section,
                                                    force=force,
                                                    startdate=start,
                                                    enddate=end,
                                                    path=path)

                                schedule.append(entry)
                        except KeyError as ke:
                            msg = 'Key Value not found for entry: "{}"'.format(entry)
                            logger.error(msg, exc_info=ke)
                            raise
            except KeyError as ke:
                msg = 'Key Value not found in "{}" section'.format(schedule_section)
                logger.error(msg, exc_info=ke)
                raise
        elif schedule_section == 'misc':
            try:
                use = contents[schedule_section]['enabled']
                if use:
                    try:
                        path = contents[schedule_section]['always_use']

                        if path:
                            entry = ScheduleEntry(type=schedule_section,
                                            force=False,
                                            startdate=datetime(today.year, today.month, today.day,
                                                                0, 0, 0),
                                            enddate=datetime(today.year, today.month, today.day,
                                                                23,59,59),
                                            path=path)

                            schedule.append(entry)
                    except KeyError as ke:
                        msg = 'Key Value not found for entry: "{}"'.format(entry)
                        logger.error(msg, exc_info=ke)
                        raise
            except KeyError as ke:
                msg = 'Key Value not found in "{}" section'.format(schedule_section)
                logger.error(msg, exc_info=ke)
                raise
        elif schedule_section == 'default':
            try:
                use = contents[schedule_section]['enabled']
                if use:
                    try:
                        path = contents[schedule_section]['path']

                        if path:
                            entry = ScheduleEntry(type=schedule_section,
                                            force=False,
                                            startdate=datetime(today.year, today.month, today.day,
                                                             0, 0, 0),
                                            enddate=datetime(today.year, today.month, today.day,
                                                            23,59,59),
                                            path=path)

                            schedule.append(entry)
                    except KeyError as ke:
                        msg = 'Key Value not found for entry: "{}"'.format(entry)
                        logger.error(msg, exc_info=ke)
                        raise
            except KeyError as ke:
                msg = 'Key Value not found in "{}" section'.format(schedule_section)
                logger.error(msg, exc_info=ke)
                raise
        else:
            msg = 'Unknown schedule_section "{}" detected'.format(schedule_section)
            logger.error(msg)
            raise ValueError(msg) 

    # Sort list so most recent Ranges appear first
    schedule.sort(reverse=True, key=lambda x:x.startdate)

    return schedule

def build_listing_string(items: List[str], play_all: bool=False) -> str:
    """Build the Plex formatted string of preroll paths

    Args:
        items (list):               List of preroll video paths to place into a string listing
        play_all (bool, optional):  Play all videos. [Default: False (Random choice)]

    Returns:
        string: CSV Listing (, or ;) based on play_all param of preroll video paths
    """
    if play_all:
        # use , to play all entries
        listing = ','.join(items)
    else:
        #use ; to play random selection
        listing = ';'.join(items)

    return listing

def preroll_listing(schedule: List[ScheduleEntry], for_datetime: Optional[datetime]=None) -> str:
    """Return listing of preroll videos to be used by Plex

    Args:
        schedule (List[ScheduleEntry]):     List of schedule entries (See: getPrerollSchedule)
        for_datetime (datetime, optional):  Date to process pre-roll string for [Default: Today]
                                            Useful for simulating what different dates produce

    Returns:
        string: listing of preroll video paths to be used for Extras. CSV style: (;|,)
    """
    listing = ''
    entries = schedule_types()

    # determine which date to build the listing for
    if for_datetime:
        if isinstance(for_datetime, datetime):
            check_datetime = for_datetime 
        else:
            check_datetime = datetime.combine(for_datetime, datetime.now().time())
    else:
        check_datetime = datetime.now()
    
    # process the schedule for the given date
    for entry in schedule:
        try:
            entry_start = entry.startdate
            entry_end = entry.enddate
            if not isinstance(entry_start, datetime):
                entry_start = datetime.combine(entry_start, datetime.min.time())
            if not isinstance(entry_end, datetime):
                entry_end = datetime.combine(entry_end, datetime.max.time())

            msg = 'checking "{}" against: "{}" - "{}"'.format(check_datetime, 
                                                            entry_start, 
                                                            entry_end)
            logger.debug(msg)

            if entry_start <= check_datetime <= entry_end:
                entry_type = entry.type
                entry_path = entry.path
                entry_force = False
                try:
                    entry_force = entry.force
                except KeyError as ke:
                    # special case Optional, ignore
                    pass 

                msg = 'Check PASS: Using "{}" - "{}"'.format(entry_start, entry_end)
                logger.debug(msg)

                if entry_path:
                    found = False
                    # check new schedule item against exist list
                    for e in entries[entry_type]:
                        duration_new = duration_seconds(entry_start, entry_end) 
                        duration_curr = duration_seconds(e.startdate, e.enddate)
                        
                        # only the narrowest timeframe should stay
                        # disregard if a force entry is there
                        if duration_new < duration_curr and e.force != True:
                            entries[entry_type].remove(e)

                        found = True
                        
                    # prep for use if New, or is a force Usage
                    if not found or entry_force == True:
                        entries[entry_type].append(entry)
        except KeyError as ke:
            msg = 'KeyError with entry "{}"'.format(entry)
            logger.error(msg, exc_info=ke)
            raise

    # Build the merged output based or order of Priority
    merged_list = []
    if entries['misc']:
        merged_list.extend([p.path for p in entries['misc']])
    if entries['date_range']:
        merged_list.extend([p.path for p in entries['date_range']])
    if entries['weekly'] and not entries['date_range']:
        merged_list.extend([p.path for p in entries['weekly']])
    if entries['monthly'] \
        and not entries['weekly'] and not entries['date_range']:
        merged_list.extend([p.path for p in entries['monthly']])
    if entries['default'] \
        and not entries['monthly'] and not entries['weekly'] and not entries['date_range']:
        merged_list.extend([p.path for p in entries['default']])

    listing = build_listing_string(merged_list)

    return listing

def save_preroll_listing(plex: PlexServer, preroll_listing: Union[str, List[str]]) -> None:
    """Save Plex Preroll info to PlexServer settings

    Args:
        plex (PlexServer): Plex server to update
        preroll_listing (str, list[str]): csv listing or List of preroll paths to save
    """
    # if happend to send in an Iterable List, merge to a string
    if type(preroll_listing) is list:
        preroll_listing = build_listing_string(list(preroll_listing))

    msg = 'Attempting save of pre-rolls: "{}"'.format(preroll_listing)
    logger.debug(msg)

    plex.settings.get('cinemaTrailersPrerollID').set(preroll_listing)    
    plex.settings.save()

    msg = 'Saved Pre-Rolls: Server: "{}" Pre-Rolls: "{}"'.format(plex.friendlyName, 
                                                                preroll_listing)
    logger.info(msg)

if __name__ == '__main__':
    args = arguments()

    plexutil.init_logger(args.log_config_file)

    cfg = plexutil.plex_config(args.config_file)

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
        msg = 'Error connecting to Plex'
        logger.error(msg, exc_info=e)
        raise e

    schedule = preroll_schedule(args.schedule_file)
    prerolls = preroll_listing(schedule)
    
    if args.do_test_run:
        msg = 'Test Run of Plex Pre-Rolls: **Nothing being saved**\n{}\n'.format(prerolls)
        logger.debug(msg)
        print(msg)
    else:
        save_preroll_listing(plex, prerolls)
