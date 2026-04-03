import os, json, warnings, idc_index
from textual import work, on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

# Ignore metadata warnings from the IDC/DuckDB backend
warnings.simplefilter(action='ignore', category=FutureWarning)

# Setup local cache paths
CACHE_DIR = os.path.expanduser("~/.cache/mirage")
CACHE_PATH = os.path.join(CACHE_DIR, "idc.json")
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class MIRAGEVimBrowser(App):
    """
    MIRAGE IDC Browser
    - Dictionary/Results on Left/Top.
    - Values/Headers on Right/Bottom.
    - 's': Toggle Multi-Sort (Slices then Size).
    - 'Space': Toggle Filters (in Value mode) or Run Search (in Dict mode).
    - 'Enter': Fetch Header to detail panel.
    """
    
    CSS = """
    Screen { background: #002b36; color: #839496; }
    #main_container { height: 1fr; }
    
    /* Layout Areas */
    #left_area { height: 1fr; width: 1.5fr; }
    #right_area { height: 1fr; width: 1fr; border-left: solid #586e75; display: none; }
    #top_panel, #bottom_panel, #results_panel { 
        height: 1fr; border: tall #268bd2; background: #073642; margin: 1; 
    }
    
    #bottom_panel { border: tall #d33682; }
    #results_panel { border: tall #859900; display: none; }
    
    .title-label { padding: 0 1; background: #268bd2; color: #eee8d5; text-style: bold; width: 100%; }
    .filter-bar { padding: 0 1; background: #586e75; color: #eee8d5; min-height: 1; }
    
    DataTable { color: #839496; }
    DataTable > .datatable--cursor { background: #073642; color: #268bd2; text-style: bold; }
    """

    BINDINGS = [
        Binding("escape", "reset_view", "Back/Reset", show=True),
        Binding("s", "toggle_sort", "Sort Toggle", show=True),
        Binding("q", "quit", "Exit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(" [ ACTIVE FILTERS ]: None", id="filter_display", classes="filter-bar")
        
        with Horizontal(id="main_container"):
            # LEFT SIDE: Search & Dictionary
            with Vertical(id="left_area"):
                yield Label(" [ METADATA DICTIONARY ]", id="dict_title", classes="title-label")
                yield DataTable(id="top_panel")
                # Removed 'display=False' argument here
                yield Label(" [ SEARCH RESULTS ]", id="res_title", classes="title-label")
                yield DataTable(id="results_panel")
            
            # RIGHT SIDE: Detail Explorer
            with Vertical(id="right_area"):
                yield Label(" [ EXPLORER ]", id="bottom_title", classes="title-label")
                yield DataTable(id="bottom_panel")
                
        yield Footer()

    def on_mount(self) -> None:
        self.filters = {}
        self.sort_state = 0 # 0:Orig, 1:Desc, 2:Asc
        self.top_table = self.query_one("#top_panel", DataTable)
        self.bottom_table = self.query_one("#bottom_panel", DataTable)
        self.results_table = self.query_one("#results_panel", DataTable)
        
        for t in [self.top_table, self.bottom_table, self.results_table]:
            t.cursor_type = "row"
        
        self.top_table.add_columns("Column", "Sample")
        self.bottom_table.add_columns("Value", "Count")
        
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r") as f:
                    data = json.load(f)
                    for k, v in data.items(): 
                        self.top_table.add_row(str(k), str(v))
            except Exception:
                pass
        self.initialize_backend()
        self.top_table.focus()

    @work(exclusive=True, thread=True)
    def initialize_backend(self):
        self.client = idc_index.IDCClient()
        self.call_from_thread(self.notify, "IDC Connected")

    def action_reset_view(self):
        self.query_one("#dict_title").display = True
        self.top_table.display = True
        self.query_one("#res_title").display = False
        self.results_table.display = False
        self.query_one("#right_area").display = False
        self.top_table.focus()

    def action_toggle_sort(self):
        if not self.results_table.display or self.results_table.row_count == 0:
            return

        self.sort_state = (self.sort_state + 1) % 3
        if self.sort_state == 0:
            self.notify("Resetting to Original Order")
            self.run_full_search()
            return

        is_rev = (self.sort_state == 1)
        mode = "[DESC]" if is_rev else "[ASC]"
        self.notify(f"Sorting: Slices + Size {mode}")

        try:
            rows = [self.results_table.get_row(rk) for rk in self.results_table.rows]
            rows.sort(key=lambda r: (int(float(r[3] or 0)), float(r[4] or 0)), reverse=is_rev)
            self.results_table.clear()
            for r in rows: 
                self.results_table.add_row(*r)
        except Exception as e:
            self.notify(f"Sort Error: {e}", severity="error")

    @on(DataTable.RowSelected, "#top_panel")
    def dive_into_values(self, event: DataTable.RowSelected):
        self.current_col = event.data_table.get_row_at(event.cursor_row)[0]
        self.query_one("#right_area").display = True
        self.update_value_list(self.current_col)

    @work(exclusive=True, thread=True)
    def update_value_list(self, col):
        res = self.client.sql_query(f'SELECT "{col}", COUNT(*) FROM index GROUP BY "{col}" ORDER BY 2 DESC LIMIT 100')
        self.call_from_thread(self.refresh_bottom, res)

    def refresh_bottom(self, df):
        self.bottom_table.clear(columns=True)
        self.bottom_table.add_columns("Value", "Count")
        self.query_one("#bottom_title", Label).update(f" [ VALUES: {self.current_col} ] ")
        for _, r in df.iterrows(): 
            self.bottom_table.add_row(str(r[0]), str(r[1]))
        self.bottom_table.focus()

    def on_key(self, event):
        if event.key == "space":
            if self.focused == self.bottom_table:
                val = self.bottom_table.get_row_at(self.bottom_table.cursor_row)[0]
                if self.current_col not in self.filters: self.filters[self.current_col] = set()
                if val in self.filters[self.current_col]:
                    self.filters[self.current_col].remove(val)
                    if not self.filters[self.current_col]: self.filters.pop(self.current_col)
                else: self.filters[self.current_col].add(val)
                self.update_filter_bar()
            elif self.focused == self.top_table:
                self.run_full_search()

    def run_full_search(self):
        clauses = [f'"{c}" IN ({", ".join([f"\'{v}\'" for v in vs])})' for c, vs in self.filters.items()]
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f'SELECT PatientID, Modality, BodyPartExamined, instanceCount, ROUND(series_size_MB,2), SeriesInstanceUID FROM index {where} LIMIT 500'
        self.execute_search(query)

    @work(exclusive=True, thread=True)
    def execute_search(self, query):
        df = self.client.sql_query(query)
        self.call_from_thread(self.show_results, df)

    def show_results(self, df):
        self.query_one("#dict_title").display = False
        self.top_table.display = False
        self.query_one("#res_title").display = True
        self.results_table.display = True
        self.query_one("#right_area").display = False
        
        self.results_table.clear(columns=True)
        self.results_table.add_columns("PatientID", "Modality", "BodyPart", "Slices", "Size(MB)", "UID")
        for _, row in df.iterrows(): 
            self.results_table.add_row(*[str(v) for v in row])
        self.results_table.focus()

    @on(DataTable.RowSelected, "#results_panel")
    def handle_header_request(self, event: DataTable.RowSelected):
        uid = event.data_table.get_row_at(event.cursor_row)[5]
        self.fetch_header_data(uid)

    @work(thread=True)
    def fetch_header_data(self, uid):
        try:
            self.call_from_thread(self.notify, f"Fetching Header: {uid[:8]}...")
            query = f"SELECT * FROM index WHERE SeriesInstanceUID='{uid}' LIMIT 1"
            df = self.client.sql_query(query)
            if not df.empty:
                items = [(str(c), str(df.iloc[0][c])) for c in df.columns if str(df.iloc[0][c]).strip().lower() != "none"]
                self.call_from_thread(self.display_header_in_panel, items)
            else:
                self.call_from_thread(self.notify, "No metadata found", severity="warning")
        except Exception as e:
            self.call_from_thread(self.notify, f"Error: {e}", severity="error")

    def display_header_in_panel(self, items):
        self.query_one("#right_area").display = True
        self.bottom_table.clear(columns=True)
        self.bottom_table.add_columns("DICOM Tag", "Value")
        self.query_one("#bottom_title", Label).update(" [ DICOM HEADER EXPLORER ] ")
        for tag, val in items: 
            self.bottom_table.add_row(tag, val)
        self.bottom_table.focus()
        self.notify("Header Loaded")

    def on_resize(self, event):
        container = self.query_one("#main_container")
        container.styles.layout = "horizontal" if event.size.width > 120 else "vertical"

    def update_filter_bar(self):
        msg = " AND ".join([f"{k} IN {tuple(v) if len(v)>1 else '('+repr(list(v)[0])+')'}" for k, v in self.filters.items()]) or "None"
        self.query_one("#filter_display", Label).update(f" [ ACTIVE FILTERS ]: {msg}")

if __name__ == "__main__":
    MIRAGEVimBrowser().run()