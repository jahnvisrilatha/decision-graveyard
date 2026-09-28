import os
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from agent.decision_agent import DecisionAgent

agent = DecisionAgent()
print("Running analyze_proposal('P001')...")
report = agent.analyze_proposal('P001')
print("Report proposal_id:", report.proposal_id)
print("Report recalled_historical_memories len:", len(report.recalled_historical_memories))
if report.recalled_historical_memories:
    print("First memory in report:", report.recalled_historical_memories[0][:150])
else:
    print("Report recalled_historical_memories is EMPTY!")
