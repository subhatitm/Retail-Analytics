import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# Path to the data
file_path = r"C:\Users\subha\Personal\Learn\Retail Data Set.xlsx"
output_html = r"C:\Users\subha\Personal\Learn\Retail_Analytics_Dashboard.html"

try:
    # Load data
    df = pd.read_excel(file_path)

    # --- 1. DATA CLEANING ---
    # Create a 'Clean' set for Revenue KPIs (remove returns/anomalies)
    df_clean = df[(df['Quantity'] > 0) & (df['UnitPrice'] > 0)].copy()
    df_clean['TotalSales'] = df_clean['Quantity'] * df_clean['UnitPrice']
    df_clean['InvoiceDate'] = pd.to_datetime(df_clean['InvoiceDate'])
    df_clean['MonthYear'] = df_clean['InvoiceDate'].dt.to_period('M').astype(str)

    # KPI Calculations
    total_revenue = df_clean['TotalSales'].sum()
    total_orders = df_clean['InvoiceNo'].nunique()
    total_customers = df_clean['CustomerID'].nunique()
    aov = total_revenue / total_orders if total_orders > 0 else 0
    
    returns_count = len(df[df['Quantity'] < 0])
    return_rate = (returns_count / len(df)) * 100 if len(df) > 0 else 0

    # --- 2. VISUALIZATIONS (Optimized for HTML layout) ---
    
    # Monthly Revenue Trend
    monthly_sales = df_clean.groupby('MonthYear')['TotalSales'].sum().reset_index()
    fig_trend = px.line(monthly_sales, x='MonthYear', y='TotalSales', 
                        title='Monthly Revenue Trend',
                        labels={'TotalSales': 'Revenue ($)', 'MonthYear': 'Month'},
                        template='plotly_white', markers=True)
    fig_trend.update_traces(line_color='#1a2a6c', line_width=3)
    fig_trend.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=400)

    # Top 10 Products
    top_products = df_clean.groupby('Description')['TotalSales'].sum().sort_values(ascending=False).head(10).reset_index()
    fig_products = px.bar(top_products, x='TotalSales', y='Description', orientation='h',
                          title='Top 10 Products by Revenue',
                          labels={'TotalSales': 'Revenue ($)', 'Description': 'Product'},
                          template='plotly_white', color='TotalSales', color_continuous_scale='Blues')
    fig_products.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20), height=400)

    # Revenue by Country
    country_sales = df_clean.groupby('Country')['TotalSales'].sum().sort_values(ascending=False).head(10).reset_index()
    fig_country = px.pie(country_sales, values='TotalSales', names='Country', 
                         title='Top 10 Markets by Revenue',
                         hole=0.4, template='plotly_white')
    fig_country.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=400)

    # Order Value Distribution
    order_values = df_clean.groupby('InvoiceNo')['TotalSales'].sum()
    fig_dist = px.histogram(order_values, nbins=50, 
                           title='Distribution of Order Values',
                           labels={'value': 'Order Value ($)'},
                           template='plotly_white', color_discrete_sequence=['#1a2a6c'])
    fig_dist.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=400)

    # --- 3. GENERATE ROBUST HTML ---
    # Use a separate div for each chart and ensure CSS handles the height
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Executive Retail Insights</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ background-color: #f4f7f6; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; }}
            .header {{ background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d); color: white; padding: 40px 0; margin-bottom: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
            .kpi-card {{ background: white; border-radius: 12px; padding: 25px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; transition: transform 0.2s; }}
            .kpi-card:hover {{ transform: translateY(-5px); }}
            .kpi-value {{ font-size: 28px; font-weight: 800; color: #1a2a6c; margin-bottom: 5px; }}
            .kpi-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
            .chart-card {{ background: white; border-radius: 15px; padding: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.08); margin-bottom: 30px; border: 1px solid #eee; }}
            .chart-title {{ font-size: 18px; font-weight: 700; color: #444; margin-bottom: 20px; border-left: 5px solid #1a2a6c; padding-left: 15px; }}
            .plotly-graph-div {{ height: 400px !important; width: 100% !important; }}
        </style>
    </head>
    <body>
        <div class="header text-center">
            <div class="container">
                <h1 class="display-4 fw-bold">Retail Executive Analytics</h1>
                <p class="lead">Strategic Performance Review & Market Intelligence</p>
            </div>
        </div>
        
        <div class="container">
            <!-- KPI Row -->
            <div class="row g-4 mb-5">
                <div class="col-md-3">
                    <div class="kpi-card">
                        <div class="kpi-label">Total Revenue</div>
                        <div class="kpi-value">${total_revenue:,.2f}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="kpi-card">
                        <div class="kpi-label">Total Orders</div>
                        <div class="kpi-value">{total_orders:,}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="kpi-card">
                        <div class="kpi-label">Avg Order Value</div>
                        <div class="kpi-value">${aov:,.2f}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="kpi-card">
                        <div class="kpi-label">Return Rate</div>
                        <div class="kpi-value">{return_rate:.2f}%</div>
                    </div>
                </div>
            </div>
            
            <!-- Main Charts Row -->
            <div class="row">
                <div class="col-lg-8">
                    <div class="chart-card">
                        <div class="chart-title">Revenue Velocity (Monthly Trend)</div>
                        <div>{fig_trend.to_html(full_html=False, include_plotlyjs=False)}</div>
                    </div>
                </div>
                <div class="col-lg-4">
                    <div class="chart-card">
                        <div class="chart-title">Market Share (Top 10)</div>
                        <div>{fig_country.to_html(full_html=False, include_plotlyjs=False)}</div>
                    </div>
                </div>
            </div>
            
            <!-- Secondary Charts Row -->
            <div class="row">
                <div class="col-lg-6">
                    <div class="chart-card">
                        <div class="chart-title">Top 10 Revenue Drivers (Products)</div>
                        <div>{fig_products.to_html(full_html=False, include_plotlyjs=False)}</div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="chart-card">
                        <div class="chart-title">Order Value Distribution</div>
                        <div>{fig_dist.to_html(full_html=False, include_plotlyjs=False)}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <footer class="text-center py-4 text-muted">
            <small>&copy; 2026 Retail Analytics Engine | Generated by Hermes AI</small>
        </footer>
    </body>
    </html>
    """
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard successfully created at: {output_html}")

except Exception as e:
    print(f"Error: {e}")
