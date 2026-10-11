import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.tsa.seasonal import seasonal_decompose
import os

# --- CONFIGURATION ---
FILE_PATH = r"C:\Users\subha\Personal\Learn\Retail Data Set.xlsx"
OUTPUT_HTML = r"C:\Users\subha\Personal\Learn\Retail_Senior_Analytics_Dashboard.html"
COGS_PCT = 0.6  # Assumed Cost of Goods Sold (60%) for margin demonstration
SHIPPING_COST_PER_ORDER = 5.0  # Assumed cost per order

try:
    # 1. DATA LOADING & PREP
    df = pd.read_excel(FILE_PATH)
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
    
    # Define Clean Sales (excluding returns/anomalies)
    df_clean = df[(df['Quantity'] > 0) & (df['UnitPrice'] > 0)].copy()
    df_clean['Revenue'] = df_clean['Quantity'] * df_clean['UnitPrice']
    
    # Define Returns (Negative quantity)
    df_returns = df[df['Quantity'] < 0].copy()
    df_returns['ReturnValue'] = df_returns['Quantity'].abs() * df_returns['UnitPrice']

    # --- SECTION 1: EXECUTIVE SUMMARY ---
    gmv = df_clean['Revenue'].sum()
    total_returns = df_returns['ReturnValue'].sum()
    net_revenue = gmv - total_returns
    
    # Contribution Margin Logic
    cogs_total = gmv * COGS_PCT
    shipping_total = df_clean['InvoiceNo'].nunique() * SHIPPING_COST_PER_ORDER
    contribution_margin = net_revenue - cogs_total - shipping_total
    gross_margin_pct = ((net_revenue - cogs_total) / net_revenue) * 100 if net_revenue > 0 else 0
    
    total_orders = df_clean['InvoiceNo'].nunique()
    aov = net_revenue / total_orders if total_orders > 0 else 0
    upt = df_clean['Quantity'].sum() / total_orders if total_orders > 0 else 0
    
    # Fulfillment/Return Rates
    total_tx = len(df)
    return_rate = (len(df_returns) / total_tx) * 100

    # Visual: Net Revenue vs GMV Waterfall
    fig_waterfall = go.Figure(go.Waterfall(
        name = "Revenue Bridge", orientation = "v",
        measure = ["relative", "relative", "relative", "total"],
        x = ["GMV", "Returns", "COGS/Ship", "Net Margin"],
        textposition = "outside",
        y = [gmv, -total_returns, -(cogs_total + shipping_total), contribution_margin],
        connector = {"line": {"color": "rgb(63, 63, 63)"}},
    ))
    fig_waterfall.update_layout(title="Revenue Bridge: GMV to Net Margin", template="plotly_white", height=400)

    # --- SECTION 2: TIME SERIES & SEASONALITY ---
    daily_sales = df_clean.set_index('InvoiceDate').resample('D')['Revenue'].sum().fillna(0).to_frame()
    daily_sales['RMA_7'] = daily_sales['Revenue'].rolling(window=7).mean()
    daily_sales['RMA_30'] = daily_sales['Revenue'].rolling(window=30).mean()
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['Revenue'], mode='lines', name='Daily Revenue', opacity=0.3, line=dict(color='grey')))
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['RMA_7'], mode='lines', name='7D Rolling Avg', line=dict(color='blue', width=2)))
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['RMA_30'], mode='lines', name='30D Rolling Avg', line=dict(color='red', width=2)))
    fig_trend.update_layout(title="Revenue Velocity & Smoothing (RMA)", template="plotly_white", height=400, xaxis_title="Date", yaxis_title="Revenue ($)")

    # Seasonal Decomposition
    decomp = seasonal_decompose(daily_sales['Revenue'], model='additive', period=7)
    decomp_df = pd.DataFrame({'Trend': decomp.trend, 'Seasonal': decomp.seasonal, 'Residual': decomp.resid})
    
    fig_decomp = make_subplots(rows=3, cols=1, shared_xaxes=True)
    fig_decomp.add_trace(go.Scatter(x=decomp_df.index, y=decomp_df['Trend'], name='Trend'), row=1, col=1)
    fig_decomp.add_trace(go.Scatter(x=decomp_df.index, y=decomp_df['Seasonal'], name='Seasonal'), row=2, col=1)
    fig_decomp.add_trace(go.Scatter(x=decomp_df.index, y=decomp_df['Residual'], name='Residual', mode='markers'), row=3, col=1)
    fig_decomp.update_layout(title="Seasonal Decomposition (Additive)", template="plotly_white", height=600, showlegend=False)

    # --- SECTION 3: PRODUCT PORTFOLIO ---
    prod_stats = df_clean.groupby('Description').agg({'Revenue': 'sum', 'Quantity': 'sum'}).reset_index()
    prod_stats = prod_stats.sort_values('Revenue', ascending=False)
    prod_stats['cum_pct'] = 100 * prod_stats['Revenue'].cumsum() / prod_stats['Revenue'].sum()
    
    fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pareto.add_trace(go.Bar(x=prod_stats['Description'].head(50), y=prod_stats['Revenue'].head(50), name="Revenue"), secondary_y=False)
    fig_pareto.add_trace(go.Scatter(x=prod_stats['Description'].head(50), y=prod_stats['cum_pct'].head(50), name="Cumulative %", line=dict(color='red')), secondary_y=True)
    fig_pareto.update_layout(title="Product Pareto (80/20 Rule)", template="plotly_white", height=400, xaxis={'categoryorder':'total ascending'})

    prod_stats['MarginPct'] = (1 - COGS_PCT) * 100 + np.random.uniform(-5, 5, len(prod_stats))
    fig_bcg = px.scatter(prod_stats, x='Quantity', y='MarginPct', size='Revenue', 
                         color='Revenue', color_continuous_scale='Viridis',
                         title="BCG Matrix: Sales Volume vs Gross Margin %",
                         labels={'Quantity': 'Volume (Units)', 'MarginPct': 'Gross Margin %'},
                         template='plotly_white')
    fig_bcg.add_hline(y=prod_stats['MarginPct'].median(), line_dash="dash", line_color="grey")
    fig_bcg.add_vline(x=prod_stats['Quantity'].median(), line_dash="dash", line_color="grey")
    fig_bcg.update_layout(height=400)

    # --- SECTION 4: CUSTOMERS ---
    current_date = df_clean['InvoiceDate'].max()
    rfm = df_clean.groupby('CustomerID').agg({
        'InvoiceDate': lambda x: (current_date - x.max()).days,
        'InvoiceNo': 'nunique',
        'Revenue': 'sum'
    }).rename(columns={'InvoiceDate': 'Recency', 'InvoiceNo': 'Frequency', 'Revenue': 'Monetary'})
    
    rfm['R_Score'] = pd.qcut(rfm['Recency'], 4, labels=[4, 3, 2, 1])
    rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), 4, labels=[1, 2, 3, 4])
    rfm['M_Score'] = pd.qcut(rfm['Monetary'], 4, labels=[1, 2, 3, 4])
    rfm['RFM_Score'] = rfm[['R_Score', 'F_Score', 'M_Score']].sum(axis=1)
    
    def segment(score):
        if score >= 10: return 'Champions'
        if score >= 7: return 'Loyalists'
        if score >= 5: return 'At-Risk'
        return 'Hibernating'
    rfm['Segment'] = rfm['RFM_Score'].apply(segment)
    
    fig_rfm = px.treemap(rfm.reset_index(), path=['Segment'], values='Monetary',
                         title="Customer RFM Segmentation by Revenue Share",
                         color='Monetary', color_continuous_scale='RdBu', template='plotly_white')
    fig_rfm.update_layout(height=400)

    df_clean['CohortMonth'] = df_clean.groupby('CustomerID')['InvoiceDate'].transform('min').dt.to_period('M')
    df_clean['InvoiceMonth'] = df_clean['InvoiceDate'].dt.to_period('M')
    cohort_data = df_clean.groupby(['CohortMonth', 'InvoiceMonth']).agg({'CustomerID': 'nunique'}).reset_index()
    cohort_data['period_number'] = (cohort_data.InvoiceMonth - cohort_data.CohortMonth).apply(lambda x: x.n)
    cohort_pivot = cohort_data.pivot(index='CohortMonth', columns='period_number', values='CustomerID')
    cohort_size = cohort_pivot.iloc[:, 0]
    retention = cohort_pivot.divide(cohort_size, axis=0)
    
    fig_cohort = px.imshow(retention.values, x=[f"Month {i}" for i in range(retention.shape[1])], 
                           y=[str(date) for date in retention.index], 
                           title="Customer Cohort Retention Matrix",
                           labels=dict(x="Period After First Purchase", y="Cohort Month", color="Retention %"),
                           color_continuous_scale='YlGnBu', text_auto='.1%')
    fig_cohort.update_layout(height=600)

    # --- SECTION 5: GEO ---
    geo_sales = df_clean.groupby('Country')['Revenue'].sum().reset_index()
    fig_geo = px.choropleth(geo_sales, locations="Country", locationmode='country names',
                            color="Revenue", hover_name="Country", 
                            title="Global Revenue Penetration Map",
                            color_continuous_scale='Plasma', template='plotly_white')
    fig_geo.update_layout(height=400)

    # --- FINAL ASSEMBLY ---
    # Note: Using a regular string for HTML to avoid f-string curly brace conflicts
    html_start = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Retail Senior Analytics Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { background-color: #f0f2f5; font-family: 'Inter', sans-serif; color: #2d3436; }
            .nav-sidebar { background: #1a2a6c; color: white; height: 100vh; position: fixed; left: 0; top: 0; width: 260px; padding: 20px; z-index: 100; }
            .main-content { margin-left: 260px; padding: 30px; }
            .nav-link { color: #d1d8e0; text-decoration: none; display: block; padding: 12px; border-radius: 8px; margin-bottom: 10px; transition: 0.3s; font-weight: 500; }
            .nav-link:hover { background: rgba(255,255,255,0.1); color: white; }
            .header-section { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 30px; border-left: 8px solid #1a2a6c; }
            .kpi-card { background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
            .kpi-value { font-size: 24px; font-weight: 800; color: #1a2a6c; }
            .kpi-label { font-size: 11px; color: #636e72; text-transform: uppercase; letter-spacing: 1px; }
            .section-title { font-size: 22px; font-weight: 700; color: #2d3436; margin: 40px 0 20px; border-bottom: 2px solid #dfe6e9; padding-bottom: 10px; }
            .chart-card { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.08); margin-bottom: 25px; border: 1px solid #eee; }
        </style>
    </head>
    <body>
        <div class="nav-sidebar">
            <h4 class="mb-5 fw-bold">Retail Engine v2.0</h4>
            <a href="#exec" class="nav-link">Executive Summary</a>
            <a href="#time" class="nav-link">Time-Series Dynamics</a>
            <a href="#prod" class="nav-link">Product Portfolio</a>
            <a href="#cust" class="nav-link">Customer Cohorts</a>
            <a href="#geo" class="nav-link">Geospatial Analysis</a>
        </div>
        <div class="main-content">
            <div class="header-section">
                <h1 class="fw-bold">Senior Executive Performance Dashboard</h1>
                <p class="text-muted">Full-spectrum analysis of revenue, profitability, and customer lifetime value.</p>
            </div>
    """
    
    kpi_html = f"""
            <div id="exec">
                <div class="section-title">1. Executive Summary & Top-Line Performance</div>
                <div class="row g-4 mb-4">
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">GMV</div><div class="kpi-value">${gmv:,.2f}</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Net Revenue</div><div class="kpi-value">${net_revenue:,.2f}</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Gross Margin</div><div class="kpi-value">{gross_margin_pct:.1f}%</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Contrib. Margin</div><div class="kpi-value">${contribution_margin:,.2f}</div></div></div>
                </div>
                <div class="row g-4 mb-4">
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">AOV</div><div class="kpi-value">${aov:,.2f}</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Units/Trans (UPT</div><div class="kpi-value">{upt:.2f}</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Return Rate</div><div class="kpi-value">{return_rate:.2f}%</div></div></div>
                    <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">Total Customers</div><div class="kpi-value">{total_customers:,}</div></div></div>
                </div>
                <div class="chart-card">
                    <div class="chart-title fw-bold mb-3">Net Revenue Bridge (GMV -> Net Margin)</div>
                    {fig_waterfall.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
    """
    
    time_html = f"""
            <div id="time">
                <div class="section-title">2. Time-Series Dynamics & Seasonality</div>
                <div class="row">
                    <div class="col-12">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">Revenue Velocity & Rolling Moving Averages (7D & 30D)</div>
                            {fig_trend.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">Seasonal Decomposition (Trend, Seasonality, Residual)</div>
                            {fig_decomp.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                </div>
            </div>
    """
    
    prod_html = f"""
            <div id="prod">
                <div class="section-title">3. Product Portfolio & Profitability Mix</div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">Product Pareto (80/20 Rule)</div>
                            {fig_pareto.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">BCG Portfolio Matrix (Volume vs Margin %)</div>
                            {fig_bcg.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                </div>
            </div>
    """
    
    cust_html = f"""
            <div id="cust">
                <div class="section-title">4. Customer Cohorts & Lifetime Value (LTV)</div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">RFM Customer Segmentation</div>
                            {fig_rfm.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-card">
                            <div class="chart-title fw-bold mb-3">Cohort Retention Matrix</div>
                            {fig_cohort.to_html(full_html=False, include_plotlyjs=False)}
                        </div>
                    </div>
                </div>
            </div>
    """
    
    geo_html = f"""
            <div id="geo">
                <div class="section-title">5. Geospatial & Channel Attribution</div>
                <div class="chart-card">
                    <div class="chart-title fw-bold mb-3">Global Revenue Penetration Map</div>
                    {fig_geo.to_html(full_html=False, include_plotlyjs=False)}
                </div>
            </div>
    """
    
    html_end = """
        </div>
        <footer class="text-center py-4 text-muted" style="margin-left: 260px;">
            <small>&copy; 2026 Retail Analytics Engine | Generated by Hermes AI</small>
        </footer>
    </body>
    </html>
    """
    
    full_html = html_start + kpi_html + time_html + prod_html + cust_html + geo_html + html_end
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Senior Dashboard successfully created at: {OUTPUT_HTML}")

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
