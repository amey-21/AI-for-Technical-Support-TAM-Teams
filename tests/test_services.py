import unittest
from src.account_brief import get_account_brief
from src.common.models import TicketInput, TriageResult
from src.triage import triage_ticket
from src.main import app

class FakeStructuredLLM:
    enabled = True
    def __init__(self): self.called = False
    def structured(self, system, user, schema):
        self.called = True
        return TriageResult(product_area="untrusted", category="Performance", urgency="P2", reasoning="The model considered the retrieved timeout evidence.", matched_kb_doc=None, recommended_team="untrusted", draft_response="We are investigating the timeout.")

class ServiceTests(unittest.TestCase):
    def test_triage_returns_structured_kb_match(self):
        result = triage_ticket(TicketInput(subject="Pipeline error", body="ERR_CONNECTION_TIMEOUT after 30s in DataBridge Pro."))
        self.assertEqual(result.category, "Performance")
        self.assertIn("performance-and-integrations", result.matched_kb_doc or "")
        self.assertEqual(result.product_area, "DataBridge Pro / Pipeline Monitoring")

    def test_triage_uses_configured_structured_llm_and_retains_grounded_fields(self):
        client = FakeStructuredLLM()
        result = triage_ticket("DataBridge Pro pipeline ERR_CONNECTION_TIMEOUT after 30s.", llm_client=client)
        self.assertTrue(client.called)
        self.assertEqual(result.product_area, "DataBridge Pro / Pipeline Monitoring")
        self.assertIn("performance-and-integrations", result.matched_kb_doc or "")

    def test_missing_account_is_an_empty_state(self):
        self.assertIsNone(get_account_brief("ACC-DOES-NOT-EXIST"))

    def test_streaming_brief_endpoint_has_all_three_sections(self):
        from fastapi.testclient import TestClient
        response = TestClient(app).get("/account-brief/ACC-3336/stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";", 1)[0], "text/event-stream")
        self.assertIn("event: executive_summary", response.text)
        self.assertIn("event: open_risks", response.text)
        self.assertIn("event: talking_points", response.text)

if __name__ == "__main__":
    unittest.main()
