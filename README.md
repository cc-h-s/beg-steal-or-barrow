# Processing 101 
### **This section of readme is intended to be a concise summary of steps required to run code. Please refer to next section for detailed explanations, tips for identifying outliers, bugs you may come across, etc. 
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
6. Section 19:
     * Add notes if needed in `"comment": ""` line of global attributes field

# Detailed section notes 
1. Import Packages
2. Metadata 
3. Load Raw Data
     * ctd processing package does not recognize all header keys (i.e. prdM). Code added so that headers aren't missed, but check that all      expected raw keys are being read correctly in this section.
4. Save Raw Data as NetCDF
5. Extract Variables
     * Check that raw keys from previous section are in variable map.
     * ★ 'p' for Seabird instruments is sea pressure, but for RBR it's *raw* pressure. Code added to convert p from RBR instruments to sea pressure. If in doubt, load original file into Ruskin to ensure p is correct. 
6. Check time data (Figure created, looking for straight line with no jumps)
   <img width="600" height="400" alt="time_check" src="https://github.com/user-attachments/assets/b3a739f8-8461-4439-8b2c-e39a3fe43cbb" />
7. Time Correction (Legacy code from Kurtis Anstey, rarely required) 
8. Correct for clock drift
     * Added print out in previous section to tell user whether cnv_jd_drift or datetime_drift should be True. 
     * Added Drift_Recorded to improve note recorded at the end of this section. If drift is recorded, set to true and change tot_drift accordingly. If no Drift_Recorded, Drift_Recorded = False and tot_drift = 0         
9. Trim indices
     * Tip: Use pressure to select indices, usually last sensor to stabilize
     * ★ because original variables are trimmed in this step (`t = t[start:finish]`), if you want to change trim indices after you've already trimmed, start again at Section 1.
10. Temperature Salinity Plot
11. Temperature Salinity Plot (Interactive) 
12. Manual Data Inspection
     * Spike data suggestions. Default is the despike function from ctd toolbox but this performs poorly and may not be suitable for our data (e.g. the 'block' parameter is supposed to be the expected length of spikes, theoretically 1 or 2, yet is set to 200). This filter also crashes with large datasets. Can still be used if Use_CHS_Func = False
     * Use_CHS_Func = True will use a Hampel filter to suggest outliers. This filter uses a rolling median and rolling median absolute deviation (MAD) to identify outliers.
     * The most accurate hampel filter is very slow for large datasets, so hampel_fast was added and will automatically run on variables longer than 200,000 points (this can be customized). The difference between the two is how MAD is calculated, the original is exact and the fast version uses an approximation.
     * The majority of "spikes" are single outliers that occur with sharp changes observed (more commonly in conductivity than temperature, often negative). Narrow windows are preferred to identify these spikes, often caused by air bubbles or electrical noise.
     * For setting the n, values of 3-4 are typical, and n > 5 is conservative (less flags). If you are finding that the filter is flagging too many points even when n is set high, the problem is that there is too little variability across some periods of the timeseries and MAD becomes extremely small. There is a floor_mad variable included that sets a minimum for MAD and prevents it from collapsing. If n is already high, try increasing this value to get a more reasonable number of flags. 
   
