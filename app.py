# Electronics sales dashboard, 2019
# Run from this folder: streamlit run app.py

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------------------
# Page setup
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Electronics Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bright professional palette used by charts and metric cards
PRIMARY = "#0EA5E9"
PRIMARY_DARK = "#0284C7"
TEAL = "#14B8A6"
AMBER = "#F59E0B"
ROSE = "#F43F5E"
INDIGO = "#6366F1"
SLATE = "#0F172A"
SOFT_BLUE = "#E0F2FE"
CHART_COLORS = [PRIMARY, TEAL, AMBER, INDIGO, "#22C55E", ROSE, "#06B6D4", "#8B5CF6"]

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

STATE_NAMES = {
    "CA": "California",
    "NY": "New York",
    "TX": "Texas",
    "MA": "Massachusetts",
    "GA": "Georgia",
    "WA": "Washington",
    "OR": "Oregon",
    "ME": "Maine",
}

# Newer Streamlit uses width="stretch". Older Streamlit uses use_container_width.
_major, _minor = (int(part) for part in st.__version__.split(".")[:2])
if (_major, _minor) >= (1, 50):
    CHART_WIDTH = {"width": "stretch"}
else:
    CHART_WIDTH = {"use_container_width": True}


# -------------------------------------------------------------------
# Data preprocessing
# -------------------------------------------------------------------
def clean_data(raw):
    """Clean the sales file and add the columns the dashboard needs.

    Returns the cleaned table, a row-count table, and a few notes about dates.
    """
    df = raw.copy()

    # The first column is an old row number saved as "Unnamed: 0". It is not data.
    unnamed = [col for col in df.columns if str(col).startswith("Unnamed")]
    df = df.drop(columns=unnamed)

    needed = [
        "Order ID", "Product", "Quantity Ordered", "Price Each",
        "Order Date", "Purchase Address",
    ]
    missing_cols = [col for col in needed if col not in df.columns]
    if missing_cols:
        raise ValueError("The file is missing: " + ", ".join(missing_cols))

    steps = []
    remaining = len(df)
    steps.append({"Step": "Rows in the file", "Rows removed": 0, "Rows remaining": remaining})

    # Make sure numbers and dates are real numbers and dates. Bad values become missing.
    df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce")
    df["Price Each"] = pd.to_numeric(df["Price Each"], errors="coerce")
    df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    df["Purchase Address"] = df["Purchase Address"].replace(r"^\s*$", pd.NA, regex=True)
    df["Product"] = df["Product"].replace(r"^\s*$", pd.NA, regex=True)

    before = len(df)
    df = df.dropna(subset=needed).copy()
    remaining = len(df)
    steps.append({
        "Step": "Rows with missing values removed",
        "Rows removed": before - remaining,
        "Rows remaining": remaining,
    })

    before = len(df)
    df = df.drop_duplicates().copy()
    remaining = len(df)
    steps.append({
        "Step": "Duplicate rows removed",
        "Rows removed": before - remaining,
        "Rows remaining": remaining,
    })

    date_min_before = df["Order Date"].min()
    date_max_before = df["Order Date"].max()

    # The store year for this project is 2019.
    outside = df["Order Date"].dt.year != 2019
    if outside.any():
        outside_min = str(df.loc[outside, "Order Date"].min())
        outside_max = str(df.loc[outside, "Order Date"].max())
    else:
        outside_min = ""
        outside_max = ""

    before = len(df)
    df = df[df["Order Date"].dt.year == 2019].copy()
    remaining = len(df)
    steps.append({
        "Step": "Orders outside 2019 removed",
        "Rows removed": before - remaining,
        "Rows remaining": remaining,
    })

    # Sales is the money for that line: how many pieces times the price of one piece.
    df["Sales"] = df["Quantity Ordered"] * df["Price Each"]
    df["Month"] = df["Order Date"].dt.month_name()
    df["Hour"] = df["Order Date"].dt.hour
    df["Weekday"] = df["Order Date"].dt.day_name()

    # Address looks like "136 Church St, New York City, NY 10001".
    # City and state are added together so Portland, OR and Portland, ME stay separate.
    parts = df["Purchase Address"].str.split(",", n=2, expand=True)
    state = parts[2].str.strip().str[:2]
    df["State"] = state
    df["City"] = parts[1].str.strip() + " (" + state + ")"
    df["State Name"] = df["State"].map(STATE_NAMES).fillna(df["State"])

    before = len(df)
    df = df.dropna(subset=["City", "State"]).copy()
    df = df[df["City"].str.len() > 4].copy()
    address_removed = before - len(df)
    if address_removed:
        steps.append({
            "Step": "Rows with an unreadable address removed",
            "Rows removed": address_removed,
            "Rows remaining": len(df),
        })

    steps.append({
        "Step": "Rows used in the dashboard",
        "Rows removed": 0,
        "Rows remaining": len(df),
    })

    notes = {
        "date_min_before": str(date_min_before),
        "date_max_before": str(date_max_before),
        "date_min_after": str(df["Order Date"].min()) if len(df) else "",
        "date_max_after": str(df["Order Date"].max()) if len(df) else "",
        "outside_min": outside_min,
        "outside_max": outside_max,
    }
    report = pd.DataFrame(steps)
    return df, report, notes


@st.cache_data
def load_default_file():
    """Load Sales Data.csv from this folder. The result is cached so filters stay fast."""
    raw = pd.read_csv("Sales Data.csv")
    return clean_data(raw)


@st.cache_data
def load_uploaded_file(file_bytes):
    """Load a CSV the user uploaded from the sidebar."""
    raw = pd.read_csv(io.BytesIO(file_bytes))
    return clean_data(raw)


# -------------------------------------------------------------------
# Small helpers used by more than one chart
# -------------------------------------------------------------------
def inject_styles():
    """Bright, professional layout for the whole dashboard."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

        html, body, [class*="css"]  {
            font-family: "DM Sans", sans-serif;
        }
        .stApp {
            background:
                radial-gradient(circle at 0% 0%, #E0F2FE 0%, transparent 42%),
                radial-gradient(circle at 100% 0%, #CCFBF1 0%, transparent 38%),
                linear-gradient(180deg, #F8FBFF 0%, #F1F5F9 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0F172A 0%, #0C4A6E 55%, #0F766E 100%);
            border-right: 0;
        }
        [data-testid="stSidebar"] * {
            color: #F8FAFC !important;
        }
        [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] label {
            color: #BAE6FD !important;
        }
        [data-testid="stSidebar"] [data-baseweb="tag"] {
            background-color: #0EA5E9 !important;
        }
        [data-testid="stSidebar"] .stDownloadButton button,
        [data-testid="stSidebar"] button[kind="secondary"] {
            background: linear-gradient(90deg, #0EA5E9, #14B8A6) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
        }
        .hero-banner {
            background: linear-gradient(120deg, #0284C7 0%, #0EA5E9 45%, #14B8A6 100%);
            color: white;
            padding: 1.35rem 1.6rem;
            border-radius: 22px;
            margin-bottom: 1.1rem;
            box-shadow: 0 18px 40px rgba(14, 165, 233, 0.28);
        }
        .hero-banner h1 {
            font-family: "Space Grotesk", sans-serif;
            font-size: 2.05rem;
            margin: 0 0 0.35rem 0;
            letter-spacing: -0.03em;
            color: white;
        }
        .hero-banner p {
            margin: 0;
            opacity: 0.95;
            font-size: 1.02rem;
        }
        .metric-card {
            background: white;
            border-radius: 18px;
            padding: 1rem 1.1rem 1.05rem 1.1rem;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-top: 5px solid var(--accent);
            min-height: 112px;
        }
        .metric-card .label {
            color: #64748B;
            font-size: 0.86rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .metric-card .value {
            color: #0F172A;
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.55rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            line-height: 1.2;
        }
        .section-chip {
            display: inline-block;
            background: linear-gradient(90deg, #E0F2FE, #CCFBF1);
            color: #0369A1;
            border: 1px solid #7DD3FC;
            border-radius: 999px;
            padding: 0.28rem 0.85rem;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }
        .insight-box {
            background: #FFFFFF;
            border-left: 5px solid #0EA5E9;
            border-radius: 0 14px 14px 0;
            padding: 0.75rem 1rem;
            margin: 0.35rem 0 1.1rem 0;
            color: #334155;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }
        .conclusion-box {
            background: linear-gradient(135deg, #ECFEFF 0%, #EFF6FF 100%);
            border: 1px solid #7DD3FC;
            border-radius: 18px;
            padding: 1rem 1.2rem;
            box-shadow: 0 10px 24px rgba(14, 165, 233, 0.12);
        }
        div[data-testid="stTabs"] button[role="tab"] {
            font-weight: 650;
            font-size: 1rem;
            border-radius: 12px 12px 0 0;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            background: linear-gradient(180deg, #E0F2FE, transparent);
            color: #0284C7 !important;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show(fig):
    """Draw a Plotly chart across the width of the page."""
    fig.update_layout(
        template="plotly_white",
        title_font=dict(size=17, color=SLATE, family="Space Grotesk"),
        font=dict(size=13, color="#334155", family="DM Sans"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,251,255,0.65)",
        margin=dict(l=40, r=20, t=58, b=42),
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.25)", zeroline=False)
    st.plotly_chart(fig, **CHART_WIDTH)


def money(value, cents=False):
    """Format a number as dollars for metric tiles and captions."""
    if cents:
        return f"${value:,.2f}"
    return f"${value:,.0f}"


def money_text(value, cents=False):
    """Same as money(), but safe inside Streamlit markdown (\\$ is not treated as math)."""
    return money(value, cents=cents).replace("$", r"\$")


def count_label(n, singular, plural):
    """'1 city' or '10 cities'."""
    word = singular if n == 1 else plural
    return f"{n} {word}"


def hour_label(hour):
    """Turn 19 into 7:00 p.m."""
    hour = int(hour)
    if hour == 0:
        return "12:00 a.m."
    if hour < 12:
        return f"{hour}:00 a.m."
    if hour == 12:
        return "12:00 p.m."
    return f"{hour - 12}:00 p.m."


def keep_order(values, order):
    """Keep only the labels that are present, in a fixed order."""
    present = set(values)
    return [item for item in order if item in present]


def order_totals(frame):
    """Add up the line items so each order has one sales total."""
    return frame.groupby("Order ID", as_index=False)["Sales"].sum()


def metric_card(label, value, accent):
    """One bright KPI tile."""
    st.markdown(
        f"""
        <div class="metric-card" style="--accent: {accent};">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(chip, title, subtitle=None):
    """Colored section heading used across the dashboard."""
    st.markdown(f'<div class="section-chip">{chip}</div>', unsafe_allow_html=True)
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)


def style_bar(fig, horizontal=False, color=PRIMARY):
    """Shared look for bar charts: bright color, soft corners, no legend."""
    fig.update_traces(
        marker_color=color,
        marker_line_width=0,
        showlegend=False,
    )
    if horizontal:
        fig.update_yaxes(categoryorder="total ascending")
    return fig


def count_chart(
    frame,
    column,
    title,
    x_title,
    y_title="Number of order lines",
    order=None,
    horizontal=False,
    color=PRIMARY,
):
    """Bar chart of how many rows each value has. Built from counts so the browser stays fast."""
    counts = frame[column].value_counts()
    if order is not None:
        counts = counts.reindex(order).fillna(0)
    else:
        counts = counts.sort_index()
    plot_df = counts.rename_axis(column).reset_index(name=y_title)
    if horizontal:
        fig = px.bar(plot_df, x=y_title, y=column, title=title, labels={column: x_title, y_title: y_title})
    else:
        fig = px.bar(plot_df, x=column, y=y_title, title=title, labels={column: x_title, y_title: y_title})
    return style_bar(fig, horizontal=horizontal, color=color)


def sales_bins_chart(series, title, color=AMBER):
    """Histogram of sales, counted in pandas first so we do not send every row to the browser."""
    bins = pd.cut(series, bins=20, duplicates="drop")
    counts = bins.value_counts().sort_index()
    labels = [f"{interval.left:,.0f} to {interval.right:,.0f}" for interval in counts.index]
    plot_df = pd.DataFrame({"Sales ($)": labels, "Number of order lines": counts.values})
    fig = px.bar(
        plot_df,
        x="Sales ($)",
        y="Number of order lines",
        title=title,
        labels={"Sales ($)": "Sales on one order line ($)", "Number of order lines": "Number of order lines"},
    )
    fig.update_xaxes(tickangle=-45)
    return style_bar(fig, color=color)


def box_from_series(series, title, y_title):
    """Box plot from the real quartiles, plus the highest values drawn as points.

    Plotly's normal box plot would ship every row to the browser. The quartiles here
    are still calculated on the full series.
    """
    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    median = float(series.median())
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr
    inside = series[(series >= low_fence) & (series <= high_fence)]
    if inside.empty:
        whisker_low = float(series.min())
        whisker_high = float(series.max())
    else:
        whisker_low = float(inside.min())
        whisker_high = float(inside.max())

    # A few of the largest real values, so the extreme points are visible.
    if iqr == 0:
        highs = series[series > q3]
    else:
        highs = series[series > high_fence]
    if highs.empty:
        highs = series.nlargest(3)
    highs = pd.Series(sorted(highs.unique())[-12:])
    fig = go.Figure()
    fig.add_trace(go.Box(
        name=y_title,
        q1=[q1],
        median=[median],
        q3=[q3],
        lowerfence=[whisker_low],
        upperfence=[whisker_high],
        marker_color=PRIMARY,
        fillcolor="rgba(14, 165, 233, 0.28)",
        line_color=PRIMARY_DARK,
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=[y_title] * len(highs),
        y=highs,
        mode="markers",
        name="Highest values",
        marker=dict(color=ROSE, size=10, line=dict(color="white", width=1)),
    ))
    fig.update_layout(title=title, yaxis_title=y_title, xaxis_title="All order lines")
    return fig


def one_line(text):
    """Observation printed under a chart."""
    st.markdown(f'<div class="insight-box">{text}</div>', unsafe_allow_html=True)


# -------------------------------------------------------------------
# Load the data
# -------------------------------------------------------------------
inject_styles()
st.markdown(
    """
    <div class="hero-banner">
        <h1>Electronics Sales Dashboard, 2019</h1>
        <p>Interactive overview of orders, products, cities, and trends — filter anything in the sidebar.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded = st.sidebar.file_uploader("Upload Sales Data.csv (optional)", type=["csv"])
try:
    if uploaded is not None:
        df, cleaning_report, cleaning_notes = load_uploaded_file(uploaded.getvalue())
    else:
        df, cleaning_report, cleaning_notes = load_default_file()
except FileNotFoundError:
    st.error("Put Sales Data.csv in the same folder as app.py, or upload it in the sidebar.")
    st.stop()
except Exception as error:
    st.error(f"The file could not be read. {error}")
    st.stop()

if df.empty:
    st.warning("The file has no orders left after cleaning, so there is nothing to chart.")
    st.stop()


# -------------------------------------------------------------------
# Sidebar filters
# Every chart and number on the Dashboard tab uses `filtered`.
# -------------------------------------------------------------------
st.sidebar.markdown("### Filters")
st.sidebar.caption("Charts and totals on the Dashboard tab follow these filters.")

cities_available = sorted(df["City"].unique())
products_available = sorted(df["Product"].unique())

months = st.sidebar.multiselect("Month", MONTHS, default=MONTHS)
cities = st.sidebar.multiselect("City", cities_available, default=cities_available)
products = st.sidebar.multiselect("Product", products_available, default=products_available)

filtered = df[
    df["Month"].isin(months)
    & df["City"].isin(cities)
    & df["Product"].isin(products)
].copy()

if filtered.empty:
    st.sidebar.caption("Nothing to download until the filters match at least one order.")
else:
    st.sidebar.download_button(
        "Download filtered data",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales.csv",
        mime="text/csv",
    )

dashboard_tab, cleaning_tab = st.tabs(["Dashboard", "Data Cleaning"])


# -------------------------------------------------------------------
# Dashboard tab
# -------------------------------------------------------------------
with dashboard_tab:
    if filtered.empty:
        st.warning(
            "No orders match these filters. Choose at least one month, one city, and one product."
        )
    else:
        orders = order_totals(filtered)
        total_sales = filtered["Sales"].sum()
        n_orders = filtered["Order ID"].nunique()
        items_sold = filtered["Quantity Ordered"].sum()
        avg_order = orders["Sales"].mean()

        # ----- number tiles -----
        tile1, tile2, tile3, tile4 = st.columns(4)
        with tile1:
            metric_card("Total Sales", money(total_sales, cents=True), PRIMARY)
        with tile2:
            metric_card("Number of Orders", f"{n_orders:,}", TEAL)
        with tile3:
            metric_card("Items Sold", f"{int(items_sold):,}", AMBER)
        with tile4:
            metric_card("Average Order Value", money(avg_order, cents=True), INDIGO)
        st.caption(
            "Showing "
            + count_label(len(months), "month", "months")
            + ", "
            + count_label(len(cities), "city", "cities")
            + ", and "
            + count_label(len(products), "product", "products")
            + "."
        )

        # -------------------------------------------------------------------
        # Univariate analysis: one variable at a time
        # -------------------------------------------------------------------
        section_title(
            "Univariate",
            "Univariate Analysis",
            "Each chart looks at one column on its own, using the orders that match the filters.",
        )

        left, right = st.columns(2)
        with left:
            qty_order = sorted(filtered["Quantity Ordered"].dropna().unique())
            fig = count_chart(
                filtered,
                "Quantity Ordered",
                "How many order lines have each quantity",
                "Quantity ordered",
                order=qty_order,
                color=PRIMARY,
            )
            fig.update_layout(height=420)
            fig.update_xaxes(type="category")
            show(fig)
            share_one = (filtered["Quantity Ordered"] == 1).mean()
            one_line(
                f"Most order lines are a single item ({share_one:.0%}), "
                f"and the highest quantity is {int(filtered['Quantity Ordered'].max())}."
            )

        with right:
            price_order = sorted(filtered["Price Each"].dropna().unique())
            fig = count_chart(
                filtered,
                "Price Each",
                "How many order lines have each unit price",
                "Price of one unit ($)",
                order=price_order,
                color=TEAL,
            )
            fig.update_layout(height=420)
            fig.update_xaxes(type="category", tickprefix="$")
            show(fig)
            common_price = filtered["Price Each"].mode().iloc[0]
            one_line(
                f"The most common unit price is {money(common_price, cents=True)}, "
                f"and prices run from {money(filtered['Price Each'].min(), cents=True)} "
                f"to {money(filtered['Price Each'].max(), cents=True)}."
            )

        fig = sales_bins_chart(filtered["Sales"], "Distribution of sales on one order line")
        fig.update_layout(height=460)
        show(fig)
        one_line(
            f"The median order line is {money(filtered['Sales'].median(), cents=True)} "
            f"and the mean is {money(filtered['Sales'].mean(), cents=True)}, "
            f"so a few expensive products pull the average up."
        )

        product_counts = filtered["Product"].value_counts()
        fig = count_chart(
            filtered,
            "Product",
            "Number of order lines for each product",
            "Product",
            horizontal=True,
            color=INDIGO,
        )
        fig.update_layout(height=max(460, 28 * filtered["Product"].nunique() + 140))
        show(fig)
        one_line(
            f"{product_counts.index[0]} appears on the most order lines ({product_counts.iloc[0]:,})."
        )

        left, right = st.columns(2)
        with left:
            city_counts = filtered["City"].value_counts()
            fig = count_chart(
                filtered,
                "City",
                "Number of order lines in each city",
                "City",
                horizontal=True,
                color=TEAL,
            )
            fig.update_layout(height=460)
            show(fig)
            city_sentence = (
                f"{city_counts.index[0]} has the most order lines ({city_counts.iloc[0]:,})."
            )
            if {"Portland (OR)", "Portland (ME)"} <= set(filtered["City"]):
                city_sentence += " Portland, Oregon and Portland, Maine are counted as two cities."
            one_line(city_sentence)

        with right:
            month_order = keep_order(filtered["Month"], MONTHS)
            fig = count_chart(
                filtered,
                "Month",
                "Number of order lines in each month",
                "Month",
                order=month_order,
            )
            fig.update_layout(height=460)
            fig.update_xaxes(categoryorder="array", categoryarray=month_order)
            show(fig)
            month_counts = filtered["Month"].value_counts()
            one_line(
                f"{month_counts.index[0]} has the most order lines ({month_counts.iloc[0]:,})."
            )

        hour_order = list(range(0, 24))
        fig = count_chart(
            filtered,
            "Hour",
            "Number of order lines by hour of the day",
            "Hour of the day",
            order=hour_order,
        )
        fig.update_layout(height=420)
        fig.update_xaxes(dtick=1)
        show(fig)
        hour_counts = filtered["Hour"].value_counts()
        busiest_count_hour = int(hour_counts.index[0])
        one_line(
            f"The hour with the most order lines is {hour_label(busiest_count_hour)} "
            f"({hour_counts.iloc[0]:,} lines)."
        )

        # -------------------------------------------------------------------
        # Bivariate analysis: relationships between two variables
        # -------------------------------------------------------------------
        section_title(
            "Bivariate",
            "Bivariate Analysis",
            "These charts compare two columns. They also follow the sidebar filters.",
        )

        left, right = st.columns(2)

        # Average sales per order in each city
        with left:
            st.subheader("Does average sales per order differ by city?")
            order_city = (
                filtered.groupby(["City", "Order ID"], as_index=False)["Sales"].sum()
            )
            city_aov = (
                order_city.groupby("City", as_index=False)["Sales"]
                .mean()
                .sort_values("Sales")
            )
            fig = px.bar(
                city_aov,
                x="Sales",
                y="City",
                title="Average sales per order by city",
                labels={"Sales": "Average sales per order ($)", "City": "City"},
            )
            fig.update_layout(height=460)
            fig.update_xaxes(tickprefix="$")
            show(style_bar(fig, horizontal=True, color=TEAL))
            low_city = city_aov.iloc[0]
            high_city = city_aov.iloc[-1]
            if len(city_aov) == 1:
                one_line(
                    f"With only {high_city['City']} selected, the average order is "
                    f"{money(high_city['Sales'], cents=True)}."
                )
            else:
                one_line(
                    f"Average order value runs from {money(low_city['Sales'], cents=True)} "
                    f"in {low_city['City']} to {money(high_city['Sales'], cents=True)} "
                    f"in {high_city['City']}."
                )

        # Quantity by product
        with right:
            st.subheader("Does quantity ordered vary by product?")
            qty_product = (
                filtered.groupby("Product", as_index=False)["Quantity Ordered"]
                .mean()
                .sort_values("Quantity Ordered")
            )
            fig = px.bar(
                qty_product,
                x="Quantity Ordered",
                y="Product",
                title="Average quantity on one order line, by product",
                labels={
                    "Quantity Ordered": "Average quantity ordered",
                    "Product": "Product",
                },
            )
            fig.update_layout(height=max(460, 26 * len(qty_product) + 140))
            show(style_bar(fig, horizontal=True, color=AMBER))
            top_qty = qty_product.iloc[-1]
            one_line(
                f"{top_qty['Product']} has the highest average quantity "
                f"({top_qty['Quantity Ordered']:.2f} per order line)."
            )

        # Sales by month
        left, right = st.columns(2)
        with left:
            st.subheader("How do total sales change by month?")
            month_order = keep_order(filtered["Month"], MONTHS)
            monthly = (
                filtered.groupby("Month", as_index=False)["Sales"]
                .sum()
            )
            monthly["Month"] = pd.Categorical(monthly["Month"], categories=month_order, ordered=True)
            monthly = monthly.sort_values("Month")
            fig = px.bar(
                monthly,
                x="Month",
                y="Sales",
                title="Total sales by month",
                labels={"Month": "Month", "Sales": "Total sales ($)"},
            )
            fig.update_layout(height=440)
            fig.update_yaxes(tickprefix="$")
            show(style_bar(fig, color=PRIMARY))
            best_month = monthly.loc[monthly["Sales"].idxmax()]
            worst_month = monthly.loc[monthly["Sales"].idxmin()]
            if best_month["Month"] == worst_month["Month"]:
                one_line(
                    f"Only {best_month['Month']} is selected, with total sales of "
                    f"{money(best_month['Sales'])}."
                )
            else:
                one_line(
                    f"{best_month['Month']} has the highest sales ({money(best_month['Sales'])}) "
                    f"and {worst_month['Month']} has the lowest ({money(worst_month['Sales'])})."
                )

        # Sales by hour
        with right:
            st.subheader("How do total sales change by hour of the day?")
            hourly = filtered.groupby("Hour", as_index=False)["Sales"].sum()
            hourly = hourly.set_index("Hour").reindex(range(24), fill_value=0).reset_index()
            fig = px.line(
                hourly,
                x="Hour",
                y="Sales",
                markers=True,
                title="Total sales by hour of the day",
                labels={"Hour": "Hour of the day", "Sales": "Total sales ($)"},
            )
            fig.update_traces(
                line_color=PRIMARY,
                marker=dict(color=TEAL, size=8, line=dict(color="white", width=1)),
                line=dict(width=3),
            )
            fig.update_layout(height=440)
            fig.update_xaxes(dtick=1)
            fig.update_yaxes(tickprefix="$")
            show(fig)
            peak_hour = hourly.loc[hourly["Sales"].idxmax()]
            quiet_hour = hourly.loc[hourly["Sales"].idxmin()]
            one_line(
                f"Sales peak at {hour_label(peak_hour['Hour'])} "
                f"({money(peak_hour['Sales'])}). "
                f"The quietest hour is {hour_label(quiet_hour['Hour'])}."
            )

        # Price related to quantity
        st.subheader("Is the price of a product related to how many pieces people buy?")
        price_qty = (
            filtered.groupby("Product", as_index=False)
            .agg(
                price=("Price Each", "median"),
                avg_qty=("Quantity Ordered", "mean"),
                lines=("Order ID", "size"),
            )
        )
        price_qty["label"] = price_qty.apply(
            lambda row: row["Product"] if row["avg_qty"] >= 1.05 or row["price"] >= 900 else "",
            axis=1,
        )
        fig = px.scatter(
            price_qty,
            x="price",
            y="avg_qty",
            text="label",
            hover_name="Product",
            hover_data={"lines": True, "label": False},
            title="Average quantity vs unit price",
            labels={
                "price": "Price of one unit ($)",
                "avg_qty": "Average quantity per order line",
                "lines": "Order lines",
            },
        )
        fig.update_traces(
            textposition="top center",
            marker=dict(color=INDIGO, size=14, line=dict(color="white", width=1)),
        )
        fig.update_layout(height=520, showlegend=False)
        fig.update_xaxes(tickprefix="$")
        show(fig)
        if filtered["Price Each"].nunique() < 2:
            only_product = filtered["Product"].iloc[0]
            one_line(
                f"Only {only_product} is selected, at "
                f"{money(filtered['Price Each'].median(), cents=True)}, "
                f"with an average quantity of {filtered['Quantity Ordered'].mean():.2f}."
            )
        else:
            corr = filtered["Price Each"].corr(filtered["Quantity Ordered"])
            if corr < -0.05:
                link = "higher prices go with smaller quantities"
            elif corr > 0.05:
                link = "higher prices go with larger quantities in this filter"
            else:
                link = "price and quantity barely move together in this filter"
            one_line(
                f"The correlation between unit price and quantity is {corr:.2f}, so {link}."
            )

        # -------------------------------------------------------------------
        # Research questions (different from the five class questions)
        # -------------------------------------------------------------------
        section_title(
            "Research",
            "Research Questions",
            "Two questions of our own, answered with the filtered data.",
        )

        st.subheader("Which day of the week has the highest sales?")
        weekday_order = keep_order(filtered["Weekday"], WEEKDAYS)
        by_day = filtered.groupby("Weekday", as_index=False)["Sales"].sum()
        by_day["Weekday"] = pd.Categorical(by_day["Weekday"], categories=weekday_order, ordered=True)
        by_day = by_day.sort_values("Weekday")
        day_orders = (
            filtered.groupby(["Weekday", "Order ID"], as_index=False)["Sales"]
            .sum()
            .groupby("Weekday")["Order ID"]
            .count()
        )
        fig = px.bar(
            by_day,
            x="Weekday",
            y="Sales",
            title="Total sales by day of the week",
            labels={"Weekday": "Day of the week", "Sales": "Total sales ($)"},
        )
        fig.update_layout(height=440)
        fig.update_yaxes(tickprefix="$")
        show(style_bar(fig, color=TEAL))

        best_day = by_day.loc[by_day["Sales"].idxmax()]
        quiet_day = by_day.loc[by_day["Sales"].idxmin()]
        if best_day["Weekday"] == quiet_day["Weekday"]:
            st.write(
                f"Every order in this filter falls on {best_day['Weekday']}, "
                f"with {money(best_day['Sales'])} in sales "
                f"and {int(day_orders.get(str(best_day['Weekday']), day_orders.iloc[0])):,} orders. "
                f"Widen the month, city, or product filters to compare it with the other days."
            )
        else:
            gap = (best_day["Sales"] - quiet_day["Sales"]) / quiet_day["Sales"] * 100
            st.write(
                f"{best_day['Weekday']} has the highest sales, at {money(best_day['Sales'])}. "
                f"{quiet_day['Weekday']} is the lowest, at {money(quiet_day['Sales'])}, "
                f"so the best day is {gap:.1f}% above the quietest day. "
                f"The days sit close together, which means the store is busy all week "
                f"and a one-day promotion would miss a lot of similar demand."
            )

        st.subheader("Which state brings in the most sales?")
        by_state = (
            filtered.groupby(["State", "State Name"], as_index=False)["Sales"]
            .sum()
            .sort_values("Sales")
        )
        by_state["State Label"] = by_state["State Name"] + " (" + by_state["State"] + ")"
        fig = px.bar(
            by_state,
            x="Sales",
            y="State Label",
            title="Total sales by state",
            labels={"Sales": "Total sales ($)", "State Label": "State"},
        )
        fig.update_layout(height=460)
        fig.update_xaxes(tickprefix="$")
        show(style_bar(fig, horizontal=True, color=INDIGO))

        lead_state = by_state.iloc[-1]
        small_state = by_state.iloc[0]
        share = lead_state["Sales"] / total_sales * 100
        if len(by_state) == 1:
            st.write(
                f"{lead_state['State Name']} is the only state in this filter, "
                f"with {money(lead_state['Sales'])} in sales. "
                f"That is the full total shown in the tiles above. "
                f"Add more cities to see how the states compare."
            )
        else:
            ca_cities = sorted(city for city in filtered["City"].unique() if str(city).endswith("(CA)"))
            if lead_state["State"] == "CA" and len(ca_cities) >= 2:
                city_text = " and ".join(ca_cities)
                mix_sentence = f"California's total adds together {city_text}."
            else:
                mix_sentence = (
                    f"The state total follows the cities selected in the sidebar."
                )
            st.write(
                f"{lead_state['State Name']} brings in the most sales, "
                f"at {money(lead_state['Sales'])}, which is {share:.1f}% of the filtered total. "
                f"{small_state['State Name']} is the smallest, at {money(small_state['Sales'])}. "
                f"{mix_sentence}"
            )

        # -------------------------------------------------------------------
        # Conclusion
        # -------------------------------------------------------------------
        section_title("Summary", "Conclusion")

        month_order = keep_order(filtered["Month"], MONTHS)
        monthly_sales = filtered.groupby("Month")["Sales"].sum().reindex(month_order)
        monthly_orders = filtered.groupby("Month")["Order ID"].nunique().reindex(month_order)
        best_m = monthly_sales.idxmax()
        worst_m = monthly_sales.idxmin()
        city_sales = filtered.groupby("City")["Sales"].sum().sort_values()
        product_sales = filtered.groupby("Product")["Sales"].sum().sort_values()
        hourly_sales = filtered.groupby("Hour")["Sales"].sum()
        peak_h = int(hourly_sales.idxmax())
        findings = []

        findings.append(
            f"These filters cover {n_orders:,} orders and {int(items_sold):,} items, "
            f"for {money(total_sales, cents=True)} in sales. "
            f"The average order is {money(avg_order, cents=True)}, "
            f"while the median order is {money(orders['Sales'].median(), cents=True)}."
        )

        if best_m == worst_m:
            findings.append(
                f"{best_m} is the only month in this view, with {money(monthly_sales.loc[best_m])} in sales "
                f"and {int(monthly_orders.loc[best_m]):,} orders."
            )
        else:
            findings.append(
                f"{best_m} is the strongest month ({money(monthly_sales.loc[best_m])}) "
                f"and {worst_m} is the quietest ({money(monthly_sales.loc[worst_m])}). "
                f"{worst_m} also has fewer orders ({int(monthly_orders.loc[worst_m]):,} "
                f"compared with {int(monthly_orders.loc[best_m]):,} in {best_m})."
            )

        if len(city_sales) == 1:
            findings.append(
                f"{city_sales.index[-1]} is the only city selected, "
                f"with {money(city_sales.iloc[-1])} in sales."
            )
        else:
            findings.append(
                f"{city_sales.index[-1]} leads the cities with {money(city_sales.iloc[-1])} in sales. "
                f"Average order value stays in a narrow band, from "
                f"{money(city_aov['Sales'].min(), cents=True)} to "
                f"{money(city_aov['Sales'].max(), cents=True)}, "
                f"so the city gap is mainly how many orders each city has."
            )

        findings.append(
            f"Sales are highest at {hour_label(peak_h)}. "
            f"{product_counts.index[0]} is the product on the most order lines, "
            f"while {product_sales.index[-1]} brings in the most revenue "
            f"({money(product_sales.iloc[-1])})."
        )

        findings.append(
            f"{best_day['Weekday']} is the strongest day of the week. "
            f"{lead_state['State Name']} is the state with the highest sales "
            f"({money(lead_state['Sales'])})."
        )

        bullets = "".join(f"<li>{finding}</li>" for finding in findings)
        st.markdown(
            f'<div class="conclusion-box"><ul style="margin:0; padding-left:1.2rem;">{bullets}</ul></div>',
            unsafe_allow_html=True,
        )


# -------------------------------------------------------------------
# Data cleaning tab
# This tab describes the whole file, before the sidebar filters.
# -------------------------------------------------------------------
with cleaning_tab:
    section_title("Cleaning", "What changed in the data")
    st.write(
        "The extra column Unnamed: 0 was dropped because it is only an old row number. "
        "The file also already had Month, Sales, City, and Hour filled in. "
        "Those columns were rebuilt: Sales is quantity times price, Month is the month name, "
        "Hour comes from the order time, and City includes the state, for example Boston (MA)."
    )
    st.write(
        f"After cleaning, the table has {df.shape[0]:,} rows and {df.shape[1]} columns. "
        f"Quantity Ordered, Price Each, Sales, and Hour are numbers. "
        f"Order Date is a date and time. Product, Month, City, State, and Weekday are text."
    )
    with st.expander("Summary statistics for the cleaned numeric columns"):
        st.table(df[["Quantity Ordered", "Price Each", "Sales", "Hour"]].describe().round(2))
    st.table(cleaning_report.set_index("Step"))
    st.write(
        f"Before the year filter, order dates run from {cleaning_notes['date_min_before']} "
        f"to {cleaning_notes['date_max_before']}. "
        f"After keeping 2019 only, they run from {cleaning_notes['date_min_after']} "
        f"to {cleaning_notes['date_max_after']}."
    )

    section_title("Quality", "Outliers")
    st.write(
        "Quantity and sales were checked on the full cleaned data. "
        "The charts below are summaries of that data, so the page does not have to draw every row."
    )

    left, right = st.columns(2)
    with left:
        qty_order = sorted(df["Quantity Ordered"].unique())
        fig = count_chart(
            df,
            "Quantity Ordered",
            "Quantity ordered on each order line",
            "Quantity ordered",
            order=qty_order,
        )
        fig.update_layout(height=440)
        show(fig)
    with right:
        fig = box_from_series(df["Quantity Ordered"], "Box plot of quantity ordered", "Quantity ordered")
        fig.update_layout(height=440)
        show(fig)

    left, right = st.columns(2)
    with left:
        fig = sales_bins_chart(df["Sales"], "Histogram of sales per order line")
        fig.update_layout(height=480)
        show(fig)
    with right:
        fig = box_from_series(df["Sales"], "Box plot of sales per order line", "Sales ($)")
        fig.update_layout(height=480)
        show(fig)

    max_sale = df.loc[df["Sales"].idxmax()]
    high_qty = df[df["Quantity Ordered"] >= 5]
    high_qty_products = ", ".join(sorted(high_qty["Product"].unique()))
    q1 = df["Sales"].quantile(0.25)
    q3 = df["Sales"].quantile(0.75)
    fence = q3 + 1.5 * (q3 - q1)
    above = int((df["Sales"] > fence).sum())

    st.subheader("Decision: the outliers are kept")
    st.write(
        f"Quantity runs from {int(df['Quantity Ordered'].min())} to {int(df['Quantity Ordered'].max())}. "
        f"Orders of 5 or more pieces are {high_qty_products}. "
        f"Those are cheap products bought in a larger count, so they are real orders and they are kept."
    )
    st.write(
        f"The highest order line is {money(max_sale['Sales'], cents=True)} "
        f"({int(max_sale['Quantity Ordered'])} × {max_sale['Product']} at "
        f"{money(max_sale['Price Each'], cents=True)} each). "
        f"A box-plot fence of about {money(fence)} marks {above:,} order lines as high, "
        f"because most lines are cables and batteries near {money(df['Sales'].median(), cents=True)}. "
        f"The high lines are laptops, phones, and monitors at their catalog prices. "
        f"They are kept, because removing them would delete the products that make most of the revenue."
    )
    outside_removed = int(
        cleaning_report.loc[
            cleaning_report["Step"] == "Orders outside 2019 removed", "Rows removed"
        ].iloc[0]
    )
    if outside_removed:
        st.write(
            f"{outside_removed:,} orders fall outside 2019 "
            f"(from {cleaning_notes['outside_min']} to {cleaning_notes['outside_max']}). "
            f"They were removed so this dashboard stays inside the 2019 period."
        )
    else:
        st.write("Every order date is inside 2019, so the year check removed no rows.")

    st.subheader("Cleaned columns, first 20 rows")
    preview_cols = [
        "Order ID", "Product", "Quantity Ordered", "Price Each", "Sales",
        "Order Date", "Month", "Hour", "Weekday", "City", "State", "Purchase Address",
    ]
    preview = df[preview_cols].head(20).copy()
    preview["Order Date"] = preview["Order Date"].astype(str)
    st.table(preview)
