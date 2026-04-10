import os
import json
import boto3
import requests
import tempfile
import subprocess
import snowflake.connector
import pandas as pd
from datetime import datetime
from botocore.config import Config
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
load_dotenv()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 {msg}")

def run_step_1_ingest():
    log("Step 1: Scraping Real Sydney EV Data...")
    api_key = os.getenv('OPEN_CHARGE_MAP_KEY')
    url = "https://api.openchargemap.io/v3/poi"
    params = {
        "key": api_key, "output": "json", "countrycode": "AU",
        "maxresults": 100, "boundingbox": "(-34.1, 150.5), (-33.5, 151.3)"
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"API Failed: {response.status_code}")
    
    raw_data = response.json()
    mapped_data = [
        {
            "station_id": f"OCM-{s.get('ID')}",
            "suburb": s.get("AddressInfo", {}).get("Town", "Unknown"),
            "status": "AVAILABLE" if s.get("StatusType", {}).get("IsOperational") else "OFFLINE",
            "kw_output": int(s.get("Connections", [{}])[0].get("PowerKW", 0) or 0),
            "timestamp": datetime.now().isoformat()
        } for s in raw_data
    ]

    # Save to temp file for transmission
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
        json.dump(mapped_data, tf)
        temp_path = tf.name
    
    filename = f"ev_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # 1. Push to MinIO
    s3 = boto3.client('s3', endpoint_url=os.getenv('MINIO_ENDPOINT'),
                      aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'),
                      aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'),
                      config=Config(s3={'addressing_style': 'path'}))
    s3.upload_file(temp_path, 'sydney-ev-raw', filename)
    log(f"Data Lake Updated: {filename}")

    # 2. Push to Snowflake Stage
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'), password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'), database='VOLTSTREAM_DB', schema='PUBLIC'
    )
    cursor = conn.cursor()
    cursor.execute(f"PUT file://{temp_path} @VOLTSTREAM_DB.PUBLIC.INTERNAL_EV_STAGE AUTO_COMPRESS=TRUE")
    
    # 3. Load into Table (COPY INTO)
    log("Step 2: Loading data into Snowflake Staging Table...")
    copy_sql = """
    COPY INTO VOLTSTREAM_DB.PUBLIC.STG_EV_DATA (station_id, suburb, status, kw_output, recorded_at)
    FROM (SELECT $1:station_id::STRING, $1:suburb::STRING, $1:status::STRING, $1:kw_output::INTEGER, $1:timestamp::TIMESTAMP
    FROM @VOLTSTREAM_DB.PUBLIC.INTERNAL_EV_STAGE)
    FILE_FORMAT = (FORMAT_NAME = 'VOLTSTREAM_DB.PUBLIC.JSONFORMAT');
    """
    cursor.execute(copy_sql)
    conn.close()
    os.remove(temp_path)
    log("Snowflake Load Complete.")

def run_step_2_transform():
    log("Step 3: Triggering dbt Transformations...")
    # We call dbt as a system command
    result = subprocess.run(["dbt", "run"], cwd="/app/voltstream_transform", capture_output=True, text=True)
    if result.returncode == 0:
        log("dbt Models Rebuilt Successfully.")
    else:
        print(result.stdout)
        raise Exception("dbt Run Failed!")

def run_step_3_report():
    log("Step 4: Generating Final Sydney Grid Report...")
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'), password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'), database='VOLTSTREAM_DB', schema='PUBLIC'
    )
    df = pd.read_sql("SELECT SUBURB, TOTAL_STATIONS, ACTIVE_KW_DRAW FROM SUBURB_POWER_DRAW ORDER BY ACTIVE_KW_DRAW DESC LIMIT 10", conn)
    print("\n⚡ VOLTSTREAM LIVE GRID REPORT ⚡")
    print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
    conn.close()

if __name__ == "__main__":
    try:
        run_step_1_ingest()
        run_step_2_transform()
        run_step_3_report()
        log("Pipeline execution finished successfully.")
    except Exception as e:
        log(f"Pipeline crashed: {e}")
