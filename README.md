# How to use this script (Quick Start) 
### **This section of readme is intended to be a concise summary of steps required to run code. Please refer to next section for detailed explanations, tips for identifying outliers, bugs you may come across, etc. 
1. For each file to be processed, create new folder locally containing: 
     * original CTD file from instrument (M0000_SN00000.cnv)
     *
     * 
2. Download CTD_process.py and save as CTD_process_M0000_SN00000.py to same folder
3. In section 2:
     * add your info to creator_name and creator_email fields
     * change directory to ` f'./' `
     * change filename to `M0000_SN00000.cnv`
     * reference excel spreadsheet and update metadata fields
4. In section 9B:
     * Choose trim indices by using the figure generated in Section 9A
     * Change start and finish fields accordingly
     * ★ because original variable is trimmed in this step (`t = t[start:finish]`), if you want to change trim indices after you've already trimmed it's reccomended to start again at Section 1
5. Section 13: 
     * Select which variables are to be flagged (e.g. `flag_c = True` if conductivity should be flagged)
     * Using the figures created to identify erroneous points, manually enter each index to be flagged and it's corresponding WHOCE flag
6. Section 19:
     * Add notes if needed in `"comment": ""` line of global attributes field

# Detailed section notes 
1. Import Packages
2. Metadata
3. Load Raw Data
     * ctd processing package does not recognize all header keys (i.e. prdM). Code added so that headers aren't missed, but check that all expected raw keys are being read in this section.
4. Save Raw Data as NetCDF
5. Extract Variables
     * check that raw keys from previous section are in variable map
6. Check time data (Figure created, looking for straight line with no jumps)
   <img width="600" height="400" alt="time_check" src="https://github.com/user-attachments/assets/b3a739f8-8461-4439-8b2c-e39a3fe43cbb" />
7. Time Correction (if required)
8. Correct for clock drift
9. Trim indices
10. Temperature Salinity Plot
11. Temperature Salinity Plot
12. Manual Data Inspection
     * Spike data suggestions. Default is the despike function from ctd toolbox but this performs poorly and may not be suitable for our data (e.g. the 'block' parameter is supposed to be the expected length of spikes, theoretically 1 or 2, yet is set to 200)
     * Optional, if you set `Use_CHS_Func = True`
   
