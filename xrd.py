import sys
import traceback
import pandas as pd
import numpy as np
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from config import state
from gui import SetupGUI, PlotViewer

def robust_read_xrd(filepath):
    """Reads XRD data (.csv, .txt, .dat, .asr) skipping text headers from diffractometers."""
    
    # Handle Excel files if someone saved them that way
    if filepath.suffix.lower() == '.xlsx':
        df = pd.read_excel(filepath, header=None)
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        if not df.empty and df.shape[1] >= 2:
            return df.iloc[:, 0].values, df.iloc[:, 1].values
        return np.array([]), np.array([])
        
    # Handle Text-based files (.dat, .txt, .csv, .asr, .raw if text)
    data_x, data_y = [], []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Standardize delimiters: replace tabs and semicolons with spaces, then split
            clean_line = line.replace('\t', ' ').replace(';', ' ').replace(',', ' ')
            parts = [p for p in clean_line.split(' ') if p.strip()]
            
            if len(parts) >= 2:
                try:
                    # If the line contains numbers, save them. 
                    # If it's a text header (like "ScanType=Continuous"), this fails and skips safely!
                    data_x.append(float(parts[0]))
                    data_y.append(float(parts[1]))
                except ValueError:
                    pass 
                    
    return np.array(data_x), np.array(data_y)

def load_data_files(root_window):
    file_list = [Path(f) for f in state.settings.get('files', [])]
    if not file_list:
        messagebox.showerror("Error", "No files selected or found.", parent=root_window)
        return False # <--- Changed to False to trigger the retry loop

    accepted_formats = ".csv, .txt, .xy, .dat, .xlsx"
    bad_files = []

    for p in file_list:
        try:
            x, y = robust_read_xrd(p)
            if len(x) > 10: 
                state.all_data.append((p.stem, x, y))
            else:
                bad_files.append(p)
        except Exception as e:
            bad_files.append(p)
            
    # --- NEW: ERROR HANDLING POP-UP ---
    if bad_files:
        ext = bad_files[0].suffix.lower() if bad_files[0].suffix else "Unknown"
        msg = (f"You uploaded a file format '{ext}' which is not processed by the program.\n\n"
               f"Please upload the list of these formats: {accepted_formats}, or try a different format file.")
        messagebox.showerror("File Format Error", msg, parent=root_window)
        
        # If no files worked at all, return to setup
        if not state.all_data:
            return False 
    # ----------------------------------
            
    state.technique = 'XRD'
    return True # <--- Signal that at least one file loaded successfully!

def main():
    # --- THE TRAFFIC COP ---
    state.technique = 'XRD'
    
    # Set default global axes labels for XRD
    state.global_set['xlabel'] = '2θ (°)'
    state.global_set['ylabel'] = 'Intensity (a.u.)'
    # -----------------------

    # ==========================================
    # RETRY LOOP: Keeps app open if files fail
    # ==========================================
    while True:
        state.all_data.clear() # Clear out old memory if we are retrying
        
        root = tk.Tk()
        setup_app = SetupGUI(root)
        root.mainloop()

        if not setup_app.ready: sys.exit() # If they clicked the red X

        dummy_root = tk.Tk()
        dummy_root.withdraw() 

        if getattr(setup_app, 'loaded_from_session', False):
            break # Success! Break the loop and go to plotter.
        else:
            if load_data_files(dummy_root):
                state.init_file_settings()
                break # Success! Break the loop and go to plotter.
            else:
                # FAILED! Destroy hidden window, 'continue' restarts the loop to show   GUI
                dummy_root.destroy()
                continue 
    # ==========================================

    mode = state.settings.get('mode', 'individual')

    if mode in ['overlay', 'stack']:
        title = "XRD Overlay Mode" if mode == 'overlay' else "XRD Stacked Grid Mode"
        viewer = PlotViewer(dummy_root, state.all_data, title, out_dir=None)
        dummy_root.wait_window(viewer)
        
    elif mode == 'individual':
        for i, data_tuple in enumerate(state.all_data):
            stem = data_tuple[0]
            viewer = PlotViewer(dummy_root, [data_tuple], f"XRD File {i+1}/{len(state.all_data)}: {stem}", out_dir=None)
            dummy_root.wait_window(viewer)

    dummy_root.destroy()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open("CRASH_REPORT_XRD.txt", "w") as f:
            f.write(traceback.format_exc())