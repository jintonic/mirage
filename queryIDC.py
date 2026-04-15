import os, warnings, pydicom, webbrowser
from textual import work, on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

warnings.simplefilter(action='ignore', category=FutureWarning)

class MIRAGEArchiveExplorer(App):
    """
    MIRAGE Local Archive Explorer
    Top Row: 4 Panels (Collection -> Case -> Study -> Series)
    Bottom Row: 1 Panel (Slice List <-> Header Table)
    """
    CSS = """
    Screen { background: #002b36; color: #839496; }
    #top_row { height: 40%; border-bottom: double #586e75; }
    #bottom_row { height: 60%; }
    .pane { height: 1fr; border-right: solid #586e75; width: 1fr; }
    .title-label { background: #268bd2; color: #eee8d5; text-style: bold; padding: 0 1; width: 100%; }
    DataTable { background: #073642; border: none; }
    #header_table { display: none; }
    """

    BINDINGS = [
        Binding("q", "quit", "Exit"),
        Binding("space", "toggle_view", "Header/Slices"),
        Binding("r", "rescan", "Rescan CWD"),
        Binding("v", "open_viewer", "View in IDC"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top_row"):
            with Vertical(classes="pane"):
                yield Label(" COLLECTIONS ", classes="title-label")
                yield DataTable(id="col_table")
            with Vertical(classes="pane"):
                yield Label(" CASES ", classes="title-label")
                yield DataTable(id="case_table")
            with Vertical(classes="pane"):
                yield Label(" STUDIES ", classes="title-label")
                yield DataTable(id="study_table")
            with Vertical(classes="pane"):
                yield Label(" SERIES ", classes="title-label")
                yield DataTable(id="series_table")
        
        with Vertical(id="bottom_row"):
            yield Label(" DATA EXPLORER ", id="bottom_title", classes="title-label")
            yield DataTable(id="slice_table")
            yield DataTable(id="header_table") # Now a DataTable
        yield Footer()

    def on_mount(self) -> None:
        self.tables = {
            "col": self.query_one("#col_table", DataTable),
            "case": self.query_one("#case_table", DataTable),
            "study": self.query_one("#study_table", DataTable),
            "series": self.query_one("#series_table", DataTable),
            "slice": self.query_one("#slice_table", DataTable),
            "header": self.query_one("#header_table", DataTable)
        }
        for t in self.tables.values():
            t.cursor_type = "row"
        
        # Init Columns
        self.tables["col"].add_column("Collection")
        self.tables["case"].add_column("Patient ID")
        self.tables["study"].add_column("Study UID")
        self.tables["series"].add_columns("Modality", "Description")
        self.tables["slice"].add_columns("Slice #", "Filename")
        self.tables["header"].add_columns("Tag (G,E)", "Name", "Value")
        
        self.action_rescan()

    @work(thread=True)
    def action_rescan(self):
        archive_map = {}
        cwd = os.getcwd()
        for root, _, files in os.walk(cwd):
            dcm_files = [f for f in sorted(files) if f.endswith(".dcm")]
            if dcm_files:
                rel_path = os.path.relpath(root, cwd)
                parts = rel_path.split(os.sep)
                if len(parts) >= 3:
                    coll_case, study_uid, series_uid = parts[-3], parts[-2], parts[-1]
                    coll = coll_case.rsplit('-', 1)[0] if '-' in coll_case else "Local"
                    case = coll_case.rsplit('-', 1)[1] if '-' in coll_case else coll_case
                    s_map = archive_map.setdefault(coll, {}).setdefault(case, {}).setdefault(study_uid, {})
                    s_map[series_uid] = [os.path.join(root, f) for f in dcm_files]
        self.archive_map = archive_map
        self.call_from_thread(self.auto_initialize_ui)

    def auto_initialize_ui(self):
        """Populates all tables and drills down to the first series automatically."""
        self.populate_collections()
        
        # 1. Select first Collection
        if self.tables["col"].row_count > 0:
            # Get the first key from the rows dictionary (ordered in newer Python)
            first_key = list(self.tables["col"].rows.keys())[0]
            self.tables["col"].move_cursor(row=0)
            self.manual_select_coll(first_key.value)
            
        # 2. Select first Case
        if self.tables["case"].row_count > 0:
            first_key = list(self.tables["case"].rows.keys())[0]
            self.tables["case"].move_cursor(row=0)
            self.manual_select_case(first_key.value)
            
        # 3. Select first Study
        if self.tables["study"].row_count > 0:
            first_key = list(self.tables["study"].rows.keys())[0]
            self.tables["study"].move_cursor(row=0)
            self.manual_select_study(first_key.value)
            
        # 4. Select first Series
        if self.tables["series"].row_count > 0:
            first_key = list(self.tables["series"].rows.keys())[0]
            self.tables["series"].move_cursor(row=0)
            self.manual_select_series(first_key.value)

        self.tables["col"].focus()

    # --- Manual Selection Helpers ---
    # These allow the UI to populate without a physical 'Enter' key press
    
    def manual_select_coll(self, coll_id):
        self.tables["case"].clear()
        for case in sorted(self.archive_map[coll_id].keys()):
            self.tables["case"].add_row(case, key=f"{coll_id}|{case}")

    def manual_select_case(self, key_str):
        coll, case = key_str.split('|')
        self.tables["study"].clear()
        for study in sorted(self.archive_map[coll][case].keys()):
            self.tables["study"].add_row(f"{study[:8]}...{study[-8:]}", key=f"{coll}|{case}|{study}")

    def manual_select_study(self, key_str):
        coll, case, study = key_str.split('|')
        self.tables["series"].clear()
        for sid, paths in self.archive_map[coll][case][study].items():
            ds = pydicom.dcmread(paths[0], stop_before_pixels=True)
            self.tables["series"].add_row(
                getattr(ds, "Modality", "??"), 
                getattr(ds, "SeriesDescription", "None")[:15], 
                key=f"{coll}|{case}|{study}|{sid}"
            )

    def manual_select_series(self, key_str):
        coll, case, study, sid = key_str.split('|')
        paths = self.archive_map[coll][case][study][sid]
        self.tables["slice"].clear()
        for i, p in enumerate(paths):
            self.tables["slice"].add_row(str(i+1), os.path.basename(p), key=p)

    def populate_collections(self):
        self.tables["col"].clear()
        for c in sorted(self.archive_map.keys()): self.tables["col"].add_row(c, key=c)
        self.tables["col"].focus()

    @on(DataTable.RowSelected, "#col_table")
    def select_coll(self, event):
        coll = event.row_key.value
        self.tables["case"].clear()
        for case in sorted(self.archive_map[coll].keys()):
            self.tables["case"].add_row(case, key=f"{coll}|{case}")
        self.tables["case"].focus()

    @on(DataTable.RowSelected, "#case_table")
    def select_case(self, event):
        coll, case = event.row_key.value.split('|')
        self.tables["study"].clear()
        for study in sorted(self.archive_map[coll][case].keys()):
            self.tables["study"].add_row(f"{study[:8]}...{study[-8:]}", key=f"{coll}|{case}|{study}")
        self.tables["study"].focus()

    @on(DataTable.RowSelected, "#study_table")
    def select_study(self, event):
        coll, case, study_folder = event.row_key.value.split('|')
        series_map = self.archive_map[coll][case][study_folder]
        self.tables["series"].clear()
        
        for sid_folder, paths in series_map.items():
            # We skip the pydicom.dcmread here for speed!
            # Just show the folder name or a placeholder
            self.tables["series"].add_row(
                "??", # Modality will be filled when selected
                sid_folder[:20], 
                key=f"{coll}|{case}|{study_folder}|{sid_folder}"
            )
        self.tables["series"].focus()

    @on(DataTable.RowSelected, "#series_table")
    def select_series(self, event):
        coll, case, study, sid = event.row_key.value.split('|')
        paths = self.archive_map[coll][case][study][sid]
        self.tables["slice"].clear()
        for i, p in enumerate(paths):
            self.tables["slice"].add_row(str(i+1), os.path.basename(p), key=p)
        self.tables["slice"].focus()

    def action_toggle_view(self):
        h_table = self.tables["header"]
        s_table = self.tables["slice"]
        title = self.query_one("#bottom_title", Label)
        
        if h_table.display:
            h_table.display = False
            s_table.display = True
            title.update(" [ SLICE LIST ] ")
            s_table.focus()
        else:
            if s_table.row_count > 0:
                # Proper coordinate-to-key mapping for newer Textual
                row_key, _ = s_table.coordinate_to_cell_key(s_table.cursor_coordinate)
                path = row_key.value
                self.populate_header_table(path)
                h_table.display = True
                s_table.display = False
                title.update(f" [ HEADER: {os.path.basename(path)} ] ")
                h_table.focus()

    def populate_header_table(self, path):
        ds = pydicom.dcmread(path, stop_before_pixels=True)
        self.tables["header"].clear()
        for el in ds:
            if el.tag.group < 0x7FE0:
                tag_hex = f"({el.tag.group:04X},{el.tag.element:04X})"
                self.tables["header"].add_row(tag_hex, el.name, str(el.value))

    def action_open_viewer(self):
        """Extracts UIDs from the exact DICOM file highlighted in the slice list."""
        if self.tables["slice"].row_count > 0:
            # Get the path of the specific slice highlighted in the bottom table
            row_key, _ = self.tables["slice"].coordinate_to_cell_key(
                self.tables["slice"].cursor_coordinate
            )
            file_path = row_key.value
            
            # Read the file to get the absolute ground truth
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
            
            # Get the UIDs from the official DICOM tags
            study_uid = str(ds.StudyInstanceUID)
            series_uid = str(ds.SeriesInstanceUID)
            
            url = (
                f"https://viewer.imaging.datacommons.cancer.gov/v3/viewer/?"
                f"StudyInstanceUIDs={study_uid}&"
                f"SeriesInstanceUIDs={series_uid}"
            )
            
            self.notify(f"Launching IDC Viewer for Slice: {os.path.basename(file_path)}")
            webbrowser.open(url)

if __name__ == "__main__":
    MIRAGEArchiveExplorer().run()