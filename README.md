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
     * Using the figures created to identify erroneous points, manually enter each index to be flagged and it's corresponding WOCE flag

# Detailed section notes 
1. Import Packages
2. Metadata 
3. Load Raw Data
     * ctd processing package does not recognize all header keys (i.e. prdM). Code added so that headers aren't missed, but check that all expected raw keys are being read correctly in this section.
4. Save Raw Data as NetCDF
5. Extract Variables
     * Check that raw keys from previous section are in variable map.
     * ★ 'p' for Seabird instruments is sea pressure, but for RBR it's *raw* pressure. Code added to convert p from RBR instruments to sea pressure. If in doubt, load original file into Ruskin to ensure p is correct. 
6. Check time data (Figure created, looking for straight line with no jumps)
   <img width="600" height="400" alt="time_check" src="https://github.com/user-attachments/assets/b3a739f8-8461-4439-8b2c-e39a3fe43cbb" />
7. Time Correction (Legacy code from Kurtis Anstey, rarely required) 
8. Correct for clock drift
     * Added print out in previous section to tell user whether cnv_jd_drift or datetime_drift should be True. 
     * Added Drift_Recorded to improve note recorded at the end of this section. If drift is recorded, set to true and change tot_drift accordingly. If no Drift_Recorded, `Drift_Recorded = False` and `tot_drift = 0`         
9. Trim indices
     * Tip: Use pressure to select indices, usually last sensor to stabilize
     * ★ because original variables are trimmed in this step (`t = t[start:finish]`), if you want to change trim indices after you've already trimmed, start again at Section 1.
10. Temperature Salinity Plot
     * If there is a strong T-S correlation observed during the deployment, these plots can be useful for identifying outliers.
11. Temperature Salinity Plot (Interactive) 
12. A) Manual Data Inspection
     * Spike data suggestions. Default is the despike function from ctd toolbox but this performs poorly and may not be suitable for our data (e.g. the 'block' parameter is supposed to be the expected length of spikes, theoretically 1 or 2, yet is set to 200). This filter also crashes with large datasets. Can still be used if Use_CHS_Func = False
     * Use_CHS_Func = True will use a Hampel filter to suggest outliers. This filter uses a rolling median and rolling median absolute deviation (MAD) to identify outliers.
     * The most accurate hampel filter is very slow for large datasets, so hampel_fast was added and will automatically run on variables longer than 200,000 points (this can be customized). The difference between the two is how MAD is calculated, the original is exact and the fast version uses an approximation.
     * The majority of "spikes" are single outliers that occur with sharp changes observed (more commonly in conductivity than temperature, often negative). Narrow windows are preferred to identify these spikes, often caused by air bubbles or electrical noise.
     * For setting the n, values of 3-4 are typical, and n > 5 is conservative (less flags). If you are finding that the filter is flagging too many points even when n is set high, the problem is that there is too little variability across some periods of the timeseries and MAD becomes extremely small. There is a floor_mad variable included that sets a minimum for MAD and prevents it from collapsing. If n is already high, try increasing this value to get a more reasonable number of flags.

    12B) Flagging
     * All flags are recorded here for measured variables temperature, conductivity, pressure, and oxygen. Derived variables inherit relevant flags.
---
12 option: Use suggested flags (`Flag_From_Filter = True`)
     * For some files that sample at a very high rate, it takes a lot of time to manually qc the entire timeseries (millions of observations) and may cause the program to crash depending on the machine you are using and memory available. In these cases, it may be useful to have the option to use the suggested flags. 
     * This option (`Flag_From_Filter = True`) will use flags from the Hampel filter in *addition* to any flags you manually enter. 
     * Using suggested flags still requires user input and supervision: the filter should be tuned and reviewed to ensure it is doing a reasonable job of flagging questionable points. 
     * Using this option will automatically update the processing note to indicate how flagging was done, and the filter options selected. 
     * All flags from filter are automatically flagged as 3 (questionable).
     * This is also a good option if you are processing a file preliminarily, and plan to return to it at a later date for a thorough manual flagging. 
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
