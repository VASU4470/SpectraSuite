import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import Cursor
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from pathlib import Path

from config import state
from processing import process_spectrum

def apply_global_aesthetics(ax, min_xs, max_xs, min_ys, max_ys, is_stack_mode=False):
    gs = state.global_set
    
    # --- SAFE AXIS INVERSION CHECK ---
    if getattr(state, 'technique', 'FTIR') == 'FTIR':
        if gs.get('xlim'): ax.set_xlim(max(gs['xlim']), min(gs['xlim']))
        else: ax.set_xlim(max(max_xs), min(min_xs)) 
    else:
        if gs.get('xlim'): ax.set_xlim(min(gs['xlim']), max(gs['xlim']))
        else: ax.set_xlim(min(min_xs), max(max_xs))
    # ---------------------------------
    
    # --- FIXED Y-LIMITS FOR STACKED GRID ---
    if gs.get('ylim'): 
        ax.set_ylim(min(gs['ylim']), max(gs['ylim']))
    elif not is_stack_mode: 
        # Only force global Y-limits if we are on a single Overlay plot
        b = (max(max_ys) - min(min_ys)) * 0.05
        ax.set_ylim(bottom=min(min_ys) - b, top=max(max_ys) + b)
        
    try:
        if gs.get('xstep'): ax.xaxis.set_major_locator(ticker.MultipleLocator(float(gs['xstep'])))
        if gs.get('ystep'): ax.yaxis.set_major_locator(ticker.MultipleLocator(float(gs['ystep'])))
    except ValueError: pass
    
    if gs.get('show_minor'): ax.minorticks_on()
    else: ax.minorticks_off()
        
    if not gs.get('show_tick_lbls', True):
        ax.set_xticklabels([])
        ax.set_yticklabels([])
    
    if gs.get('title'): ax.set_title(gs['title'], fontweight="bold")
    if gs.get('xlabel'): ax.set_xlabel(gs['xlabel'], fontweight="bold")
    if gs.get('ylabel'): ax.set_ylabel(gs['ylabel'], fontweight="bold")

class SetupGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Processing Suite Launcher")
        self.root.geometry("500x700") # Made slightly wider and taller for new buttons
        self.root.minsize(450, 650)
        
        try:
            # Dynamically load the correct icon based on the session!
            if getattr(state, 'technique', 'FTIR') == 'XRD':
                app_icon = tk.PhotoImage(file='xrd_icon.png')
            else:
                app_icon = tk.PhotoImage(file='ir_icon.png')
            self.root.iconphoto(False, app_icon)
        except Exception:
            pass # If the icon is missing, just ignore it and keep running
        
        self.ready = False
        self.loaded_from_session = False 
        
        self.is_all_var = tk.BooleanVar(value=False) 
        self.plot_mode_var = tk.StringVar(value="individual")
        self.smooth_var = tk.IntVar(value=15)
        
        # Memory for the file browser
        self.last_open_dir = None 
        
        if 'files' not in state.settings or not isinstance(state.settings.get('files'), list):
            state.settings['files'] = []
            
        self._build_ui()

    def _build_ui(self):
        ttk.Label(self.root, text="Data Processing Suite", font=("Arial", 16, "bold")).pack(pady=10)
        
        f_frame = ttk.LabelFrame(self.root, text="1. Select & Arrange Data", padding=10)
        f_frame.pack(fill="x", padx=15, pady=5)
        
        self.lbl_f = ttk.Label(f_frame, text="Loaded: 0 file(s) ready", font=("Arial", 10, "bold"))
        self.lbl_f.pack(pady=5)
        
        btn_f = ttk.Frame(f_frame)
        btn_f.pack(fill="x", pady=2)
        ttk.Button(btn_f, text="📂 Add Folder", command=self.browse_folder).pack(side="left", expand=True, padx=2)
        ttk.Button(btn_f, text="📄 Add Files", command=self.browse_files).pack(side="right", expand=True, padx=2)
        
        # --- Listbox and Reorder Frame ---
        list_container = ttk.Frame(f_frame)
        list_container.pack(fill="x", pady=5)
        
        self.file_listbox = tk.Listbox(list_container, height=6, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        
        # Double-click to remove binding
        self.file_listbox.bind('<Double-1>', lambda e: self.remove_selected())
        
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.file_listbox.yview)
        scrollbar.pack(side="left", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        # Reorder Buttons (Up/Down)
        reorder_f = ttk.Frame(list_container)
        reorder_f.pack(side="right", fill="y", padx=(5, 0))
        ttk.Button(reorder_f, text="⬆️", width=3, command=self.move_up).pack(side="top", pady=(0, 2))
        ttk.Button(reorder_f, text="⬇️", width=3, command=self.move_down).pack(side="top", pady=2)
        # ---------------------------------
        
        action_btn_f = ttk.Frame(f_frame)
        action_btn_f.pack(fill="x", pady=(2, 0))
        ttk.Button(action_btn_f, text="➖ Remove Selected", command=self.remove_selected).pack(side="left", expand=True, padx=2)
        ttk.Button(action_btn_f, text="🗑️ Clear All", command=self.clear_selection).pack(side="right", expand=True, padx=2)

        m_frame = ttk.LabelFrame(self.root, text="2. Plotting Mode", padding=10)
        m_frame.pack(fill="x", padx=15, pady=5)
        ttk.Radiobutton(m_frame, text="Individual Plots", variable=self.plot_mode_var, value="individual").pack(anchor="w")
        ttk.Radiobutton(m_frame, text="Stacked Grid", variable=self.plot_mode_var, value="stack").pack(anchor="w")
        ttk.Radiobutton(m_frame, text="Overlay", variable=self.plot_mode_var, value="overlay").pack(anchor="w")
        
        s_frame = ttk.Frame(m_frame)
        s_frame.pack(fill="x", pady=5)
        ttk.Label(s_frame, text="Default Smoothing (Pts):").pack(side="left")
        ttk.Entry(s_frame, textvariable=self.smooth_var, width=5).pack(side="left", padx=10)

        # ==========================================
        # SUPPORTED FORMATS INFO BOX (DYNAMIC)
        # ==========================================
        info_frame = ttk.LabelFrame(self.root, text="ℹ️ Supported File Formats", padding=10)
        info_frame.pack(fill="x", padx=15, pady=10)

        # Show FT-IR formats if ir.py called this window
        if getattr(state, 'technique', 'FTIR') == 'FTIR':
            ttk.Label(info_frame, text="FT-IR Spectroscopy:", font=("Arial", 10, "bold")).pack(anchor="w")
            ttk.Label(info_frame, text="• .dpt or .csv or .txt or .xy or (Comma, Tab, or Space separated Text File)").pack(anchor="w", padx=10, pady=(2, 0))
            
        # Show XRD formats if xrd.py called this window
        elif getattr(state, 'technique', 'FTIR') == 'XRD':
            ttk.Label(info_frame, text="X-Ray Diffraction:", font=("Arial", 10, "bold")).pack(anchor="w")
            ttk.Label(info_frame, text="• .csv or .txt or .xy or .dat or (Standard 2-Column X/Y Numeric Data)").pack(anchor="w", padx=10, pady=(2, 0))
        # ==========================================
        
        ttk.Button(self.root, text="🚀 Launch Processing", command=self.start).pack(pady=10)
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', pady=10)
        ttk.Button(self.root, text="📂 Load Previous Session (.json)", command=self.load_session_cmd).pack(pady=5)

    def _update_file_count(self):
        count = len(state.settings['files'])
        self.lbl_f.config(text=f"Loaded: {count} file(s) ready")

    def _add_to_list(self, file_paths):
        duplicates = 0
        added = 0
        
        for path in file_paths:
            p_str = str(Path(path).resolve()) 
            if p_str not in state.settings['files']:
                state.settings['files'].append(p_str)
                self.file_listbox.insert(tk.END, Path(p_str).name)
                added += 1
            else:
                duplicates += 1
                
        self._update_file_count()
        if duplicates > 0:
            messagebox.showinfo("Duplicates Skipped", f"Successfully added {added} new file(s).\n\nSkipped {duplicates} file(s) that were already loaded.", parent=self.root)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder containing Data Files", initialdir=self.last_open_dir)
        if folder:
            self.last_open_dir = folder # Remember for next time!
            valid_exts = ['.csv', '.txt', '.xlsx', '.dat', '.asr', '.raw']
            found_files = [p for p in Path(folder).iterdir() if p.suffix.lower() in valid_exts]
            
            if not found_files:
                messagebox.showwarning("No Data", "No valid data files found in this folder!", parent=self.root)
                return
                
            self.is_all_var.set(False) 
            self._add_to_list(found_files)
            
    def browse_files(self):
        f = filedialog.askopenfilenames(title="Select Data Files", initialdir=self.last_open_dir, 
                                        filetypes=[("Data files", "*.csv *.txt *.xlsx *.dat *.asr *.raw *.CSV *.TXT")])
        if f:
            self.last_open_dir = str(Path(f[0]).parent) # Remember for next time!
            self.is_all_var.set(False)
            self._add_to_list(f)

    # --- NEW: Reorder Functions ---
    def move_up(self):
        selected = self.file_listbox.curselection()
        if not selected or selected[0] == 0:
            return # Can't move up if nothing is selected or it's already at the top
            
        for idx in selected:
            # Swap in the UI Listbox
            text = self.file_listbox.get(idx)
            self.file_listbox.delete(idx)
            self.file_listbox.insert(idx - 1, text)
            
            # Swap in the backend state
            file_path = state.settings['files'].pop(idx)
            state.settings['files'].insert(idx - 1, file_path)
            
            # Keep it highlighted so the user can click up multiple times!
            self.file_listbox.selection_set(idx - 1)

    def move_down(self):
        selected = self.file_listbox.curselection()
        if not selected or selected[-1] == self.file_listbox.size() - 1:
            return 
            
        for idx in reversed(selected):
            text = self.file_listbox.get(idx)
            self.file_listbox.delete(idx)
            self.file_listbox.insert(idx + 1, text)
            
            file_path = state.settings['files'].pop(idx)
            state.settings['files'].insert(idx + 1, file_path)
            
            self.file_listbox.selection_set(idx + 1)
    # ------------------------------
    def remove_selected(self):
        selected_indices = list(self.file_listbox.curselection())
        if not selected_indices: return
            
        selected_indices.reverse() 
        for idx in selected_indices:
            self.file_listbox.delete(idx)
            state.settings['files'].pop(idx)
            
        self._update_file_count()

    def clear_selection(self):
        self.file_listbox.delete(0, tk.END)
        state.settings['files'] = []
        state.settings.pop('folder', None)
        self._update_file_count()

    def start(self):
        if self.is_all_var.get() and 'folder' not in state.settings:
            state.settings['folder'] = '.' 
            
        state.settings['is_all'] = self.is_all_var.get()
        state.settings['mode'] = self.plot_mode_var.get()
        state.settings['smooth'] = self.smooth_var.get()
        
        if not self.is_all_var.get() and not state.settings.get('files'):
            messagebox.showwarning("Warning", "Please select specific files first!", parent=self.root)
            return
            
        self.ready = True
        self.root.destroy()

    def load_session_cmd(self):
        try:
            from session import load_session
            if load_session(self.root):
                self.ready = True
                self.loaded_from_session = True
                self.root.destroy()
        except ImportError:
            pass

class CloseDialog(tk.Toplevel):
    """A clean, custom pop-up to handle closing the app without cluttering the UI."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Close Session")
        self.geometry("380x150")
        self.resizable(False, False)
        
        # Make the dialog modal (forces user to answer this window before clicking anything else)
        self.transient(parent)
        self.grab_set()
        
        self.choice = None # Will store our final decision
        
        # --- UI Design ---
        ttk.Label(self, text="Do you want to save your session before closing?", font=("Arial", 10, "bold")).pack(pady=(15, 10))
        
        # The Checkbox that acts as our "Destination Modifier"
        self.return_to_menu = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Return to Main Menu instead of exiting the app", variable=self.return_to_menu).pack(pady=(0, 15))
        
        # The 3 simple buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="Save", width=10, command=lambda: self.set_choice("save")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Don't Save", width=10, command=lambda: self.set_choice("discard")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=5)

    def set_choice(self, action):
        # Combine their button click with the checkbox state
        destination = "menu" if self.return_to_menu.get() else "exit"
        self.choice = f"{action}_{destination}"
        self.destroy()

class PlotViewer(tk.Toplevel):
    def __init__(self, master, data_tuples, title, out_dir=None):
        super().__init__(master)
        self.title(title)
        self.geometry("1400x800")
        
        try:
            if getattr(state, 'technique', 'FTIR') == 'XRD':
                app_icon = tk.PhotoImage(file='xrd_icon.png')
            else:
                app_icon = tk.PhotoImage(file='ir_icon.png')
            self.iconphoto(False, app_icon)
        except Exception:
            pass
        
        self.data_dict = {d[0]: (d[1], d[2]) for d in data_tuples}
        self.stems = list(self.data_dict.keys())
        self.current_stem = self.stems[0]
        self.out_dir = Path(out_dir) if out_dir else None

        # --- Interactive Annotation Trackers ---
        self.annotations = []             # Stores all drawn labels
        self.dragging_ann = None          # Tracks which label is currently being dragged
        self.is_adding_annotation = False # Toggle switch for "Click to Add" mode
        
        # --- Variables for UI ---
        self.var_name = tk.StringVar()
        self.var_color = tk.StringVar()
        self.var_offset = tk.DoubleVar()
        self.var_smooth = tk.IntVar()
        self.var_baseline = tk.BooleanVar()
        self.var_norm = tk.BooleanVar()
        self.var_deriv = tk.IntVar(value=0)
        self.var_als_lam = tk.DoubleVar(value=8.0)
        self.var_t2a = tk.BooleanVar()
        self.var_click_mode = tk.StringVar(value='none')
        # --- XRD Specific Variables ---
        self.var_show_fwhm = tk.BooleanVar(value=True)
        self.var_xrd_min_height = tk.DoubleVar(value=5.0) # To filter out noise
        # --- Baseline Subtraction Variables ---
        self.var_bg_sub = tk.BooleanVar(value=False)
        self.var_bg_file = tk.StringVar(value="")
        self.var_bg_mult = tk.DoubleVar(value=1.0)
        
        # --- UI Component Placeholders ---
        self.cb_files = None
        self.peak_listbox = None
        self.area_start = None
        self.deconv_start = None
        
        # Global variables
        self.var_xlim = tk.StringVar(value=state.global_set.get('xlim', ''))
        self.var_ylim = tk.StringVar(value=state.global_set.get('ylim', ''))
        self.var_xstep = tk.StringVar(value=state.global_set.get('xstep', ''))
        self.var_ystep = tk.StringVar(value=state.global_set.get('ystep', ''))
        self.var_xlabel = tk.StringVar(value=state.global_set.get('xlabel', ''))
        self.var_ylabel = tk.StringVar(value=state.global_set.get('ylabel', ''))
        self.var_bg = tk.StringVar(value=state.global_set.get('bg', ''))
        self.var_title_color = tk.StringVar(value=state.global_set.get('title_color', ''))
        self.var_prominence = tk.DoubleVar(value=10.2)
        self.var_title = tk.StringVar(value=state.global_set.get('title', ''))

        self.cursors = []
        self.baseline_pts = []
        
        self.build_layout()
        self.build_controls()
        self.load_active_settings()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_plot()

    def build_layout(self):
        """Splits the window into a Left Control Panel and a Right Plot Area."""
        self.control_frame = ttk.Frame(self, width=400)
        self.control_frame.pack(side="left", fill="y", padx=5, pady=5)
        self.control_frame.pack_propagate(False)
        
        self.plot_frame = ttk.Frame(self)
        self.plot_frame.pack(side="right", fill="both", expand=True)
        
        self.fig = plt.Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
    
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        
        self.cursor_label = ttk.Label(self.plot_frame, text="X: -- | Y: --", font=("Arial", 10, "bold"), foreground="blue")
        self.cursor_label.pack(side="bottom", anchor="e", padx=10, pady=5)

        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move) # Tracks the mouse!

    def get_processed_data_for_stem(self, stem):
        """Returns the X and Y data exactly as they appear on the screen."""
        raw_x, raw_y = self.data_dict[stem]
        fs = state.file_set[stem]
        
        # 1. Primary Processing (Smoothing, Deriv, etc.)
        try:
            x, y = process_spectrum(raw_x, raw_y, stem)
        except Exception:
            x, y = raw_x, raw_y
        x_arr, y_arr = np.array(x, dtype=float), np.array(y, dtype=float)

        # 2. Convert %T to Absorbance (if applicable)
        if fs.get('t2a', False):
            y_safe = np.clip(y_arr, 0.0001, None)
            y_arr = 2 - np.log10(y_safe)

        # 3. Background File Subtraction (THE MISSING PIECE)
        if fs.get('bg_sub', False) and 'bg_data' in fs:
            bg_x, bg_y = fs['bg_data']
            bg_interp = np.interp(x_arr, bg_x, bg_y)
            y_arr -= (bg_interp * fs.get('bg_mult', 1.0))

        # 4. Manual Baseline Subtraction
        manual_pts = fs.get('manual_baseline_pts', [])
        if len(manual_pts) >= 2:
            pts_x = np.array([p[0] for p in manual_pts])
            pts_y = np.array([p[1] for p in manual_pts])
            sort_idx = np.argsort(pts_x)
            baseline_curve = np.interp(x_arr, pts_x[sort_idx], pts_y[sort_idx])
            y_arr -= baseline_curve

        # 5. Normalization and Y-Offset
        if fs.get('normalize', False):
            y_arr = (y_arr - np.min(y_arr)) / (np.max(y_arr) - np.min(y_arr)) * 100
        y_arr += fs.get('offset', 0.0)
            
        return x_arr, y_arr
    
    def on_mouse_move(self, event):
        # 1. Update the coordinate label at the bottom of the screen
        if event.inaxes == self.ax:
            self.cursor_label.config(text=f"X: {event.xdata:.1f} | Y: {event.ydata:.1f}")
        else:
            self.cursor_label.config(text="X: -- | Y: --")
            
        # 2. Handle dragging the annotation box
        if not self.dragging_ann or event.inaxes != self.ax: return
        self.dragging_ann.set_position((event.xdata, event.ydata))
        self.canvas.draw_idle()

    def _create_scrollable_tab(self, notebook, title):
        """Creates a notebook tab with a built-in vertical scrollbar."""
        # 1. Create the outer tab frame and add it to the notebook
        outer_frame = ttk.Frame(notebook)
        notebook.add(outer_frame, text=title)
        
        # 2. Create the Canvas and Scrollbar
        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 3. Create the inner frame where your actual widgets will live
        inner_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        # 4. Make sure everything resizes properly
        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        # 5. Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 6. Enable Mousewheel scrolling ONLY when hovering over the tab
        def _on_mousewheel(e):
            if hasattr(e, 'delta') and e.delta != 0:
                canvas.yview_scroll(int(-1*(e.delta/120)), "units")
                
        def _on_linux_up(e): canvas.yview_scroll(-1, "units")
        def _on_linux_down(e): canvas.yview_scroll(1, "units")

        def _bind_mouse(e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_linux_up)
            canvas.bind_all("<Button-5>", _on_linux_down)

        def _unbind_mouse(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_mouse)
        canvas.bind("<Leave>", _unbind_mouse)
        
        return inner_frame
    
    def build_controls(self):
        
        style = ttk.Style()
        style.configure("TLabelframe", padding=2) # Shrinks the inside of the group boxes
        style.configure("TButton", padding=2)     # Shrinks the buttons natively

        # 1. BUILD BOTTOM BUTTONS FIRST (Locks them to the bottom!)
        self._build_bottom_buttons()

        # 2. CREATE THE NOTEBOOK TABS SECOND
        self.notebook = ttk.Notebook(self.control_frame)
        
        # --- FIXED: WE NOW USE OUR NEW SCROLLABLE TAB FUNCTION ---
        self.tab_file = self._create_scrollable_tab(self.notebook, "File Settings")
        self.tab_axes = self._create_scrollable_tab(self.notebook, "Axes & Style")
        self.tab_tools = self._create_scrollable_tab(self.notebook, "Peaks & Export")
        # ---------------------------------------------------------
        
        self._build_file_tab()
        self._build_axes_tab()
        self._build_tools_tab()

        # 3. PACK THE NOTEBOOK LAST
        self.notebook.pack(side="top", fill="both", expand=True)

    def _build_file_tab(self):
        """Builds the Advanced Spectrum Settings tab."""
        ttk.Label(self.tab_file, text="Select File to Edit:").pack(anchor="w", pady=(5,0))
        self.cb_files = ttk.Combobox(self.tab_file, values=self.stems, state="readonly")
        self.cb_files.set(self.current_stem)
        self.cb_files.pack(fill="x", pady=2)
        self.cb_files.bind("<<ComboboxSelected>>", self.on_file_select)
        
        # --- HERE IS THE MISSING f_frame ---
        f_frame = ttk.LabelFrame(self.tab_file, text="Line Appearance", padding=5)
        f_frame.pack(fill="x", pady=5)
        
        ttk.Label(f_frame, text="Color:").pack(anchor="w")
        
        # The text box + the Color Picker button
        c_frame = ttk.Frame(f_frame)
        c_frame.pack(fill="x", pady=(0, 2))
        ttk.Entry(c_frame, textvariable=self.var_color).pack(side="left", fill="x", expand=True)
        ttk.Button(c_frame, text="🎨 Pick", width=6, command=self.choose_color).pack(side="left", padx=(2, 0))
        
        # A row of quick-select color swatches
        pal_frame = ttk.Frame(f_frame)
        pal_frame.pack(fill="x", pady=(0, 5))
        for col in ['black', 'red', '#1f77b4', '#2ca02c', '#9467bd', '#ff7f0e', 'gray']:
            lbl = tk.Label(pal_frame, bg=col, width=2, cursor="hand2", relief="ridge")
            lbl.pack(side="left", padx=1)
            lbl.bind("<Button-1>", lambda e, c=col: self.var_color.set(c))
        
        ttk.Label(f_frame, text="Y-Offset:").pack(anchor="w")
        ttk.Entry(f_frame, textvariable=self.var_offset).pack(fill="x", pady=(0,5))
        
        ttk.Label(f_frame, text="Smoothing (Pts):").pack(anchor="w")
        ttk.Entry(f_frame, textvariable=self.var_smooth).pack(fill="x", pady=(0,5))
        
        ttk.Checkbutton(f_frame, text="Normalize to 0-100%", variable=self.var_norm).pack(anchor="w", pady=2)
        
        # %T to Abs Toggle --- ONLY SHOWS FOR FTIR
        if getattr(state, 'technique', 'FTIR') == 'FTIR':
            ttk.Checkbutton(f_frame, text="Convert %T to Absorbance", variable=self.var_t2a).pack(anchor="w", pady=2)

        # ALS Baseline Controls
        f_base = ttk.Frame(f_frame)
        f_base.pack(fill="x", pady=2)
        ttk.Checkbutton(f_base, text="Apply ALS Baseline", variable=self.var_baseline).pack(side="left")
        ttk.Label(f_base, text=" Stiffness (10^X):").pack(side="left")
        ttk.Entry(f_base, textvariable=self.var_als_lam, width=4).pack(side="left", padx=2)
        
        # Derivative Controls
        f_deriv = ttk.Frame(f_frame)
        f_deriv.pack(fill="x", pady=5)
        ttk.Label(f_deriv, text="Derivative:").pack(side="left")
        ttk.Radiobutton(f_deriv, text="None", variable=self.var_deriv, value=0).pack(side="left", padx=2)
        ttk.Radiobutton(f_deriv, text="1st", variable=self.var_deriv, value=1).pack(side="left", padx=2)
        ttk.Radiobutton(f_deriv, text="2nd", variable=self.var_deriv, value=2).pack(side="left", padx=2)

        # ==========================================
        # REFERENCE BASELINE SUBTRACTION
        # ==========================================
        bg_frame = ttk.LabelFrame(self.tab_file, text="Reference Baseline Subtraction", padding=5)
        bg_frame.pack(fill="x", pady=(10, 5))
        
        ttk.Checkbutton(bg_frame, text="Subtract Baseline File", variable=self.var_bg_sub).pack(anchor="w", pady=2)
        
        bg_inner1 = ttk.Frame(bg_frame)
        bg_inner1.pack(fill="x", pady=2)
        ttk.Label(bg_inner1, text="Baseline:").pack(side="left")
        
        # Changed from a Dropdown to a Read-Only Text Box + Browse Button
        ttk.Entry(bg_inner1, textvariable=self.var_bg_file, state="readonly", width=15).pack(side="left", fill="x", expand=True, padx=(5, 2))
        ttk.Button(bg_inner1, text="Browse...", width=8, command=self.load_baseline_file).pack(side="left")
        
        bg_inner2 = ttk.Frame(bg_frame)
        bg_inner2.pack(fill="x", pady=2)
        ttk.Label(bg_inner2, text="Multiplier:").pack(side="left")
        ttk.Entry(bg_inner2, textvariable=self.var_bg_mult, width=6).pack(side="left", padx=5)

        ttk.Button(self.tab_file, text="Apply Changes", command=self.save_and_update).pack(fill="x", pady=5)
        ttk.Button(self.tab_file, text="🔄 Reset to Raw Data", command=self.reset_file_settings).pack(fill="x", pady=2)
        ttk.Button(self.tab_file, text="🔄 Apply Math Settings to ALL Files", command=self.apply_to_all).pack(fill="x", pady=2)

    def choose_color(self):
        """Opens the native OS color wheel and saves the hex code."""
        from tkinter.colorchooser import askcolor
        # Get current color as starting point
        current = self.var_color.get()
        if not current: current = "black"
        
        # Open the color wheel
        color = askcolor(initialcolor=current, title="Choose Line Color")
        
        # If the user picked a color (and didn't hit cancel), update the entry
        if color[1]: 
            self.var_color.set(color[1])

    def load_active_settings(self):
        """Loads the settings for the currently selected file into the UI."""
        fs = state.file_set[self.current_stem]
        self.var_name.set(fs.get('custom_name', self.current_stem))
        self.var_color.set(fs.get('color', 'black'))
        self.var_offset.set(fs.get('offset', 0.0))
        self.var_smooth.set(fs.get('smooth', 15))
        self.var_baseline.set(fs.get('do_baseline', False))
        self.var_norm.set(fs.get('normalize', False))
        self.var_deriv.set(fs.get('derivative', 0))
        self.var_als_lam.set(fs.get('als_lam', 8.0))
        self.var_t2a.set(fs.get('t2a', False))

    def on_file_select(self, event=None):
        """Triggers when a new file is selected from the dropdown menu."""
        self.current_stem = self.cb_files.get()
        self.load_active_settings()
        fs = state.file_set.get(self.current_stem, {})
        self.var_bg_sub.set(fs.get('bg_sub', False))
        self.var_bg_file.set(fs.get('bg_filename', ''))
        self.var_bg_mult.set(fs.get('bg_mult', 1.0))
    
    def load_baseline_file(self):
        """Browses for a baseline file and loads it silently as background data."""
        filepath = filedialog.askopenfilename(
            title="Select Baseline / Empty Substrate File",
            filetypes=[("Data Files", "*.csv *.txt *.xy *.dat"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        try:
            # Try to read comma-separated first, then space/tab separated
            try:
                data = np.loadtxt(filepath, delimiter=',')
            except Exception:
                data = np.loadtxt(filepath, delimiter=None)
                
            if data.shape[1] < 2:
                raise ValueError("File does not contain X and Y columns.")
                
            fs = state.file_set[self.current_stem]
            fs['bg_data'] = (data[:, 0], data[:, 1]) # Save the X and Y arrays
            fs['bg_filename'] = Path(filepath).name  # Save the name
            
            # Update the UI
            self.var_bg_file.set(fs['bg_filename'])
            self.var_bg_sub.set(True) 
            fs['bg_sub'] = True
            
            self.update_plot()
            messagebox.showinfo("Success", f"Baseline '{fs['bg_filename']}' loaded successfully!", parent=self)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read baseline file. Ensure it is a standard 2-column numeric file.\n\nDetails: {e}", parent=self)

    def _build_axes_tab(self):
        """Builds the Axes & Style tab."""
        a_frame = ttk.LabelFrame(self.tab_axes, text="Global Axes Settings", padding=5)
        a_frame.pack(fill="x", pady=5)
        
        ttk.Label(a_frame, text="X-Axis Label:").grid(row=0, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_xlabel).grid(row=0, column=1, sticky="ew")
        
        ttk.Label(a_frame, text="Y-Axis Label:").grid(row=1, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_ylabel).grid(row=1, column=1, sticky="ew")
        
        ttk.Label(a_frame, text="X Limits (min,max):").grid(row=2, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_xlim).grid(row=2, column=1, sticky="ew")
        
        ttk.Label(a_frame, text="Y Limits (min,max):").grid(row=3, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_ylim).grid(row=3, column=1, sticky="ew")
        
        ttk.Label(a_frame, text="X Tick Step:").grid(row=4, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_xstep).grid(row=4, column=1, sticky="ew")
        
        ttk.Label(a_frame, text="Y Tick Step:").grid(row=5, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_ystep).grid(row=5, column=1, sticky="ew")

        ttk.Label(a_frame, text="Graph Title:").grid(row=6, column=0, sticky="w")
        ttk.Entry(a_frame, textvariable=self.var_title).grid(row=6, column=1, sticky="ew")
        
        ttk.Button(self.tab_axes, text="Apply Global Settings", command=self.save_and_update).pack(pady=5)

    def _build_tools_tab(self):
        """Builds the Annotations & Peaks tab."""
        ttk.Label(self.tab_tools, text="Interactive Tools:").pack(anchor="w", pady=(5,0))
        
        mode_frame = ttk.Frame(self.tab_tools)
        mode_frame.pack(fill="x", pady=2)
        
        ttk.Radiobutton(mode_frame, text="Navigation (Zoom/Pan)", variable=self.var_click_mode, value='none', command=self.update_plot).pack(anchor="w")
        
        # --- SHARED BASELINE TOOL (Now available for XRD and FTIR) ---
        ttk.Radiobutton(mode_frame, text="Draw Manual Baseline", variable=self.var_click_mode, value='baseline', command=self.update_plot).pack(anchor="w")
        
        base_btn_frame = ttk.Frame(mode_frame)
        base_btn_frame.pack(fill="x", pady=2)
        ttk.Button(base_btn_frame, text="✅ Apply", width=8, command=self.apply_manual_baseline).pack(side="left", padx=2)
        ttk.Button(base_btn_frame, text="❌ Clear", width=8, command=self.clear_manual_baseline).pack(side="left", padx=2)
        # -------------------------------------------------------------

        # ==========================================
        # FT-IR SPECIFIC TOOLS
        # ==========================================
        if getattr(state, 'technique', 'FTIR') == 'FTIR':
            ttk.Radiobutton(mode_frame, text="Pick Peak", variable=self.var_click_mode, value='peak', command=self.update_plot).pack(anchor="w")
            ttk.Radiobutton(mode_frame, text="Calculate Area", variable=self.var_click_mode, value='area', command=self.update_plot).pack(anchor="w")
            ttk.Button(self.tab_tools, text="📖 FT-IR Functional Group Cheat Sheet", command=self.show_cheat_sheet).pack(fill="x", pady=(5, 0))
            ttk.Radiobutton(mode_frame, text="Peak Deconvolution", variable=self.var_click_mode, value='deconv', command=self.update_plot).pack(anchor="w")

            deconv_btn_frame = ttk.Frame(mode_frame)
            deconv_btn_frame.pack(fill="x", pady=2)
            ttk.Button(deconv_btn_frame, text="❌ Clear Fit", width=10, command=self.clear_deconv).pack(side="left", padx=20)
            ttk.Button(deconv_btn_frame, text="💾 Export Data", width=12, command=self.export_deconv_data).pack(side="left", padx=5)

            auto_frame = ttk.LabelFrame(self.tab_tools, text="Auto-Find Peaks", padding=5)
            auto_frame.pack(fill="x", pady=5)
            ttk.Label(auto_frame, text="Prominence:").pack(side="left")
            ttk.Entry(auto_frame, textvariable=self.var_prominence, width=5).pack(side="left", padx=5)
            ttk.Button(auto_frame, text="Find", width=6, command=self.auto_find_peaks).pack(side="left")

        # ==========================================
        # XRD SPECIFIC TOOLS
        # ==========================================
        elif getattr(state, 'technique', 'FTIR') == 'XRD':
            ttk.Radiobutton(mode_frame, text="Pick XRD Peak (Smart Snap)", variable=self.var_click_mode, value='xrd_peak', command=self.update_plot).pack(anchor="w")
            ttk.Radiobutton(mode_frame, text="Calculate Peak Area", variable=self.var_click_mode, value='area', command=self.update_plot).pack(anchor="w")
            
            xrd_options = ttk.Frame(self.tab_tools)
            xrd_options.pack(fill="x", pady=5)
            ttk.Checkbutton(xrd_options, text="Show FWHM & Grain Size on Graph", variable=self.var_show_fwhm, command=self.update_plot).pack(anchor="w")
            
            auto_xrd = ttk.LabelFrame(self.tab_tools, text="Auto-Find XRD Peaks", padding=5)
            auto_xrd.pack(fill="x", pady=5)
            ttk.Label(auto_xrd, text="Min Height:").pack(side="left")
            ttk.Entry(auto_xrd, textvariable=self.var_xrd_min_height, width=5).pack(side="left", padx=2)
            ttk.Label(auto_xrd, text="Prom:").pack(side="left")
            ttk.Entry(auto_xrd, textvariable=self.var_prominence, width=4).pack(side="left", padx=2)
            ttk.Button(auto_xrd, text="Find", width=5, command=self.auto_find_xrd_peaks).pack(side="left", padx=2)

            ttk.Button(self.tab_tools, text="📊 Plot Grain Size Distribution", command=self.show_grain_size_chart).pack(fill="x", pady=5, ipady=5)
            
        # ==========================================
        # SHARED LISTBOX & EXPORT (For Both)
        # ==========================================
        list_frame = ttk.LabelFrame(self.tab_tools, text="Saved Peaks", padding=5)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.peak_listbox = tk.Listbox(list_frame, height=8)
        self.peak_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.peak_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.peak_listbox.config(yscrollcommand=scrollbar.set)
        
        btn_frame = ttk.Frame(self.tab_tools)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_selected_peak).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_peaks).pack(side="left", expand=True, fill="x", padx=2)
        
        ttk.Separator(self.tab_tools, orient='horizontal').pack(fill='x', pady=5)
        export_frame = ttk.Frame(self.tab_tools)
        export_frame.pack(fill="x", pady=5)
        ttk.Button(export_frame, text="💾 Export Data, Peaks & Graph", command=self.export_data).pack(fill="x", ipady=5)
        ttk.Button(export_frame, text="📁 Save Workspace Session (.json)", command=self.save_session_cmd).pack(fill="x", ipady=4)
    
    def save_and_update(self):
        """Saves UI variables back to the state dictionary and redraws."""
        # 1. Define 'fs' FIRST so the rest of the code knows where to save data
        fs = state.file_set[self.current_stem]
        
        # --- REFERENCE BASELINE SETTINGS ---
        fs['bg_sub'] = self.var_bg_sub.get()
        fs['bg_filename'] = self.var_bg_file.get()
        fs['bg_mult'] = self.var_bg_mult.get()
        
        # --- FIXED: Clear peaks if math mode changes so they don't linger! ---
        if fs.get('t2a', False) != self.var_t2a.get() or fs.get('normalize', False) != self.var_norm.get():
            self.clear_peaks()
        # ---------------------------------------------------------------------
        
        # 2. Save File Settings (fs)
        fs['custom_name'] = self.var_name.get()
        fs['color'] = self.var_color.get()
        
        try:
            fs['offset'] = float(self.var_offset.get())
        except ValueError: pass
        
        try:
            fs['smooth'] = int(self.var_smooth.get())
        except ValueError: pass
        
        fs['do_baseline'] = self.var_baseline.get()
        fs['normalize'] = self.var_norm.get()
        fs['t2a'] = self.var_t2a.get()
        fs['derivative'] = self.var_deriv.get()
        
        try:
            fs['als_lam'] = float(self.var_als_lam.get())
        except ValueError: pass
        
        # 3. Save Global Settings (gs)
        gs = state.global_set
        gs['xlabel'] = self.var_xlabel.get()
        gs['ylabel'] = self.var_ylabel.get()
        gs['title'] = self.var_title.get() # Moved up so it applies instantly!
        
        def parse_lims(val):
            if not val: return None
            try:
                return [float(x.strip()) for x in val.split(',')]
            except:
                return None
                
        gs['xlim'] = parse_lims(self.var_xlim.get())
        gs['ylim'] = parse_lims(self.var_ylim.get())
        gs['xstep'] = self.var_xstep.get()
        gs['ystep'] = self.var_ystep.get()
        
        # 4. Redraw the graph with all the new settings!
        if hasattr(self, 'update_plot'):
            self.update_plot()
    
    def apply_to_all(self):
        """Copies the current math settings to all loaded spectra so you don't have to do it manually."""
        self.save_and_update() # Save current first
        
        current_fs = state.file_set[self.current_stem]
        keys_to_copy = ['smooth', 'do_baseline', 'normalize', 'derivative', 'als_lam', 't2a', 'offset']
        
        for stem in self.stems:
            if stem != self.current_stem:
                for key in keys_to_copy:
                    state.file_set[stem][key] = current_fs.get(key)
                    
        self.update_plot()
        messagebox.showinfo("Success", "Settings (Smoothing, Baseline, %T→Abs, etc.) applied to all files!", parent=self)
    
    def apply_manual_baseline(self):
        """Saves the drawn points and triggers the math to subtract them."""
        if len(self.baseline_pts) < 2:
            messagebox.showwarning("Warning", "Please click at least 2 points on the graph first!", parent=self)
            return
        
        fs = state.file_set[self.current_stem]
        fs['manual_baseline_pts'] = self.baseline_pts.copy()
        self.baseline_pts = [] # Reset the clicking tool
        self.var_click_mode.set('none') # Turn off the tool automatically
        self.update_plot()
        
    def clear_manual_baseline(self):
        """Erases the custom baseline and resets the graph."""
        fs = state.file_set[self.current_stem]
        fs['manual_baseline_pts'] = []
        self.baseline_pts = []
        self.update_plot()
    
    def clear_deconv(self):
        """Erases the deconvoluted curves from the current spectrum."""
        fs = state.file_set[self.current_stem]
        fs['deconvs'] = [] # Wipe the saved math
        self.deconv_start = None # Reset the clicking tool just in case
        self.update_plot() # Redraw the blank graph

    def show_cheat_sheet(self):
        """Opens a pop-up window with common FT-IR functional groups."""
        win = tk.Toplevel(self)
        win.title("FT-IR Cheat Sheet")
        win.geometry("450x350")
        win.transient(self) # Keep on top
        
        cols = ("Frequency (cm⁻¹)", "Functional Group", "Intensity")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=140, anchor="center")
            
        bands = [
            ("3200 - 3600", "O-H Stretch (Alcohols)", "Broad, Strong"),
            ("3300 - 3500", "N-H Stretch (Amines)", "Medium"),
            ("2850 - 3000", "C-H Stretch (Alkanes)", "Medium / Strong"),
            ("3000 - 3100", "=C-H Stretch (Alkenes)", "Medium"),
            ("2100 - 2260", "C≡C / C≡N Stretch", "Weak / Medium"),
            ("1650 - 1750", "C=O Stretch (Carbonyl)", "Strong"),
            ("1600 - 1680", "C=C Stretch (Alkenes)", "Weak / Medium"),
            ("1500 - 1600", "N-H Bend (Amines)", "Medium"),
            ("1000 - 1300", "C-O Stretch (Ethers/Esters)", "Strong"),
            ("600 - 900", "C-H Bend (Aromatics)", "Strong")
        ]
        
        for band in bands:
            tree.insert("", tk.END, values=band)
            
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)

    def clear_peaks(self):
        state.file_set[self.current_stem]['labels'] = []
        state.file_set[self.current_stem]['areas'] = []
        state.file_set[self.current_stem]['deconvs'] = []
        if hasattr(self, 'update_plot'):
            self.update_plot()

    def save_session_cmd(self):
        """Triggers the session save logic natively handled by session.py"""
        try:
            from session import save_session
            
            # We pass 'self' so session.py can use this window for popups
            # We pass save_as=True to force the 'Save As' menu
            save_session(root_window=self, viewer_instance=self, save_as=True)
            
        except ImportError:
            messagebox.showerror("Missing Module", "Could not find 'session.py'. Please ensure the file exists.", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", f"An error occurred while launching the save sequence:\n{e}", parent=self)

    def sync_annotations_to_state(self):
        """
        Placeholder for session.py. 
        Currently does nothing since there are no annotations to save yet!
        """
        pass

    def reset_file_settings(self):
        """Unchecks all math boxes, clears drawings, and restores pure raw data."""
        self.var_offset.set(0.0)
        self.var_smooth.set(15)
        self.var_baseline.set(False)
        self.var_norm.set(False)
        self.var_deriv.set(0)
        self.var_t2a.set(False)
        
        self.clear_manual_baseline()
        self.clear_peaks()
        self.clear_deconv()
        self.save_and_update()
        
    def export_data(self):
        """Opens a pop-up window letting the user choose exactly what to export."""
    
        # Create the pop-up window
        export_win = tk.Toplevel(self)
        export_win.title("Export Options")
        export_win.geometry("400x250")
        export_win.transient(self) # Keeps it floating on top of the main window
        export_win.grab_set()      # Blocks clicking the main window until this is closed
        
        # UI Variables
        var_csv = tk.BooleanVar(value=True)
        var_txt = tk.BooleanVar(value=True)
        var_img = tk.BooleanVar(value=True)
        var_fmt = tk.StringVar(value=".png")
        var_dpi = tk.IntVar(value=300)
        
        # Build the UI
        ttk.Label(export_win, text="Select items to export:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        ttk.Checkbutton(export_win, text="1. Processed Data (.csv)", variable=var_csv).pack(anchor="w", padx=25, pady=2)
        ttk.Checkbutton(export_win, text="2. Peaks & Areas Report (.txt)", variable=var_txt).pack(anchor="w", padx=25, pady=2)
        
        # Image options row
        img_frame = ttk.Frame(export_win)
        img_frame.pack(fill="x", padx=25, pady=2)
        ttk.Checkbutton(img_frame, text="3. Graph Image", variable=var_img).pack(side="left")
        
        ttk.Label(img_frame, text="  Format:").pack(side="left")
        ttk.Combobox(img_frame, textvariable=var_fmt, values=[".png", ".jpg", ".svg", ".pdf", ".tiff"], width=5, state="readonly").pack(side="left", padx=2)
        
        ttk.Label(img_frame, text="  DPI:").pack(side="left")
        ttk.Combobox(img_frame, textvariable=var_dpi, values=[150, 300, 600, 1200], width=5).pack(side="left", padx=2)
        
        def process_export():
            """The brain that actually saves the checked items."""
            if not (var_csv.get() or var_txt.get() or var_img.get()):
                messagebox.showwarning("Warning", "Please select at least one item to export!", parent=export_win)
                return
                
            # Ask the user WHERE to save right now!
            save_dir = filedialog.askdirectory(title="Select Folder to Save Exports", parent=export_win)
            if not save_dir:
                return # User clicked Cancel
                
            save_dir = Path(save_dir)
            fs = state.file_set[self.current_stem]
            raw_x, raw_y = self.data_dict[self.current_stem]
            
            try:
                x, y = process_spectrum(raw_x, raw_y, self.current_stem)
            except Exception:
                x, y = raw_x, raw_y

            # Apply %T to Absorbance Math for the Exported Data ---
            x_arr, y_arr = np.array(x, dtype=float), np.array(y, dtype=float)
            if getattr(state, 'technique', 'FTIR') == 'FTIR' and fs.get('t2a', False):
                y_safe = np.clip(y_arr, 0.0001, None)
                y_arr = 2 - np.log10(y_safe)
            x, y = x_arr, y_arr

            try:
                # 1. Export CSV
                if var_csv.get():
                    data_path = save_dir / f"{self.current_stem}_processed.csv"
                    # Dynamic Header based on technique
                    csv_header = "Wavenumber,Intensity" if getattr(state, 'technique', 'FTIR') == 'FTIR' else "2-Theta,Intensity"
                    np.savetxt(data_path, np.column_stack((x, y)), delimiter=",", header=csv_header, comments="")
                    
                # 2. Export TXT Report
                if var_txt.get():
                    report_path = save_dir / f"{self.current_stem}_analysis_report.txt"
                    with open(report_path, 'w') as f:
                        
                        # ==========================================
                        # FT-IR REPORT
                        # ==========================================
                        if getattr(state, 'technique', 'FTIR') == 'FTIR':
                            peaks = fs.get('labels', [])
                            areas = fs.get('areas', [])
                            
                            f.write(f"--- FT-IR Analysis Report for {self.current_stem} ---\n\n")
                            if peaks:
                                f.write("PEAKS (Local Minima/Maxima):\n")
                                f.write("X (Wavenumber)\tY (Intensity)\n")
                                for px, py, text in peaks:
                                    f.write(f"{px:.2f}\t\t{py:.4f}\t\t({text})\n")
                                f.write("\n")
                            if areas:
                                f.write("INTEGRATED AREAS:\n")
                                f.write("Start X\t\tEnd X\t\tArea Value\n")
                                for x1, x2, val in areas:
                                    f.write(f"{x1:.2f}\t\t{x2:.2f}\t\t{val:.4f}\n")
                                    
                        # ==========================================
                        # XRD REPORT
                        # ==========================================
                        elif getattr(state, 'technique', 'FTIR') == 'XRD':
                            xrd_peaks = fs.get('xrd_peaks', [])
                            areas = fs.get('areas', [])
                            
                            f.write(f"--- XRD Analysis Report for {self.current_stem} ---\n\n")
                            if xrd_peaks:
                                f.write("PEAKS & CRYSTALLITE SIZE (Scherrer Equation):\n")
                                f.write("2-Theta\t\tIntensity\tFWHM\t\tSize (nm)\n")
                                for px, py, fwhm, d in xrd_peaks:
                                    f.write(f"{px:.2f}\t\t{py:.4f}\t\t{fwhm:.4f}\t\t{d:.2f}\n")
                                
                                # Append Statistics
                                valid_sizes = [p[3] for p in xrd_peaks if p[3] > 0]
                                if valid_sizes:
                                    avg_sz = np.mean(valid_sizes)
                                    std_sz = np.std(valid_sizes) if len(valid_sizes) > 1 else 0.0
                                    f.write(f"\nSTATISTICS: Average Size = {avg_sz:.2f} nm (Std Dev: {std_sz:.2f} nm)\n\n")
                                    
                            if areas:
                                f.write("INTEGRATED AREAS:\n")
                                f.write("Start 2-Theta\tEnd 2-Theta\tArea Value\n")
                                for x1, x2, val in areas:
                                    f.write(f"{x1:.2f}\t\t{x2:.2f}\t\t{val:.4f}\n")
                
                # 3. Export Image
                if var_img.get():
                    fmt = var_fmt.get()
                    dpi = var_dpi.get()
                    # By forcing str() here, we guarantee matplotlib can save it properly on all OS's!
                    img_path = str(save_dir / f"{self.current_stem}_plot{fmt}")
                    self.fig.savefig(img_path, dpi=dpi, bbox_inches='tight')
                    
                messagebox.showinfo("Success", f"Files successfully exported to:\n\n{save_dir}", parent=export_win)
                export_win.destroy() # Close the pop-up
                
            except Exception as e:
                messagebox.showerror("Export Error", f"An error occurred while saving:\n{e}", parent=export_win)
                
        # Action Buttons
        ttk.Separator(export_win, orient='horizontal').pack(fill='x', pady=(15, 10))
        btn_frame = ttk.Frame(export_win)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Cancel", command=export_win.destroy).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Choose Folder & Save", command=process_export).pack(side="right")

    def auto_find_peaks(self):
        """FT-IR Auto-peak detection handling both %T and Absorbance."""
        x, y = self.get_processed_data_for_stem(self.current_stem)
        fs = state.file_set[self.current_stem]
        
        # --- THE FIX: Handle FT-IR Valleys vs Peaks ---
        # If we are in Transmittance (default), chemical peaks point DOWN. 
        # We temporarily invert y (-y) so find_peaks can detect the valleys.
        if not fs.get('t2a', False): 
            search_y = -y  
        else:
            # If converted to Absorbance, peaks point UP natively.
            search_y = y   
            
        prom = float(self.var_prominence.get())
        
        # Run find_peaks on the correctly oriented data
        peaks_idx, _ = find_peaks(search_y, prominence=prom)
        
        # Save the points using the ORIGINAL 'y' so they plot at the correct height
        for p in peaks_idx:
            # Prevent duplicating peaks if you click 'Find' multiple times
            px, py = x[p], y[p]
            existing_peaks = fs.get('labels', [])
            if not any(abs(ex[0] - px) < 0.1 for ex in existing_peaks):
                fs.setdefault('labels', []).append((px, py, f"{px:.1f}"))
                
        self.update_plot()

    def sync_peak_listbox(self):
        """Updates the sidebar listbox with the currently saved peaks."""
        self.peak_listbox.delete(0, tk.END)
        fs = state.file_set.get(self.current_stem, {})
        
        # --- IF WE ARE IN FT-IR MODE ---
        if getattr(state, 'technique', 'FTIR') == 'FTIR':
            for i, (px, py, text) in enumerate(fs.get('labels', [])):
                # Formats like: "Peak 1: 1500.5 (C=C stretch)"
                self.peak_listbox.insert(tk.END, f"Peak {i+1}: {px:.1f} cm⁻¹ ({text})")
        
        # --- IF WE ARE IN XRD MODE ---
        elif getattr(state, 'technique', 'FTIR') == 'XRD':
            # 1. Print the Peaks
            for i, (px, py, fwhm, d) in enumerate(fs.get('xrd_peaks', [])):
                if d > 0:
                    self.peak_listbox.insert(tk.END, f"2θ: {px:.2f}° | FWHM: {fwhm:.2f}° | Size: {d:.1f}nm")
                else:
                    self.peak_listbox.insert(tk.END, f"2θ: {px:.2f}° | FWHM: {fwhm:.2f}°")
            
            # 2. Print the Areas
            for i, (x1, x2, area) in enumerate(fs.get('areas', [])):
                self.peak_listbox.insert(tk.END, f"Area: {area:.2f} (from {min(x1,x2):.1f}° to {max(x1,x2):.1f}°)")

    def delete_selected_peak(self):
        """Deletes whichever Peak OR Area is clicked in the listbox."""
        sel = self.peak_listbox.curselection()
        if not sel: return
        idx = sel[0]
        fs = state.file_set[self.current_stem]
        
        # --- IF WE ARE IN FT-IR MODE ---
        if getattr(state, 'technique', 'FTIR') == 'FTIR':
            num_peaks = len(fs.get('labels', []))
            
            # If the clicked item is a Peak
            if idx < num_peaks:
                fs['labels'].pop(idx)
            # If the clicked item is an Area
            else:
                area_idx = idx - num_peaks
                if area_idx < len(fs.get('areas', [])):
                    fs['areas'].pop(area_idx)
                    
        # --- IF WE ARE IN XRD MODE ---
        elif getattr(state, 'technique', 'FTIR') == 'XRD':
            if idx < len(fs.get('xrd_peaks', [])):
                fs['xrd_peaks'].pop(idx)
                
        self.update_plot()

    def clear_peaks(self):
        """Removes all saved peaks, areas, and deconvolutions for the active file."""
        fs = state.file_set[self.current_stem]
        
        # Safely wipe all lists regardless of mode
        if 'labels' in fs: fs['labels'] = []
        if 'areas' in fs: fs['areas'] = []
        if 'deconvs' in fs: fs['deconvs'] = []
        if 'xrd_peaks' in fs: fs['xrd_peaks'] = []
        
        self.update_plot()

    def _build_bottom_buttons(self):
        bot_frame = ttk.Frame(self.control_frame)
        bot_frame.pack(side="bottom", fill="x", pady=10)
        
        # Check if we have more files to go
        is_last = False
        if state.settings.get('mode') == 'individual':
            current_idx = next((i for i, d in enumerate(state.all_data) if d[0] == self.stems[0]), 0)
            if current_idx == len(state.all_data) - 1:
                is_last = True
                
        if state.settings.get('mode') != 'individual' or is_last:
            btn_text = "✅ Finish & Close"
            cmd = self.on_close
        else:
            btn_text = "Next Spectrum ➔"
            cmd = self.next_spectrum

        ttk.Button(bot_frame, text=btn_text, command=cmd).pack(fill="x", ipady=8)
        
    def next_spectrum(self):
        self.destroy() # Silently destroys window so ir.py loops to the next file!

    def update_plot(self):
        """The main engine that draws the graph on the screen."""
        self.fig.clear()
        self.cursors = [] 
        
        mode = state.settings.get('mode', 'individual')
        is_stack = (mode == 'stack') # Flag to help our aesthetics function
        
        if is_stack:
            axes = self.fig.subplots(len(self.stems), 1, sharex=True)
            if len(self.stems) == 1: axes = [axes]
        else:
            ax = self.fig.add_subplot(111)
            axes = [ax] * len(self.stems)
            
        min_xs, max_xs, min_ys, max_ys = [], [], [], []
        
        for i, stem in enumerate(self.stems):
            ax = axes[i]
            fs = state.file_set[stem]
            raw_x, raw_y = self.data_dict[stem]
            
            try:
                x, y = process_spectrum(raw_x, raw_y, stem)
            except Exception:
                x, y = raw_x, raw_y
            
            x_arr = np.array(x, dtype=float)
            y_arr = np.array(y, dtype=float)
            
            if fs.get('t2a', False):
                y_safe = np.clip(y_arr, 0.0001, None)
                y_arr = 2 - np.log10(y_safe)

            manual_pts = fs.get('manual_baseline_pts', [])
            if len(manual_pts) >= 2:
                pts_x = np.array([p[0] for p in manual_pts])
                pts_y = np.array([p[1] for p in manual_pts])
                sort_idx = np.argsort(pts_x)
                pts_x, pts_y = pts_x[sort_idx], pts_y[sort_idx]
                baseline_curve = np.interp(x_arr, pts_x, pts_y)
                y_arr = y_arr - baseline_curve
            
            if fs.get('normalize', False):
                y_min = np.min(y_arr)
                y_max = np.max(y_arr)
                if y_max != y_min:
                    target_max = 1.0 if fs.get('t2a', False) else 100.0
                    y_arr = ((y_arr - y_min) / (y_max - y_min)) * target_max

            # --- REFERENCE BASELINE SUBTRACTION MATH ---
            if fs.get('bg_sub', False) and 'bg_data' in fs:
                bg_raw_x, bg_raw_y = fs['bg_data']
                
                # Sort background data mathematically to ensure safe interpolation
                sort_idx = np.argsort(bg_raw_x)
                bg_x_sorted = bg_raw_x[sort_idx]
                bg_y_sorted = bg_raw_y[sort_idx]
                
                # Interpolate background Y-values to perfectly match the Sample's X-coordinates
                bg_y_interp = np.interp(x, bg_x_sorted, bg_y_sorted)
                
                # Apply multiplier and subtract!
                y_arr = y_arr - (bg_y_interp * fs.get('bg_mult', 1.0))
            # -------------------------------------------
            
            # --- THE MISSING Y-OFFSET MATH FIX ---
            # This makes the "Y-Offset" box in the UI actually work!
            y_arr = y_arr + fs.get('offset', 0.0)
            # -------------------------------------

            x, y = x_arr, y_arr 

            if len(x) > 0:
                min_xs.append(min(x)); max_xs.append(max(x))
                min_ys.append(min(y)); max_ys.append(max(y))
                
            label_name = fs.get('custom_name', stem)
            color = fs.get('color', 'black')
            
            ax.plot(x, y, label=label_name, color=color, linewidth=1.5)
            
            # --- DRAW FT-IR PEAKS ---
            for px, py, text in fs.get('labels', []):
                ax.plot(px, py, 'v', color=color, markersize=6)
                ax.annotate(text, xy=(px, py), xytext=(0, -20), textcoords="offset points", ha='center', va='bottom', color=color, fontsize=9, bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8, edgecolor='none'), annotation_clip=True)

            # --- DRAW XRD PEAKS ---
            for px, py, fwhm, d in fs.get('xrd_peaks', []):
                ax.plot(px, py, 'o', color=color, markersize=5) # Mark tip
                
                # Check if the user toggled the FWHM/Grain Size box
                if self.var_show_fwhm.get():
                    text = f"2θ: {px:.1f}°\nFWHM: {fwhm:.2f}°\nD: {d:.1f} nm"
                else:
                    text = f"2θ: {px:.1f}°"
                    
                ax.annotate(text, xy=(px, py), xytext=(0, 10), textcoords="offset points", ha='center', va='bottom', color=color, fontsize=8, bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.9, edgecolor='gray'), annotation_clip=True)

            # Draw any saved areas
            for x1, x2, area_val in fs.get('areas', []):
                x_arr_area, y_arr_area = np.array(x), np.array(y)
                mask = (x_arr_area >= x1) & (x_arr_area <= x2)
                x_sel, y_sel = x_arr_area[mask], y_arr_area[mask]
                
                if len(x_sel) > 1:
                    sort_idx = np.argsort(x_sel)
                    x_sel, y_sel = x_sel[sort_idx], y_sel[sort_idx]
                    baseline = np.interp(x_sel, [x_sel[0], x_sel[-1]], [y_sel[0], y_sel[-1]])
                    ax.fill_between(x_sel, y_sel, baseline, color=color, alpha=0.4)
                    mid_idx = len(x_sel) // 2
                    ax.text(x_sel[mid_idx], y_sel[mid_idx], f"Area:\n{area_val:.1f}", color='black', ha='center', va='center', bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))

            # Draw Deconvoluted Sub-Peaks
            for deconv_data in fs.get('deconvs', []):
                if len(deconv_data) == 6:
                    x1, x2, baseline, popt, num_peaks, is_valley = deconv_data
                else:
                    x1, x2, baseline, popt, num_peaks = deconv_data
                    is_valley = False # Fallback for old data
                    
                x_arr_area, y_arr_area = np.array(x), np.array(y)
                mask = (x_arr_area >= x1) & (x_arr_area <= x2)
                x_sel = x_arr_area[mask]
                
                composite_curve = np.zeros_like(x_sel)
                sign = -1 if is_valley else 1
                
                for j in range(0, len(popt), 3):
                    A, mu, sigma = popt[j], popt[j+1], popt[j+2]
                    sub_peak = A * np.exp(-((x_sel - mu)**2) / (2 * sigma**2))
                    composite_curve += sub_peak
                    
                    ax.plot(x_sel, baseline + (sign * sub_peak), linestyle='--', alpha=0.8)
                    ax.fill_between(x_sel, baseline, baseline + (sign * sub_peak), alpha=0.2)
                
                ax.plot(x_sel, baseline + (sign * composite_curve), color='red', linestyle=':', linewidth=2, label=f"Fit Envelope ({num_peaks} peaks)")

            # --- FIX Y-LIMITS FOR STACKED GRID ---
            # Automatically zoom in perfectly on each individual subplot
            if is_stack and len(y) > 0:
                b = (max(y) - min(y)) * 0.05
                ax.set_ylim(bottom=min(y) - b, top=max(y) + b)

        if mode == 'overlay':
            axes[0].legend(loc='best', fontsize=8)
            
        for ax in set(axes):
            # --- PASS is_stack FLAG TO AESTHETICS ---
            apply_global_aesthetics(ax, min_xs, max_xs, min_ys, max_ys, is_stack_mode=is_stack)
            cursor = Cursor(ax, useblit=True, color='red', linewidth=1, linestyle='dotted')
            cursor.visible = self.var_click_mode.get() in ['peak', 'area', 'baseline', 'deconv']
            self.cursors.append(cursor)
        
        self.fig.tight_layout() 
        self.canvas.draw_idle()
        self.sync_peak_listbox()
    
    def on_click(self, event):
        """Captures mouse clicks to label peaks or measure areas interactively."""
        if event.inaxes is None or self.var_click_mode.get() == 'none': 
            return
            
        mode = self.var_click_mode.get()
        x_click = event.xdata
        
        # --- THE KEY FIX: Use the helper to get the CORRECT Visual Y values ---
        x_arr, y_arr = self.get_processed_data_for_stem(self.current_stem)
        fs = state.file_set[self.current_stem]
        
        # Find the point closest to the click using the NEW Y-values
        idx = (np.abs(x_arr - x_click)).argmin()
        closest_x, closest_y = x_arr[idx], y_arr[idx]
        
        if mode == 'peak':
            # This now saves the peak at the NEW corrected height!
            fs.setdefault('labels', []).append((closest_x, closest_y, f"{closest_x:.1f}"))
            self.update_plot()

        elif mode == 'xrd_peak':
            # XRD Logic now sees the baseline-corrected data
            result = self.calculate_xrd_peak(x_click, x_arr, y_arr)
            if result:
                px, py, fwhm, d = result
                fs.setdefault('xrd_peaks', []).append((px, py, fwhm, d))
                self.update_plot()
            
        elif mode == 'area':
            if getattr(self, 'area_start', None) is None:
                self.area_start = closest_x
                event.inaxes.axvline(closest_x, color='gray', linestyle='--', alpha=0.7)
                event.inaxes.text(closest_x, closest_y, " Start", color='gray', fontweight='bold')
                self.canvas.draw()
            else:
                area_end = closest_x
                x1, x2 = min(self.area_start, area_end), max(self.area_start, area_end)
                try:
                    mask = (x_arr >= x1) & (x_arr <= x2)
                    x_sel, y_sel = x_arr[mask], y_arr[mask]
                    if len(x_sel) > 1:
                        # Area calculation on corrected data
                        baseline = np.interp(x_sel, [x_sel[0], x_sel[-1]], [y_sel[0], y_sel[-1]])
                        true_peak_y = y_sel - baseline
                        area_val = abs(np.trapz(true_peak_y, x_sel))
                        fs.setdefault('areas', []).append((x1, x2, area_val))
                except Exception as e:
                    print(f"🚨 MATH ERROR: {e}")
                self.area_start = None 
                self.update_plot()
                
        elif mode == 'baseline':
            # Note: For DRAWING the baseline, we usually use the data before correction
            # so we use the local closest_y calculated from x_arr, y_arr.
            self.baseline_pts.append((closest_x, closest_y))
            event.inaxes.plot(closest_x, closest_y, 'go', markersize=6)
            if len(self.baseline_pts) > 1:
                pts = sorted(self.baseline_pts, key=lambda p: p[0])
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                event.inaxes.plot(xs, ys, 'g--', alpha=0.7)
            self.canvas.draw()
        
        elif mode == 'deconv':
            if getattr(self, 'deconv_start', None) is None:
                self.deconv_start = closest_x
                event.inaxes.axvline(closest_x, color='purple', linestyle='--', alpha=0.7)
                event.inaxes.text(closest_x, closest_y, " Fit Start", color='purple', fontweight='bold')
                self.canvas.draw()
            else:
                deconv_end = closest_x
                x1, x2 = min(self.deconv_start, deconv_end), max(self.deconv_start, deconv_end)
                self.deconv_start = None 
                # Deconvolution now runs on the CLEANED data!
                self.perform_deconvolution(x1, x2, x_arr, y_arr)
    
    def perform_deconvolution(self, x1, x2, x_arr, y_arr):
        """Fits multiple Gaussian curves under a selected peak region."""

        # Ask user how many sub-peaks they expect
        num_peaks = simpledialog.askinteger("Deconvolution", "How many sub-peaks do you expect in this region?", parent=self, minvalue=1, maxvalue=5)
        if not num_peaks:
            self.update_plot()
            return

        # Isolate the data block
        mask = (x_arr >= x1) & (x_arr <= x2)
        x_sel = x_arr[mask]
        y_sel = y_arr[mask]

        if len(x_sel) < 10:
            messagebox.showwarning("Error", "Not enough data points in this region to run a fit.")
            self.update_plot()
            return

        # Subtract baseline just for the fitting area
        baseline = np.interp(x_sel, [x_sel[0], x_sel[-1]], [y_sel[0], y_sel[-1]])
        
        # --- NEW: Smart detection for %Transmittance (Valleys) vs Absorbance (Peaks) ---
        mid_idx = len(y_sel) // 2
        is_valley = y_sel[mid_idx] < baseline[mid_idx]
        
        if is_valley:
            y_fit = baseline - y_sel # Flip valley upside-down into a positive peak for the math
        else:
            y_fit = y_sel - baseline
            
        y_fit = np.clip(y_fit, 0, None) # Ensure we don't fit negative noise

        def multi_gaussian(x, *params):
            y = np.zeros_like(x)
            for i in range(0, len(params), 3):
                A, mu, sigma = params[i], params[i+1], params[i+2]
                y += A * np.exp(-((x - mu)**2) / (2 * sigma**2))
            return y

        # Build initial guesses (Amplitude, Center, Width)
        guess, bounds_lower, bounds_upper = [], [], []
        amp_guess = np.max(y_fit)
        width = x2 - x1
        spacing = width / (num_peaks + 1)
        
        for i in range(num_peaks):
            guess.extend([amp_guess, x1 + spacing * (i + 1), width / (num_peaks * 2)])
            bounds_lower.extend([0, x1, 0.01]) # Min limits
            bounds_upper.extend([amp_guess * 1.5, x2, width]) # Max limits

        try:
            # Run the Levenberg-Marquardt fitting algorithm
            popt, _ = curve_fit(multi_gaussian, x_sel, y_fit, p0=guess, bounds=(bounds_lower, bounds_upper))
            
            # Save the results (Now we also save 'is_valley' so the graph knows which way to draw it)
            fs = state.file_set[self.current_stem]
            fs.setdefault('deconvs', []).append((x1, x2, baseline, popt, num_peaks, is_valley))
            print(f"✅ Deconvolution successful with {num_peaks} curves.")
            
        except Exception as e:
            messagebox.showerror("Fitting Error", f"Could not converge on a fit. Try a narrower region.\n\nError: {e}")
        
        self.var_click_mode.set('none') # Turn off the tool
        self.update_plot()
    
    def export_deconv_data(self):
        """Exports the deconvolution mathematical curves to CSV and saves a plot image."""
        fs = state.file_set.get(self.current_stem, {})
        deconvs = fs.get('deconvs', [])
        
        if not deconvs:
            messagebox.showwarning("No Data", "No deconvolution fits found for the current file.", parent=self)
            return
            
        folder = filedialog.askdirectory(title="Select Folder to Save Deconvolution Data", parent=self)
        if not folder: return
        
        import csv, os
        base_name = self.current_stem
        
        # 1. Export High-Res Image of the graph
        img_path = os.path.join(folder, f"{base_name}_Deconvolution_Plot.png")
        self.fig.savefig(img_path, dpi=300, bbox_inches='tight')
        
        # 2. Export Math Data to CSV
        for idx, (x1, x2, baseline, popt, num_peaks, is_valley) in enumerate(deconvs):
            csv_path = os.path.join(folder, f"{base_name}_Deconv_Region_{idx+1}.csv")
            
            x_fit = np.linspace(min(x1, x2), max(x1, x2), 500)
            
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                headers = ["Wavenumber", "Total Fit"] + [f"Peak_{i+1}" for i in range(num_peaks)]
                writer.writerow(headers)
                
                for x_val in x_fit:
                    row = [x_val]
                    total_y = 0
                    peak_ys = []
                    
                    for i in range(num_peaks):
                        A, mu, sigma = popt[i*3], popt[i*3+1], popt[i*3+2]
                        y_peak = A * np.exp(-((x_val - mu)**2) / (2 * sigma**2)) # Gaussian formula
                        peak_ys.append(y_peak)
                        total_y += y_peak
                        
                    # Calculate final Y values based on whether it is Absorbance or %T
                    if is_valley:
                        row.append(baseline - total_y)
                        for py in peak_ys: row.append(baseline - py)
                    else:
                        row.append(baseline + total_y)
                        for py in peak_ys: row.append(baseline + py)
                        
                    writer.writerow(row)
                    
        messagebox.showinfo("Success", f"Exported Plot Image and {len(deconvs)} CSV data file(s) to:\n{folder}", parent=self)

    def on_close(self):
        # Call our custom dialog
        dialog = CloseDialog(self)
        self.wait_window(dialog) # Pause the app until the dialog is closed
        
        # If they clicked Cancel or the red 'X' on the pop-up, do nothing
        if not dialog.choice:
            return 
            
        # --- 1. HANDLE SAVING ---
        if "save" in dialog.choice:
            try:
                # FIXED: This now exactly matches your actual Export/Save function!
                self.save_session_cmd() 
            except Exception:
                pass # If they cancel the save window, ignore the error
                
        # --- 2. HANDLE DESTINATION ---
        if "exit" in dialog.choice:
            # FIXED: Bypass Tkinter's safety blocks and force the app to close immediately
            import os
            os._exit(0) 
            
        elif "menu" in dialog.choice:
            # FIXED: Literally restarts the Python script from scratch for a perfectly clean Main Menu!
            import sys
            import os
            os.execl(sys.executable, sys.executable, *sys.argv)
    
    def calculate_xrd_peak(self, x_click, x_arr, y_arr):
        """Finds the true peak tip, calculates FWHM, and computes Grain Size."""
        # 1. SMART SNAP: Find the highest point within +/- 1 degree of the click
        mask = (x_arr >= x_click - 1.0) & (x_arr <= x_click + 1.0)
        if not np.any(mask): return None
        
        x_window = x_arr[mask]
        y_window = y_arr[mask]
        
        max_idx = np.argmax(y_window)
        peak_x = x_window[max_idx]
        peak_y = y_window[max_idx]
        
        # 2. FWHM Calculation
        half_max = peak_y / 2.0
        
        # Find left and right bounds of the peak
        left_mask = (x_window < peak_x)
        right_mask = (x_window > peak_x)
        
        try:
            # Interpolate to find exact X coordinates where Y crosses half-max
            left_x = np.interp(half_max, y_window[left_mask], x_window[left_mask])
            # For the right side, x must be strictly increasing for interp, so we reverse it
            right_x = np.interp(half_max, y_window[right_mask][::-1], x_window[right_mask][::-1])
            fwhm = right_x - left_x
        except ValueError:
            fwhm = 0.0 # If interpolation fails due to noise
            
        # 3. Scherrer Equation for Grain Size (D = K * lambda / (FWHM * cos(theta)))
        if fwhm > 0:
            K = 0.9
            lam = 0.15406 # Cu K-alpha in nanometers
            
            theta_deg = peak_x / 2.0
            theta_rad = np.radians(theta_deg)
            fwhm_rad = np.radians(fwhm)
            
            grain_size_nm = (K * lam) / (fwhm_rad * np.cos(theta_rad))
        else:
            grain_size_nm = 0.0
            
        return (peak_x, peak_y, fwhm, grain_size_nm)
    
    def auto_find_xrd_peaks(self):
        """Automatically detects XRD peaks and calculates grain size using processed data."""
        # --- THE FIX: Use processed data for accurate height/prominence ---
        x_data, y_data = self.get_processed_data_for_stem(self.current_stem)
        
        # Use 'height' and 'prominence' from the UI on the CORRECTED y_data
        peaks, _ = find_peaks(y_data, 
                               height=float(self.var_xrd_min_height.get()),
                               prominence=float(self.var_prominence.get()))
        
        fs = state.file_set[self.current_stem]
        for p in peaks:
            # Use the XRD Smart Snap logic on the corrected data
            result = self.calculate_xrd_peak(x_data[p], x_data, y_data)
            if result:
                px, py, fwhm, d = result
                fs.setdefault('xrd_peaks', []).append((px, py, fwhm, d))
                
        self.update_plot()
    
    def show_grain_size_chart(self):
        """Pops up a 2-panel chart: Bar Graph and Gaussian Distribution."""
        fs = state.file_set.get(self.current_stem, {})
        peaks = fs.get('xrd_peaks', [])
        
        # Filter out peaks that failed math (Size 0)
        valid_peaks = [p for p in peaks if p[3] > 0]
        
        if not valid_peaks:
            messagebox.showwarning("No Data", "Please select valid peaks to calculate grain size first!", parent=self)
            return
            
        # Sort by 2-theta
        valid_peaks.sort(key=lambda p: p[0])
        
        labels = [f"{p[0]:.1f}°" for p in valid_peaks]
        sizes = [p[3] for p in valid_peaks]
        
        # Calculate Statistics
        avg_size = np.mean(sizes)
        std_dev = np.std(sizes) if len(sizes) > 1 else 0.0
        
        # Setup Window
        chart_win = tk.Toplevel(self)
        chart_win.title(f"Grain Size Analysis - {self.current_stem}")
        chart_win.geometry("1000x550") # Made the window taller to safely fit the button!
        
        # ==========================================
        # 1. BUILD THE SAVE BUTTON FIRST (So it doesn't get squished)
        # ==========================================
        def save_distribution_chart():
            filepath = filedialog.asksaveasfilename(
                title="Save Distribution Chart",
                initialfile=f"{self.current_stem}_grain_size_distribution.png",
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("SVG", "*.svg")],
                parent=chart_win
            )
            if filepath:
                fig.savefig(filepath, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Success", f"Chart saved successfully!\n{filepath}", parent=chart_win)

        btn_frame = ttk.Frame(chart_win)
        btn_frame.pack(side="bottom", fill="x", pady=10)
        ttk.Button(btn_frame, text="💾 Export This 2-Panel Chart as Image", command=save_distribution_chart).pack(ipady=5)

        # ==========================================
        # 2. BUILD THE GRAPHS
        # ==========================================
        fig = plt.Figure(figsize=(10, 4), dpi=100)
        
        # Left Graph: BAR CHART (Size vs 2-Theta)
        ax1 = fig.add_subplot(121)
        ax1.bar(labels, sizes, color='#89b4fa', edgecolor='black', zorder=3)
        ax1.axhline(avg_size, color='red', linestyle='--', linewidth=2, zorder=4, label=f"Average: {avg_size:.1f} nm")
        if std_dev > 0:
            ax1.fill_between([-0.5, len(labels)-0.5], avg_size - std_dev, avg_size + std_dev, color='red', alpha=0.1, zorder=1, label=f"±1σ ({std_dev:.1f} nm)")
            
        ax1.set_ylabel("Crystallite Size (nm)", fontweight='bold')
        ax1.set_xlabel("Peak Position (2θ)", fontweight='bold')
        ax1.set_title("Size per Diffraction Peak", fontweight='bold')
        ax1.grid(axis='y', linestyle='--', alpha=0.7, zorder=0)
        ax1.legend()
        
        # Right Graph: GAUSSIAN FIT (Probability vs Size)
        ax2 = fig.add_subplot(122)
        if len(sizes) > 1 and std_dev > 0:
            bins = max(3, len(sizes))
            ax2.hist(sizes, bins=bins, density=True, color='#a6adc8', edgecolor='black', alpha=0.6, label='Data Histogram')
            
            x_curve = np.linspace(min(sizes) - 3*std_dev, max(sizes) + 3*std_dev, 100)
            y_curve = (1 / (std_dev * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_curve - avg_size) / std_dev)**2)
            
            ax2.plot(x_curve, y_curve, color='#1e1e2e', linewidth=2.5, label='Gaussian Fit')
            ax2.axvline(avg_size, color='red', linestyle='--', linewidth=2, label=f"Mean: {avg_size:.1f} nm")
        else:
            ax2.text(0.5, 0.5, "Need at least 2 peaks\nfor a Gaussian fit.", ha='center', va='center', fontsize=12, color='gray')
            ax2.set_xlim(0, 1)
            ax2.set_ylim(0, 1)

        ax2.set_xlabel("Crystallite Size (nm)", fontweight='bold')
        ax2.set_ylabel("Probability Density", fontweight='bold')
        ax2.set_title("Gaussian Size Distribution", fontweight='bold')
        ax2.legend(loc='upper right')
        
        # Pack the canvas LAST so it takes up the remaining space perfectly
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=chart_win)
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        canvas.draw()