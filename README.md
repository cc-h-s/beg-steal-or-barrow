# Processing 101 - Quick Start
### **This section is intended to be a concise summary of steps required to run code. Please refer to next section for detailed explanations, tips for identifying outliers, bugs you may come across, updates to code, etc. 
1. For each file to be processed, create new folder locally containing: 
     * original CTD file from instrument (M0000_SN00000.cnv)
     * Any auxiliary files from instrument
2. Download CTD_process.py and save as CTD_process_M0000_SN00000.py (or similar) to same folder
3. In section 2:
     * change directory to ` f'./' `
     * change filename (i.e. `M0000_SN00000.cnv`)
     * reference excel spreadsheet and update metadata fields
4. In section 9B:
     * Choose trim indices by using the figure generated in Section 9A
     * Change start and finish fields accordingly
5. Section 13: 
     * Select which variables are to be flagged (e.g. `flag_c = True` if conductivity should be flagged)
     * Use the figures created to identify outliers that are likely not true measurements. Manually enter each index to be flagged and it's corresponding WOCE flag (3 if questionable, 4 if clearly bad datum). 

# Detailed section notes 
1. Import Packages
2. Metadata
   #### These are all the fields that need to be reviewed and/or updated for each file. The lock symbol indicates fields that will generally be the same for an entire set of files. All other fields need to be altered for each instrument. To complete this section reference the mooring logs for instrument deployment. Specific codes can be found here: https://vocab.seadatanet.org/search.

    - 🔒 `creator_name = "Clark Richards"` Creator fields should be whoever processes the file, or whoever is most familiar with the processing of the file, *and* is likely to be available to contact about file for the forseeable future.
    - 🔒 `creator_email = "Clark.Richards@dfo-mpo.gc.ca"`

    * `directory = f'./Barrow_RawData/'` directory of raw data file, change to: f'./' when file in same folder as processing script 
    * `filename = 'M2170_SN22954.cnv'` 
    - 🔒 `year_n = 2022`  year deployed, not recovered
    - 🔒 `chief_scientist = "Clark Richards"` 
    - 🔒 `cruise_number = 'RAD2022375'` 
    - 🔒 `deployment_name = "CCGS PIERRE RADISSON"`  deployment refers to the vessel
    - 🔒 `sdn_deployment_id = "SDN:C17::18RD"` SDN-C17 vocabulary #18RD = RADISSON; 18GO = Des Gros

    * `site = 'BS-SOUTH-CENTRAL'` mooring site (eg. BS-SOUTH, BS-SOUTH-CENTRAL, etc.)
    * `mooring = 'M2170'`
    * `latdeg = 74`
    * `latdec = 11.874`  latitude in degrees and decimal minutes
    * `londeg = 90`
    * `londec = 49.038`  longitude in degrees and decimal minutes
    - 🔒 `platform = "mooring"`
    - 🔒 `sdn_platform_id = "SDN:L06::48, SDN:L06::43"` SDN-L06 vocabulary #EX. 48 = mooring, 43 = subsurface mooring
      
    * `corr_water_depth = 259`  in metres, from sounding
    - 🔒 `data_type = "moored CTD"` data type (for netcdf, eg. moored CTD)
    - 🔒 `instrument_type = "MCTD"` short form (eg. MCTD)
    - `inst_type = "Microcat"` instrument type (for netcdf, eg. Microcat)
    * `instrument_model = "SBE37-SM"`  instrument model, eg. SBE37-SM, SBE37-SMP, SBE37-SMP-ODO, RBR Solo, RBR Concerto
    * `serial = 'SN22954'`  instrument serial number 
    - 🔒 `project = "Barrow Strait Monitoring and Real Time Observatory Project"`
    - 🔒 `program = "Maritimes Region Barrow Strait Monitoring Program"`
    - 🔒 `location = "Barrow Strait"`
    - 🔒 `country = "SDN:C32::CA, SDN:C18::18"` SDN C32 vocabulary, CA = CANADA
    - 🔒 `country_code = "1810"` 1810 = CANADA
    - 🔒 `cruise_name = "mooring deployment"` generic descriptor for the cruise

I added code for the following fields that assigns the correct id based on `instrument_model`:

    if instrument_model == "SBE37-SM" or instrument_model == "SBE37-SMP":
        `sdn_instrument_id = "SDN:L22::TOOL1456"`
        `sdn_device_id = "SDN:L05::350, SDN:L05::130, SDN:L05::134, SDN:L05::WPS"`

This currently works for SBE37-SM, SBE37-SMP, SBE37-SMP-ODO, RBR Solo, RBR Concerto, and RBR Duet. Other instruments can be added as needed. 

4. Load Raw Data
     * ctd processing package does not recognize all header keys (i.e. prdM). Code added so that headers aren't missed, but check that all expected raw keys are being read correctly in this section.
5. Save Raw Data as NetCDF
6. Extract Variables
     * Check that raw keys from previous section are in variable map.
     * ★ 'p' for Seabird instruments is sea pressure, but for RBR it's *raw* pressure. Code added to convert p from RBR instruments to sea pressure. If in doubt, load original file into Ruskin to ensure p is correct. 
7. Check time data (Figure created, looking for straight line with no jumps)
   <img width="600" height="400" alt="time_check" src="https://github.com/user-attachments/assets/b3a739f8-8461-4439-8b2c-e39a3fe43cbb" />
8. Time Correction (Legacy code from Kurtis Anstey, rarely required. (but if you have questions ask him). 
9. Correct for clock drift
     * Added print out in previous section to tell user whether cnv_jd_drift or datetime_drift should be True. 
     * Added Drift_Recorded to improve note recorded at the end of this section. If drift is recorded, set to true and change tot_drift accordingly. If no Drift_Recorded, `Drift_Recorded = False` and `tot_drift = 0`         
10. Trim indices
     * Tip: Use pressure to select indices, usually last sensor to stabilize
     * ★ because original variables are trimmed in this step (`t = t[start:finish]`), if you want to change trim indices after you've already trimmed, start again at Section 1.
11. Temperature Salinity Plot
     * If there is a strong T-S correlation observed during the deployment, these plots can be useful for identifying outliers.
12. Temperature Salinity Plot (Interactive) 
13. A) Manual Data Inspection
     * Spike data suggestions. Default is the despike function from ctd toolbox but this performs poorly and may not be suitable for our data (e.g. the 'block' parameter is supposed to be the expected length of spikes, theoretically 1 or 2, yet is set to 200). This filter also crashes with large datasets. Can still be used if Use_CHS_Func = False
     * Use_CHS_Func = True will use a Hampel filter to suggest outliers. This filter uses a rolling median and rolling median absolute deviation (MAD) to identify outliers.
     * The most accurate hampel filter is very slow for large datasets, so hampel_fast was added and will automatically run on variables longer than 200,000 points (this can be customized). The difference between the two is how MAD is calculated, the original is exact and the fast version uses an approximation.
     * The majority of "spikes" are single outliers that occur with sharp changes observed (more commonly in conductivity than temperature, often negative). Narrow windows are preferred to identify these spikes, often caused by air bubbles or electrical noise.
     * For setting the n, values of 3-4 are typical, and n > 5 is conservative (less flags). If you are finding that the filter is flagging too many points even when n is set high, the problem is that there is too little variability across some periods of the timeseries and MAD becomes extremely small. There is a floor_mad variable included that sets a minimum for MAD and prevents it from collapsing. If n is already high, try increasing this value to get a more reasonable number of flags.

    12B) Flagging
     * All flags are recorded here for measured variables temperature, conductivity, pressure, and oxygen. Derived variables inherit relevant flags.
---
12 option: Use suggested flags (`Flag_From_Filter = True`)
- For some files that sample at a very high rate, it takes a lot of time to manually qc the entire timeseries (millions of observations) and may cause the program to crash depending on the machine you are using and memory available. In these cases, it may be useful to have the option to use the suggested flags. 
- This option (`Flag_From_Filter = True`) will use flags from the Hampel filter in *addition* to any flags you manually enter. 
- Using suggested flags still requires user input and supervision: the filter should be tuned and reviewed to ensure it is doing a reasonable job of flagging bad data. 
- Using this option will automatically update the processing note to indicate how flagging was done, as well as the filter parameters used. 
- All flags from filter are automatically flagged as 3 (questionable).
- This is also a good option if you are processing a file preliminarily, and plan to return to it at a later date for a thorough manual flagging. 
___
       
13. Plots
14. Conductivity Offset
     * Updated to improve processing note. Set cond_offset to False and c_offset to 1 if no CTD data available for comparison. 
15. Derive Quantities from Temperature and Salinity
16. pt and svel derive flags from component variables
17. Compute Pressure to calculate instrument depth
     * Instrument depth was originally recorded just as mean p, now calculated using the median of pressure and latitude.
     * If there is no pressure measured by instrument, set assumed instrument depth. Update note in this section with relevant info about how this assumption was made (from sounding depth, position on mooring, relative to other instrument on mooring, etc.). No pressure variable is generally only the case for RBR Solo's.
18. Create Objects for NetCDF
     * This section calculates variable min and max recorded in metadata by excluding all flagged variables.
     * The second part of this section is for recording mooring movement during the deployment. If the mooring moved (evident from pressure timeseries reviewed in flagging section), set Mooring_Move to True and change the index of the shift accordingly. If numerous data were distorted during this shift, change index_impact to the approximate length of bad data. Intrument depth is then calculated for before and after the shift and recorded in the processing notes along with the date of the shift. The very last note in the section is for any additional notes about why the mooring moved (suspected causes, known recovery for maintenance, etc.)
19. Create NetCDF Variables
     * This is where all the variables are prepared for CIOOS compliant file and shouldn't require any changes.
     * If there is additional information about the deployment/processing not recorded in the comment earlier in the script, add it at the end before the file is saved using `note("Additional important info")`. 

## Let's check! 
### Once you've run the processing script, check for any inconsistencies between the metadata and the log sheets: 

1. Instrument depth
   * Check that instrument is close to target depth by referencing the mooring diagram. Any offset present should be the approximate difference between the depth on the mooring diagram and the sounding depth recorded during deployment.
   * Confirm that instrument depth makes sense relative to other instruments on mooring. Locations on mooring are not exact (it is unlikely for calculated depths of two instruments to be precisely 20.0 m apart as designed), but if anything is off by more than a couple metres it should be investigated (could be error on mooring diagram, pressure converted incorrectly, change of plans during mooring deployment, etc.)
   * If instrument is at unexpected depth it may be necessary to add note to file comment.
2. Sampling rate
   * Confirm that true sample_rate is the same as the target sample_rate recorded in instrument log files.
3. Variables
   * Check that all expected variables exist in the final file and that values are reasonable for mooring location (max and min are recorded in metadata).
4. Everything else
   * Generate report by uploading file to [compliance checker](https://compliance.ioos.us/index.html) with appropriate convention selected (i.e. CF 1.6) to make sure the file is compliant. Look through the metadata and check that all fields are correct and appropriate.

# Suggested next steps 
### This script should run without issue, but there are a few ways the workflow should or could be improved upon. 

1. Update variable names so that original variables are not overwritten when trimmed. This would allow changes to trim indices after trimming without requiring the variables to be reloaded.
2. Update conversion of p for RBR files from raw pressure to sea pressure so that it can't get accidentally converted more than once if the section is run again. (Easy fix: Add while loop with flag that is set in previous section, so that conversion will only run once unless variables reloaded).
3. Add a section that checks for stationarity of variables across deployment to identify any sensor drift.
4. Possible accompanying file: plots data from all instruments on single mooring to check that all measurements make sense relative to other observations in water column. This script would then edit the comment of the .nc file to record that this test was done and that observations are within expected range.
5. For files with high sampling rate, changes are necessary to be able to efficiently and accurately flag data. This could include: plotting the timeseries in chunks so that the data can be scanned thoroughly without the figure window lagging/crashing. In some instances there are hundreds of flags manually recorded which aren't easily transcribed directly into the script: add an option for the processing script to read in an excel file where flags have been recorded.
6. When using the option to use flags from filter, the current script sets these all to 3 (questionable). It would make sense to assign these indices flags based on how much they exceed the threshold. This would allow user to set conservative filter parameters (more flags, possibly including some false negatives as to not miss any true negatives) but still have extreme statistical outliers to be flagged as 4. 
