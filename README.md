# How to use this script 
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
