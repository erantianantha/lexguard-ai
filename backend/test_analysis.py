import asyncio
from app.services.analysis_engine import AnalysisEngine

async def test():
    engine = AnalysisEngine()
    try:
        clauses = await engine.extract_clauses("This is a rental agreement. Section 1: Rent is $500.", "chunk_1")
        print("Clauses extracted:", clauses)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
