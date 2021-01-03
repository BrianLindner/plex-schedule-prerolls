# Schedule Plex server related Pre-roll intro videos

A helper script to automate management of Plex pre-rolls. \
Define when you want different pre-rolls to play throughout the year.

Ideas include:

- Holiday pre-roll rotations
- Special occasions
- Summer/Winter/Seasonal rotations
- Breaking up the monotony
- Keeping your family on their toes!

Simple steps:

> 1. Config the schedule
> 2. Schedule script on server
> 3. ...
> 4. Profit!

See [Installation & Setup](#install) section

---

## Schedule Rules

Schedule priority for a given Date:

1. **misc**
    - always_use - always includes in listing (append)

2. **date_range** \
Include listing for the specified Start/End date range that include the given Date \
Multipe ranges may apply at same time (append) \
**overrides usage of *week/month/default* listings

3. **weekly** \
Include listing for the specified WEEK of the year for the given Date \
  **override usage of *month/default* listings

4. **monthly** \
Include listing for the specified MONTH of the year for the given Date \
**overrides usage of *week/month/default* listings

5. **default** \
Default listing used of none of above apply to the given Date

---

## Installation & Setup <a id="install"></a>

Grab a copy of the code

```sh
cd /path/to/your/location
git clone https://github.com/BrianLindner/plex-schedule-prerolls.git
```

### Install Requirements <a id="requirements"></a>

Requires:

- Python 3.8+  [may work on 3.5+ but not tested]

See `requirements.txt` for Python modules used [link](requirements.txt)

Install Python requirements

```sh
pip install -r requirements.txt
```

### Create `config.ini` file with Plex connection information

Script checks for:

- local ./config.ini (See: [Sample](config.ini.sample))
- PlexAPI global config.ini
- Custom location config.ini (see [Arguments](#arguments))

(See: [plexapi.CONFIG](https://python-plexapi.readthedocs.io/en/latest/configuration.html) for more info)

Rename `config.ini.sample` -> `config.ini` and update to your environment

Example `config.ini`

```ini
[auth]
server_baseurl = http://127.0.0.1:32400 # your plex server url
server_token = <PLEX_TOKEN> # access token
```

### Create `preroll_schedules.yaml` file with desired schedule

Rename `preroll_schedules.yaml.sample` -> `preroll_schedules.yaml` and update for your environment

Example YAML config layout (See: [Sample](preroll_schedules.yaml.sample) for more info)

```yaml
---
monthly:
  enabled: (yes/no)
  jan: /path/to/file.mp4;/path/to/file.mp4
  ...
  dec: /path/to/file.mp4;/path/to/file.mp4
date_range:
  enabled: (yes/no)
  ranges:
    - start_date: 2020-01-01 12:01:00
      end_date: 2020-01-01 16:59:59
      path: /path/to/video.mp4
    - start_date: 2020-07-03
      end_date: 2020-07-05
      path: /path/to/video.mp4
    - start_date: 2020-12-19
      end_date: 2020-12-26
      path: /path/to/video.mp4
weekly:
  enabled: (yes/no)
  1: /path/to/file(s)
  ...
  52: /path/to/file(s)
misc:
  enabled: (yes/no)
  always_use: /path/to/file(s)
default:
  enabled: (yes/no)
  path: /path/to/file.mp4;/path/to/file.mp4
```

#### Date Range Section:
Use it for *Day* or *Ranges of Time* needs; \
Now with Time support!

Formatting Supported:

- Dates: yyyy-mm-dd
- DateTime: yyyy-mm-dd hh:mm:ss  (24hr time format)

### (Optional) Config `logger.conf` to your needs

See: [https://docs.python.org/3/howto/logging.html](https://docs.python.org/3/howto/logging.html)

---

## Usage <a id="usage"></a>

### Default Usage

```sh
python schedule_preroll.py
```

### Runtime Arguments <a id="arguments"></a>

- -v : version information
- -h : help information
- -c : config.ini (local or PlexAPI system central) for Connection Info (see [config.ini.sample](config.ini.sample))
- -s : preroll_schedules.yaml for various scheduling information (see [spreroll_schedules.yaml.sample](preroll_schedules.yaml.sample))
- -l : location of custom logger.conf config file \
See:
  - Sample [logger config](logging.conf)
  - Logger usage [Examples](https://github.com/amilstead/python-logging-examples/blob/master/configuration/fileConfig/config.ini)
  - Logging [Info](https://www.internalpointers.com/post/logging-python-sub-modules-and-configuration-files)

```sh
python schedule_preroll.py -h

usage: schedule_preroll.py [-h] [-v] [-l LOG_CONFIG_FILE] [-c CONFIG_FILE] [-s SCHEDULE_FILE]

Automate scheduling of pre-roll intros for Plex

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show the version number and exit
  -l LOG_CONFIG_FILE, --logconfig-path LOG_CONFIG_FILE
                        Path to logging config file. [Default: ./logging.conf]
  -c CONFIG_FILE, --config-path CONFIG_FILE
                        Path to Config.ini to use for Plex Server info. [Default: ./config.ini]
  -s SCHEDULE_FILE, --schedule-path SCHEDULE_FILE
                        Path to pre-roll schedule file (YAML) to be use. [Default: ./preroll_schedules.yaml]
```

### Runtime Arguments Example

```sh
python schedule_preroll.py \
    -c path/to/custom/config.ini \
    -s path/to/custom/preroll_schedules.yaml \
    -l path/to/custom/logger.conf
```

---

## Scheduling (Optional)

Add to system scheduler:

Linux:

```sh
crontab -e
```

Place desired schedule (example below for everyday at midnight)

```sh
0 0 * * * python /path/to/schedule_preroll.py >/dev/null 2>&1
```

or \
(Optional) Wrap in a shell script: \
useful if running other scripts/commands, using venv encapsulation, customizing arguments

```sh
0 0 * * * /path/to/schedule_preroll.sh >/dev/null 2>&1
```

---

## Wrapping Up

> Sit back and enjoy the Intros!

---

## Shout out to places to get Pre-Roll

[https://prerolls.video](https://prerolls.video)
