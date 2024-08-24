from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import cups
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing_extensions import Annotated

templates = Jinja2Templates(directory="templates")

documents = Path("documents")
documents.mkdir(exist_ok=True)
conn = cups.Connection()
printer = conn.getDefault()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# https://www.rfc-editor.org/rfc/rfc2911
cups_job_states = {
    3: "⌛️",  # "pending",
    4: "pending-held",
    5: "🖨️",  # "processing",
    6: "processing-stopped",
    7: "🛑",  # "canceled",
    8: "🛑",  # "aborted",
    9: "✅",  # completed
}


def timestamp_to_str(timestamp: int = None):
    if timestamp is None:
        return "not finished"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


@app.post("/print", response_class=HTMLResponse)
async def print_file(
    file: UploadFile = File(),
    copies: Annotated[int, Form()] = 1,
    pages: Annotated[str, Form()] = "",
    number_up: Annotated[int, Form()] = 1,
    page_set: Annotated[str, Form()] = "all",
    scale_to_fit: Annotated[bool, Form()] = False,
    sides: Annotated[str, Form()] = "one-sided",
):
    if file.content_type != "application/pdf":
        return '<div class="alert alert-danger" role="alert">Only PDF files are allowed</div>'

    options = {"copies": str(copies)}

    if pages != "":
        options["pages"] = pages

    if number_up != 1:
        options["number-up"] = str(number_up)

    if page_set != "all":
        options["page-set"] = page_set

    if scale_to_fit:
        options["fit-to-page"] = "true"

    options["sides"] = sides

    print(file.filename, copies, pages)
    with TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / file.filename
        with file_path.open("wb") as buffer:
            buffer.write(file.file.read())

        conn.printFile(
            printer,
            str(file_path),
            "",
            options,
        )

    return f'<div class="alert alert-primary" role="alert">File "{file.filename}" sent to printer</div>'

    return RedirectResponse(url="/", status_code=303)


@app.get("/")
async def main(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/queue")
async def queue(request: Request):
    queue = conn.getJobs(which_jobs="all")

    jobs = []
    for job_id in list(reversed(queue.keys()))[0:15]:
        job = conn.getJobAttributes(job_id)
        jobs.append(
            {
                "id": job_id,
                "status": cups_job_states[job["job-state"]],
                "time": timestamp_to_str(job["time-at-completed"]),
            }
        )

    return templates.TemplateResponse(
        request=request, name="queue.html", context={"jobs": jobs}
    )


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    printer_info = conn.getPrinterAttributes(printer)

    return f"""
    <b>{printer_info['printer-info']}</b>
    </div>
    """
