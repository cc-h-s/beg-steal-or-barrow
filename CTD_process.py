#Load mooring CTD data and process. Code produced by Kurtis Anstey, Shannon Nudds, and Annie Howard
### = Sections that require input from the user

#%%Section 1: Imports
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

#Function to append processing to comment attribute in the final NetCDF
processing_notes = []
def update_comment(ds, message: str):
    # append to the global 'comment' attribute, creating it if needed
    prev = str(ds.attrs.get("comment", "")).strip()
    ds.attrs["comment"] = message if not prev else f"{prev}; {message}"
def note(msg: str):
    processing_notes.append(msg)

#Function to convert time ordinal to datetime
def OrdinalToDatetime(ordinal):
    plaindate = dt.date.fromordinal(int(ordinal))
    date_time = dt.datetime.combine(plaindate, dt.datetime.min.time())
    return date_time + dt.timedelta(days=ordinal-int(ordinal))

# endregion

#%%Section 2: Metadata
###
creator_name = "Carmen Holmes-Smith"; processor_name = creator_name
creator_email = "carmen.holmes-smith@dfo-mpo.gc.ca"; processor_email = creator_email
# directory = f'./2022-2024/CTD/M2170_SN22954/'                         # directory of raw data file
directory = f'./Barrow_RawData/'     # directory of raw data file, change to: f'./'
filename = 'M2170_SN22954.cnv'       # filename

# Mission info
year_n = 2022                                       # year of DEPLOYMENT
chief_scientist = "Clark Richards"                  # chief scientist
cruise_number = 'RAD2022375'                        # cruise number (eg. RAD2022375)
deployment_name = "CCGS PIERRE RADISSON"            # deployment refers to the vessel
sdn_deployment_id = "SDN:C17::18RD"                 # SDN-C17 vocabulary #18RD = RADISSON; 18GO = Des Gros
site = 'BS-SOUTH-CENTRAL'                           # mooring site (eg. BS-SOUTH, BS-SOUTH-CENTRAL, etc.)

# mooring (aka platform) details
mooring = 'M2170'                                   # mooring number; set to '' for single mooring sites, or '-1' etc. for multiple mooring sites, e.g. QN2024-2
mooring_number = mooring[1:]  # !
latdeg = 74; latdec = 12.573                        # latitude in degrees and decimal minutes
londeg = 90; londec = 49.641                        # longitude in degrees and decimal minutes
platform = "mooring"          # !                   #
sdn_platform_id = "SDN:L06::48, SDN:L06::43"  # !   # SDN-L06 vocabulary #EX. 48 = mooring, 43 = subsurface mooring

# subsite = mooring                                 # no subsite for Barrow Strait [FROM KURTIS: set to '' for single mooring sites, or '-1' etc. for multiple mooring sites, e.g. QN2024-2]
corr_water_depth = 256                              # in metres, computed from sounding
pres = ' '                                          # '_34m' if one of multiple instruments on line mooring
# offbottom_depth = " "                             # computed later

# instrument (aka device) details
data_type = "moored CTD"    # !                     # data type (for netcdf, eg. moored CTD)
instrument_type = "MCTD"    # !                     # short form (eg. MCTD)
inst_type = "Microcat"      # !                     # instrument type (for netcdf, eg. Microcat)
instrument_model = "SBE37-SM"                       # instrument model, eg. SBE37-SM, SBE37-SMP, SBE37-SMP-ODO
serial = 'SN22954';                                 # instrument serial number (if included in filename)
serial_number = serial[2:]  # !
sdn_instrument_id = "SDN:L22::TOOL1456"                         # SDN:L22::TOOL1456 vocabulary #EX. TOOL1456 = "Sea-Bird SBE 37 MicroCat SM-CTP (submersible) CTD sensor"
sdn_device_id = "SDN:L05::350, SDN:L05::134, SDN:L05::WPS"      # SDN-L05 vocabulary: https://vocab.seadatanet.org/search #EX. 350 = CTD, 134 = water temperature sensor, WPS = Water Pressure Sensor

# program and project info
project = "Barrow Strait Monitoring and Real Time Observatory Project"
program = "Maritimes Region Barrow Strait Monitoring Program"
location = "Barrow Strait"
country = "SDN:C32::CA, SDN:C18::18"  # !                       # SDN C32 vocabulary, CA = CANADA
country_code = "1810"                 # !                       # 1810 = CANADA
cruise_name = "mooring deployment"    # !              # generic descriptor for the cruise

# processing notes
processing = "Data trimmed for in water measurements, drift corrected and QC flags applied. Refer to comment section for details."

# region

year_1 = year_n + 1; year_str = str(year_n); year_2str = str(int(year_n) - 2000) # year of DEPLOYMENT
dataset_id =  f"{instrument_type}_{cruise_number}_{mooring_number}_{serial_number}_{year_n}"
lat = round((latdeg + latdec/60), ndigits=6); latstr = f'{latdeg} {latdec}'
lon = round((-(londeg + londec/60)), ndigits=6); lonstr = f'{-londeg} {londec}'

# endregion

#%%Section 3: Load raw data
###
# region
cnv = filename.endswith(".cnv")
asc = filename.endswith(".asc")
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
    #df = pd.read_fwf(f"{directory}{filename}", skiprows=data_start)

    colnames = []

    for line in lines:
        if line.startswith("# name"):
            raw = line.split("=")[1].split(":")[0].strip()
            colnames.append(raw)

    df.columns = colnames[:len(df.columns)]

    # print("Raw keys detected:", df.columns)
    #df.columns = ["tv290C", "cond0S/m", "prdM", "timeJV2", "flag"]
    # print("Raw keys detected:", df.columns)

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

	# ✅ FIX 1: Clean whitespace
	data['dates'] = data['dates'].astype(str).apply(lambda x: " ".join(x.split()))
	data['times'] = data['times'].astype(str).apply(lambda x: " ".join(x.split()))

	# ✅ FIX 2: Build datetime column
	data['datetime'] = pd.to_datetime(
		data['dates'] + " " + data['times'],
		format="%d %b %Y %H:%M:%S",
		errors='coerce'
	)

# elif asc:
#     # Load ASCII files using np.genfromtxt
#     dtype = [
#         ('temperature', 'f8'),
#         ('conductivity', 'f8'),
#         ('pressure', 'f8'),
#         ('dates', 'U19'),
#         ('times', 'U19')
#     ]
#     data_array = np.genfromtxt(
#         f"{directory}{filename}",
#         skip_header=0,
#         delimiter=",",
#         dtype=dtype,
#         encoding="utf-8"
#     )
#
#     data = pd.DataFrame(data_array)


	raw_keys = ['temperature', 'conductivity', 'pressure', 'dates', 'times']

else:
    raise ValueError("Unsupported file type. Must be CNV or ASC.")

print("Raw keys detected:", raw_keys)

# end region
###
#%%Section 4: Save raw data as NetCDF
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

raw_ds.attrs['source_file'] = filename
raw_ds.attrs['description'] = 'Raw instrument data (no QC, no corrections)'
raw_ds.attrs['comment'] = 'Converted from CNV or ASC to NetCDF'

raw_output_path = f"{directory}{filename.replace('.cnv', '_raw.nc').replace('.asc', '_raw.nc')}"
#raw_nc_name = f"{directory}{filename}_RAW.nc"
#raw_ds.to_netcdf(raw_nc_name)
#print(f"Saved RAW NetCDF → {raw_nc_name}")
raw_ds.to_netcdf(raw_output_path)
print(f"Saved RAW NetCDF → {raw_output_path}")

# endregion
###
#%%Section 5: Extract variables
#region

data_ = data.copy()
do = None
# Standard variable mapping
var_map = {
    'tv290C': 't',          # Temperature
    'cond0S/m': 'c',        # Conductivity
    'prdM': 'p',            # Pressure
	'sbeopoxML/L': 'do',	# Oxygen mL/L
    'timeJV2': 'time',      # CNV Time
    'temperature': 't',     # ASC Temperature
    'conductivity': 'c',    # ASC Conductivity
    'pressure': 'p',        # ASC Pressure
    'dates': 'dates',       # ASC Dates
    'times': 'times'        # ASC Times
}

vars_dict = {}
available_vars = []

for raw_var, new_var in var_map.items():
    if raw_var in raw_keys:
        print(raw_var)
        vars_dict[new_var] = data_[raw_var].values
        available_vars.append(new_var)

# Core variables
t = vars_dict.get('t')
c = vars_dict.get('c')
p = vars_dict.get('p')
time = vars_dict.get('time')
do = vars_dict.get('do') if 'do' in vars_dict else None

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

# endregion
###
#%%Section 6: Check time data
# region
fig, ax0 = plt.subplots(1,1,figsize=(12,8)) # fig.tight_layout();
ax0.plot(range(0, len(time)), time, lw=1, color='k') # change second time to timej
ax0.set_xlabel('Index'); ax0.set_ylabel('Time')
plt.title("Time Check!")
plt.show(block=True)

# endregion
##
#%%Section 7: Time Data Corrections (IF REQUIRED)
# region
# SHN \/\/\/ Do I need to run this section with all = False if there is no time correction required, or can I skip it altogether?
#Set all to 'False' if no correction necessary
#
no_time_data = False        # if time data does not exist or is entirely incorrect, and have initialisation time from data or metadata
format_time_data = False    # if time data in wrong format e.g. separate year, month, day, hour, min, sec values
time_trim = False           # if totally incorrect time data on either end of record (e.g. data present from previous deployment); time out-of-water can still be correct!
time_spike = False          # if bad time data somewhere in record
fix_irregular_data = False  # if cnv jd time data exists but incorrect, and need to manufacture NEW time data (NOTE: can typically just use 'no_time_data' case)
UTC_offset = False          # e.g. add 7 hours if obviously not synced to UTC upon deployment; must already be in datetime format
time_offset = False         # if need to add or remove regular time offset throughout record; must already be in datetime format


if no_time_data:
	#
	time0 = dt.datetime.strptime('2022-10-04 13:00:03.000000', '%Y-%m-%d %H:%M:%S.%f') # initial time
	burstn = 10             # how many samples per burst
	sample_rate = dt.timedelta(seconds=1) # time between samples
	burst_rate = dt.timedelta(minutes=1) # time between bursts
	#

	timen = len(data[:, 0]) # length of time data
	time_data = np.zeros_like(data[:, 0], dtype=dt.datetime) # empty array for time data
	burst_count = 0         # tracker for samples within burst
	for i in range(timen):
		if i == 0:          # first time datapoint
			time_data[i] = time0
			burst_count += 1
		else:               # subsequent datapoints
			if burst_count == 0:
				time_data[i] = time_data[i-burstn] + burst_rate # add burst interval
				burst_count += 1
			elif burst_count > 0 and burst_count != (burstn - 1):
				time_data[i] = time_data[i-1] + sample_rate # add sample interval
				burst_count += 1
			elif burst_count > 0  and burst_count == (burstn - 1):
				time_data[i] = time_data[i - 1] + sample_rate # add sample interval
				burst_count = 0 # reset burst tracker
	time = time_data.copy()
	print(f'Instrument started (not deployed): {time[0]}')
	print(f'Instrument stopped (not recovered): {time[-1]}')

if format_time_data:
	time0 = dt.datetime(int(data[0, 0]), int(data[0, 1]), int(data[0, 2]), int(data[0, 3]), int(data[0, 4]), int(data[0, 5]))  # initial time
	timen = len(data[:, 0]) # length of time data
	time_data = np.zeros_like(data[:, 0], dtype=dt.datetime)  # empty array for time data
	for i in range(timen):
		time_data[i] = dt.datetime(int(data[i, 0]), int(data[i, 1]), int(data[i, 2]), int(data[i, 3]), int(data[i, 4]), int(data[i, 5])) # format time at each step
	time = time_data.copy()
	print(f'Instrument started (not deployed): {time[0]}')
	print(f'Instrument stopped (not recovered): {time[-1]}')

if time_trim:
	time = time[3849:].copy() # check time, p, t, c for proper trim indices
	print(f'Instrument started (not deployed): {time[0]}')
	print(f'Instrument stopped (not recovered): {time[-1]}')

if time_spike:
	trim_times = np.r_[35232:35235] # indices of spike; use len(time) for end of record if necessary
	time[trim_times] = np.nan       # set bad time data to NaN
	time_temp = pd.Series(time);
	time_int = time_temp.interpolate(method="linear", limit=10, limit_direction='forward'); # interpolate over the time gap
	time = np.array(time_int)       # set interpolated data to original array
	print(f'Instrument started (not deployed): {time[0]}')
	print(f'Instrument stopped (not recovered): {time[-1]}')

if fix_irregular_data:      # can tyically use 'no_time_data' case

	use_rate = 'manual'     # init, final, or manual (from CNV) whichever is correct; typically use manual
	manual_sample_rate = 900 # if use_rate set to manual
	start_time_incorrect = False # True if time0 incorrect
	# correct_start_time = dt.datetime.strptime('2022-10-04 13:00:03.000000', '%Y-%m-%d %H:%M:%S.%f') # use if start_time_incorrect is True
	correct_start_time = time[0]
	irreg_sampling = False  # True if periods of different sampling rates
	time0_idx = 0           # index of first real time stamp (sometimes this is incorrect at startup, time data does NOT have to be trimmed for out-of-water time)
	timez_idx = len(time) - 2 # for checking sample rates

	# determine sample interval at start of data
	tn = len(time[time0_idx:]) # length of time data
	init_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[time0_idx] # initial timestamp
	time0 = OrdinalToDatetime(init_time)
	next_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[time0_idx + 1] # consecutive timestamp
	time1 = OrdinalToDatetime(next_time)
	sample_init = time1 - time0 # time delta between samples
	sample_int_0_s = sample_init.seconds
	sample_int_0_ms = sample_init.microseconds
	sample_int_0 = sample_int_0_s + (sample_int_0_ms/1e6)
	sample_int_0_rounded_s = int(round(sample_int_0, 0))
	print(f'Initial sample interval: {sample_int_0_rounded_s} s')

	late_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[timez_idx] # initial timestamp (at end of data)
	time2 = OrdinalToDatetime(late_time)
	later_time = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + time[timez_idx + 1] # consecutive timestamp (at end of data)
	time3 = OrdinalToDatetime(later_time)
	sample_final = time3 - time2 # time delta between samples
	sample_int_1_s = sample_final.seconds
	sample_int_1_ms = sample_final.microseconds
	sample_int_1 = sample_int_1_s + (sample_int_1_ms/1e6)
	sample_int_1_rounded_s = int(round(sample_int_1, 0))
	print(f'Final sample interval: {sample_int_1_rounded_s} s')

	if use_rate == 'init': # change 'use_rate' above, if necessary; typically use manual
		fix_rate = sample_int_0_rounded_s
	elif use_rate == 'final':
		fix_rate = sample_int_1_rounded_s
	elif use_rate == 'manual':
		fix_rate = manual_sample_rate # seconds, set above

	if start_time_incorrect:
		time0 = correct_start_time

	if irreg_sampling:  # input indices for periods with variable sampling rates
		irreg_int_0 = np.r_[0:3763]
		irreg_int_1 = np.r_[3763:3780]
		irreg_int_2 = np.r_[3780:41962]
		fix_rate_0 = 30 # expected sample rate for incorrect periods
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

	elif not irreg_sampling: # create new time data from initial time and sample rate
		time_new = []
		for i in range(tn):
			delta_i = int(i) * int(fix_rate)
			time_new_temp = time0 + dt.timedelta(seconds=delta_i)
			time_new.append(time_new_temp)

	time_new = np.asarray(time_new)
	print(f'New times begin: {time_new[0]}, end: {time_new[-1]}')

	time = time_new.copy() # set new time data

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

#%%Section 8: Correct for clock drift

###
# *** if SLOWER/BEHIND than PC/true time, tot_drift is NEGATIVE; ***
# *** if FASTER/AHEAD, this value POSITIVE (PC/true time + tot_drift = instrument time)***
tot_drift = -46             # total clock drift from recovery time check, seconds.
cnv_jd_drift = True         # True if .cnv file with Julian day time data, not corrected above
datetime_drift = False      # True if datetime time data, or if corrected above


import numpy as np
import datetime as dt  # ensure dt is the datetime module

# region

if cnv_jd_drift:
	jd = time #timej                            # copy Julian day time data
	drift = (-tot_drift)/len(time) #timej       # incremental clock drift in seconds (assuming linear)
	jd_drift = drift / 86400                    # drift in JD
	offset = np.zeros_like(jd)                  # empty array to track linearly increasing drift offsets
	jd_adjusted = np.zeros_like(jd)             # empty array for adjusted JD times
	for i in range(len(jd)):
		offset[i] = jd_drift * i
		jd_adjusted[i] = jd[i] + offset[i]
	print('Instrument clock drift = {} seconds'.format(tot_drift))
	print('Drift correction = {:.0f} seconds'.format(offset[-1] * 86400))
	dn_initial = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + jd_adjusted # convert JD to datenumber; last day of PREVIOUS YEAR as day '0', so Jan 1 is day '1'
	dn_dt = []                                  # empty list for datetime values
	for i in range(len(dn_initial)):
		dn_dt.append(OrdinalToDatetime(dn_initial[i]))
	dn_dt = np.asarray(dn_dt)                   # convert list to numpy array
	print(f'Instrument started (not deployed): {dn_dt[0]}')
	print(f'Instrument stopped (drift corrected): {dn_dt[-1]}')
	dn_initial_raw = dt.date.toordinal(dt.date(year_n - 1, 12, 31)) + jd
	dn_dt_raw = np.asarray([OrdinalToDatetime(val) for val in dn_initial_raw])
	print(f'Instrument stopped (drift uncorrected): {dn_dt_raw[-1]}')
	sample_rate = round((dn_dt[100]-dn_dt[99]).seconds, ndigits=-1) # check correct sample rate
	print(f'Sample rate: {sample_rate} s')

if datetime_drift:
	time_adj = timej.copy()                     # copy datetime data
	drift = dt.timedelta(seconds=((-tot_drift)/len(time_adj))) # incremental drift in seconds
	offset = np.zeros_like(time_adj)            # empty array to track linearly increasing drift offsets
	time_adjusted = np.zeros_like(time_adj)     # empty array for adjusted times
	for i in range(len(time_adj)):
		offset[i] = drift * i
		time_adjusted[i] = time_adj[i] + offset[i]
	print(f'Instrument clock drift = {tot_drift} seconds')
	print(f'Drift correction = {offset[-1].seconds} seconds')
	dn_dt = time_adjusted.copy() #copy adjusted times
	print(f'Instrument started (not deployed): {dn_dt[0]}')
	print(f'Instrument stopped (drift corrected): {dn_dt[-1]}')
	print(f'Instrument stopped (drift uncorrected): {time_adj[-1]}')
	sample_rate = round((dn_dt[100]-dn_dt[99]).seconds, ndigits=-1)
	print(f'Sample rate: {sample_rate} s')

if not cnv_jd_drift and not datetime_drift:
	dn_dt = time.copy()

note(f"Clock drift setting tot_drift={tot_drift} s "
     f"via {'JD' if cnv_jd_drift else 'datetime' if datetime_drift else 'none'} method")

#endregion
###
#%% Section 9A: Plot raw data to identify time in water
# Examine the plot to identify indices to trim for in water
# region

# Setup Plotting Structure
available_vars = [var for var in available_vars if var != 'time']
if 'p' not in available_vars:
    available_vars.append('p')

var_labels = {
    't': 'Temp.',
    'c': 'Cond.',
    'do': 'Dissolved Oxygen',
    'p': 'Pressure'  # Ensure pressure is included
}
num_vars = len(available_vars)

#Plots to determine TRIM indices for instrument IN water; must check P, T, and C
fig, axes = plt.subplots(num_vars, 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()
for i, var_name in enumerate(available_vars):
    if var_name in var_labels:  # Ensure we only plot variables with labels
        axes[i].plot(eval(var_name), lw=1, color='k')  # Use eval to get the variable
        axes[i].set_ylabel(var_labels[var_name])
plt.show(block=True)

# endregion

#%% Section 9B: Input and check trim indices
###
start = 7501
finish = 112160 + 1   # last good point +1

# region

if "t_ut" not in globals():
    t_ut = t.copy()
    c_ut = c.copy()
    p_ut = p.copy()
    do_ut = do.copy() if do is not None else None

raw_var_labels = {
    't_ut': 'Temperature',
    'c_ut': 'Conductivity',
    'p_ut': 'Pressure',
}
if do_ut is not None:
    raw_var_labels['do_ut'] = 'Dissolved Oxygen'

# Plot raw variables with trim lines to check:

raw_plot_vars = {'t_ut': t_ut, 'c_ut': c_ut, 'p_ut': p_ut}
if do_ut is not None:
    raw_plot_vars['do_ut'] = do_ut

fig, axes = plt.subplots(len(raw_plot_vars), 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

for i, (var_name, data_array) in enumerate(raw_plot_vars.items()):
    axes[i].plot(data_array, lw=1, color='gray')
    axes[i].axvline(start, color='g', linestyle='--', label='Start Trim')
    axes[i].axvline(finish-1, color='r', linestyle='--', label='Finish Trim')
    axes[i].set_ylabel(raw_var_labels[var_name])
    if i == 0:
        axes[i].legend(loc='best')

plt.suptitle('Untrimmed Variables with Trim Indices')
plt.show(block=True)

# endregion
##
#%% SECTION 9C - Trim Data and Plot
# region

# --- (3) NOW TRIM ORIGINALS ---

# LEGACY CODE FROM KURTIS - IGNORE
# if not time_trim:
#     dt = dn_dt[start:finish]
# else:
#     dt = dn_dt[:(finish - start)].copy()

dt = dn_dt[start:finish]
t = t[start:finish]
c = c[start:finish]
p = p[start:finish]
if do is not None:
    do = do[start:finish]

# recalc salinity after trimming
s = gsw.SP_from_C(10 * c, t, p)
##
# --- (4) PLOT TRIMMED DATA ---
dt_str = np.array([d.strftime('%Y-%m-%d %H:%M:%S.%f') for d in dt])
var_labels = {'t': 'Temperature', 'c': 'Conductivity', 'p': 'Pressure', 's': 'Salinity'}
if do is not None:
    var_labels['do'] = 'Dissolved Oxygen'

plot_vars = {'t': t, 'c': c, 'p': p, 's': s}
if do is not None:
    plot_vars['do'] = do

fig, axes = plt.subplots(len(plot_vars), 1, figsize=(12, 8), sharex=True)
fig.subplots_adjust(hspace=0.04)
fig.align_ylabels()

for i, (var_name, data_array) in enumerate(plot_vars.items()):
    axes[i].plot(data_array, lw=1, color='k')
    axes[i].set_ylabel(var_labels[var_name])

plt.suptitle('Trimmed In-Place Variables')
plt.show(block=True)

note(f"Trimmed in-water indices: start={start}, finish={finish}")
# endregion
#
#%% !! (SKIP THIS) Section 10: Temperature Salinity Plot
##
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
#%% Section 11: Temperature Salinity Plot, Interactive
#region
import plotly.express as px
import pandas as pd
import numpy as np

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

#endregion

#%% Section 12: Manual Data Inspection with Spike Suggestions
###
detect_spikes_t = True    # Detect spikes in Temperature
detect_spikes_c = True    # Detect spikes in Conductivity
detect_spikes_do = False  # Optional: Detect in DO
detect_spikes_p = False   # Optional: Detect in Pressure
#
#region
Use_CHS_Func = False # Function I prefer to use to suggest flags
#sample_rate = 900
# Spike detection parameters
if sample_rate == 900:
    n1 = 2; n2 = 10; block = 200
else:
    n1 = 2; n2 = 20; block = 200

#
#NOTE: These plots are for manual review only.
# Spikes are algorithmically suggested, but no data is removed or altered.
# Use this as a guide to record spike locations in your lab notebook per WHOCE QC flagging.

def detect_spikes(data, n1, n2, block):
    original = pd.Series(data)
    processed = ctd.processing.despike(original.copy(), n1=n1, n2=n2, block=block)
    return np.where(~np.isclose(original, processed, equal_nan=True))[0]


def detect_outliers(data1, data2, window_size, n, n0):
	# --- Find Outliers ---
	slope, intercept = np.polyfit(data1, data2, 1)
	y_predict  = slope * data1 + intercept
	residuals  = data2 - y_predict
	threshold  = n0 * np.std(residuals)
	outlier_inds = np.where(np.abs(residuals) > threshold)[0]

	print(f"Array size: {len(outlier_inds)}")
	print("Outlier test:", outlier_inds[:20])

	Make_Figure = True

	s1 = pd.Series(data1).astype(float)
	k = 1.4826  # scale factor for Gaussian distribution
	rolling_median1 = s1.rolling(window=2 * window_size + 1, center=True).median()
	diff1 = np.abs(s1 - rolling_median1)
	mad1 = s1.rolling(window=2 * window_size + 1, center=True) \
		.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
	threshold1 = n * k * mad1
	spike_bins1 = diff1 > threshold1
	spike_inds1 = np.where(spike_bins1.fillna(False).values)[0]
	z_score1 = diff1 / threshold1

	s2 = pd.Series(data2).astype(float)
	k = 1.4826  # scale factor for Gaussian distribution
	rolling_median2 = s2.rolling(window=2 * window_size + 1, center=True).median()
	diff2 = np.abs(s2 - rolling_median2)
	mad2 = s2.rolling(window=2 * window_size + 1, center=True) \
		.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
	threshold2 = n * k * mad2
	spike_bins2 = diff2 > threshold2
	spike_inds2 = np.where(spike_bins2.fillna(False).values)[0]
	z_score2 = diff2 / threshold2


	for i in range(1, len(outlier_inds)):
		if outlier_inds[i] == outlier_inds[i - 1] + 1:
			z_score1[outlier_inds[i]] = z_score1[outlier_inds[i]-1]
			z_score2[outlier_inds[i]] = z_score2[outlier_inds[i]-1]

	outliers1   = np.intersect1d(np.where(np.abs(z_score1) - np.abs(z_score2) > 0), outlier_inds)
	outliers2   = np.intersect1d(np.where(np.abs(z_score1) - np.abs(z_score2) < 0), outlier_inds)

	flags1 = np.union1d(spike_inds1, outliers1)
	flags2 = np.union1d(spike_inds2, outliers2)


	if Make_Figure:

		fig2, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
		ax1.plot(data1, color='black')
		ax1.set_ylabel("Temperature")
		ax1.scatter(spike_inds1, data1[spike_inds1], facecolors='c', edgecolors='c', zorder=3)
		ax1.scatter(outliers1, data1[outliers1],facecolors='none',edgecolors='m',zorder=4, linewidths=1)

		ax2.plot(data2, color='black')
		ax2.scatter(spike_inds2, data2[spike_inds2], facecolors='c', edgecolors='c', zorder=3)
		ax2.scatter(outliers2, data2[outliers2],facecolors='none',edgecolors='m',zorder=4, linewidths=1)
		ax2.set_ylabel("Conductivity")
		plt.tight_layout()
		plt.show()
		fig2.show()

	return flags1, flags2

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

if Use_CHS_Func:
	window_size = 50
	n = 9
	spike_indices_t  = hampel_indices(t, window_size, n) if detect_spikes_t else []
	spike_indices_c  = hampel_indices(c, window_size, n) if detect_spikes_c else []
	spike_indices_do = hampel_indices(do, window_size, n) if detect_spikes_t else []
	spike_indices_p  = hampel_indices(p, window_size, n) if detect_spikes_c else []

	if detect_spikes_t and detect_spikes_c:
		n0 = 4
		spike_indices_t, spike_indices_c = detect_outliers(t, c, window_size, n, n0)
	print("Outliers in t:", spike_indices_t[:20])
	print("Outliers in c:", spike_indices_c[:20])
else:
	# Run spike detection (as guidance only)
	spike_indices_t = detect_spikes(t, n1, n2, block) if detect_spikes_t else []
	spike_indices_c = detect_spikes(c, n1, n2, block) if detect_spikes_c else []
	spike_indices_do = detect_spikes(do, n1, n2, block) if detect_spikes_do else []
	spike_indices_p = detect_spikes(p, n1, n2, block) if detect_spikes_p else []
	print("Outliers in t (despike):", spike_indices_t[:20])
	print("Outliers in c (despike):", spike_indices_c[:20])

##
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

#%% Section 13A: Apply WHOCE CTD Flags to variables
# WHOCE CTD Flag Definitions: 2 = Acceptable measurement (default), 3 = Questionable measurement, 4 = Bad measurement, 5 = Not reported (e.g. missing/NaN)

### CONTROL WHICH VARIABLES GET FLAGGED ###
flag_c = True   # True if conductivity should be flagged
flag_t = True   # True if temperature should be flagged
flag_do = False # True if dissolved oxygen should be flagged
flag_s = True   # True if salinity should be flagged (inherited from T + C)
flag_p = True   # True if pressure should be flagged
flag_pt = True
flag_svel = True

# --- Temperature Flags ---
if flag_t:
    flag_t_array = np.full_like(t, 2, dtype=int)
    flagged_t_data = [
        # e.g., (1000, 3), (2000, 4)
	    (68072, 4),
	    (68073, 4),
	    (747, 3),
	    (839, 3),
	    (1951, 3),
	    (4777, 3),
	    (38480, 3),
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
	    (68073,4),
        (80520, 4),
    ]
    if flagged_c_data:
        c_indices, c_values = zip(*flagged_c_data)
        flag_c_array[np.array(c_indices, dtype=int)] = np.array(c_values, dtype=int)
    flag_c_array[np.isnan(c)] = 5

# --- Salinity Flags (from T + C flags) ---
if flag_s:
    flag_s_array = np.full_like(s, 2, dtype=int)
    combined_flagged_data = flagged_c_data + flagged_t_data
    if combined_flagged_data:
        s_indices, s_values = zip(*combined_flagged_data)
        flag_s_array[np.array(s_indices, dtype=int)] = np.array(s_values, dtype=int)
    flag_s_array[np.isnan(s)] = 5

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

##
#%% !! (SKIP THIS) Section 13B: PLOT QC FLAGS

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

if has_real_flags(flag_t_array, t):
    flagged_vars.append(('Temperature', t, flag_t_array))
if has_real_flags(flag_c_array, c):
    flagged_vars.append(('Conductivity', c, flag_c_array))
if has_real_flags(flag_s_array, s):
    flagged_vars.append(('Salinity', s, flag_s_array))
if has_real_flags(flag_p_array, p):
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
	plt.suptitle("QC Flags Applied (WHOCE Scheme)", fontsize=16)
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

note("WHOCE QC flags created for all available variables")

# endregion
##
#%% Section 13C: PLOT QC FLAGS, with Plotly
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
if has_real_flags(flag_t_array, t):
    flagged_vars.append(('Temperature', t, flag_t_array))
if has_real_flags(flag_c_array, c):
    flagged_vars.append(('Conductivity', c, flag_c_array))
if has_real_flags(flag_s_array, s):
    flagged_vars.append(('Salinity', s, flag_s_array))
if has_real_flags(flag_p_array, p):
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
        title_text="QC Flags Applied (WHOCE Scheme)",
        legend=dict(orientation="h", y=-0.1),
        margin=dict(t=50, b=50)
    )
    fig.update_xaxes(title_text="Index", row=len(flagged_vars), col=1)

    fig.show()

# endregion

#%% 13D: TS plot omitting flag 4 data from view
    #fig.write_html(f'{directory}{site}{year_str}{mooring}{pres}_{serial}_ManualSpikeReview.html')

#%% 13D: Interactive T-S Plot with WHOCE QC flags (by Salinity Flag)
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
    title="Interactive TS Diagram with WHOCE QC Flags (by Salinity Flag)",
    xaxis=dict(title="Salinity"),
    yaxis=dict(title="Temperature (°C)"),
    legend=dict(title="WHOCE QC Flags", traceorder='normal'),
    margin=dict(l=70, r=20, t=70, b=70),
    height=600
)

fig.show()

# endregion
###
#%% Section 14: Conductivity Offset
# SHN \/\/\/ Consider removing plot and printing pre and post correction linear slope.

# region


c0_offset = 1.0000          # multiplier at start of record
c_offset = 1.0000           # multiplier at end of record

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

note(f"Conductivity offset applied (c0_offset={c0_offset}, c_offset={c_offset})")

# endregion
###
#%% Section 15: Derive Quantities from Temperature and Salinity
# salinity is derived from T and C above for the T/S plots.
SA = gsw.SA_from_SP(s_adj, p, lon, lat)  # absolute salinity (g/kg) for gsw calculations
pt = gsw.pt0_from_t(SA, t, p)   # potential temperature at p = 0 db
svel = gsw.sound_speed_t_exact(SA, t, p)  # sound speed in seawater
###
#%%Section 16: Derive Flags for PT and SVEL from Component Variables
def combine_flags(*flag_arrays):
    """Return the highest (worst) flag value at each index."""
    stacked = np.vstack(flag_arrays)
    return np.nanmax(stacked, axis=0).astype(int)

if flag_pt:
    flag_pt_array = combine_flags(flag_t_array, flag_s_array, flag_p_array)

if flag_svel:
    flag_svel_array = combine_flags(flag_t_array, flag_s_array, flag_p_array)

#%%Section 17: Compute Pressure Mode to Calculate Instrument Depth Later
####
no_pressure_sensor = False      # True is no pressure sensor

if no_pressure_sensor:
	round_p = 108               # constant pressure value if no pressure sensor

else:
	mean_p = np.nanmean(p)
	round_p = np.asarray(p, dtype=int)
	round_p = stats.mode(round_p, keepdims=False)[0]
##
#%%Section 18: Create objects for the NetCDF
import datetime as dtmod
def safe_minmax(arr):
    return float(np.nanmin(arr)), float(np.nanmax(arr))

t_min, t_max = safe_minmax(t)
c_min, c_max = safe_minmax(c_adj)
p_min, p_max = safe_minmax(p)
s_min, s_max = safe_minmax(s_adj)
pt_min, pt_max = safe_minmax(pt)
svel_min, svel_max = safe_minmax(svel)
inst_depth = float(-gsw.z_from_p(round_p, lat))
offbottom_depth = corr_water_depth - inst_depth
time_coverage_resolution = isodate.duration_isoformat(dtmod.timedelta(seconds=sample_rate))
###
#%%Section 19: Create NetCDF, only including available variables
import numpy as np
import xarray as xr
import os

reshape = lambda arr: arr.reshape(-1, 1)

# Convert datetime array to seconds since epoch
epoch = dtmod.datetime(1970, 1, 1)
time_seconds = np.array([(d - epoch).total_seconds() for d in dt])
delta_seconds = float(time_seconds[-1] - time_seconds[0])
time_coverage_duration   = isodate.duration_isoformat(dtmod.timedelta(seconds=delta_seconds))
# Build dataset adaptively
data_vars = {}

#Temperature
if 't' in locals() and t is not None:
    data_vars["TE90_01"] = (["time", "station"], reshape(t))
    if 'flag_t_array' in locals():
        data_vars["TE90_01_QC"] = (["time", "station"], reshape(flag_t_array))

#Conductivity
if 'c_adj' in locals() and c_adj is not None:
    data_vars["CNDC_01"] = (["time", "station"], reshape(c_adj))
    if 'flag_c_array' in locals():
        data_vars["CNDC_01_QC"] = (["time", "station"], reshape(flag_c_array))

#Pressure
if 'p' in locals() and p is not None:
    data_vars["PRES_01"] = (["time", "station"], reshape(p))
    if 'flag_p_array' in locals():
        data_vars["PRES_01_QC"] = (["time", "station"], reshape(flag_p_array))

#Salinity
if 's_adj' in locals() and s_adj is not None:
    data_vars["PSAL_01"] = (["time", "station"], reshape(s_adj))
    if 'flag_s_array' in locals():
        data_vars["PSAL_01_QC"] = (["time", "station"], reshape(flag_s_array))

#Dissolved Oxygen
if 'do' in locals() and do is not None:
    data_vars["DOXY_01"] = (["time", "station"], reshape(do))
    if 'flag_do_array' in locals():
        data_vars["DOXY_01_QC"] = (["time", "station"], reshape(flag_do_array))

#Potential Temperature
if 'pt' in locals() and pt is not None:
    data_vars["POTM_01"] = (["time", "station"], reshape(pt))
    if 'flag_pt_array' in locals():
        data_vars["POTM_01_QC"] = (["time", "station"], reshape(flag_pt_array))

# Sound Velocity
if 'svel' in locals() and svel is not None:
    data_vars["SVEL_01"] = (["time", "station"], reshape(svel))
    if 'flag_svel_array' in locals():
        data_vars["SVEL_01_QC"] = (["time", "station"], reshape(flag_svel_array))

# Always include datetime
data_vars["datetime"] = (["station", "time"], time_seconds.reshape(1, -1))

# Build dataset
ds = xr.Dataset(
    data_vars=data_vars,
    coords=dict(
        time=("time", time_seconds),
        station=("station", [0]),
        lat=("station", [lat]),
        lon=("station", [lon]),
        depth=("station", [round_p]),
    )
)

# Link QC flags
for var in ["TE90_01", "CNDC_01", "PRES_01", "PSAL_01", "POTM_01", "SVEL_01", "DOXY_01"]:
    qc_var = var + "_QC"
    if var in ds and qc_var in ds:
        ds[var].attrs["ancillary_variables"] = qc_var

# QC flag attributes
qc_attrs = {
    "long_name": "quality flag",
    "conventions": "WOCE",
    "flag_values": np.array([2, 3, 4, 5], dtype="i1"),
    "flag_meanings": "acceptable questionable bad missing",
    "_FillValue": 9,
    "coverage_content_type": "qualityInformation"
}
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
        "coverage_content_type": "physicalMeasurement",
        "reference_scale": "ITS-90",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(t)),
        "data_max": float(np.nanmax(t)),
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
        "coverage_content_type": "physicalMeasurement",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(c_adj)),
        "data_max": float(np.nanmax(c_adj)),
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
        "coverage_content_type": "physicalMeasurement",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(p)),
        "data_max": float(np.nanmax(p)),
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
        "coverage_content_type": "physicalMeasurement",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(s_adj)),
        "data_max": float(np.nanmax(s_adj)),
    })

if "DOXY_01" in ds:
    ds["DOXY_01"].attrs.update({
        "units": "ml l-1",
        "long_name": "dissolved oxygen",
        "standard_name": "moles_of_oxygen_per_unit_mass_in_sea_water",
        "sdn_parameter_urn": "SDN:P01::DOXMZZ01",  # Dissolved oxygen concentration
        "sdn_uom_urn": "UMLL",
        "sdn_uom_name": "Millilitres per litre",
        "generic_name": "oxygen",
        "coverage_content_type": "physicalMeasurement",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(do)),
        "data_max": float(np.nanmax(do)),
    })

if "POTM_01" in ds:
    ds["POTM_01"].attrs.update({
        "units": "degree_C",
        "long_name": "potential_temperature",
        "standard_name": "sea_water_potential_temperature",
        "sdn_uom_urn": "UPAA",
        "sdn_uom_name": "Degrees Celsius",
        "generic_name": "potential_temperature",
        "coverage_content_type": "physicalMeasurement",
        "reference_scale": "ITS-90",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(pt)),
        "data_max": float(np.nanmax(pt)),
    })

if "SVEL_01" in ds:
    ds["SVEL_01"].attrs.update({
        "units": "m s-1",
        "long_name": "sound_velocity",
        "standard_name": "speed_of_sound_in_sea_water",
        "sdn_parameter_urn": "SDN:P01::SVELXXXX",
        "sdn_uom_urn": "UVAA",
        "sdn_uom_name": "metres per second",
        "generic_name": "sound_velocity",
        "coverage_content_type": "physicalMeasurement",
        "sensor_type": "SBE37-SM",
        "sensor_depth": inst_depth,
        "serial_number": serial,
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(svel)),
        "data_max": float(np.nanmax(svel)),
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
        "coverage_content_type": "physicalMeasurement",
        "_FillValue": 1e35,
        "data_min": float(np.nanmin(time_seconds)),
        "data_max": float(np.nanmax(time_seconds)),
    })

# ---------------- Coordinate Attributes ----------------
ds["lat"].attrs.update({
    "units": "degrees_north",
    "standard_name": "latitude",
    "long_name": "latitude",
    "sdn_parameter_urn": "SDN:P01::ALATZZ01",
    "sdn_uom_urn": "SDN:P06::DEGN",
    "sdn_uom_name": "Degrees north"
})
ds["lon"].attrs.update({
    "units": "degrees_east",
    "standard_name": "longitude",
    "long_name": "longitude",
    "sdn_parameter_urn": "SDN:P01::ALONZZ01",
    "sdn_uom_urn": "SDN:P06::DEGE",
    "sdn_uom_name": "Degrees east"
})
ds["depth"].attrs.update({
    "units": "metres",
    "positive": "down",
    "standard_name": "depth",
    "long_name": "distance below the surface",
    "sdn_parameter_urn": "SDN:P01::ADEPZZ01",
    "sdn_uom_urn": "SDN:P06::ULAA",
    "sdn_uom_name": "Metres"
})

# ---------------- Global Attributes ----------------
ds.attrs.update({
    "Conventions": "CF-1.6, ACDD-1.3, IOOS-1.2",
    "standard_name_vocabulary": "CF Standard Name Table v80",
    "source": dataset_id,
    "id": dataset_id,
    "featureType": "timeseries",
    "cdm_data_type": "station",
    "data_type": data_type,
    "processing_level": processing,
    "country_code": country_code,
    "sdn_country_id": country, #SDN-C18 vocabulary
    "sdn_country_vocabulary": "http://vocab.nerc.ac.uk/collection/C18/current/",
    "institution": "DFO BIO",
    "sdn_institution_id": "SDN:EDMO::1811", #EDMO database, maintained by SeaDataNet #1811 is Woods Hole
    "sdn_institution_vocabulary": "https://edmo.seadatanet.org",
    "creator_type": "person",
    "creator_name": creator_name,
	"processor_name": processor_name,
    "creator_country": "Canada",
    "creator_email": creator_email,
	"processor_email": processor_email,
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
    "sdn_custodian_id": "SDN:EDMO::1811", #The Bedford Institute of Oceanography has a European Directory of Marine Organisations (EDMO) code  of 1811 http://edmo.seadatanet.org/report/1811
    "sdn_originator_id": "SDN:EDMO::1811",
    "sdn_creator_id": "SDN:EDMO::1811",
    "sdn_publisher_id": "SDN:EDMO::1811",
    "sdn_distributor_id": "SDN:EDMO::1979", #DFO data shop (MEDS)  has an EDMO code of 1979  https://edmo.seadatanet.org/report/1979
    "naming_authority": "ca.gc.bio",
    "license": "Open Government License - Canada, https://open.canada.ca/en/open-government-licence-canada",
    "infoUrl": "https://www.bio.gc.ca/science/newtech-technouvelles/observatory-observatoire-en.php",
    "inst_type": inst_type,
    "sampling_interval": sample_rate,
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
    "geospatial_vertical_max": round_p,
    "geospatial_vertical_min": round_p,
    "geospatial_vertical_units": "metres",
    "geospatial_vertical_positive": "down",
    "geospatial_bounds": f"POINT({lat} {lon})",
    "geospatial_bounds_crs": "EPSG:4326", #"EPSG:4326" corresponds to the WGS 84 coordinate system, commonly used for GPS coordinates.
    "geospatial_bounds_vertical_crs": "EPSG:5831", #"EPSG:5831" corresponds to the "Vertical CRS based on the EGM96 geoid model".
    "project": project,
    "program": program,
    "mission_description": program,
    "keywords": "Time-series, Marine-data, oceans, climate, water-temperature, salinity, mooring, moored-ctd, conductivity, pressure",
    "history": f"Created on {dtmod.datetime.utcnow().isoformat()}",
    "comment": ""   # start empty

})

#Preserve date_created if file exists, if it does not set to now
output_path = f"{directory}{site}{year_str}{mooring}{pres}_{serial}_CFcompliant_CTD.nc"
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
note("date_created and date_modified are recorded in UTC (Coordinated Universal Time)")

#Add processing notes to the comment: global attribute
for msg in processing_notes:
    update_comment(ds, msg)
update_comment(ds, "Final NetCDF created (CF-compliant)")

#Save NetCDF
ds.to_netcdf(output_path, format="NETCDF4", mode="w")
print(f"✔ Adaptive NetCDF file saved: {output_path}")

##
#%% Section 20: COMPUTE MEAN PRESSURE AND SAMPLE RATE ---
# SHN -- maybe redundant -- TBD
mean_pressure = np.mean(p)
print(f'Mean Pressure: {mean_pressure:.2f} db')
time_diff = np.diff(dt)  #Time differences between consecutive timestamps
time_diff_seconds = np.array([td.total_seconds() for td in time_diff])  #Convert to seconds
computed_sample_rate = np.mean(time_diff_seconds)
print(f"Computed Sample Rate: {computed_sample_rate:.2f} s")
