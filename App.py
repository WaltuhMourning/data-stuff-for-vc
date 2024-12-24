import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import altair as alt

# --------------------------------------------
# 1. Name Unification Logic
# --------------------------------------------

# Each entry is ([list_of_patterns], unified_display_name).
# If a user name (lowercased) contains any pattern, we unify it to that name.
# Special rule: if a user name contains "hull's wife", skip unifying to "Hull".
unification_map = [
    (['sullivan'], 'Sullivan'),
    (['deb'], 'Deb'),
    (['diana'], 'Diana'),
    (['kyo'], 'Kyo'),
    (['fmr president', 'fmr_president'], 'Fmr President'),
    (['pluribus'], 'Pluribus'),
    (['aislinn'], 'Aislinn'),
    (['kayla'], 'Kayla'),
    (['long'], 'Long'),
    # Merge "james hersey" or "james_heresy" into James Hersey
    (['james hersey', 'james_heresy'], 'James Hersey'),
    (['kearsley'], 'Kearsley'),
    (['zimmerman'], 'Zimmerman'),
    (['toward'], 'Toward'),
    (['nord'], 'Nord'),
    (['molhoj'], 'Molhoj'),
    (['posting'], 'Posting'),
    (['iron smith'], 'Iron Smith'),
    (['pickle hersey'], 'Pickle Hersey'),
    (['ducky'], 'Ducky'),
    (['marks'], 'Marks'),
    (['hull'], 'Hull'),
    (['mccarthy'], 'McCarthy'),
    (['loz'], 'Loz'),
    (['hoffman'], 'Hoffman'),
    (['bloodshed'], 'Bloodshed'),
    (['miller'], 'Miller'),
    (['watluhum'], 'Watluhum'),
    (['derek'], 'Derek'),
]

def unify_name(name: str) -> str:
    """
    Returns a unified name if the name contains any of the unification patterns
    (case-insensitive). Otherwise the original name.
    - If 'hull's wife' is in the name, do NOT unify to 'Hull'.
    """
    name_lower = name.lower()

    # Special skip for "hull's wife"
    if "hull's wife" in name_lower:
        return name  # do NOT unify to "Hull"

    for patterns, unified_display in unification_map:
        for pattern in patterns:
            if pattern.lower() in name_lower:
                # Found a match => unify
                return unified_display

    # Otherwise, keep as is
    return name


# --------------------------------------------
# 2. Data Load & Preprocessing
# --------------------------------------------

@st.cache_data
def load_and_preprocess_data(local_csv_file: str) -> pd.DataFrame:
    """
    Loads the CSV file (bundled with the app), unifies certain names,
    then sums up the influences on each date for each group.
    Finally, re-ranks the users for each date based on total influence.
    """
    # Load from local file in the same repo
    df = pd.read_csv(local_csv_file, parse_dates=["Date"])

    # Step 1: unify names
    df["UnifiedUser"] = df["User"].apply(unify_name)

    # Step 2: group by (Date, UnifiedUser), summing up influence
    grouped = df.groupby(["Date", "UnifiedUser"], as_index=False)["Political Influence"].sum()

    # Step 3: re-compute daily rank
    def compute_daily_ranks(group):
        group = group.sort_values("Political Influence", ascending=False)
        group["Rank"] = range(1, len(group) + 1)
        return group

    grouped = grouped.groupby("Date").apply(compute_daily_ranks).reset_index(drop=True)

    return grouped

def create_all_dates_user_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with columns [Date, UnifiedUser, Political Influence, Rank],
    expand so that every user has a row for every date in the range.
    If a row doesn't exist for that user+date, fill in Political Influence=0
    and Rank=bottom rank (max rank for that date).
    """
    all_dates = pd.date_range(start=df["Date"].min(), end=df["Date"].max(), freq="D")
    all_users = df["UnifiedUser"].unique()

    # Cartesian product of all dates x all unified users
    full_index = pd.MultiIndex.from_product([all_dates, all_users], names=["Date", "UnifiedUser"])
    full_df = pd.DataFrame(index=full_index).reset_index()

    merged = pd.merge(full_df, df, how="left", on=["Date", "UnifiedUser"])

    # Fill missing influence with 0 and missing rank with the bottom rank
    def fill_missing(group):
        max_rank = group["Rank"].max(skipna=True)
        group["Rank"] = group["Rank"].fillna(max_rank)
        group["Political Influence"] = group["Political Influence"].fillna(0)
        return group

    merged = merged.groupby("Date").apply(fill_missing).reset_index(drop=True)

    return merged


# --------------------------------------------
# 3. Main Streamlit App
# --------------------------------------------

def main():
    st.set_page_config(
        page_title="4 Eagle News: Virtual Congress Influence Dashboard",
        page_icon="🦅",  # a simple eagle emoji
        layout="centered"
    )

    # 4 Eagle news styling
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(180deg, #ffffff 10%, #f0f0f0 100%);
            font-family: 'Verdana', sans-serif;
        }
        /* Top header style */
        .css-18e3th9 {
            color: #A10000 !important; /* deep red for "breaking news" feel */
            text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }
        /* Sidebar styling */
        .css-1d391kg {
            background-color: #222F48 !important; /* dark navy */
        }
        .css-1d391kg h2, .css-1d391kg label, .css-1d391kg div {
            color: #ffffff !important;
        }
        /* Expander headers in red */
        .streamlit-expanderHeader {
            font-size: 1rem;
            font-weight: 700;
            color: #A10000 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("**4 Eagle News: Virtual Congress Influence Dashboard**")
    st.write("Your trusted source for political analysis in Virtual Congress.")

    # Hard-coded path (relative to this app file)
    local_csv_file = "4Eagle_with_ranks_real.csv"  # name of your CSV in the repo

    # Load data
    try:
        df = load_and_preprocess_data(local_csv_file)
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return

    # Expand to ensure every user has all dates
    df_full = create_all_dates_user_df(df)

    # -- Sidebar controls
    st.sidebar.header("Display Options")

    # Choose rank or influence
    measure_to_show = st.sidebar.radio(
        "Which metric would you like to display?",
        ["Political Influence", "Rank"],
        index=0
    )

    # Log scale (for influence only)
    log_scale = False
    if measure_to_show == "Political Influence":
        log_scale = st.sidebar.checkbox("Use log scale (Y-axis)?", value=False)

    # Select politicians
    all_users_sorted = sorted(df_full["UnifiedUser"].unique())
    selected_users = st.sidebar.multiselect(
        "Select politician(s) to compare:",
        options=all_users_sorted,
        default=all_users_sorted[:3]
    )

    # Date range
    min_date = df_full["Date"].min()
    max_date = df_full["Date"].max()
    date_range = st.sidebar.slider(
        "Select date range:",
        min_value=min_date.to_pydatetime(),
        max_value=max_date.to_pydatetime(),
        value=(min_date.to_pydatetime(), max_date.to_pydatetime())
    )

    # Filter
    df_filtered = df_full[
        (df_full["Date"] >= date_range[0]) & (df_full["Date"] <= date_range[1])
    ]
    df_filtered = df_filtered[df_filtered["UnifiedUser"].isin(selected_users)]

    # If measure = Influence, allow an optional influence range filter
    if measure_to_show == "Political Influence" and not df_filtered.empty:
        min_influence = float(df_filtered["Political Influence"].min())
        max_influence = float(df_filtered["Political Influence"].max())

        with st.expander("Influence Score Filter", expanded=False):
            influence_range = st.slider(
                "Filter by Influence Score (after date/user selection):",
                min_value=min_influence,
                max_value=max_influence,
                value=(min_influence, max_influence)
            )
        df_filtered = df_filtered[
            (df_filtered["Political Influence"] >= influence_range[0]) &
            (df_filtered["Political Influence"] <= influence_range[1])
        ]

    st.subheader("Time-Series Chart")
    if df_filtered.empty:
        st.warning("No data matches your filters. Please adjust.")
        return

    # Altair chart
    y_axis = alt.Y(
        measure_to_show,
        scale=alt.Scale(
            type="log" if (measure_to_show == "Political Influence" and log_scale) else "linear"
        )
    )
    chart = (
        alt.Chart(df_filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=y_axis,
            color=alt.Color("UnifiedUser:N", title="Politician"),
            tooltip=["Date", "UnifiedUser", "Political Influence", "Rank"]
        )
        .properties(width=800, height=400)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)

    # Optional "Top 10" chart if measure_to_show is "Political Influence"
    if measure_to_show == "Political Influence":
        with st.expander("Top 10 Politicians by Influence (in this range)"):
            top_df = (
                df_filtered
                .groupby("UnifiedUser", as_index=False)["Political Influence"]
                .sum()
                .sort_values("Political Influence", ascending=False)
                .head(10)
            )
            bar_chart = (
                alt.Chart(top_df)
                .mark_bar()
                .encode(
                    x=alt.X("Political Influence:Q", title="Total Influence Over Selected Range"),
                    y=alt.Y("UnifiedUser:N", sort="-x", title="Politician"),
                    tooltip=["UnifiedUser", "Political Influence"]
                )
                .properties(width=600, height=300)
            )
            st.altair_chart(bar_chart, use_container_width=True)

    # Show filtered data & Download button
    with st.expander("Show Filtered Data"):
        st.write(df_filtered)

        csv_data = df_filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Filtered Data as CSV",
            data=csv_data,
            file_name="filtered_data.csv",
            mime="text/csv"
        )

    # Final sign-off
    st.markdown(
        """
        ---
        <div style='text-align: center;'>
            <h3 style='color:#A10000'>4 Eagle News</h3>
            <p><em>Your best source for the latest Virtual Congress updates. Stay informed!</em></p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
