import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash.dash_table import DataTable
from scipy.optimize import root_scalar

# Initialize the Dash app
app = dash.Dash(__name__)

# Layout of the dashboard
app.layout = html.Div([
    html.Div([
        html.H1("Asset Management Dashboard", style={"textAlign": "center", "color": "#2c3e50"}),
        html.Div([
            html.Label("Number of Years (default: 24)"),
            dcc.Input(id="input_years", type="number", value=24, style={"marginBottom": "10px"}),

            html.Label("Select Asset"),
            dcc.Dropdown(
                id="input_asset_dropdown",
                options=[
                    {"label": "Bitcoin (BTC)", "value": "BTC-USD"},
                    {"label": "Solana (SOL)", "value": "SOL-USD"},
                    {"label": "Tesla (TSLA)", "value": "TSLA"},
                    {"label": "MicroStrategy (MSTR)", "value": "MSTR"},
                    {"label": "Custom Asset", "value": "CUSTOM"}
                ],
                value="BTC-USD",
                style={"marginBottom": "10px"}
            ),

            html.Label("Custom Asset Ticker"),
            dcc.Input(id="input_custom_asset", type="text", placeholder="Enter custom asset ticker", style={"marginBottom": "10px"}),

            html.Label("Monthly Spend"),
            dcc.Input(id="input_monthly_spend", type="number", value=5000, style={"marginBottom": "10px"}),

            html.Label("Inflation Rate"),
            dcc.Input(id="input_inflation", type="number", value=7, style={"marginBottom": "10px"}),

            html.Label("Appreciation Rate"),
            dcc.Input(id="input_appreciation", type="number", value=15, style={"marginBottom": "10px"}),

            html.Label("Value of Asset", id="input_value_label"),
            dcc.Input(id="input_value", type="number", value=623197, style={"marginBottom": "10px"}),

            html.Label("Starting Year"),
            dcc.Input(id="input_start_year", type="number", value=2032, style={"marginBottom": "10px"}),

            html.Button("Update Dashboard", id="update_button", n_clicks=0, style={"marginTop": "20px", "backgroundColor": "#2c3e50", "color": "white", "padding": "10px 20px"}),
        ], style={"padding": "20px", "border": "1px solid #ddd", "borderRadius": "5px", "backgroundColor": "#f9f9f9", "width": "300px", "margin": "auto"}),
    ], style={"textAlign": "center", "marginBottom": "20px"}),

    html.Div(id="summary_section", style={"margin": "20px auto", "padding": "20px", "border": "1px solid #ddd", "borderRadius": "5px", "backgroundColor": "#ecf0f1", "width": "70%"}),

    html.Div(id="table_section", style={"margin": "20px auto", "width": "90%"}),

    html.Div(dcc.Graph(id="graph_section"), style={"margin": "20px auto", "width": "90%"})
])

# Function to fetch the current price of the asset using Yahoo Finance
def fetch_asset_price(asset):
    try:
        ticker = yf.Ticker(asset)
        price = ticker.history(period="1d").iloc[-1]['Close']
        return price
    except Exception as e:
        print(f"Error fetching asset price: {e}")
        return None

# Callback to dynamically set the default value of the asset
@app.callback(
    Output("input_value", "value"),
    [Input("input_asset_dropdown", "value")]
)
def set_default_asset_value(asset):
    default_values = {
        "BTC-USD": 623197,
        "SOL-USD": 1360,
        "TSLA": 4803,
        "MSTR": 9299
    }
    return default_values.get(asset, 0)

# Callback to update the dashboard
@app.callback(
    [Output("summary_section", "children"),
     Output("table_section", "children"),
     Output("graph_section", "figure")],
    [Input("input_asset_dropdown", "value"),
     Input("input_custom_asset", "value"),
     Input("input_years", "value"),
     Input("input_inflation", "value"),
     Input("input_appreciation", "value"),
     Input("input_value", "value"),
     Input("input_monthly_spend", "value"),
     Input("input_start_year", "value")]
)
def update_dashboard(asset, custom_asset, years, inflation, appreciation, asset_value, monthly_spend, start_year):
    # Determine the asset ticker
    asset_ticker = custom_asset if asset == "CUSTOM" else asset

    # Fetch the current price of the asset for the summary section
    current_price = fetch_asset_price(asset_ticker)
    if current_price is None:
        current_price = 623197  # Default BTC price or fallback

    # Convert rates to decimals
    inflation_rate = inflation / 100
    appreciation_rate = appreciation / 100

    # Calculate annual expenses from monthly spend
    E0 = monthly_spend * 12

    # Calculate the required number of assets
    def calculate_balance_with_skip_growth(A, n_years, E0, i, r, V):
        initial_balance = A * V
        balance = initial_balance
        for year in range(1, n_years + 1):
            expenses = E0 * (1 + i)**(year - 1)
            if year == 1:
                asset_growth = 0  # Skip growth in year 1
            else:
                asset_growth = balance * r
            balance = balance + asset_growth - expenses
        return balance

    def find_required_assets_with_skip_growth(n_years, E0, i, r, V):
        def balance_to_zero(A):
            return calculate_balance_with_skip_growth(A, n_years, E0, i, r, V)
        
        # Dynamically expand or shrink the bracket
        a, b = 0.01, 100
        fa, fb = balance_to_zero(a), balance_to_zero(b)
        while fa * fb > 0:
            a /= 2
            b *= 2
            fa, fb = balance_to_zero(a), balance_to_zero(b)
            if abs(a) < 1e-8 or abs(b) > 1e8:
                raise ValueError("Could not find a valid bracket containing the root.")
        
        solution = root_scalar(balance_to_zero, bracket=[a, b], method='brentq')
        return solution.root

    try:
        A_required = find_required_assets_with_skip_growth(years, E0, inflation_rate, appreciation_rate, asset_value)
    except ValueError:
        return (html.Div([
                    html.H3(f"Asset Type: {asset_ticker}"),
                    html.P(f"Could not find the required balance within the specified range."),
                ], style={"color": "red"}), html.Div(), go.Figure())

    total_cost = A_required * current_price  # Total cost uses the current price

    # Generate the table data using the asset value (input_value)
    balance = A_required * asset_value
    data = []
    total_expenses = 0
    total_appreciation = 0

    for year in range(1, years + 1):
        expenses = E0 * (1 + inflation_rate)**(year - 1)
        if year == 1:
            asset_growth = 0  # Skip growth in year 1
        else:
            asset_growth = balance * appreciation_rate
        subtotal = balance + asset_growth
        ending_balance = subtotal - expenses
        data.append({
            "Year": start_year + year - 1,
            "Starting Balance (BAL)": round(balance, 0),
            "Appreciation Rate": f"{appreciation}%%",
            "Appreciation Value (Apprec)": round(asset_growth, 0),
            "Subtotal": round(subtotal, 0),
            "Living Expenses": round(expenses, 0),
            "Ending Balance": round(ending_balance, 0)
        })
        balance = ending_balance
        total_expenses += expenses
        total_appreciation += asset_growth

    # Append totals row
    data.append({
        "Year": "Total",
        "Starting Balance (BAL)": "-",
        "Appreciation Rate": "-",
        "Appreciation Value (Apprec)": round(total_appreciation, 0),
        "Subtotal": "-",
        "Living Expenses": round(total_expenses, 0),
        "Ending Balance": "-"
    })

    df = pd.DataFrame(data)

    # Create the table
    table = DataTable(
        columns=[{"name": col, "id": col} for col in df.columns],
        data=df.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "#2c3e50", "color": "white", "fontWeight": "bold"}
    )

    # Create the graph
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[df["Year"] != "Total"]["Year"], y=df[df["Year"] != "Total"]["Starting Balance (BAL)"], mode="lines+markers", name="Starting Balance"))
    fig.add_trace(go.Scatter(x=df[df["Year"] != "Total"]["Year"], y=df[df["Year"] != "Total"]["Ending Balance"], mode="lines+markers", name="Ending Balance"))
    fig.update_layout(title="Financial Progression", xaxis_title="Year", yaxis_title="Balance ($)",
                      template="plotly_white")

    # Create the summary section
    summary = html.Div([
        html.H3(f"Asset Type: {asset_ticker}"),
        html.P(f"Total Assets Required: {round(A_required, 2)}"),
        html.P(f"Current Asset Price: ${round(current_price, 2)}"),
        html.P(f"Total Cost to Purchase: ${round(total_cost, 2)}")
    ], style={"color": "#2c3e50"})

    return summary, table, fig

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)

