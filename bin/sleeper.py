#!/usr/bin/env python3

import json
import requests
import datetime
import pathlib
from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, Tree, DataTable, Input, Button, Label, Select
)
from textual.containers import Container, Horizontal


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
        self.league_id = league_id

    def league(self, force=False):
        return api_get(
            f"league_{self.league_id}",
            f"{BASE_URL}/league/{self.league_id}",
            force
        )

    def users(self, force=False):
        return api_get(
            f"users_{self.league_id}",
            f"{BASE_URL}/league/{self.league_id}/users",
            force
        )

    def rosters(self, force=False):
        return api_get(
            f"rosters_{self.league_id}",
            f"{BASE_URL}/league/{self.league_id}/rosters",
            force
        )

    def matchups(self, week: int, force=False):
        return api_get(
            f"matchups_{self.league_id}_week_{week}",
            f"{BASE_URL}/league/{self.league_id}/matchups/{week}",
            force
        )

    def user(self, username: str):
        """Return user info by username (public)."""
        return fetch(f"{BASE_URL}/user/{username}")

    def user_leagues(self, user_id: str, season: int):
        """Return all NFL leagues the user is in."""
        return fetch(f"{BASE_URL}/user/{user_id}/leagues/nfl/{season}")


# --------------------------
# Textual UI
# --------------------------

class SleeperTUI(App):
    CSS_PATH = None
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_data", "Refresh Cache"),
    ]

    def __init__(self, title, league_id: str=""):
        super().__init__()
        if league_id:
            self.api = SleeperAPI(league_id)
        self.current_table = None
        self.week_select = None

    # Layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

        with Horizontal():
            self.nav = Tree("Navigation", id="nav")
            yield self.nav

            self.content = Static("Select an option from the left.", id="content")
            yield self.content

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
        root.add("Lookup League By Name")

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
        elif label == "Lookup League By Name":
            self.lookup_league_by_name()

    # Content rendering ----------------------------------------------------

    def show_table(self, rows, columns):
        table = DataTable()
        for col in columns:
            table.add_column(col)

        for row in rows:
            table.add_row(*[str(x) for x in row])

        self.content.update(table)

    # View: League ---------------------------------------------------------

    def show_league(self):
        data = self.api.league()
        rows = [(k, json.dumps(v)) for k, v in data.items()]
        self.show_table(rows, ["Field", "Value"])

    def lookup_league_by_name(self):
        """Ask for username + league name, then show matches."""
        container = Container()

        container.mount(Label("Enter Sleeper Username:"))
        username_input = Input(placeholder="username")
        container.mount(username_input)

        container.mount(Label("Enter part of the League Name:"))
        name_input = Input(placeholder="league name")
        container.mount(name_input)

        submit_btn = Button("Search", id="search_league_btn")
        container.mount(submit_btn)

        # Store fields so we can read them later
        self._lookup_username = username_input
        self._lookup_name = name_input

        self.content.update(container)

        # Bind button event
        submit_btn.on_click = self._perform_league_lookup


    def _perform_league_lookup(self, event):
        username = self._lookup_username.value.strip()
        name_query = self._lookup_name.value.strip().lower()

        if not username or not name_query:
            self.content.update("Both fields are required.")
            return

        # Step 1: find user
        try:
            user_data = self.api.user(username)
        except:
            self.content.update("User not found.")
            return

        user_id = user_data.get("user_id")
        if not user_id:
            self.content.update("Could not resolve user ID.")
            return

        # Step 2: find user's leagues for current season
        current_year = datetime.datetime.now().year
        leagues = self.api.user_leagues(user_id, current_year)

        # Step 3: filter by name
        matches = [lg for lg in leagues if name_query in lg["name"].lower()]

        if not matches:
            self.content.update("No matching leagues found.")
            return

        # Step 4: display matches and let user pick one
        rows = [(lg["league_id"], lg["name"], lg.get("season", "")) for lg in matches]
        table = DataTable()
        table.add_column("League ID")
        table.add_column("Name")
        table.add_column("Season")

        for row in rows:
            table.add_row(*[str(x) for x in row])

        # When user clicks a row, load that league into the dashboard
        table.on_row_selected = self._select_league_from_search

        self._search_results = matches
        self.content.update(table)


    def _select_league_from_search(self, event):
        row_index = event.row_index
        league = self._search_results[row_index]

        # Switch app to use this league ID
        self.api = SleeperAPI(league["league_id"])

        self.content.update(
            f"Loaded league: {league['name']} ({league['league_id']})"
        )

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
        select = Select(
            options=[(str(i), i) for i in range(1, 19)],
            prompt="Select Week",
        )
        select.on_change = self._on_week_selected
        self.content.update(select)
        self.week_select = select

    def _on_week_selected(self, event):
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
            self.content.update("Refreshing cache…")

            self.api.league(force=True)
            self.api.users(force=True)
            self.api.rosters(force=True)
            for w in range(1, 19):
                try:
                    self.api.matchups(w, force=True)
                except:
                    pass

            self.content.update("Cache refreshed!")
        except AttributeError as e:
            self.content.update("No league loaded to refresh.")


# --------------------------
# Launcher
# --------------------------

def main():
    sleeper = SleeperTUI(title="Sleeper Fantasy Football TUI", league_id="")
    sleeper.run()


if __name__ == "__main__":
    main()
