from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os

class SearchRequest(BaseModel):
    search_term: str
    index: str | None = None

app = FastAPI()

SPLUNK_HOST = os.environ.get('SPLUNK_HOST')
SPLUNK_TOKEN = os.environ.get('SPLUNK_TOKEN')

API_URL = f"{SPLUNK_HOST}/services/search/jobs?output_mode=json"
RESULTS_API_URL = f"{SPLUNK_HOST}/services/search/jobs/{{sid}}/results?output_mode=json"

HEADERS = {
    "Authorization": SPLUNK_TOKEN,
    "Content-Type": "application/x-www-form-urlencoded"
}

@app.post("/search")
def trigger_search(request: SearchRequest):
    try:
        # Construct search query
        search_index = request.index
        if request.index is None:
            search_index = "test_index_01"

        search_query = f"search index=\"{search_index}\" {request.search_term}"
        payload = {
            "search": search_query,
            "latest_time": "",
            "earliest_time": "0"
        }
        
        response = requests.post(API_URL, data=payload, headers=HEADERS, verify=False)
        response_data = response.json()
        
        if response.status_code == 201 and "sid" in response_data:
            sid = response_data["sid"]

            print(f"Search job created with SID: {sid}")

            results_response = requests.get(RESULTS_API_URL.format(sid=sid), headers=HEADERS, verify=False)
            return results_response.json()
        
        raise HTTPException(status_code=response.status_code, detail=response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
