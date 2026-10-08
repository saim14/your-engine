import os
import unittest
from unittest.mock import patch

from thinkgate.production import PilotGateway


class ProductionGatewayTests(unittest.TestCase):
    def setUp(self):
        self.gateway = PilotGateway()

    @patch.dict(os.environ, {}, clear=True)
    def test_sandbox_mode_when_no_customer_keys_configured(self):
        context = self.gateway.authenticate(None)
        self.assertTrue(context.sandbox)
        self.assertEqual(context.customer_id, "sandbox")

    @patch.dict(os.environ, {"THINKGATE_CUSTOMER_KEYS": "acme:secret-key"}, clear=True)
    def test_valid_customer_key_authenticates(self):
        context = self.gateway.authenticate("secret-key")
        self.assertFalse(context.sandbox)
        self.assertEqual(context.customer_id, "acme")

    @patch.dict(os.environ, {"THINKGATE_CUSTOMER_KEYS": "acme:secret-key"}, clear=True)
    def test_invalid_customer_key_rejected(self):
        with self.assertRaises(PermissionError):
            self.gateway.authenticate("wrong-key")

    @patch.dict(os.environ, {"THINKGATE_RATE_LIMIT_PER_MINUTE": "2"}, clear=True)
    def test_rate_limit_is_enforced(self):
        self.gateway.enforce_rate_limit("acme")
        self.gateway.enforce_rate_limit("acme")
        with self.assertRaises(RuntimeError):
            self.gateway.enforce_rate_limit("acme")

    def test_stop_decision_updates_usage(self):
        result = self.gateway.make_decision(
            customer_id="acme",
            predicted_gain=0.01,
            next_step_cost=0.10,
            margin=0.0,
            step_index=1,
            max_steps=4,
        )
        self.assertEqual(result["decision"], "STOP")
        usage = self.gateway.usage("acme")
        self.assertEqual(usage["requests"], 1)
        self.assertEqual(usage["stop"], 1)
        self.assertGreater(usage["estimated_avoided_cost"], 0)

    def test_continue_decision_updates_usage(self):
        result = self.gateway.make_decision(
            customer_id="acme",
            predicted_gain=0.30,
            next_step_cost=0.05,
            margin=0.0,
            step_index=1,
            max_steps=4,
        )
        self.assertEqual(result["decision"], "CONTINUE")
        usage = self.gateway.usage("acme")
        self.assertEqual(usage["continue"], 1)
        self.assertEqual(usage["estimated_avoided_cost"], 0.0)

    def test_max_steps_forces_stop(self):
        result = self.gateway.make_decision(
            customer_id="acme",
            predicted_gain=0.90,
            next_step_cost=0.01,
            margin=0.0,
            step_index=4,
            max_steps=4,
        )
        self.assertEqual(result["decision"], "STOP")
        self.assertEqual(result["reason"], "max_steps_reached")


if __name__ == "__main__":
    unittest.main()
