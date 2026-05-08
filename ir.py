import sys
import os
import traceback

try:
    # --- YOUR ACTUAL IR.PY CODE STARTS HERE ---
    import pandas as pd
    import numpy as np
    from pathlib import Path
    from datetime import datetime
    import tkinter as tk
    from tkinter import messagebox
    from config import state
    from gui import SetupGUI, PlotViewer    

    # (The imports at the top of your file stay exactly the same)

    def robust_read_ftir(filepath):
        if filepath.suffix.lower() == '.xlsx':
            df = pd.read_excel(filepath, header=None)
            df = df.apply(pd.to_numeric, errors='coerce').dropna()
            if not df.empty and df.shape[1] >= 2:
                return df.iloc[:, 0].values, df.iloc[:, 1].values
            return np.array([]), np.array([])
            
        data_x, data_y = [], []
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean_line = line.replace('\t', ',').replace(';', ',').replace(' ', ',')
                parts = [p for p in clean_line.split(',') if p.strip()]
                if len(parts) >= 2:
                    try:
                        data_x.append(float(parts[0]))
                        data_y.append(float(parts[1]))
                    except ValueError:
                        pass 
                        
        return np.array(data_x), np.array(data_y)

    def load_data_files(root_window):
        # We unified the files logic in gui.py, so we just read from state.settings['files']
        file_list = [Path(f) for f in state.settings.get('files', [])]
            
        if not file_list:
            messagebox.showerror("Error", "No files selected or found.", parent=root_window)
            return False # <--- Changed from sys.exit()

        accepted_formats = ".dpt, .csv, .txt, .xy, .xlsx"
        bad_files = []

        for p in file_list:
            try:
                x, y = robust_read_ftir(p)
                if len(x) > 10: 
                    state.all_data.append((p.stem, x, y))
                else:
                    bad_files.append(p)
            except Exception:
                bad_files.append(p)

        # --- NEW: ERROR HANDLING POP-UP ---
        if bad_files:
            ext = bad_files[0].suffix.lower() if bad_files[0].suffix else "Unknown"
            msg = (f"You uploaded a file format '{ext}' which is not processed by the program.\n\n"
                   f"Please upload the list of these formats: {accepted_formats}, or try a different format file.")
            messagebox.showerror("File Format Error", msg, parent=root_window)
            
            # If no files worked at all, we must return to setup
            if not state.all_data:
                return False # <--- Changed from sys.exit()
        # ----------------------------------
        
        return True # <--- Signal that the files loaded successfully!

    def main():
               
        from config import state
        state.technique = 'FTIR'
        
        # ==========================================
        # RETRY LOOP: Keeps app open if files fail
        # ==========================================
        while True:
            state.all_data.clear() # Clear out old memory if we are retrying
            
            root = tk.Tk()
            setup_app = SetupGUI(root)
            root.mainloop()

            if not setup_app.ready: 
                sys.exit() # If they clicked the red X to close the window, actually close.

            dummy_root = tk.Tk()
            dummy_root.withdraw() 

            if getattr(setup_app, 'loaded_from_session', False):
                break # Success! Break the loop and go to plotter.
            else:
                if load_data_files(dummy_root):
                    state.init_file_settings()
                    break # Success! Break the loop and go to plotter.
                else:
                    # FAILED! Destroy hidden window, 'continue' restarts the loop to show SetupGUI
                    dummy_root.destroy()
                    continue 
        # ==========================================

        mode = state.settings.get('mode', 'individual')

        if mode in ['overlay', 'stack']:
            title = "Overlay Mode" if mode == 'overlay' else "Stacked Grid Mode"
            
            # Note: We removed the 'out_dir=' argument from PlotViewer here
            viewer = PlotViewer(dummy_root, state.all_data, title, out_dir=None)
            dummy_root.wait_window(viewer)
            
        elif mode == 'individual':
            for i, data_tuple in enumerate(state.all_data):
                stem = data_tuple[0]
                
                # 👻 GHOST SUB-FOLDER CREATION DELETED FROM HERE! 👻
                
                viewer = PlotViewer(dummy_root, [data_tuple], f"File {i+1}/{len(state.all_data)}: {stem}", out_dir=None)
                dummy_root.wait_window(viewer)

        dummy_root.destroy()

    if __name__ == "__main__":
        main()

# --- THE FAILSAFE ---
except Exception as e:
    # If the app crashes, write the exact error to a text file!
    with open("CRASH_REPORT.txt", "w") as f:
        f.write("THE APP CRASHED. HERE IS THE EXACT ERROR:\n\n")
        f.write(traceback.format_exc())