import os
import sys
import glob
import boto3
from botocore.client import Config
from tqdm import tqdm
import config

# MinIO Config
MINIO_ENDPOINT = config.MINIO_ENDPOINT
MINIO_ACCESS_KEY = config.MINIO_ACCESS_KEY
MINIO_SECRET_KEY = config.MINIO_SECRET_KEY
MINIO_BUCKET = config.MINIO_BUCKET
MINIO_PATH = config.MINIO_PATH

def upload_to_minio(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        sys.exit(1)
        
    print("Connecting to MinIO...")
    # Using boto3 client
    s3 = boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    # Ensure MinIO path ends with a slash if it's considered a directory prefix
    path_prefix = MINIO_PATH if MINIO_PATH.endswith('/') else MINIO_PATH + '/'
    object_name = f"{path_prefix}{filename}"
    
    print(f"Uploading {file_path} to s3://{MINIO_BUCKET}/{object_name}...")
    
    with tqdm(total=file_size, unit='B', unit_scale=True, desc=filename) as pbar:
        s3.upload_file(
            file_path, 
            MINIO_BUCKET, 
            object_name,
            Callback=lambda bytes_transferred: pbar.update(bytes_transferred)
        )
    
    print("Upload complete.")

def main():
    file_to_upload = None
    
    # If a specific file is passed via arguments
    if len(sys.argv) > 1:
        file_to_upload = sys.argv[1]
    else:
        # Auto-detect the most recent dump file in the directory
        dumps = glob.glob("pqrs_dump_*.sql")
        if not dumps:
            print("No dump files found in the current directory. Please specify a file or run dump_db.py first.")
            sys.exit(1)
        file_to_upload = max(dumps, key=os.path.getctime)
        print(f"Auto-selected latest dump file: {file_to_upload}")

    try:
        upload_to_minio(file_to_upload)
        # Clean up local file after successful upload
        if os.path.exists(file_to_upload):
            os.remove(file_to_upload)
            print(f"Local dump file removed: {file_to_upload}")
    except Exception as e:
        print(f"An error occurred during upload: {e}")

if __name__ == "__main__":
    main()
