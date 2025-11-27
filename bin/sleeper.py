#!/usr/bin/env python3

import argparse
import datetime
import json
import pathlib
import sys
from typing import Optional

import requests
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static, Tree

# --------------------------
# Cache + API
# --------------------------

CACHE = pathlib.Path("cache")
CACHE.mkdir(exist_ok=True)
BASE_URL = "https://api.sleeper.app/v1"


def cache_path(name: str) -> pathlib.Path:
    return CACHE / f"{name}.json"


def load_cache(name: str) -> Optional[dict]:
    p = cache_path(name)
    if p.exists():
        try:
            return json.load(open(p))
        except:
            return None


def save_cache(name: str, data: dict):
    with open(cache_path(name), "w") as f:
        json.dump(data, f, indent=2)


def fetch(url: str):
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def api_get(name: str, url: str, force: bool = False):
    cached = load_cache(name)
    if cached and not force:
        return cached
    data = fetch(url)
    save_cache(name, data)
    return data


# --------------------------
# Sleeper API wrapper
# --------------------------


class SleeperAPI:
    def __init__(self, league_id: str):
        try:
            validated_id = int(league_id)
        except ValueError:
            print(f"League ID must be an integer string, got {league_id} type {type(league_id)}")
            sys.exit(1)
        else:
            self.league_id = str(validated_id)

    def league(self, force=False):
        return api_get(f"league_{self.league_id}", f"{BASE_URL}/league/{self.league_id}", force)

    def users(self, force=False):
        return api_get(f"users_{self.league_id}", f"{BASE_URL}/league/{self.league_id}/users", force)

    def rosters(self, force=False):
        return api_get(f"rosters_{self.league_id}", f"{BASE_URL}/league/{self.league_id}/rosters", force)

    def matchups(self, week: int, force=False):
        return api_get(
            f"matchups_{self.league_id}_week_{week}", f"{BASE_URL}/league/{self.league_id}/matchups/{week}", force
        )

    def user(self, username: str):
        """Return user info by username (public)."""
        return fetch(f"{BASE_URL}/user/{username}")

    def user_leagues(self, user_id: str, season: int):
        """Return all NFL leagues the user is in."""
        return fetch(f"{BASE_URL}/user/{user_id}/leagues/nfl/{season}")


# --------------------------
# League Lookup Screen
# --------------------------


class LeagueLookupScreen(App):
    """Initial screen to get league ID."""

    CSS = """
    Vertical {
        align: center middle;
        width: 100%;
        height: 100%;
    }

    Container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }

    Label {
        margin: 1 0;
    }

    Input {
        margin-bottom: 1;
    }

    Button {
        margin: 1 0;
        width: 100%;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, username: Optional[str] = None):
        super().__init__()
        self.username = username
        self.league_id = 0
        self.api = SleeperAPI("0")  # Temporary API for user lookup

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with Vertical():
            with Container():
                yield Label("Welcome to Sleeper Fantasy Football TUI", id="title")
                yield Label("Choose how to find your league:")
                yield Label("Option 1: Enter League ID")
                yield Input(placeholder="League ID", id="league_id_input")
                yield Button("Load by League ID", id="btn_load_id", variant="primary")
                yield Label("Option 2: Search by Username")
                yield Input(
                    placeholder="Sleeper Username", id="username_input", value=self.username if self.username else ""
                )
                yield Input(placeholder="League Name (partial match)", id="league_name_input")
                yield Button("Search Leagues", id="btn_search", variant="success")
                yield Static("", id="status")

    def on_mount(self):
        # If league_id provided, load it directly
        if self.league_id:
            self._load_league(str(self.league_id))

    def _load_league(self, league_id: str):
        """Validate and load the league."""
        try:
            # Validate league ID
            int(league_id)
            # Test the API
            test_api = SleeperAPI(league_id)
            test_api.league()

            # Success - exit and launch main app
            self.league_id = league_id
            self.exit(league_id)
        except ValueError:
            self.query_one("#status", Static).update("League ID must be numeric")
        except Exception as e:
            self.query_one("#status", Static).update(f"Error loading league: {str(e)}")

    def _search_leagues(self, username: str, league_name: str):
        """Search for leagues by username and name."""
        status = self.query_one("#status", Static)
        status.update("Searching...")

        try:
            # Step 1: find user
            user_data = self.api.user(username)
            user_id = user_data.get("user_id")
            if not user_id:
                status.update("Could not resolve user ID")
                return

            # Step 2: find user's leagues for current season
            current_year = datetime.datetime.now().year
            leagues = self.api.user_leagues(user_id, current_year)

            # Step 3: filter by name
            name_query = league_name.lower()
            matches = [lg for lg in leagues if name_query in lg["name"].lower()]

            if not matches:
                status.update("No matching leagues found")
                return

            # Step 4: show results
            self._show_search_results(matches)

        except Exception as e:
            status.update(f"Error: {str(e)}")

    def _show_search_results(self, leagues):
        """Display search results in a table."""
        # Get the existing container and clear it
        container = self.query_one(Vertical).query_one(Container)
        container.remove_children()

        # Add new content to the existing container
        container.mount(Label("Select a league:"))

        table = DataTable(id="results_table", cursor_type="row")
        table.add_column("League Name")
        table.add_column("League ID")
        table.add_column("Season")

        for lg in leagues:
            table.add_row(lg["name"], lg["league_id"], str(lg.get("season", "")))

        container.mount(table)
        container.mount(Button("Back", id="btn_back"))

        # Store leagues for selection
        self._leagues = leagues

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Handle league selection from table."""
        if hasattr(self, "_leagues"):
            league = self._leagues[event.cursor_row]
            self._load_league(league["league_id"])

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        if event.button.id == "btn_load_id":
            league_id = self.query_one("#league_id_input", Input).value.strip()
            if league_id:
                self._load_league(league_id)
            else:
                self.query_one("#status", Static).update("Please enter a League ID")

        elif event.button.id == "btn_search":
            username = self.query_one("#username_input", Input).value.strip()
            league_name = self.query_one("#league_name_input", Input).value.strip()
            if username and league_name:
                self._search_leagues(username, league_name)
            else:
                self.query_one("#status", Static).update("Please enter both username and league name")

        elif event.button.id == "btn_back":
            # Restore the original form
            container = self.query_one(Vertical).query_one(Container)
            container.remove_children()

            # Rebuild the original form
            container.mount(Label("Welcome to Sleeper Fantasy Football TUI", id="title"))
            container.mount(Label("Choose how to find your league:"))
            container.mount(Label("Option 1: Enter League ID"))
            container.mount(Input(placeholder="League ID", id="league_id_input"))
            container.mount(Button("Load by League ID", id="btn_load_id", variant="primary"))
            container.mount(Label("Option 2: Search by Username"))
            container.mount(Input(placeholder="Sleeper Username", id="username_input"))
            container.mount(Input(placeholder="League Name (partial match)", id="league_name_input"))
            container.mount(Button("Search Leagues", id="btn_search", variant="success"))
            container.mount(Static("", id="status"))


# --------------------------
# Main Application
# --------------------------


class SleeperTUI(App):
    CSS = """
    #nav {
        width: 30;
        dock: left;
    }

    #content_container {
        width: 1fr;
    }

    Horizontal {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_data", "Refresh Cache"),
    ]

    def __init__(self, title, league_id: str):
        super().__init__()
        self.api = SleeperAPI(league_id)
        self.league_id = league_id
        self.current_table = None
        self.week_select = None

    # Layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

        with Horizontal():
            self.nav = Tree("Navigation", id="nav")
            yield self.nav

            # Use a container for content that we can replace children in
            with Container(id="content_container"):
                yield Static("Select an option from the left.")

    # App startup ----------------------------------------------------------

    def on_mount(self):
        self.setup_navigation()

        if self.is_tuesday():
            self.action_refresh_data()

    def setup_navigation(self):
        rootname = "Navigation"
        root = self.nav.root
        root.label = rootname
        root.add("League Info")
        root.add("Users")
        root.add("Rosters")
        root.add("Matchups")
        root.add("Refresh Cache")
        root.expand()

    def is_tuesday(self):
        return datetime.datetime.now().strftime("%A") == "Tuesday"

    # Navigation events ----------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        label = event.node.label

        if label == "League Info":
            self.show_league()
        elif label == "Users":
            self.show_users()
        elif label == "Rosters":
            self.show_rosters()
        elif label == "Matchups":
            self.show_matchups_selector()
        elif label == "Refresh Cache":
            self.action_refresh_data()

    # Content rendering ----------------------------------------------------

    def show_table(self, rows, columns):
        table = DataTable()
        for col in columns:
            table.add_column(col)

        for row in rows:
            table.add_row(*[str(x) for x in row])

        self._replace_content_widget(table)

    # View: League ---------------------------------------------------------

    def show_league(self):
        data = self.api.league()
        rows = [(k, json.dumps(v)) for k, v in data.items()]
        self.show_table(rows, ["Field", "Value"])

    # View: Users ----------------------------------------------------------

    def show_users(self):
        data = self.api.users()

        rows = []
        for u in data:
            rows.append([
                u.get("user_id"),
                u.get("display_name"),
                u.get("metadata", {}).get("team_name"),
            ])

        self.show_table(rows, ["User ID", "Name", "Team Name"])

    # View: Rosters --------------------------------------------------------

    def show_rosters(self):
        rosters = self.api.rosters()
        users = {u["user_id"]: u["display_name"] for u in self.api.users()}

        rows = []
        for r in rosters:
            rows.append([
                users.get(r["owner_id"], "Unknown"),
                ",".join(r.get("players", [])),
            ])

        self.show_table(rows, ["Owner", "Players"])

    # Matchups selection ---------------------------------------------------

    def show_matchups_selector(self):
        # interactive dropdown
        container = Container()
        select = Select(options=[(str(i), i) for i in range(1, 19)], prompt="Select Week", id="week_select")
        container.mount(select)
        self.week_select = select

        self._replace_content_widget(container)

    def on_select_changed(self, event: Select.Changed):
        """Handle week selection from dropdown."""
        if event.select.id == "week_select" and event.value != Select.BLANK:
            week = int(event.value)
            self.show_matchups(week)

    # View: Matchups -------------------------------------------------------

    def show_matchups(self, week: int):
        data = self.api.matchups(week)
        users = {u["user_id"]: u["display_name"] for u in self.api.users()}

        rows = []
        for m in data:
            rows.append([
                users.get(m["owner_id"], "Unknown"),
                json.dumps(m.get("starters", [])),
                m.get("points", 0),
            ])

        self.show_table(rows, ["Owner", "Starters", "Points"])

    # Refresh --------------------------------------------------------------

    def action_refresh_data(self):
        try:
            self._replace_content_text("Refreshing cache…")

            self.api.league(force=True)
            self.api.users(force=True)
            self.api.rosters(force=True)
            for w in range(1, 19):
                try:
                    self.api.matchups(w, force=True)
                except:
                    pass

            self._replace_content_text("Cache refreshed!")
        except AttributeError:
            self._replace_content_text("No league loaded to refresh.")

    # Helper methods -------------------------------------------------------

    def _replace_content_widget(self, new_widget):
        """Replace the content widget with a new widget."""
        # Get the content container and clear all children, then add new widget
        content_container = self.query_one("#content_container")

        # Remove all children (don't wait for async removal)
        for child in list(content_container.children):
            child.remove()

        # Mount the new widget (no ID needed since container manages it)
        content_container.mount(new_widget)

    def _replace_content_text(self, text: str):
        """Replace the content widget with a Static text widget."""
        new_content = Static(text)
        self._replace_content_widget(new_content)


# --------------------------
# Launcher
# --------------------------


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Sleeper Fantasy Football TUI")
    parser.add_argument("--id", dest="league_id", required=False, help="League ID to load directly")
    parser.add_argument("--user", dest="username", required=False, help="Sleeper username to search leagues")
    args = parser.parse_args()

    if args.league_id and args.username:
        print("Error: Cannot specify both --id and --user")
        sys.exit(1)

    league_id = None

    # If league ID provided, validate and use it
    if args.league_id:
        try:
            int(args.league_id)
            league_id = args.league_id
        except ValueError:
            print("Error: League ID must be numeric")
            sys.exit(1)
    # If username provided, we still need to show the lookup screen
    # but could pre-populate the username field (future enhancement)

    # If no league_id from args, show lookup screen
    if not league_id:
        lookup_app = LeagueLookupScreen(username=args.username)
        league_id = lookup_app.run()

    # If we got a league_id (either from args or lookup), start main app
    if league_id:
        sleeper = SleeperTUI(title="Sleeper Fantasy Football TUI", league_id=league_id)
        sleeper.run()


if __name__ == "__main__":
    main()
