import logging

from escpos_server import printer
from fastapi import FastAPI

logger = logging.getLogger(__name__)
app = FastAPI()


@app.get("/")
async def root():
    status = printer.get_status()

    return {
        "status": {
            "type": status.type,
            "paper_end": status.paper_end,
            "paper_near_end": status.paper_near_end,
        }
    }
