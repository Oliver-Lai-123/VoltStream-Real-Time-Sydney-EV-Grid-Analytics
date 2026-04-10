import snowflake.connector
import pandas as pd
import os
from dotenv import load_dotenv

# This loads the hidden passwords from your .env file
load_dotenv()

print(" Connecting to Snowflake Data Warehouse...")

# Connect to Snowflake
conn = snowflake.connector.connect(
    user=os.getenv('SNOWFLAKE_USER'),
    password=os.getenv('SNOWFLAKE_PASSWORD'),
    account=os.getenv('SNOWFLAKE_ACCOUNT'),
    warehouse='COMPUTE_WH',
    database='VOLTSTREAM_DB',
    schema='PUBLIC'
)

print(" Connected! Fetching real-time Sydney EV grid data...\n")

# Query the dbt-transformed table
query = """
SELECT 
    SUBURB, 
    TOTAL_STATIONS, 
    ACTIVE_KW_DRAW, 
    LAST_UPDATED 
FROM SUBURB_POWER_DRAW
ORDER BY ACTIVE_KW_DRAW DESC;
"""

# Load the results directly into a Pandas DataFrame
df = pd.read_sql(query, conn)

# Print a beautiful terminal dashboard
print(" VOLTSTREAM LIVE GRID REPORT ")
print("===================================")
print(df.to_markdown(index=False))
print("===================================")

conn.close()
