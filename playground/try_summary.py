import asyncio

from dotenv import load_dotenv

load_dotenv()

from pathways.ivf.activities import summarize_labs
from pathways.ivf.models import LabResult

labs = [
    LabResult("estradiol", 850, "pg/mL"),
    LabResult("lh", 5.2, "mIU/mL"),
]
print(asyncio.run(summarize_labs(labs)))
