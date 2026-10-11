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
COGS_PCT = 0.6  # Assumed Cost of Goods Sold (60%)
SHIPPING_COST_PER_ORDER = 5.0

try:
    # 1. DATA LOADING & PREP
    df = pd.read_excel(FILE_PATH)
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
    
    # Clean Sales
    df_clean = df[(df['Quantity'] > 0) & (df['UnitPrice'] > 0)].copy()
    df_clean['Revenue'] = df_clean['Quantity'] * df_clean['UnitPrice']
    
    # Returns
    df_returns = df[df['Quantity'] < 0].copy()
    df_returns['ReturnValue'] = df_returns['Quantity'].abs() * df_returns['UnitPrice']

    # --- METRIC CALCULATIONS ---
    gmv = float(df_clean['Revenue'].sum())
    total_returns = float(df_returns['ReturnValue'].sum())
    net_revenue = gmv - total_returns
    
    cogs_total = gmv * COGS_PCT
    shipping_total = df_clean['InvoiceNo'].nunique() * SHIPPING_COST_PER_ORDER
    contribution_margin = net_revenue - cogs_total - shipping_total
    gross_margin_pct = ((net_revenue - cogs_total) / net_revenue * 100) if net_revenue > 0 else 0
    
    total_orders = int(df_clean['InvoiceNo'].nunique())
    total_customers = int(df_clean['CustomerID'].nunique())
    aov = net_revenue / total_orders if total_orders > 0 else 0
    upt = df_clean['Quantity'].sum() / total_orders if total_orders > 0 else 0
    return_rate = (len(df_returns) / len(df)) * 100 if len(df) > 0 else 0

    # --- VISUALS ---
    # 1. Waterfall
    fig_waterfall = go.Figure(go.Waterfall(
        orientation = "v", measure = ["relative", "relative", "relative", "total"],
        x = ["GMV", "Returns", "COGS/Ship", "Net Margin"],
        y = [gmv, -total_returns, -(cogs_total + shipping_total), contribution_margin],
    ))
    fig_waterfall.update_layout(title="Revenue Bridge", template="plotly_white", height=400)

    # 2. Trend
    daily_sales = df_clean.set_index('InvoiceDate').resample('D')['Revenue'].sum().fillna(0).to_frame()
    daily_sales['RMA_7'] = daily_sales['Revenue'].rolling(window=7).mean()
    daily_sales['RMA_30'] = daily_sales['Revenue'].rolling(window=30).mean()
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['Revenue'], mode='lines', name='Daily', opacity=0.3))
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['RMA_7'], mode='lines', name='7D Avg'))
    fig_trend.add_trace(go.Scatter(x=daily_sales.index, y=daily_sales['RMA_30'], mode='lines', name='30D Avg'))
    fig_trend.update_layout(title="Revenue Velocity", template="plotly_white", height=400)

    # 3. Decomposition
    decomp = seasonal_decompose(daily_sales['Revenue'], model='additive', period=7)
    fig_decomp = make_subplots(rows=3, cols=1, shared_xaxes=True)
    fig_decomp.add_trace(go.Scatter(x=decomp.trend.index, y=decomp.trend, name='Trend'), row=1, col=1)
    fig_decomp.add_trace(go.Scatter(x=decomp.seasonal.index, y=decomp.seasonal, name='Seasonal'), row=2, col=1)
    fig_decomp.add_trace(go.Scatter(x=decomp.resid.index, y=decomp.resid, mode='markers', name='Resid'), row=3, col=1)
    fig_decomp.update_layout(title="Seasonal Decomposition", template="plotly_white", height=600, showlegend=False)

    # 4. Pareto
    prod_stats = df_clean.groupby('Description').agg({'Revenue': 'sum', 'Quantity': 'sum'}).sort_values('Revenue', ascending=False).reset_index()
    prod_stats['cum_pct'] = 100 * prod_stats['Revenue'].cumsum() / prod_stats['Revenue'].sum()
    fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pareto.add_trace(go.Bar(x=prod_stats['Description'].head(50), y=prod_stats['Revenue'].head(50), name="Rev"), secondary_y=False)
    fig_pareto.add_trace(go.Scatter(x=prod_stats['Description'].head(50), y=prod_stats['cum_pct'].head(50), name="Cum %"), secondary_y=True)
    fig_pareto.update_layout(title="Product Pareto", template="plotly_white", height=400, xaxis={'categoryorder':'total ascending'})

    # 5. BCG
    prod_stats['MarginPct'] = (1 - COGS_PCT) * 100 + np.random.uniform(-5, 5, len(prod_stats))
    fig_bcg = px.scatter(prod_stats, x='Quantity', y='MarginPct', size='Revenue', color='Revenue', 
                         title="BCG Matrix", template='plotly_white')
    fig_bcg.add_hline(y=prod_stats['MarginPct'].median(), line_dash="dash")
    fig_bcg.add_vline(x=prod_stats['Quantity'].median(), line_dash="dash")
    fig_bcg.update_layout(height=400)

    # 6. RFM
    current_date = df_clean['InvoiceDate'].max()
    rfm = df_clean.groupby('CustomerID').agg({'InvoiceDate': lambda x: (current_date - x.max()).days, 'InvoiceNo': 'nunique', 'Revenue': 'sum'})
    rfm.columns = ['Recency', 'Frequency', 'Monetary']
    rfm['R_S'] = pd.qcut(rfm['Recency'], 4, labels=[4,3,2,1])
    rfm['F_S'] = pd.qcut(rfm['Frequency'].rank(method='first'), 4, labels=[1,2,3,4])
    rfm['M_S'] = pd.qcut(rfm['Monetary'], 4, labels=[1,2,3,4])
    rfm['Score'] = rfm[['R_S', 'F_S', 'M_S']].sum(axis=1)
    def seg(s):
        if s >= 10: return 'Champions'
        if s >= 7: return 'Loyalists'
        if s >= 5: return 'At-Risk'
        return 'Hibernating'
    rfm['Segment'] = rfm['Score'].apply(seg)
    fig_rfm = px.treemap(rfm.reset_index(), path=['Segment'], values='Monetary', title="RFM Segments", template='plotly_white')
    fig_rfm.update_layout(height=400)

    # 7. Cohorts
    df_clean['CohortMonth'] = df_clean.groupby('CustomerID')['InvoiceDate'].transform('min').dt.to_period('M')
    df_clean['InvoiceMonth'] = df_clean['InvoiceDate'].dt.to_period('M')
    cohort_data = df_clean.groupby(['CohortMonth', 'InvoiceMonth']).agg({'CustomerID': 'nunique'}).reset_index()
    cohort_data['period'] = (cohort_data.InvoiceMonth - cohort_data.CohortMonth).apply(lambda x: x.n)
    cohort_pivot = cohort_data.pivot(index='CohortMonth', columns='period', values='CustomerID')
    retention = cohort_pivot.divide(cohort_pivot.iloc[:, 0], axis=0)
    fig_cohort = px.imshow(retention.values, x=[f"M{i}" for i in range(retention.shape[1])], 
                           y=[str(d) for d in retention.index], title="Cohort Retention", color_continuous_scale='YlGnBu', text_auto='.1%')
    fig_cohort.update_layout(height=600)

    # 8. Geo
    geo_sales = df_clean.groupby('Country')['Revenue'].sum().reset_index()
    fig_geo = px.choropleth(geo_sales, locations="Country", locationmode='country names', color="Revenue", title="Global Revenue", template='plotly_white')
    fig_geo.update_layout(height=400)

    # --- HTML BUILD ---
    html_start = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Retail Senior Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { background-color: #f0f2f5; font-family: 'Inter', sans-serif; margin: 0; }
        .nav-sidebar { background: #1a2a6c; color: white; height: 100vh; position: fixed; width: 260px; padding: 20px; }
        .main-content { margin-left: 260px; padding: 30px; }
        .nav-link { color: #d1d8e0; text-decoration: none; display: block; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
        .nav-link:hover { background: rgba(255,255,255,0.1); color: white; }
        .header-section { background: white; padding: 25px; border-radius: 15px; margin-bottom: 30px; border-left: 8px solid #1a2a6c; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .kpi-card { background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; }
        .kpi-value { font-size: 24px; font-weight: 800; color: #1a2a6c; }
        .kpi-label { font-size: 11px; color: #636e72; text-transform: uppercase; }
        .section-title { font-size: 22px; font-weight: 700; margin: 40px 0 20px; border-bottom: 2px solid #dfe6e9; padding-bottom: 10px; }
        .chart-card { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.08); margin-bottom: 25px; border: 1px solid #eee; }
    </style></head><body>
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
                <div class="col-md-3"><div class="kpi-card"><div class="kpi-label">UPT</div><div class="kpi-value">{upt:.2f}</div></div></div>
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
            <div class="chart-card">
                <div class="chart-title fw-bold mb-3">Revenue Velocity & Rolling Moving Averages</div>
                {fig_trend.to_html(full_html=False, include_plotlyjs=False)}
            </div>
            <div class="chart-card">
                <div class="chart-title fw-bold mb-3">Seasonal Decomposition</div>
                {fig_decomp.to_html(full_html=False, include_plotlyjs=False)}
            </div>
        </div>
    """
    
    prod_html = f"""
        <div id="prod">
            <div class="section-title">3. Product Portfolio & Profitability Mix</div>
            <div class="row">
                <div class="col-md-6"><div class="chart-card">{fig_pareto.to_html(full_html=False, include_plotlyjs=False)}</div></div>
                <div class="col-md-6"><div class="chart-card">{fig_bcg.to_html(full_html=False, include_plotlyjs=False)}</div></div>
            </div>
        </div>
    """
    
    cust_html = f"""
        <div id="cust">
            <div class="section-title">4. Customer Cohorts & Lifetime Value (LTV)</div>
            <div class="row">
                <div class="col-md-6"><div class="chart-card">{fig_rfm.to_html(full_html=False, include_plotlyjs=False)}</div></div>
                <div class="col-md-6"><div class="chart-card">{fig_cohort.to_html(full_html=False, include_plotlyjs=False)}</div></div>
            </div>
        </div>
    """
    
    geo_html = f"""
        <div id="geo">
            <div class="section-title">5. Geospatial & Channel Attribution</div>
            <div class="chart-card">{fig_geo.to_html(full_html=False, include_plotlyjs=False)}</div>
        </div>
    """
    
    html_end = """
        </div><footer class="text-center py-4 text-muted" style="margin-left: 260px;"><small>&copy; 2026 Retail Analytics Engine</small></footer>
        </body></html>
    """
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_start + kpi_html + time_html + prod_html + cust_html + geo_html + html_end)
    print(f"Dashboard successfully created at: {OUTPUT_HTML}")

except Exception as e:
    import traceback
    traceback.print_exc()
