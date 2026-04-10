import boto3
import os
import json
import requests
from datetime import datetime
from botocore.config import Config
from dotenv import load_dotenv
import snowflake.connector # Add this at the top!
import tempfile            # Built-in Python library
import random

# Load credentials from your .env file
load_dotenv()

print(" Starting VoltStream Live Ingestor...")

# 1. Setup MinIO Connection
local_s3_config = Config(s3={'addressing_style': 'path'})
minio_client = boto3.client(
    's3',
    endpoint_url=os.getenv('MINIO_ENDPOINT'),
    aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'),
    config=local_s3_config
)

# 2. Fetch Live Sydney EV Data
def get_sydney_ev_data():
    """Fetches real-time data from Open Charge Map for Sydney."""
    api_key = os.getenv('OPEN_CHARGE_MAP_KEY')
    url = "https://api.openchargemap.io/v3/poi"
    
    # Bounding box roughly around the Greater Sydney area
    params = {
        "key": api_key,
        "output": "json",
        "countrycode": "AU",
        "maxresults": 100,
        "boundingbox": "(-34.1, 150.5), (-33.5, 151.3)" 
    }
    
    print(" Pulling real EV data from Open Charge Map...")
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f" API Failed with status code: {response.status_code}")
        return []
        
    raw_data = response.json()
    mapped_data = []
    
    # Python Mapping Layer: Transform Open Charge Map schema to VoltStream schema
    for station in raw_data:
        # Safely extract kW output
        kw = 0
        if station.get("Connections") and len(station["Connections"]) > 0:
            kw = station["Connections"][0].get("PowerKW", 0) or 22
            
        # Simulate Live Telemetry: If operational, give it a 40% chance of being in use
        is_operational = station.get("StatusType", {}).get("IsOperational")
        if is_operational:
            # Randomly assign 'CHARGING' to simulate active load
            live_status = random.choices(["AVAILABLE", "CHARGING"], weights=[60, 40])[0]
        else:
            live_status = "OFFLINE"
            
        # Map fields
        mapped_station = {
            "station_id": f"OCM-{station.get('ID')}",
            "suburb": station.get("AddressInfo", {}).get("Town", "Unknown"),
            "status": live_status,
            "kw_output": int(kw),
            "timestamp": datetime.now().isoformat()
        }
        mapped_data.append(mapped_station)
        
    return mapped_data

def upload_to_snowflake(file_path, filename):
    """Automatically pushes the local file to the Snowflake cloud stage."""
    print(f"☁️ Pushing {filename} to Snowflake Cloud Stage...")
    
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse='COMPUTE_WH',
        database='VOLTSTREAM_DB',
        schema='PUBLIC'
    )
    
    try:
        cursor = conn.cursor()
        # The magic command: PUT 'local_file' @stage_name
        cursor.execute(f"PUT file://{file_path} @VOLTSTREAM_DB.PUBLIC.INTERNAL_EV_STAGE AUTO_COMPRESS=TRUE")
        print(f"✅ Snowflake received: {filename}")
    finally:
        conn.close()

def upload_to_datalake():
    bucket_name = 'sydney-ev-raw'
    ev_data = get_sydney_ev_data()
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ev_status_{timestamp_str}.json"
    
    # We create a temporary file on the disk so Snowflake can "PUT" it
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
        json.dump(ev_data, tf, indent=2)
        temp_path = tf.name

    try:
        # 1. Upload to Local MinIO
        minio_client.upload_file(temp_path, bucket_name, filename)
        print(f"📦 Saved to Local MinIO: {filename}")

        # 2. Upload to Snowflake (AUTOMATED!)
        upload_to_snowflake(temp_path, filename)

    finally:
        # Clean up the temp file from your laptop
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    upload_to_datalake()