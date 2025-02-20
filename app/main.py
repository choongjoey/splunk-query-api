from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
import time
import datetime
import logging

class SearchRequest(BaseModel):
    search_term: str
    index: str | None = None
    latest_time: str | None = None
    earliest_time: str | None = None
    search_date: str | None = None

app = FastAPI()
logger = logging.getLogger('uvicorn.error')

SPLUNK_HOST = os.environ.get('SPLUNK_HOST')
SPLUNK_TOKEN = os.environ.get('SPLUNK_TOKEN')

API_URL = f"{SPLUNK_HOST}/services/search/jobs?output_mode=json"
STATUS_API_URL = f"{SPLUNK_HOST}/services/search/jobs/{{sid}}?output_mode=json"
RESULTS_API_URL = f"{SPLUNK_HOST}/services/search/jobs/{{sid}}/results?output_mode=json"

HEADERS = {
    "Authorization": SPLUNK_TOKEN,
    "Content-Type": "application/x-www-form-urlencoded"
}

MAX_RETRIES = 30  # Maximum number of status check retries
RETRY_DELAY = 1  # Delay (in seconds) between retries

@app.post("/search")
def trigger_search(request: SearchRequest):
    try:
        # Construct search query
        search_index = request.index
        if request.index is None:
            search_index = "test_index_01"

        latest_time = request.latest_time or ""
        earliest_time = request.earliest_time or "0"

        if request.search_date is not None:
            request_date_start= datetime.datetime.fromisoformat(request.search_date)
            request_date_end = request_date_start + datetime.timedelta(days=1)

            earliest_time = request_date_start.timestamp()
            latest_time = request_date_end.timestamp()


        search_query = f"search index=\"{search_index}\" {request.search_term}"
        payload = {
            "search": search_query,
            "latest_time": latest_time,
            "earliest_time": earliest_time
        }

        logger.info(f"Search payload: {payload}")
        
        response = requests.post(API_URL, data=payload, headers=HEADERS, verify=False)
        response_data = response.json()
        
        if response.status_code == 201 and "sid" in response_data:
            sid = response_data["sid"]

            logger.info(f"Search job created with SID: {sid}")

            # Poll for search job status
            for _ in range(MAX_RETRIES):
                status_response = requests.get(STATUS_API_URL.format(sid=sid), headers=HEADERS, verify=False)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    dispatch_state = status_data.get("entry", [{}])[0].get("content", {}).get("dispatchState", "")
                    logger.info(f"Search job status: {dispatch_state}")
                    
                    if dispatch_state == "DONE":
                        break
                retryDelaySeconds = RETRY_DELAY * _;
                logger.info(f"Retrying in {retryDelaySeconds} seconds")
                time.sleep(retryDelaySeconds)
            else:
                raise HTTPException(status_code=408, detail="Search job did not complete in time")
            
            results_response = requests.get(RESULTS_API_URL.format(sid=sid), headers=HEADERS, verify=False)

            if results_response.status_code == 200:
                logger.info(f"Success retrieving {sid}, returning results")
                return results_response.json()
            else:
                logger.info(f"Not successful retrieving {sid}, returning error: {results_response.status_code}")
                raise HTTPException(status_code=results_response.status_code, detail=results_response.json())
        
        raise HTTPException(status_code=response.status_code, detail=response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
