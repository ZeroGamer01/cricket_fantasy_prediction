import streamlit as st
import pandas as pd
import random
from io import StringIO

st.set_page_config(
    page_title="Cricket Fantasy Prediction",
    page_icon="🏏",
    layout="wide"
)

st.title("🏏 Cricket Fantasy Prediction")
st.caption("Player analysis • Fantasy team generator • Match scenarios")

st.info(
    "Version 1: Upload player statistics to generate predictions. "
    "Demo scores are not guaranteed fantasy points."
)

# -----------------------------
# PLAYER DATA TEMPLATE
# -----------------------------

COLUMNS = [
    "player", "team", "role",
    "recent_runs", "recent_wickets",
    "venue_runs", "venue_wickets",
    "batting_position", "overs_expected",
    "consistency", "pitch_fit", "matchup",
    "fantasy_avg", "credits",
    "selection_pct", "confirmed_xi"
]

template = pd.DataFrame([
    ["Example Batter", "Team A", "Batter", 180, 0, 90, 0, 1, 0, 75, 70, 65, 48, 9, 65, True],
    ["Example Allrounder", "Team B", "All-rounder", 100, 5, 50, 3, 5, 3, 80, 85, 75, 65, 9, 35, True],
    ["Example Bowler", "Team A", "Bowler", 10, 8, 5, 4, 10, 4, 70, 90, 80, 55, 8, 20, True],
    ["Example Keeper", "Team B", "Wicketkeeper", 140, 0, 70, 0, 2, 0, 75, 75, 70, 52, 9, 45, True],
], columns=COLUMNS)

st.download_button(
    "📥 Download player CSV template",
    template.to_csv(index=False),
    file_name="cricket_player_template.csv",
    mime="text/csv"
)

# -----------------------------
# MATCH SETTINGS
# -----------------------------

st.header("1. Match details")

c1, c2 = st.columns(2)

with c1:
    match_format = st.selectbox(
        "Match format",
        ["T20", "ODI", "Test"]
    )
    team_a = st.text_input("Team A", "Team A")

with c2:
    pitch = st.selectbox(
        "Pitch type",
        ["Balanced", "Batting-friendly", "Bowling-friendly",
         "Spin-friendly", "Pace-friendly", "Unknown"]
    )
    team_b = st.text_input("Team B", "Team B")

scenario = st.radio(
    "Toss / batting scenario",
    [
        "Team A bats first",
        "Team B bats first",
        "Generate both scenarios"
    ]
)

st.caption(
    "The toss scenario is recorded for comparison. "
    "It will not automatically change player scores without supporting data."
)

# -----------------------------
# PLAYER DATA UPLOAD
# -----------------------------

st.header("2. Upload player statistics")

uploaded_file = st.file_uploader(
    "Upload your player CSV file",
    type=["csv"]
)

if uploaded_file is None:
    st.warning(
        "Please upload a CSV containing at least 11 players. "
        "Download the template above to see the required columns."
    )
    st.stop()

try:
    df = pd.read_csv(uploaded_file)
except Exception as e:
    st.error(f"Could not read the CSV file: {e}")
    st.stop()

missing = [col for col in COLUMNS if col not in df.columns]

if missing:
    st.error("Your CSV is missing these columns: " + ", ".join(missing))
    st.stop()

df = df[COLUMNS].copy()

numeric_columns = [
    "recent_runs", "recent_wickets",
    "venue_runs", "venue_wickets",
    "batting_position", "overs_expected",
    "consistency", "pitch_fit", "matchup",
    "fantasy_avg", "credits", "selection_pct"
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df[numeric_columns] = df[numeric_columns].fillna(0)

df["confirmed_xi"] = (
    df["confirmed_xi"].astype(str).str.lower()
    .isin(["true", "1", "yes", "confirmed"])
)

valid_roles = ["Wicketkeeper", "Batter", "All-rounder", "Bowler"]

df = df[df["role"].isin(valid_roles)].copy()
df = df.dropna(subset=["player", "team"])

if len(df) < 11:
    st.error("At least 11 valid players are required.")
    st.stop()

# -----------------------------
# PLAYER SCORING ENGINE
# -----------------------------

def normalise(series):
    low = series.min()
    high = series.max()

    if high == low:
        return pd.Series([50.0] * len(series), index=series.index)

    return ((series - low) / (high - low)) * 100


df["form_score"] = (
    normalise(df["recent_runs"]) * 0.5
    + normalise(df["recent_wickets"]) * 0.5
)

df["venue_score"] = (
    normalise(df["venue_runs"]) * 0.5
    + normalise(df["venue_wickets"]) * 0.5
)

df["role_score"] = (
    normalise(df["overs_expected"]) * 0.5
    + (100 - normalise(df["batting_position"])) * 0.5
)

df["fantasy_score"] = (
    df["form_score"] * 0.25
    + df["venue_score"] * 0.15
    + df["role_score"] * 0.15
    + df["pitch_fit"].clip(0, 100) * 0.15
    + df["matchup"].clip(0, 100) * 0.10
    + df["consistency"].clip(0, 100) * 0.10
    + normalise(df["fantasy_avg"]) * 0.10
)

# Small penalty for unconfirmed players
df.loc[~df["confirmed_xi"], "fantasy_score"] *= 0.85

df["fantasy_score"] = df["fantasy_score"].round(1)

# -----------------------------
# PLAYER RANKINGS
# -----------------------------

st.header("3. Player predictions")

ranked = df.sort_values(
    "fantasy_score", ascending=False
).reset_index(drop=True)

display_columns = [
    "player", "team", "role",
    "fantasy_score", "fantasy_avg",
    "selection_pct", "confirmed_xi"
]

st.dataframe(
    ranked[display_columns],
    use_container_width=True,
    hide_index=True
)

st.download_button(
    "📥 Download player rankings",
    ranked[display_columns].to_csv(index=False),
    file_name="player_predictions.csv",
    mime="text/csv"
)

# -----------------------------
# FANTASY TEAM GENERATOR
# -----------------------------

def generate_teams(players, number_of_teams=5):
    results = []
    seen = set()

    role_limits = {
        "Wicketkeeper": (1, 4),
        "Batter": (3, 6),
        "All-rounder": (1, 4),
        "Bowler": (3, 6)
    }

    for attempt in range(1500):
        if len(results) >= number_of_teams:
            break

        pool = players.copy()

        # Random variation creates different combinations
        pool["random_score"] = pool["fantasy_score"].apply(
            lambda x: max(1, x + random.uniform(-18, 18))
        )

        pool = pool.sort_values(
            "random_score", ascending=False
        )

        selected = []
        role_counts = {role: 0 for role in valid_roles}
        team_counts = {}

        for _, player in pool.iterrows():
            role = player["role"]
            team_name = player["team"]

            if len(selected) == 11:
                break

            if role_counts[role] >= role_limits[role][1]:
                continue

            if team_counts.get(team_name, 0) >= 7:
                continue

            selected.append(player)
            role_counts[role] += 1
            team_counts[team_name] = (
                team_counts.get(team_name, 0) + 1
            )

        if len(selected) != 11:
            continue

        valid = True

        for role, limits in role_limits.items():
            if role_counts[role] < limits[0]:
                valid = False

        if not valid:
            continue

        team_df = pd.DataFrame(selected)

        signature = tuple(sorted(team_df["player"].tolist()))

        if signature in seen:
            continue

        seen.add(signature)

        team_df = team_df.sort_values(
            "fantasy_score", ascending=False
        ).reset_index(drop=True)

        results.append(team_df)

    return results


# -----------------------------
# GENERATE FIVE TEAMS
# -----------------------------

st.header("4. Generate fantasy teams")

confirmed = df[df["confirmed_xi"]].copy()

if len(confirmed) < 11:
    st.warning(
        "Fewer than 11 players are marked as confirmed. "
        "For better results, update your CSV with the confirmed playing XI."
    )

if st.button("🏏 Generate 5 fantasy teams", type="primary"):

    if len(confirmed) < 11:
        st.error("Please upload at least 11 confirmed players.")
    else:
        teams = generate_teams(confirmed, 5)

        if not teams:
            st.error(
                "Could not create valid teams with these players. "
                "Check player roles and team names in your CSV."
            )
        else:
            st.session_state["generated_teams"] = teams
            st.success(f"Generated {len(teams)} teams!")

if "generated_teams" in st.session_state:

    all_downloads = []

    for index, team in enumerate(
        st.session_state["generated_teams"], start=1
    ):

        st.subheader(f"Team {index}")

        team = team.copy()
        team["fantasy_role"] = "Player"

        if len(team) >= 2:
            team.loc[0, "fantasy_role"] = "Captain (C)"
            team.loc[1, "fantasy_role"] = "Vice-Captain (VC)"

        team["team_number"] = index

        st.dataframe(
            team[
                [
                    "player", "team", "role",
                    "fantasy_score", "fantasy_role"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        all_downloads.append(team)

    if all_downloads:
        combined = pd.concat(all_downloads)

        st.download_button(
            "📥 Download all generated teams",
            combined.to_csv(index=False),
            file_name="cricket_fantasy_teams.csv",
            mime="text/csv"
        )

st.divider()

st.caption(
    "Cricket Fantasy Prediction | Version 1 | "
    "Predictions are estimates, not guarantees. "
    "Always verify the playing XI and match conditions."
)
