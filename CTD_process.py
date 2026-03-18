# Load mooring CTD data and process. Code produced by Kurtis Anstey, Shannon Nudds, Annie Howard, and Carmen Holmes-Smith
### = Sections that require input from the user

# %%Section 1: Imports
# region
import xarray as xr
import gsw
import ctd
from numpy.ma.core import shape
from scipy import stats
import pandas as pd
import datetime as dt
import matplotlib
from scipy.ndimage import median_filter

matplotlib.use('Qt5Agg')  # Or 'Qt5Agg', 'WebAgg' for interactive plots
import matplotlib.pyplot as plt
import numpy as np
import isodate

plt.ion()  # turn on interactive mode at the very start of your script
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 14

# Function to append processing to comment attribute in the final NetCDF
processing_notes = []


def update_comment(ds, message: str):
    # append to the global 'comment' attribute, creating it if needed
    prev = str(ds.attrs.get("comment", "")).strip()
    ds.attrs["comment"] = message if not prev else f"{prev}; {message}"


def note(msg: str):
    processing_notes.append(msg)


# Function to convert time ordinal to datetime
def OrdinalToDatetime(ordinal):
    plaindate = dt.date.fromordinal(int(ordinal))
    date_time = dt.datetime.combine(plaindate, dt.datetime.min.time())
    return date_time + dt.timedelta(days=ordinal - int(ordinal))


# endregion

# %%Section 2: Metadata
###
creator_name = "Clark Richards"
creator_email = "Clark.Richards@dfo-mpo.gc.ca"

directory = f'./Barrow_RawData/'  # directory of raw data file, change to: f'./'
filename = 'M2170_SN22954.cnv'

# Mission info
year_n = 2022  # year of DEPLOYMENT
chief_scientist = "Clark Richards"  # chief scientist
cruise_number = 'RAD2022375'  # cruise number (eg. RAD2022375)
deployment_name = "CCGS PIERRE RADISSON"  # deployment refers to the vessel
sdn_deployment_id = "SDN:C17::18RD"  # SDN-C17 vocabulary #18RD = RADISSON; 18GO = Des Gros
site = 'BS-SOUTH-CENTRAL'  # mooring site (eg. BS-SOUTH, BS-SOUTH-CENTRAL, etc.)

# mooring (aka platform) details
mooring = 'M2170'  # mooring number; set to '' for single mooring sites, or '-1' etc. for multiple mooring sites, e.g. QN2024-2
mooring_number = mooring[1:]  # !
latdeg = 74
latdec = 11.874  # latitude in degrees and decimal minutes
londeg = 90
londec = 49.038  # longitude in degrees and decimal minutes
platform = "mooring"  # !                   #
sdn_platform_id = "SDN:L06::48, SDN:L06::43"  # !   # SDN-L06 vocabulary #EX. 48 = mooring, 43 = subsurface mooring

# subsite = mooring                                 # no subsite for Barrow Strait [FROM KURTIS: set to '' for single mooring sites, or '-1' etc. for multiple mooring sites, e.g. QN2024-2]
corr_water_depth = 259  # in metres, computed from sounding
pres = ''  # '_34m' if one of multiple instruments on line mooring
# offbottom_depth = " "                             # computed later

# instrument (aka device) details
data_type = "moored CTD"  # !                     # data type (for netcdf, eg. moored CTD)
instrument_type = "MCTD"  # !                     # short form (eg. MCTD)
inst_type = "Microcat"  # !                     # instrument type (for netcdf, eg. Microcat)
instrument_model = "SBE37-SM"  # instrument model, eg. SBE37-SM, SBE37-SMP, SBE37-SMP-ODO, RBR Solo, RBR Concerto
serial = 'SN22954'  # instrument serial number (if included in filename)
serial_number = serial[2:]  # !

# program and project info
project = "Barrow Strait Monitoring and Real Time Observatory Project"
program = "Maritimes Region Barrow Strait Monitoring Program"
location = "Barrow Strait"
country = "SDN:C32::CA, SDN:C18::18"  # !                       # SDN C32 vocabulary, CA = CANADA
country_code = "1810"  # !                       # 1810 = CANADA
cruise_name = "mooring deployment"  # !              # generic descriptor for the cruise

# processing notes
processing = "Data trimmed for in water measurements, drift corrected and QC flags applied. Refer to comment section for details."

# region

year_1 = year_n + 1;
year_str = str(year_n);
year_2str = str(int(year_n) - 2000)  # year of DEPLOYMENT
dataset_id = f"{instrument_type}_{cruise_number}_{mooring_number}_{serial_number}_{year_n}"
lat = round((latdeg + latdec / 60), ndigits=6);
latstr = f'{latdeg} {latdec}'
lon = round((-(londeg + londec / 60)), ndigits=6);
lonstr = f'{-londeg} {londec}'

if instrument_model == "SBE37-SM" or instrument_model == "SBE37-SMP":
    sdn_instrument_id = "SDN:L22::TOOL1456"
    sdn_device_id = "SDN:L05::350, SDN:L05::130, SDN:L05::134, SDN:L05::WPS"
elif instrument_model == "SBE37-SMP-ODO" or instrument_model == "SBE37-SMP-DO":
    sdn_instrument_id = "SDN:L22::TOOL1456"
    sdn_device_id = "SDN:L05::350, SDN:L05::130, SDN:L05::134, SDN:L05::WPS, SDN:L05::351"
elif instrument_model == "RBR Solo":
    sdn_instrument_id = "SDN:L22::TOOL1872"
    sdn_device_id = "SDN:L05::134"
elif instrument_model == "RBR Duet":
    sdn_instrument_id = "SDN:L22::TOOL1873"
    sdn_device_id = "SDN:L05::134, SDN:L05::WPS"
elif instrument_model == "RBR Concerto":
    sdn_instrument_id = "SDN:L22::TOOL1874"
    sdn_device_id = "SDN:L05::350, SDN:L05::130, SDN:L05::134, SDN:L05::WPS"
else:
    # None of the known instruments — manual entry SDN-L05 vocabulary: https://vocab.seadatanet.org/search
    sdn_instrument_id = ""
    sdn_device_id = ""

# endregion

# %%Section 3: Load raw data
###
# region
cnv = filename.endswith(".cnv")
asc = filename.endswith(".asc")
is_rsk = filename.endswith(".rsk") #pyrsktools loaded as 'rsk', so flag is changed to is_rsk

data = None
raw_keys = []
available_vars = []

if cnv:
    # --- 3.1 Find first numeric line ---
    with open(f"{directory}{filename}", "r") as f:
        lines = f.readlines()

    data_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s and (s[0].isdigit() or s.startswith("-")):
            data_start = i
            break

    if data_start is None:
        raise ValueError("Could not detect start of numeric data block in the CNV file.")

    df = pd.read_csv(f"{directory}{filename}", skiprows=data_start, sep='\s+', header=None)
    # Verify alignment
    for i in range(2):
        print(lines[data_start + i].strip())
        print(df.iloc[i].tolist())
        print("---")
    # df = pd.read_fwf(f"{directory}{filename}", skiprows=data_start)

    colnames = []

    for line in lines:
        if line.startswith("# name"):
            raw = line.split("=")[1].split(":")[0].strip()
            colnames.append(raw)

    df.columns = colnames[:len(df.columns)]

    data = df
    raw_keys = df.columns.tolist()
elif asc:
    with open(f"{directory}{filename}", "r") as f:
        lines = f.readlines()

    data_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s and (s[0].isdigit() or s[0] == "-"):
            data_start = i
            break

    if data_start is None:
        raise ValueError("Could not detect start of numeric data in ASC file.")

    data = pd.read_csv(
        f"{directory}{filename}",
        skiprows=data_start,
        header=None,
        names=['temperature', 'conductivity', 'pressure', 'dates', 'times']
    )

    # Clean whitespace
    data['dates'] = data['dates'].astype(str).apply(lambda x: " ".join(x.split()))
    data['times'] = data['times'].astype(str).apply(lambda x: " ".join(x.split()))

    # Build datetime column
    data['datetime'] = pd.to_datetime(
        data['dates'] + " " + data['times'],
        format="%d %b %Y %H:%M:%S",
        errors='coerce'
    )

    raw_keys = ['temperature', 'conductivity', 'pressure', 'dates', 'times']
# -----------------------------
# 3.3 RSK FILES (using pyrsktools)
# -----------------------------
elif is_rsk:
    from pyrsktools import RSK
    rsk = RSK(f"{directory}{filename}")
    rsk.open()
    rsk.readdata()

    if rsk.data is None or len(rsk.data) == 0:
        raise RuntimeError("RSK file contains no data.")

    # df_raw is EXACTLY what came from the instrument
    df_raw = pd.DataFrame.from_records(rsk.data).copy()

    # df_proc is used for processing only
    df_proc = df_raw.copy()

    # Convert timestamp ONLY in df_proc
    if 'timestamp' in df_proc.columns:
        df_proc['timestamp'] = pd.to_datetime(df_proc['timestamp'], errors='coerce')
        df_proc['timestamp'] = df_proc['timestamp'].dt.to_pydatetime()
    else:
        raise RuntimeError("RSK file missing timestamp column")

    # Save raw keys from df_raw (not df_proc)
    data = df_proc          # used for Section 5 and processing
    raw_data = df_raw       # used for saving raw NetCDF
    raw_keys = df_raw.columns.tolist()

else:
    raise ValueError("Unsupported file type. Must be CNV, ASC, or RSK")

print("Raw keys detected:", raw_keys)

# end region
###
# %%Section 4: Save raw data as NetCDF
# region
raw_ds = xr.Dataset()

if cnv:
    for key in raw_keys:
        safe_key = key.replace("/", "_")
        raw_ds[safe_key] = (['obs'], data[key].values)
elif asc:
    for key in ['temperature', 'conductivity', 'pressure']:
        raw_ds[key] = (['time'], data[key].values)
    # Save date/time columns as strings if desired
    raw_ds['dates'] = (['time'], data['dates'].values)
    raw_ds['times'] = (['time'], data['times'].values)

elif is_rsk:
    # Get all field names from the structured array
    dtype_fields = set(rsk.data.dtype.names)

    for ch in rsk.channels:
        # Try all possible attribute names that might match dtype fields
        candidates = [
            ch.longName,
            ch.shortName,
            ch.label,
            getattr(ch, "_dbName", None),
            ch.longName.lower(),
            ch.shortName.lower(),
            ch.label.lower(),
        ]

        # Pick the first candidate that exists in the dtype
        field = next((c for c in candidates if c in dtype_fields), None)

        if field is None:
            print(f"⚠ Warning: No matching data field found for channel '{ch.longName}'")
            continue

        # Clean variable name for NetCDF
        varname = ch.longName.replace(" ", "_").replace("/", "_")

        # Add to dataset
        raw_ds[varname] = (['time'], rsk.data[field])

    # Add timestamp if present
    if 'timestamp' in dtype_fields:
        raw_ds['datetime'] = (
            ['time'],
            rsk.data['timestamp'].astype('datetime64[ns]')
        )


raw_ds.attrs['source_file'] = filename
raw_ds.attrs['description'] = 'Raw instrument data (no QC, no corrections)'
raw_ds.attrs['comment'] = 'Converted from CNV or ASC or RSK to NetCDF'

# ---- Output path ----
raw_output_path = ( f"{directory}" 
                    f"{filename.replace('.cnv', '_raw.nc').replace('.asc', '_raw.nc').replace('.rsk', '_raw.nc')}" )
# raw_nc_name = f"{directory}{filename}_RAW.nc"
# raw_ds.to_netcdf(raw_nc_name)
# print(f"Saved RAW NetCDF → {raw_nc_name}")
raw_ds.to_netcdf(raw_output_path)
print(f"Saved RAW NetCDF → {raw_output_path}")

# endregion
###
# %%Section 5: Extract variables
# region

data_ = data.copy()
# --- Convert RSK datetime64 to Python datetime for processing only ---
if is_rsk:
    data_ = data_.copy()  # ensure we don't modify the raw DataFrame
    data_['timestamp'] = pd.to_datetime(data_['timestamp'], errors='coerce')
    data_['timestamp'] = data_['timestamp'].dt.to_pydatetime()

do = None
# Standard variable mapping
var_map = {
    'tv290C': 't',  # Temperature
    'cond0S/m': 'c',  # Conductivity
    'prdM': 'p',  # Pressure
    'sbeopoxML/L': 'do',  # Oxygen mL/L
    'timeJV2': 'time',  # CNV Time
    'temperature': 't',  # ASC Temperature
    'conductivity': 'c',  # ASC Conductivity
    'pressure': 'p',  # ASC Pressure
    'dates': 'dates',  # ASC Dates
    'times': 'times',  # ASC Times
    'timestamp': 'time' # RSK Times
}

vars_dict = {}
available_vars = []


for raw_var, new_var in var_map.items():
    if raw_var in raw_keys:
        print(raw_var)
        #vars_dict[new_var] = data_[raw_var].to_numpy(dtype=object)
        vars_dict[new_var] = data_[raw_var].values
        available_vars.append(new_var)

# Core variables
t = vars_dict.get('t') if 't' in vars_dict else None
c = vars_dict.get('c') if 'c' in vars_dict else None
p = vars_dict.get('p') if 'p' in vars_dict else None
time = vars_dict.get('time')
do = vars_dict.get('do') if 'do' in vars_dict else None

# --- Convert RBR abs p to sea p, same way Seabird does ---
if is_rsk and p is not None:
    # Subtract standard atmospheric pressure: 10.1325 dbar
    p = p - 10.1325
    # Prevent negative values
    p[p < 0] = 0

# --- ASC time conversion ---
if asc and 'dates' in raw_keys and 'times' in raw_keys:
    time = np.array([
        dt.datetime.strptime(f"{date} {tm}", "%d %b %Y %H:%M:%S")
        for date, tm in zip(data_['dates'], data_['times'])
    ])
    # Convert to Julian days relative to Dec 31 previous year
    reference_date = dt.datetime(year_n - 1, 12, 31)
    time = np.array([
        (dt_obj - reference_date).days + (dt_obj - reference_date).seconds / 86400
        for dt_obj in time
    ])


print("Available variables:", available_vars)
print("t/c/p/time shapes:", [v.shape for v in [t, c, p, time] if v is not None])

print("Before drift: type(time[0]) =", type(time[0]))


# endregion
###
# %%Section 6: Check time data
# region
fig, ax0 = plt.subplots(1, 1, figsize=(12, 8))  # fig.tight_layout();
ax0.plot(range(0, len(time)), time, lw=1, color='k')  # change second time to timej
ax0.set_xlabel('Index');
ax0.set_ylabel('Time')
plt.title("Time Check!")
plt.show(block=True)

# endregion
##
# %%Section 7: Time Data Corrections (IF REQUIRED)
# region
# SHN \/\/\/ Do I need to run this section with all = False if there is no time correction required, or can I skip it altogether?
# Set all to 'False' if no correction necessary
#
no_time_data = False  # if time data does not exist or is entirely incorrect, and have initialisation time from data or metadata
format_time_data = False  # if time data in wrong format e.g. separate year, month, day, hour, min, sec values
time_trim = False  # if totally incorrect time data on either end of record (e.g. data present from previous deployment); time out-of-water can still be correct!
time_spike = False  # if bad time data somewhere in record
fix_irregular_data = False  # if cnv jd time data exists but incorrect, and need to manufacture NEW time data (NOTE: can typically just use 'no_time_data' case)
UTC_offset = False  # e.g. add 7 hours if obviously not synced to UTC upon deployment; must already be in datetime format
time_offset = False  # if need to add or remove regular time offset throughout record; must already be in datetime format

if no_time_data:
    #
    time0 = dt.datetime.strptime('2022-10-04 13:00:03.000000', '%Y-%m-%d %H:%M:%S.%f')  # initial time
    burstn = 10  # how many samples per burst
    sample_rate = dt.timedelta(seconds=1)  # time between samples
    burst_rate = dt.timedelta(minutes=1)  # time between bursts
    #

    timen = len(data[:, 0])  # length of time data
    time_data = np.zeros_like(data[:, 0], dtype=dt.datetime)  # empty array for time data
    burst_count = 0  # tracker for samples within burst
    for i in range(timen):
        if i == 0:  # first time datapoint
            time_data[i] = time0
            burst_count += 1
        else:  # subsequent datapoints
            if burst_count == 0:
                time_data[i] = time_data[i - burstn] + burst_rate  # add burst interval
                burst_count += 1
            elif burst_count > 0 and burst_count != (burstn - 1):
                time_data[i] = time_data[i - 1] + sample_rate  # add sample interval
                burst_count += 1
            elif burst_count > 0 and burst_count == (burstn - 1):
                time_data[i] = time_data[i - 1] + sample_rate  # add sample interval
                burst_count = 0  # reset burst tracker
    time = time_data.copy()
    print(f'Instrument started (not deployed): {time[0]}')
    print(f'Instrument stopped (not recovered): {time[-1]}')

if format_time_data:
    time0 = dt.datetime(int(data[0, 0]), int(data[0, 1]), int(data[0, 2]), int(data[0, 3]), int(data[0, 4]),
                        int(data[0, 5]))  # initial time
    timen = len(data[:, 0])  # length of time data
    time_data = np.zeros_like(data[:, 0], dtype=dt.datetime)  # empty array for time data
    for i in range(timen):
        time_data[i] = dt.datetime(int(data[i, 0]), int(data[i, 1]), int(data[i, 2]), int(data[i, 3]), int(data[i, 4]),
                                   int(data[i, 5]))  # format time at each step
    time = time_data.copy()
    print(f'Instrument started (not deployed): {time[0]}')
    print(f'Instrument stopped (not recovered): {time[-1]}')

if time_trim:
    time = time[3849:].copy()  # check time, p, t, c for proper trim indices
    print(f'Instrument started (not deployed): {time[0]}')
    print(f'Instrument stopped (not recovered): {time[-1]}')

if time_spike:
    trim_times = np.r_[35232:35235]  # indices of spike; use len(time) for end of record if necessary
    time[trim_times] = np.nan  # set bad time data to NaN
    time_temp = pd.Series(time);
    time_int = time_temp.interpolate(method="linear", limit=10,
                                     limit_direction='forward');  # interpolate over the time gap
    time = np.array(time_int)  # set interpolated data to original array
    print(f'Instrument started (not deployed): {time[0]}')
    print(f'Instrument stopped (not recovered): {time[-1]}')

if fix_irregular_data:  # can tyically use 'no_time_data' case

    use_rate = 'manual'  # init, final, or manual (from CNV) whichever is correct; typically use manual
    manual_sample_rate = 900  # if use_rate set to manual
    start_time_incorrect = False  # True if time0 incorrect
    # correct_start_time = dt.datetime.strptime('2022-10-04 13:00:03.000000', '%Y-%m-%d %H:%M:%S.%f') # use if start_time_incorrect is True
    correct_start_time = time[0]
    irreg_sampling = False  # True if periods of different sampling rates
    time0_idx = 0  # index of first real time stamp (sometimes this is incorrect at startup, time data does NOT have to be trimmed for out-of-water time)
    timez_idx = len(time) - 2  # for checking sample rates

    # determine sample interval at start of data
    tn = len(time[time0_idx:])  # length of time data
    init_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[time0_idx]  # initial timestamp
    time0 = OrdinalToDatetime(init_time)
    next_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[time0_idx + 1]  # consecutive timestamp
    time1 = OrdinalToDatetime(next_time)
    sample_init = time1 - time0  # time delta between samples
    sample_int_0_s = sample_init.seconds
    sample_int_0_ms = sample_init.microseconds
    sample_int_0 = sample_int_0_s + (sample_int_0_ms / 1e6)
    sample_int_0_rounded_s = int(round(sample_int_0, 0))
    print(f'Initial sample interval: {sample_int_0_rounded_s} s')

    late_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[timez_idx]  # initial timestamp (at end of data)
    time2 = OrdinalToDatetime(late_time)
    later_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[
        timez_idx + 1]  # consecutive timestamp (at end of data)
    time3 = OrdinalToDatetime(later_time)
    sample_final = time3 - time2  # time delta between samples
    sample_int_1_s = sample_final.seconds
    sample_int_1_ms = sample_final.microseconds
    sample_int_1 = sample_int_1_s + (sample_int_1_ms / 1e6)
    sample_int_1_rounded_s = int(round(sample_int_1, 0))
    print(f'Final sample interval: {sample_int_1_rounded_s} s')

    if use_rate == 'init':  # change 'use_rate' above, if necessary; typically use manual
        fix_rate = sample_int_0_rounded_s
    elif use_rate == 'final':
        fix_rate = sample_int_1_rounded_s
    elif use_rate == 'manual':
        fix_rate = manual_sample_rate  # seconds, set above

    if start_time_incorrect:
        time0 = correct_start_time

    if irreg_sampling:  # input indices for periods with variable sampling rates
        irreg_int_0 = np.r_[0:3763]
        irreg_int_1 = np.r_[3763:3780]
        irreg_int_2 = np.r_[3780:41962]
        fix_rate_0 = 30  # expected sample rate for incorrect periods
        fix_rate_1 = 900

        time_new = []
        for i in irreg_int_0:
            delta_i = int(i) * int(fix_rate_0)
            time_new_temp = time0 + dt.timedelta(seconds=delta_i)
            time_new.append(time_new_temp)
        for i in irreg_int_1:
            delta_i = int(i) * int(fix_rate_0)
            time_new_temp = time0 + dt.timedelta(seconds=delta_i)
            time_new.append(time_new_temp)
        for i in irreg_int_2:
            delta_i = int(i) * int(fix_rate_1)
            time_new_temp = time0 + dt.timedelta(seconds=delta_i)
            time_new.append(time_new_temp)

    elif not irreg_sampling:  # create new time data from initial time and sample rate
        time_new = []
        for i in range(tn):
            delta_i = int(i) * int(fix_rate)
            time_new_temp = time0 + dt.timedelta(seconds=delta_i)
            time_new.append(time_new_temp)

    time_new = np.asarray(time_new)
    print(f'New times begin: {time_new[0]}, end: {time_new[-1]}')

    time = time_new.copy()  # set new time data

if UTC_offset:
    time = time.copy() + dt.timedelta(hours=7)
    print(f'UTC adjusted instrument started (not deployed): {time[0]}')
    print(f'UTC adjusted instrument stopped (not recovered): {time[-1]}')

if time_offset:
    offset = dt.timedelta(days=-365)
    time = time.copy() + offset
    print(f'Offset adjusted instrument started (not deployed): {time[0]}')
    print(f'Offset adjusted instrument stopped (not recovered): {time[-1]}')

# endregion

# %%Section 8: Correct for clock drift
print("Detected time format:",
      "Julian Day → set cnv_jd_drift=True" if isinstance(time[0], (int, float, np.floating))
      else "datetime → set datetime_drift=True")
###
# *** if SLOWER/BEHIND than PC/true time, tot_drift is NEGATIVE; ***
# *** if FASTER/AHEAD, this value POSITIVE (PC/true time + tot_drift = instrument time)***

Drift_Recorded = True # Added separate case for when clock drift not recorded vs truly 0 -chs
tot_drift = -46  # total clock drift from recovery time check, seconds.
cnv_jd_drift = True  # True if .cnv file with Julian day time data, not corrected above
datetime_drift = False  # True if datetime time data, or if corrected above

import numpy as np
import datetime as dt  # ensure dt is the datetime module

# region

if cnv_jd_drift:
    jd = time  # timej                            # copy Julian day time data
    drift = (-tot_drift) / len(time)  # timej       # incremental clock drift in seconds (assuming linear)
    jd_drift = drift / 86400  # drift in JD
    offset = np.zeros_like(jd)  # empty array to track linearly increasing drift offsets
    jd_adjusted = np.zeros_like(jd)  # empty array for adjusted JD times
    for i in range(len(jd)):
        offset[i] = jd_drift * i
        jd_adjusted[i] = jd[i] + offset[i]
    print('Instrument clock drift = {} seconds'.format(tot_drift))
    print('Drift correction = {:.0f} seconds'.format(offset[-1] * 86400))
    dn_initial = dt.date.toordinal(dt.date(year_n - 1, 12,
                                           31)) + jd_adjusted  # convert JD to datenumber; last day of PREVIOUS YEAR as day '0', so Jan 1 is day '1'
    dn_dt = []  # empty list for datetime values
    for i in range(len(dn_initial)):
        dn_dt.append(OrdinalToDatetime(dn_initial[i]))
    dn_dt = np.asarray(dn_dt)  # convert list to numpy array
    print(f'Instrument started (not deployed): {dn_dt[0]}')
    print(f'Instrument stopped (drift corrected): {dn_dt[-1]}')
    dn_initial_raw = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + jd
    dn_dt_raw = np.asarray([OrdinalToDatetime(val) for val in dn_initial_raw])
    print(f'Instrument stopped (drift uncorrected): {dn_dt_raw[-1]}')
    sample_rate = round((dn_dt[100] - dn_dt[99]).seconds, ndigits=-1)  # check correct sample rate
    print(f'Sample rate: {sample_rate} s')

if datetime_drift:
    if isinstance(time[0], np.datetime64):
        time = time.astype('datetime64[us]').astype(object)

    time_adj = time.copy()  # array of Python datetime objects
    # incremental drift per sample
    drift = dt.timedelta(seconds=(-tot_drift) / len(time_adj))

    # build adjusted times using pure Python
    time_adjusted = [t + drift * i for i, t in enumerate(time_adj)]

    print(f'Instrument clock drift = {tot_drift} seconds')
    print(f'Drift correction = {(drift * (len(time_adj)-1)).seconds} seconds')

    dn_dt = np.array(time_adjusted, dtype=object)

    print(f'Instrument started (not deployed): {dn_dt[0]}')
    print(f'Instrument stopped (drift corrected): {dn_dt[-1]}')
    print(f'Instrument stopped (drift uncorrected): {time_adj[-1]}')

    sample_rate = (dn_dt[100] - dn_dt[99]).total_seconds()
    print(f"Sample rate: {sample_rate} s")

if not cnv_jd_drift and not datetime_drift:
    dn_dt = time.copy()

if Drift_Recorded:
    note(f"Clock drift setting tot_drift={tot_drift} s "
     f"via {'JD' if cnv_jd_drift else 'datetime' if datetime_drift else 'none'} method")
else:
    note(f"Clock drift not recorded, no correction made. ")

# endregion
###
# %% Section 9A: Plot raw data to identify time in water
# Examine the plot to identify indices to trim for in water
# region

# Setup Plotting Structure
available_vars = [var for var in available_vars if var != 'time']
# if 'p' not in available_vars:
#     available_vars.append('p')

var_labels = {
    't': 'Temp.',
    'c': 'Cond.',
    'do': 'Dissolved Oxygen',
    'p': 'Pressure'  # Ensure pressure is included
}
num_vars = len(available_vars)

# Plots to determine TRIM indices for instrument IN water; must check P, T, and C
fig, axes = plt.subplots(num_vars, 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

if num_vars == 1: # Added to deal with cases where theres only one variable
    axes = [axes]

for i, var_name in enumerate(available_vars):
    if var_name in var_labels:  # Ensure we only plot variables with labels
        axes[i].plot(eval(var_name), lw=1, color='k')  # Use eval to get the variable
        axes[i].set_ylabel(var_labels[var_name])
plt.show(block=True)

# endregion

# %% Section 9B: Input and check trim indices
###
start = 7501
finish = 112160 + 1  # last good point +1

# region

if "t_ut" not in globals():
    t_ut = t.copy() if t is not None else None
    c_ut = c.copy() if c is not None else None
    p_ut = p.copy() if p is not None else None
    do_ut = do.copy() if do is not None else None

raw_var_labels = {
    't_ut': 'Temperature',
    'c_ut': 'Conductivity',
    'p_ut': 'Pressure',
}
if do_ut is not None:
    raw_var_labels['do_ut'] = 'Dissolved Oxygen'

# Plot raw variables with trim lines to check:

# Build dict ONLY with variables that actually exist
raw_plot_vars = {}
if t_ut is not None: raw_plot_vars['t_ut'] = t_ut
if c_ut is not None: raw_plot_vars['c_ut'] = c_ut
if p_ut is not None: raw_plot_vars['p_ut'] = p_ut
if do_ut is not None: raw_plot_vars['do_ut'] = do_ut

fig, axes = plt.subplots(len(raw_plot_vars), 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

# Fix single-axis case
if len(raw_plot_vars) == 1:
    axes = [axes]

for i, (var_name, data_array) in enumerate(raw_plot_vars.items()):
    axes[i].plot(data_array, lw=1, color='gray')
    axes[i].axvline(start, color='g', linestyle='--', label='Start Trim')
    axes[i].axvline(finish - 1, color='r', linestyle='--', label='Finish Trim')
    axes[i].set_ylabel(raw_var_labels[var_name])
    if i == 0:
        axes[i].legend(loc='best')

plt.suptitle('Untrimmed Variables with Trim Indices')
plt.show(block=True)

# endregion
##
# %% SECTION 9C - Trim Data and Plot
# region

# --- (3) NOW TRIM ORIGINALS ---

# LEGACY CODE FROM KURTIS - IGNORE
# if not time_trim:
#     dt = dn_dt[start:finish]
# else:
#     dt = dn_dt[:(finish - start)].copy()

dt = dn_dt[start:finish]
if t is not None:
    t = t[start:finish]

if c is not None:
    c = c[start:finish]

if p is not None:
    p = p[start:finish]

if do is not None:
    do = do[start:finish]

# recalc salinity only if conductivity + pressure exist
if c is not None and p is not None:
    s = gsw.SP_from_C(10 * c, t, p)
else:
    s = None

##
# --- (4) PLOT TRIMMED DATA ---
dt_str = np.array([d.strftime('%Y-%m-%d %H:%M:%S.%f') for d in dt])
var_labels = {
    't': 'Temperature',
    'c': 'Conductivity',
    'p': 'Pressure',
    's': 'Salinity',
    'do': 'Dissolved Oxygen'
}

# Build plot_vars ONLY with variables that exist
plot_vars = {}
if t is not None: plot_vars['t'] = t
if c is not None: plot_vars['c'] = c
if p is not None: plot_vars['p'] = p
if s is not None: plot_vars['s'] = s
if do is not None: plot_vars['do'] = do

fig, axes = plt.subplots(len(plot_vars), 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

# Fix single-axis case
if len(plot_vars) == 1:
    axes = [axes]

for i, (var_name, data_array) in enumerate(plot_vars.items()):
    axes[i].plot(data_array, lw=1, color='k')
    axes[i].set_ylabel(var_labels[var_name])

plt.suptitle('Trimmed In-Place Variables')
plt.show(block=True)

note(f"Trimmed in-water indices: start={start}, finish={finish}")
# endregion
#
# %% !! (SKIP THIS) Section 10: Temperature Salinity Plot
##
# Only run if both s and t have data
if s is not None and t is not None and len(s) > 0 and len(t) > 0:

    # region
    fig_ts, ax_ts = plt.subplots(figsize=(8, 6))
    sc = ax_ts.scatter(
        s, t,
        c=np.arange(len(t)), cmap="viridis",
        edgecolor='k', alpha=0.7
    )
    ax_ts.set_xlabel('Salinity')
    ax_ts.set_ylabel('Temperature')
    ax_ts.set_title('T-S Diagram')
    cbar = plt.colorbar(sc, label='Index')

    ts_plot_path = f'{directory}{site}{year_str}{mooring}{pres}_{serial}_TS_plot.png'
    plt.savefig(ts_plot_path, dpi=300, bbox_inches='tight')
    plt.show(block=True)


# endregion
###
# %% Section 11: Temperature Salinity Plot, Interactive
# region
import plotly.express as px
import pandas as pd
import numpy as np

if s is not None and t is not None and len(s) > 0 and len(t) > 0:
    # Assuming s and t are your salinity and temperature arrays
    df = pd.DataFrame({
        'Salinity': s,
        'Temperature': t,
        'Index': np.arange(len(t))  # This is what you'll see on hover
    })

    # Create interactive scatter plot
    fig = px.scatter(
        df,
        x='Salinity',
        y='Temperature',
        color='Index',
        color_continuous_scale='viridis',
        title='T-S Diagram',
        hover_data={'Index': True}  # Show index on hover
    )

    fig.update_traces(marker=dict(size=6, line=dict(width=1, color='DarkSlateGrey')))

    # Show the plot
    fig.show()

# endregion

# %% Section 12: Manual Data Inspection with Spike Suggestions
###
detect_spikes_t = True  # Detect spikes in Temperature
detect_spikes_c = True  # Detect spikes in Conductivity
detect_spikes_do = False  # Optional: Detect in DO
detect_spikes_p = False  # Optional: Detect in Pressure

# region
Use_CHS_Func = True  # Uses Hampel detection to suggest outliers

# Spike detection parameters from original code
if sample_rate == 900:
    n1 = 2;
    n2 = 10;
    block = 200
else:
    n1 = 2;
    n2 = 20;
    block = 200

#
# NOTE: These plots are for manual review only.
# Spikes are algorithmically suggested, but no data is removed or altered.
# Use this as a guide to record spike locations in your lab notebook per WOCE QC flagging.

def detect_spikes(data, n1, n2, block):
    original = pd.Series(data)
    processed = ctd.processing.despike(original.copy(), n1=n1, n2=n2, block=block)
    return np.where(~np.isclose(original, processed, equal_nan=True))[0]


def hampel_indices(series, window_size=5, n=3):
    s = pd.Series(series).astype(float)
    k = 1.4826  # scale factor for Gaussian distribution
    rolling_median = s.rolling(window=2 * window_size + 1, center=True).median()
    diff = np.abs(s - rolling_median)
    mad = s.rolling(window=2 * window_size + 1, center=True) \
        .apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
    threshold = n * k * mad
    outliers = diff > threshold
    return np.where(outliers.fillna(False).values)[0]

def hampel_fast(x, window_size=5, n=3, floor_mad=1e-3):
    x = np.asarray(x, float)
    k = window_size
    L = 1.4826
    # true-ish rolling median
    med = median_filter(x, size=2*k+1, mode='reflect')
    # absolute deviation
    diff = np.abs(x - med)
    # true-ish rolling MAD
    mad = median_filter(diff, size=2*k+1, mode='reflect')
    # prevent collapse
    mad = np.maximum(mad, floor_mad)
    threshold = n * L * mad
    return np.where(diff > threshold)[0]

if Use_CHS_Func:
    if len(data) > 200000:
        window_size = 15
        n = 5
        floor_mad = 8e-3
        spike_indices_t = hampel_fast(t, window_size, n, floor_mad) if detect_spikes_t else []
        spike_indices_c = hampel_fast(c, window_size, n, floor_mad) if detect_spikes_c else []
        spike_indices_do = hampel_fast(do, window_size, n, floor_mad) if detect_spikes_do else []
        spike_indices_p = hampel_fast(p, window_size, n, floor_mad) if detect_spikes_p else []
    else:
        window_size = 50
        n = 8
        spike_indices_t = hampel_indices(t, window_size, n) if detect_spikes_t else []
        spike_indices_c = hampel_indices(c, window_size, n) if detect_spikes_c else []
        spike_indices_do = hampel_indices(do, window_size, n) if detect_spikes_t else []
        spike_indices_p = hampel_indices(p, window_size, n) if detect_spikes_c else []

else:
    # Run spike detection (as guidance only)
    spike_indices_t = detect_spikes(t, n1, n2, block) if detect_spikes_t else []
    spike_indices_c = detect_spikes(c, n1, n2, block) if detect_spikes_c else []
    spike_indices_do = detect_spikes(do, n1, n2, block) if detect_spikes_do else []
    spike_indices_p = detect_spikes(p, n1, n2, block) if detect_spikes_p else []
    print("Outliers in t (despike):", spike_indices_t[:20])
    print("Outliers in c (despike):", spike_indices_c[:20])

## 12B - plotting
# Plotting
var_labels = {
    't': 'Temperature',
    'c': 'Conductivity',
    'do': 'Dissolved Oxygen',
    'p': 'Pressure',
}

plot_vars = [var for var in ['t', 'c', 'do', 'p'] if eval(var) is not None]
spike_indices = {
    't': spike_indices_t,
    'c': spike_indices_c,
    'do': spike_indices_do,
    'p': spike_indices_p,
}

fig, axes = plt.subplots(len(plot_vars), 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

if len(plot_vars) == 1:
    axes = [axes]

for i, var in enumerate(plot_vars):
    data = eval(var)
    axes[i].plot(data, lw=1, color='k')

    idx = spike_indices[var]
    if len(idx) > 0:
        axes[i].scatter(idx, data[idx], color='red', zorder=5)

    axes[i].set_ylabel(var_labels[var])

plt.suptitle('Manual Data Inspection with Spike Suggestions')
plt.savefig(f'{directory}{site}{year_str}{mooring}{pres}_{serial}_ManualSpikeReview.png', dpi=300, bbox_inches='tight')
plt.show(block=True)

# endregion

# %% Section 13A: Apply WOCE CTD Flags to variables
# WOCE CTD Flag Definitions: 2 = Acceptable measurement (default), 3 = Questionable measurement, 4 = Bad measurement, 5 = Not reported (e.g. missing/NaN)

### CONTROL WHICH VARIABLES GET FLAGGED ###
flag_c = True  # True if conductivity should be flagged
flag_t = True  # True if temperature should be flagged
flag_do = False  # True if dissolved oxygen should be flagged
flag_s = True  # True if salinity should be flagged (inherited from T + C)
flag_p = True  # True if pressure should be flagged
flag_pt = True
flag_svel = True

Flag_From_Filter = False
# --- Temperature Flags ---
if flag_t:
    flag_t_array = np.full_like(t, 2, dtype=int)
    flagged_t_data = [
        # e.g., (1000, 3), (2000, 4)
        (837, 4),
    ]
    if flagged_t_data:
        t_indices, t_values = zip(*flagged_t_data)
        flag_t_array[np.array(t_indices, dtype=int)] = np.array(t_values, dtype=int)
    flag_t_array[np.isnan(t)] = 5

# --- Conductivity Flags ---
if flag_c:
    flag_c_array = np.full_like(c, 2, dtype=int)
    flagged_c_data = [
        (126, 4),
        (2251, 4),
        *[(i, 4) for i in range(15925, 15937)],
        (65435, 4),
        (68072, 4),
        (68073, 4),
        (80520, 4),
    ]
    if flagged_c_data:
        c_indices, c_values = zip(*flagged_c_data)
        flag_c_array[np.array(c_indices, dtype=int)] = np.array(c_values, dtype=int)
    flag_c_array[np.isnan(c)] = 5

# --- Pressure Flags ---
if flag_p:
    flag_p_array = np.full_like(p, 2, dtype=int)
    flagged_p_data = [
        # e.g., (2022, 3)
        (68072, 4),
        (68073, 4),
    ]
    if flagged_p_data:
        p_indices, p_values = zip(*flagged_p_data)
        flag_p_array[np.array(p_indices, dtype=int)] = np.array(p_values, dtype=int)
    flag_p_array[np.isnan(p)] = 5

# --- Dissolved Oxygen Flags (optional) ---
if flag_do and do is not None:
    flag_do_array = np.full_like(do, 2, dtype=int)
    flagged_do_data = [
        # e.g., (9000, 4)
    ]
    if flagged_do_data:
        do_indices, do_values = zip(*flagged_do_data)
        flag_do_array[np.array(do_indices, dtype=int)] = np.array(do_values, dtype=int)
    flag_do_array[np.isnan(do)] = 5

if Flag_From_Filter:
    note(f"Data flagged using Hampel filter (window={window_size}, n={n}, floor={floor_mad})")

    # --- Temperature spikes from filter ---
    if flag_t and spike_indices_t is not None and len(spike_indices_t) > 0:
        flag_t_array[np.array(spike_indices_t, dtype=int)] = 3

    # --- Conductivity spikes from filter ---
    if flag_c and spike_indices_c is not None and len(spike_indices_c) > 0:
        flag_c_array[np.array(spike_indices_c, dtype=int)] = 3

    # --- Pressure spikes (optional, if you compute them) ---
    if flag_p and spike_indices_p is not None and len(spike_indices_p) > 0:
        flag_p_array[np.array(spike_indices_p, dtype=int)] = 3

    # --- DO spikes (optional) ---
    if flag_do and do is not None and spike_indices_do is not None and len(spike_indices_do) > 0:
        flag_do_array[np.array(spike_indices_do, dtype=int)] = 3

# --- Salinity Flags (from T + C flags) ---
if flag_s:
    flag_s_array = np.full_like(s, 2, dtype=int)
    # Inherit the worst flag from temperature and conductivity
    if flag_t:
        flag_s_array = np.maximum(flag_s_array, flag_t_array)
    if flag_c:
        flag_s_array = np.maximum(flag_s_array, flag_c_array)
    # NaNs in salinity get flag 5
    flag_s_array[np.isnan(s)] = 5

##
# %% !! (SKIP THIS) Section 13B: PLOT QC FLAGS

# region

# SHN, new section for plots

# --- Plot QC Flags ---
flag_colors = {
    3: '#DAA520',
    4: '#B22222',
    5: '#A9A9A9',
}
flag_labels = {
    3: "Flag 3: Questionable",
    4: "Flag 4: Bad",
    5: "Flag 5: Not Reported",
}


def has_real_flags(flags, data):
    flagged = np.isin(flags, list(flag_colors.keys()))
    return np.any(flagged) and np.any(~np.isnan(data[flagged]))


flagged_vars = []

if flag_t and 'flag_t_array' in locals() and has_real_flags(flag_t_array, t):
    flagged_vars.append(('Temperature', t, flag_t_array))
if flag_c and 'flag_c_array' in locals() and has_real_flags(flag_c_array, c):
    flagged_vars.append(('Conductivity', c, flag_c_array))
if flag_s and 'flag_s_array' in locals() and has_real_flags(flag_s_array, s):
    flagged_vars.append(('Salinity', s, flag_s_array))
if flag_p and 'flag_p_array' in locals() and has_real_flags(flag_p_array, p):
    flagged_vars.append(('Pressure', p, flag_p_array))
if flag_do and 'flag_do_array' in locals() and has_real_flags(flag_do_array, do):
    flagged_vars.append(('Dissolved Oxygen', do, flag_do_array))

if not flagged_vars:
    print("No flagged values to plot.")
else:

    # SHN \/\/\/ edit for efficiency in plotting:
    # fig, axes = plt.subplots(len(flagged_vars), 1, figsize=(12, 3 * len(flagged_vars)), sharex=True)
    fig, axes = plt.subplots(len(flagged_vars), 1, figsize=(10, min(3 * len(flagged_vars), 12)), sharex=True)
    # fig.subplots_adjust(hspace=0.2)
    plt.tight_layout()

    if len(flagged_vars) == 1:
        axes = [axes]

    for i, (label, data_var, flags) in enumerate(flagged_vars):
        ax = axes[i]
        ax.plot(data_var, color='black', lw=1)
        ax.set_ylabel(label)

        for flag_value, color in flag_colors.items():
            idx = np.where(flags == flag_value)[0]
            if len(idx) > 0:
                ax.scatter(idx, data_var[idx], color=color, s=8)

    axes[-1].set_xlabel("Index")
    plt.suptitle("QC Flags Applied (WOCE Scheme)", fontsize=16)
    fig.subplots_adjust(top=0.9, bottom=0.15)

    fig.legend(
        flag_labels.values(),
        loc='lower center',
        bbox_to_anchor=(0.5, -0.05),
        ncol=len(flag_labels),
        fontsize=12
    )

# plt.show()
plt.savefig("qc_flags_plot.png", dpi=150)

note("WOCE QC flags created for all available variables")

# endregion
##
# %% Section 13C: PLOT QC FLAGS, with Plotly
# region

import plotly.graph_objects as go
import numpy as np

# Define flag colors and labels
flag_colors = {
    3: '#DAA520',
    4: '#B22222',
    5: '#A9A9A9',
}
flag_labels = {
    3: "Flag 3: Questionable",
    4: "Flag 4: Bad",
    5: "Flag 5: Not Reported",
}


def has_real_flags(flags, data):
    flagged = np.isin(flags, list(flag_colors.keys()))
    return np.any(flagged) and np.any(~np.isnan(data[flagged]))


# Collect flagged variables
flagged_vars = []
if flag_t and 'flag_t_array' in locals() and has_real_flags(flag_t_array, t):
    flagged_vars.append(('Temperature', t, flag_t_array))
if flag_c and 'flag_c_array' in locals() and has_real_flags(flag_c_array, c):
    flagged_vars.append(('Conductivity', c, flag_c_array))
if flag_s and 'flag_s_array' in locals() and has_real_flags(flag_s_array, s):
    flagged_vars.append(('Salinity', s, flag_s_array))
if flag_p and 'flag_p_array' in locals() and has_real_flags(flag_p_array, p):
    flagged_vars.append(('Pressure', p, flag_p_array))
if flag_do and 'flag_do_array' in locals() and has_real_flags(flag_do_array, do):
    flagged_vars.append(('Dissolved Oxygen', do, flag_do_array))

# Plot using Plotly
if not flagged_vars:
    print("No flagged values to plot.")
else:
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=len(flagged_vars), cols=1, shared_xaxes=True,
                        subplot_titles=[label for label, _, _ in flagged_vars],
                        vertical_spacing=0.05)

    for i, (label, data_var, flags) in enumerate(flagged_vars, start=1):
        fig.add_trace(go.Scatter(
            x=np.arange(len(data_var)),
            y=data_var,
            mode='lines',
            line=dict(color='black'),
            name=label,
            showlegend=False
        ), row=i, col=1)

        for flag_value, color in flag_colors.items():
            idx = np.where(flags == flag_value)[0]
            if len(idx) > 0:
                fig.add_trace(go.Scatter(
                    x=idx,
                    y=data_var[idx],
                    mode='markers',
                    marker=dict(color=color, size=6),
                    name=flag_labels[flag_value],
                    showlegend=(i == 1)  # Show legend only once
                ), row=i, col=1)

    fig.update_layout(
        height=300 * len(flagged_vars),
        title_text="QC Flags Applied (WOCE Scheme)",
        legend=dict(orientation="h", y=-0.1),
        margin=dict(t=50, b=50)
    )
    fig.update_xaxes(title_text="Index", row=len(flagged_vars), col=1)

    fig.show()

# endregion

# %% 13D: TS plot omitting flag 4 data from view
fig.write_html(f'{directory}{site}{year_str}{mooring}{pres}_{serial}_ManualSpikeReview.html')

# %% 13D: Interactive T-S Plot with WOCE QC flags (by Salinity Flag)
# region
###
import plotly.graph_objects as go

df = pd.DataFrame({
    'Salinity': s,
    'Temperature': t,
    'Index': np.arange(len(t)),
    'T_Flag': flag_t_array,
    'S_Flag': flag_s_array
})
df['QC_Flag'] = df['S_Flag']

flag_order = [2, 3, 4, 5]
flag_labels = {
    2: "Flag 2: Acceptable",
    3: "Flag 3: Questionable",
    4: "Flag 4: Bad",
    5: "Flag 5: Not Reported"
}
flag_colors = {
    2: 'black',
    3: '#DAA520',  # goldenrod / orange-ish
    4: '#B22222',  # firebrick / red
    5: '#A9A9A9'  # dark grey for missing
}

fig = go.Figure()

for flag in flag_order:
    mask = df['QC_Flag'] == flag
    if mask.any():
        sub = df[mask]
        fig.add_trace(go.Scatter(
            x=sub['Salinity'],
            y=sub['Temperature'],
            mode='markers',
            name=flag_labels[flag],
            marker=dict(size=8, color=flag_colors[flag],
                        line=dict(width=1, color='DarkSlateGrey')),
            # Pass Index, T_Flag, and S_Flag to hover
            customdata=np.stack((sub['Index'].values, sub['T_Flag'].values, sub['S_Flag'].values), axis=-1),
            hovertemplate=(
                "Index: %{customdata[0]}<br>"
                "T_Flag: %{customdata[1]}<br>"
                "S_Flag: %{customdata[2]}<br>"
                "Salinity: %{x:.4f}<br>"
                "Temp: %{y:.4f}<extra></extra>"
            )
        ))
    else:

        fig.add_trace(go.Scatter(
            x=[np.nan], y=[np.nan],
            mode='markers',
            name=flag_labels[flag],
            marker=dict(size=8, color=flag_colors[flag],
                        line=dict(width=1, color='DarkSlateGrey')),
            hoverinfo='skip', showlegend=True
        ))

fig.update_layout(
    title="Interactive TS Diagram with WOCE QC Flags (by Salinity Flag)",
    xaxis=dict(title="Salinity"),
    yaxis=dict(title="Temperature (°C)"),
    legend=dict(title="WOCE QC Flags", traceorder='normal'),
    margin=dict(l=70, r=20, t=70, b=70),
    height=600
)

fig.show()

# endregion
###
# %% Section 14: Conductivity Offset
# SHN \/\/\/ Consider removing plot and printing pre and post correction linear slope.

# region

if c is not None and len(c) > 0:
    cond_offset = False

    c0_offset = 1.0000  # multiplier at start of record
    c_offset = 1.0000  # multiplier at end of record

    c_offset_arr = np.linspace(c0_offset, c_offset, len(dt))
    print('---')
    print(f'Conductivity offset range: {c_offset_arr[0]:.4f} - {c_offset_arr[-1]:.4f}')
    print('---')
    print('Initial conductivity: {:.4f} mS/cm'.format(c[0]))
    print('Final conductivity: {:.4f} mS/cm'.format(c[-1]))

    if c0_offset == 1.0000 and c_offset == 1.0000:
        c_adj = c.copy()
        s_adj = s.copy()
        print('Corrected initial conductivity: {:.4f} mS/cm'.format(c_adj[0]))
        print('Corrected final conductivity: {:.4f} mS/cm'.format(c_adj[-1]))
        print('No correction made.')
    else:
        c_adj = c.copy() * c_offset_arr
        s_adj = gsw.SP_from_C(10 * c_adj, t.copy(), p)  # recalc salinity using mS/cm
        print('Initial corrected conductivity: {:.4f} mS/cm'.format(c_adj[0]))
        print('Final corrected conductivity: {:.4f} mS/cm'.format(c_adj[-1]))

    pre_slope = (c[-1] - c[0]) / len(c)
    post_slope = (c_adj[-1] - c_adj[0]) / len(c_adj)

    print('---')
    print(f"Pre-correction conductivity slope: {pre_slope:.6f} mS/cm per sample")
    print(f"Post-correction conductivity slope: {post_slope:.6f} mS/cm per sample")
    print('---')

    if cond_offset:
        note(f"Conductivity offset applied (c0_offset={c0_offset}, c_offset={c_offset})")
    else:
        note(f"No CTD profile data available for comparison. No conductivity offset applied.")

# endregion
###
# %% Section 15: Derive Quantities from Temperature and Salinity
# salinity is derived from T and C above for the T/S plots.
if s is not None and t is not None and len(s) > 0 and len(t) > 0:
    SA = gsw.SA_from_SP(s_adj, p, lon, lat)  # absolute salinity (g/kg) for gsw calculations
    pt = gsw.pt0_from_t(SA, t, p)  # potential temperature at p = 0 db
    svel = gsw.sound_speed_t_exact(SA, t, p)  # sound speed in seawater


###
# %%Section 16: Derive Flags for PT and SVEL from Component Variables
def combine_flags(*flag_arrays):
    """Return the highest (worst) flag value at each index."""
    stacked = np.vstack(flag_arrays)
    return np.nanmax(stacked, axis=0).astype(int)


if flag_pt:
    flag_pt_array = combine_flags(flag_t_array, flag_s_array, flag_p_array)

if flag_svel:
    flag_svel_array = combine_flags(flag_t_array, flag_s_array, flag_p_array)

# %%Section 17: Compute Pressure Mode to Calculate Instrument Depth Later
####
no_pressure_sensor = False  # True is no pressure sensor

if no_pressure_sensor:
    round_p = 10000  # constant pressure value if no pressure sensor
    p0 = round_p
    inst_depth = 100000
    note(f"Pressure not recorded by instrument, depth assumed from position on mooring and sounding depth recorded.")
else:
    mean_p = np.nanmean(p)
    p0 = np.nanmedian(p)
    round_p = np.asarray(p, dtype=int)
    round_p = stats.mode(round_p, keepdims=False)[0]
    inst_depth = float(-gsw.z_from_p(p0, lat))
##
# %%Section 18: Create objects for the NetCDF
import datetime as dtmod

def safe_minmax_qc(data, flags=None, good_flags=(1, 2)):
    """
    Compute min/max using only QC-approved values.
    If no flags are provided, use all non-NaN data.
    If no valid data remain, return (None, None).
    """
    if data is None:
        return None, None

    arr = np.array(data, dtype=float)

    # Apply QC mask if flags exist
    if flags is not None:
        flags = np.array(flags)
        mask = np.isin(flags, good_flags)
        arr = np.where(mask, arr, np.nan)
    # If everything is NaN after masking, return None
    if np.all(np.isnan(arr)):
        return None, None
    return float(np.nanmin(arr)), float(np.nanmax(arr))


# Temperature
if t is not None:
    t_min, t_max = safe_minmax_qc(t,
        flags=flag_t_array if (flag_t and 'flag_t_array' in locals() and has_real_flags(flag_t_array, t)) else None)

# Conductivity
if c is not None:
    c_min, c_max = safe_minmax_qc(c_adj,
        flags=flag_c_array if (flag_c and 'flag_c_array' in locals() and has_real_flags(flag_c_array, c)) else None)

# Pressure
if p is not None:
    p_min, p_max = safe_minmax_qc(p,
        flags=flag_p_array if (flag_p and 'flag_p_array' in locals() and has_real_flags(flag_p_array, p)) else None)

# Salinity
if s is not None:
    s_min, s_max = safe_minmax_qc(s_adj,
        flags=flag_s_array if (flag_s and 'flag_s_array' in locals() and has_real_flags(flag_s_array, s)) else None)

# Potential Temperature
if 'pt' in locals():
    pt_min, pt_max = safe_minmax_qc(pt,
        flags=flag_pt_array if (flag_pt and 'flag_pt_array' in locals() and has_real_flags(flag_pt_array, pt)) else None)

# Sound Speed
if 'svel' in locals():
    svel_min, svel_max = safe_minmax_qc(svel,
        flags=flag_svel_array if (flag_svel and 'flag_svel_array' in locals() and has_real_flags(flag_svel_array, svel)) else None)

# Dissolved Oxygen
if 'do' in locals():
    do_min, do_max = safe_minmax_qc(do,
        flags=flag_do_array if (flag_do and 'flag_do_array' in locals() and has_real_flags(flag_do_array, do)) else None)


offbottom_depth = corr_water_depth - inst_depth
time_coverage_resolution = isodate.duration_isoformat(dtmod.timedelta(seconds=sample_rate))

Mooring_Move = False

if Mooring_Move:
    index_shift = 68072 # first index impacted
    index_impact = 1

    p0 = np.nanmedian(p[:index_shift-1])
    inst_depth = float(-gsw.z_from_p(p0, lat))
    offbottom_depth = corr_water_depth - inst_depth
    p0_shift = np.nanmedian(p[index_shift+index_impact:])
    inst_depth_shift = float(-gsw.z_from_p(p0_shift, lat))

    date_of_shift = dt[index_shift]
    pretty_date = date_of_shift.strftime("%B %d, %Y")

    note(f"Mooring moved during deployment on {pretty_date}")
    note(f"Initial depth={inst_depth:.2f}m, Final Depth={inst_depth_shift:.2f}m .")
    # ---------- Add additional comments about shift below ----------------
    note(f"Mooring briefly recovered and redeployed in same location. ")

###
# %%Section 19: Create NetCDF, only including available variables
import numpy as np
import xarray as xr
import os

reshape = lambda arr: arr.reshape(-1, 1)

# Convert datetime array to seconds since epoch
epoch = dtmod.datetime(1970, 1, 1)
time_seconds = np.array([(d - epoch).total_seconds() for d in dt])
delta_seconds = float(time_seconds[-1] - time_seconds[0])
time_coverage_duration = isodate.duration_isoformat(dtmod.timedelta(seconds=delta_seconds))
# Build dataset adaptively
data_vars = {}

# Temperature
if 't' in locals() and t is not None:
    data_vars["TE90_01"] = (["station", "time"], reshape(t).T)
    if 'flag_t_array' in locals():
        data_vars["TE90_01_QC"] = (["station", "time"], reshape(flag_t_array).T)

# Conductivity
if 'c_adj' in locals() and c_adj is not None:
    data_vars["CNDC_01"] = (["station", "time"], reshape(c_adj).T)
    if 'flag_c_array' in locals():
        data_vars["CNDC_01_QC"] = (["station", "time"], reshape(flag_c_array).T)

# Pressure
if 'p' in locals() and p is not None:
    data_vars["PRES_01"] = (["station", "time"], reshape(p).T)
    if 'flag_p_array' in locals():
        data_vars["PRES_01_QC"] = (["station", "time"], reshape(flag_p_array).T)

# Salinity
if 's_adj' in locals() and s_adj is not None:
    data_vars["PSAL_01"] = (["station", "time"], reshape(s_adj).T)
    if 'flag_s_array' in locals():
        data_vars["PSAL_01_QC"] = (["station", "time"], reshape(flag_s_array).T)

# Dissolved Oxygen
if 'do' in locals() and do is not None:
    data_vars["DOXY_01"] = (["station", "time"], reshape(do).T)
    if 'flag_do_array' in locals():
        data_vars["DOXY_01_QC"] = (["station", "time"], reshape(flag_do_array).T)

# Potential Temperature
if 'pt' in locals() and pt is not None:
    data_vars["POTM_01"] = (["station", "time"], reshape(pt).T)
    if 'flag_pt_array' in locals():
        data_vars["POTM_01_QC"] = (["station", "time"], reshape(flag_pt_array).T)

# Sound Velocity
if 'svel' in locals() and svel is not None:
    data_vars["SVEL_01"] = (["station", "time"], reshape(svel).T)
    if 'flag_svel_array' in locals():
        data_vars["SVEL_01_QC"] = (["station", "time"], reshape(flag_svel_array).T)

# datetime - removed this because redundant -CHS
# data_vars["datetime"] = (["station", "time"], time_seconds.reshape(1, -1))

ds = xr.Dataset(
    data_vars=data_vars,
    coords=dict(
        time=("time", time_seconds),  # already fine
        station=("station", np.array([0], dtype="int32")),        # CF‑compliant
        lat=("station", np.array([lat], dtype="float64")),        # CF‑compliant
        lon=("station", np.array([lon], dtype="float64")),        # CF‑compliant
        depth=("station", np.array([round_p], dtype="float32")),  # CF‑compliant
    )
)
qc_attrs = {
    "standard_name": "quality_flag",
    "conventions": "WOCE",
    "flag_values": np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dtype="int8"),
    "flag_meanings": (
        "no_qc_performed "
        "good "
        "probably_good "
        "probably_bad "
        "bad "
        "changed "
        "below_detection "
        "in_excess "
        "interpolated "
        "missing"
    ),
    "_FillValue": np.int8(9),
    "_Unsigned": "true",
}
qc_long_names = {
    "TE90_01_QC": "quality flag for temperature",
    "CNDC_01_QC": "quality flag for conductivity",
    "PRES_01_QC": "quality flag for pressure",
    "PSAL_01_QC": "quality flag for salinity",
    "POTM_01_QC": "quality flag for potential temperature",
    "SVEL_01_QC": "quality flag for sound velocity",
    "DOXY_01_QC": "quality flag for dissolved oxygen",
}

for var in ["TE90_01", "CNDC_01", "PRES_01", "PSAL_01", "POTM_01", "SVEL_01", "DOXY_01"]:
    qc_var = var + "_QC"

    if var in ds and qc_var in ds:

        old = ds[qc_var]
        dims = old.dims
        data_int8 = old.values.astype("int8")

        ds = ds.drop_vars(qc_var)
        ds[qc_var] = (dims, data_int8)

        # Apply QC attributes
        for att, val in qc_attrs.items():
            ds[qc_var].attrs[att] = val

        # Add CIOOS-required long_name
        ds[qc_var].attrs["long_name"] = qc_long_names.get(qc_var, "quality flag")

        # Link QC variable to data variable
        ds[var].attrs["ancillary_variables"] = qc_var

for var in ds.data_vars:
    if var.endswith("_QC"):
        ds[var].attrs.update(qc_attrs)

# ---------------- Variable Attributes ----------------
if "TE90_01" in ds:
    ds["TE90_01"].attrs.update({
        "units": "degree_C",
        "long_name": "temperature",
        "standard_name": "sea_water_temperature",
        "sdn_parameter_urn": "SDN:P01::TEMPPR01",
        "sdn_parameter_name": "Temperature of the water body",
        "sdn_uom_urn": "UPAA",
        "sdn_uom_name": "Degrees Celsius",
        "generic_name": "temperature",
        "reference_scale": "ITS-90",
        "_FillValue": 1e35,
        "data_min": t_min,
        "data_max": t_max,
    })

if "CNDC_01" in ds:
    ds["CNDC_01"].attrs.update({
        "units": "S m-1",
        "long_name": "conductivity",
        "standard_name": "sea_water_electrical_conductivity",
        "sdn_parameter_urn": "SDN:P01::CNDCZZ01",
        "sdn_uom_urn": "UECA",
        "sdn_uom_name": "Siemens per metre",
        "generic_name": "conductivity",
        "_FillValue": 1e35,
        "data_min": c_min,
        "data_max": c_max,
    })

if "PRES_01" in ds:
    ds["PRES_01"].attrs.update({
        "units": "decibars",
        "long_name": "pressure",
        "standard_name": "sea_water_pressure",
        "sdn_parameter_urn": "SDN:P01::PRESPR01",
        "sdn_uom_urn": "UPDB",
        "sdn_uom_name": "decibars",
        "generic_name": "pressure",
        "_FillValue": 1e35,
        "data_min": p_min,
        "data_max": p_max,
    })

if "PSAL_01" in ds:
    ds["PSAL_01"].attrs.update({
        "units": "psu",
        "long_name": "salinity",
        "standard_name": "sea_water_practical_salinity",
        "sdn_parameter_urn": "SDN:P01::PSLTZZ01",
        "sdn_uom_urn": "UUUU",
        "sdn_uom_name": "dimensionless",
        "generic_name": "salinity",
        "_FillValue": 1e35,
        "data_min": s_min,
        "data_max": s_max,
    })

if "DOXY_01" in ds:
    ds["DOXY_01"].attrs.update({
        "units": "ml l-1",
        "long_name": "dissolved oxygen concentration",
        "standard_name": "volume_fraction_of_oxygen_in_sea_water",
        "sdn_parameter_urn": "SDN:P01::DOXMZZ01",  # Dissolved oxygen concentration
        "sdn_uom_urn": "UMLL",
        "sdn_uom_name": "Millilitres per litre",
        "generic_name": "oxygen",
        "_FillValue": 1e35,
        "data_min": do_min,
        "data_max": do_max,
    })

if "POTM_01" in ds:
    ds["POTM_01"].attrs.update({
        "units": "degree_C",
        "long_name": "potential_temperature",
        "standard_name": "sea_water_potential_temperature",
        "sdn_uom_urn": "UPAA",
        "sdn_uom_name": "Degrees Celsius",
        "generic_name": "potential_temperature",
        "reference_scale": "ITS-90",
        "_FillValue": 1e35,
        "data_min": pt_min,
        "data_max": pt_max,
    })

if "SVEL_01" in ds:
    ds["SVEL_01"].attrs.update({
        "units": "m s-1",
        "long_name": "sound_velocity",
        "standard_name": "speed_of_sound_in_sea_water",
        "sdn_parameter_urn": "SDN:P01::SVELCV01",
        "sdn_parameter_name": "Sound velocity in the water body by computation from temperature and salinity by unspecified algorithm",
        "sdn_uom_urn": "UVAA",
        "sdn_uom_name": "metres per second",
        "generic_name": "sound_velocity",
        "algorithm": "TEOS-10 GSW function gsw.sound_speed_t_exact",
        "_FillValue": 1e35,
        "data_min": svel_min,
        "data_max": svel_max,
    })

if "datetime" in ds:
    ds["datetime"].attrs.update({
        "units": "seconds since 1970-01-01T00:00:00Z",
        "standard_name": "time",
        "long_name": "date_time",
        "sdn_parameter_urn": "SDN:P01::ELTMEP01",
        "sdn_uom_urn": "SDN:P06::TISO",
        "sdn_uom_name": "Seconds",
        "generic_name": "time",
        #"coverage_content_type": "physicalMeasurement",
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(time_seconds)),
        "data_max": float(np.nanmax(time_seconds)),
    })

if "time" in ds:
    ds["time"].attrs.update({
        "units": "seconds since 1970-01-01T00:00:00Z",
        "standard_name": "time",
        "long_name": "time_of_measurement",
        "sdn_parameter_urn": "SDN:P01::ELTMEP01",
        "sdn_uom_urn": "SDN:P06::TISO",
        "sdn_uom_name": "Seconds",
        "generic_name": "time",
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(time_seconds)),
        "data_max": float(np.nanmax(time_seconds)),
    })

# ---------------- Coordinate Attributes ----------------
ds["lat"].attrs.update({
    "units": "degrees_north",
    "standard_name": "latitude",
    "long_name": "latitude",
    "sdn_parameter_name": "Latitude north",
    "sdn_parameter_urn": "SDN:P01::ALATZZ01",
    "sdn_uom_urn": "SDN:P06::DEGN",
    "sdn_uom_name": "Degrees north"
})
ds["lon"].attrs.update({
    "units": "degrees_east",
    "standard_name": "longitude",
    "long_name": "longitude",
    "sdn_parameter_name": "Longitude east",
    "sdn_parameter_urn": "SDN:P01::ALONZZ01",
    "sdn_uom_urn": "SDN:P06::DEGE",
    "sdn_uom_name": "Degrees east"
})
ds["depth"].attrs.update({
    "units": "m",
    "positive": "down",
    "standard_name": "depth",
    "long_name": "distance below the surface",
    "sdn_parameter_name": "Depth (spatial coordinate) relative to water surface in the water body",
    "sdn_parameter_urn": "SDN:P01::ADEPZZ01",
    "sdn_uom_urn": "SDN:P06::ULAA",
    "sdn_uom_name": "Metres",
    "comment": "If mooring shifts during deployment, depth calculated from initial location. Any additional depths recorded in comments. ",
    "processing_method": "TEOS-10 Gibbs SeaWater function using median p: depth = -gsw.z_from_p(pressure, latitude)",
})
ds["station"].attrs.update({
    "long_name": "station identifier",
    #"cf_role": "timeseries_id",
    "station_name": mooring,
    "comment": "Mooring deployment identifier",
})

# ---------------- Global Attributes ----------------
ds.attrs.update({
    "Conventions": "CF-1.6, ACDD-1.3, IOOS-1.2",
    "standard_name_vocabulary": "CF Standard Name Table v80",
    "source": dataset_id,
    "id": dataset_id,
    "sensor_type": instrument_model,
    "sensor_depth": inst_depth,
    "serial_number": serial,
    "coverage_content_type": "physicalMeasurement",
    "featureType": "timeSeries",
    "cdm_data_type": "TimeSeries",
    "data_type": data_type,
    "processing_level": processing,
    "country_code": country_code,
    "sdn_country_id": country,  # SDN-C18 vocabulary
    "sdn_country_vocabulary": "http://vocab.nerc.ac.uk/collection/C18/current/",
    "institution": "DFO BIO",
    "sdn_institution_id": "SDN:EDMO::1811",  # EDMO database, maintained by SeaDataNet #1811 is Woods Hole
    "sdn_institution_vocabulary": "https://edmo.seadatanet.org",
    "creator_type": "person",
    "creator_name": creator_name,
    #"processor_name": processor_name,
    "creator_country": "Canada",
    "creator_email": creator_email,
    #"processor_email": processor_email,
    "creator_institution": "Bedford Institute of Oceanography",
    "creator_address": "1 Challenger Drive, Dartmouth NS, B2Y 4A2.",
    "creator_city": "Dartmouth",
    "creator_sector": "gov federal",
    "creator_url": "https://www.bio.gc.ca/index-en.php",
    "publisher_type": "institution",
    "publisher_name": "Fisheries and Oceans Canada (DFO)",
    "publisher_country": "Canada",
    "publisher_email": "BIO.Datashop@dfo-mpo.gc.ca",
    "publisher_institution": "Bedford Institute of Oceanography",
    "publisher_sector": "gov federal",
    "publisher_url": "https://www.bio.gc.ca/index-en.php",
    "sdn_custodian_id": "SDN:EDMO::1811",
    # The Bedford Institute of Oceanography has a European Directory of Marine Organisations (EDMO) code  of 1811 http://edmo.seadatanet.org/report/1811
    "sdn_originator_id": "SDN:EDMO::1811",
    "sdn_creator_id": "SDN:EDMO::1811",
    "sdn_publisher_id": "SDN:EDMO::1811",
    "sdn_distributor_id": "SDN:EDMO::1979",
    # DFO data shop (MEDS)  has an EDMO code of 1979  https://edmo.seadatanet.org/report/1979
    "naming_authority": "ca.gc.bio",
    "license": "Open Government License - Canada, https://open.canada.ca/en/open-government-licence-canada",
    "infoUrl": "https://www.bio.gc.ca/science/newtech-technouvelles/observatory-observatoire-en.php",
    "inst_type": inst_type,
    "sampling_interval": float(sample_rate),
    "cruise_number": cruise_number,
    "cruise_name": cruise_name,
    "mooring_number": mooring_number,
    "serial_number": serial,
    "instrument_offbottom_depth": offbottom_depth,
    "instrument_depth": inst_depth,
    "chief_scientist": chief_scientist,
    "platform": platform,
    "platform_name": mooring_number,
    "platform_id": mooring_number,
    "sdn_platform_id": sdn_platform_id,
    "sdn_platform_vocabulary": "https://vocab.nerc.ac.uk/collection/L06/current/",
    "deployment_platform_name": deployment_name,
    "sdn_deployment_platform_id": sdn_deployment_id,
    "sdn_deployment_platform_vocabulary": "https://vocab.nerc.ac.uk/collection/C17/current/",
    "instrument_model": instrument_model,
    "instrument": f"{inst_type}, model number '{instrument_model}', serial number {serial_number}",
    "sdn_instrument_id": sdn_instrument_id,
    "sdn_instrument_vocabulary": "http://vocab.nerc.ac.uk/collection/L22/current/",
    "sdn_device_category_id": sdn_device_id,
    "sdn_device_category_vocabulary": "http://vocab.nerc.ac.uk/collection/L05/current/",
    "time_coverage_start": dt[0].isoformat(),
    "time_coverage_end": dt[-1].isoformat(),
    "time_coverage_resolution": time_coverage_resolution,
    "time_coverage_duration": time_coverage_duration,
    "location_description": location,
    "longitude": lon,
    "latitude": lat,
    "geospatial_lat_min": lat,
    "geospatial_lat_max": lat,
    "geospatial_lat_units": "degrees_north",
    "geospatial_lon_min": lon,
    "geospatial_lon_max": lon,
    "geospatial_lon_units": "degrees_east",
    "geospatial_vertical_max": inst_depth,
    "geospatial_vertical_min": inst_depth,
    "geospatial_vertical_units": "metres",
    "geospatial_vertical_positive": "down",
    "geospatial_bounds": f"POINT({lon} {lat})",
    "geospatial_bounds_crs": "EPSG:4326",
    # "EPSG:4326" corresponds to the WGS 84 coordinate system, commonly used for GPS coordinates.
    "geospatial_bounds_vertical_crs": "EPSG:5831",
    # "EPSG:5831" corresponds to the "Vertical CRS based on the EGM96 geoid model".
    "project": project,
    "program": program,
    "mission_description": program,
    "keywords": "Time-series, Marine-data, oceans, climate, water-temperature, salinity, mooring, moored-ctd, conductivity, pressure",
    "history": f"Created on {dtmod.datetime.utcnow().isoformat()}",
    "comment": ""  # start empty

})
sample_rate_rounded = int(round(sample_rate))
# Preserve date_created if file exists, if it does not set to now

output_path = f"{directory}{instrument_type}_{cruise_number}_{mooring_number}_{serial_number}_{sample_rate_rounded}.nc"
date_created_val = dtmod.datetime.utcnow().isoformat()

if os.path.exists(output_path):
    try:
        with xr.open_dataset(output_path) as old_ds:
            if "date_created" in old_ds.attrs:
                date_created_val = old_ds.attrs["date_created"]
    except Exception as e:
        print(f"⚠ Could not read existing file's date_created: {e}")


ds.attrs["date_created"] = date_created_val
ds.attrs["date_modified"] = dtmod.datetime.utcnow().isoformat()
#note("date_created and date_modified are recorded in UTC (Coordinated Universal Time)")
ds.attrs["title"] = project

# Add processing notes to the comment: global attribute
for msg in processing_notes:
    update_comment(ds, msg)
#update_comment(ds, "Final NetCDF created (CF-compliant)")


# Save NetCDF
ds.to_netcdf(output_path, format="NETCDF4", mode="w")
print(f"✔ Adaptive NetCDF file saved: {output_path}")

##
# %% Section 20: COMPUTE MEAN PRESSURE AND SAMPLE RATE ---
# SHN -- maybe redundant -- TBD
mean_pressure = np.mean(p)
print(f'Mean Pressure: {mean_pressure:.2f} db')
print(f'Depth Calculated: {inst_depth:.2f} m')
time_diff = np.diff(dt)  # Time differences between consecutive timestamps
time_diff_seconds = np.array([td.total_seconds() for td in time_diff])  # Convert to seconds
computed_sample_rate = np.mean(time_diff_seconds)
print(f"Computed Sample Rate: {computed_sample_rate:.2f} s")

##

