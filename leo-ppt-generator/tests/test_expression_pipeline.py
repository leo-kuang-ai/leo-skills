import unittest
from leo_ppt_generator.application.expression_pipeline import (
    ExpressionPipelineError, PipelineRequest, run_expression_pipeline,
)

class ExpressionPipelineTests(unittest.TestCase):
    def test_empty_pack_fails_closed(self):
        with self.assertRaises(ExpressionPipelineError):
            run_expression_pipeline(PipelineRequest({}, {}))

class ExpressionRouteTests(unittest.TestCase):
    def test_route_rejects_invalid_request(self):
        from leo_ppt_generator.application.routes import generate_expression, RouteContractError
        with self.assertRaises(RouteContractError):
            generate_expression(None)

class SelectionDigestTests(unittest.TestCase):
    def test_digest_is_order_independent(self):
        from leo_ppt_generator.application.expression_pipeline import selection_digest
        a = {"p2": {"layout_id":"b", "binding_digest":"2"}, "p1": {"layout_id":"a", "binding_digest":"1"}}
        b = {"p1": {"layout_id":"a", "binding_digest":"1"}, "p2": {"layout_id":"b", "binding_digest":"2"}}
        self.assertEqual(selection_digest(a), selection_digest(b))

class SelectionFreezeVerificationTests(unittest.TestCase):
    def test_tampered_selection_digest_fails(self):
        from leo_ppt_generator.application.expression_pipeline import verify_selection_frozen, ExpressionPipelineError
        with self.assertRaises(ExpressionPipelineError):
            verify_selection_frozen({"selection": {}, "selection_frozen": True, "selection_digest": "bad"})

class TaskLocalProposalTests(unittest.TestCase):
    def test_proposal_digest_and_scope(self):
        from leo_ppt_generator.task_local_layout_proposals import proposal_digest, validate_task_local_proposal
        proposal = {"run_scope":"r1", "base_asset":"layout/a", "patch":[{"op":"set_slot", "path":"slots/title"}]}
        proposal["proposal_digest"] = proposal_digest(proposal)
        validate_task_local_proposal(proposal, run_scope="r1", allowed_assets={"layout/a"})

    def test_proposal_rejects_fact_deletion(self):
        from leo_ppt_generator.task_local_layout_proposals import proposal_digest, validate_task_local_proposal, ProposalError
        proposal = {"run_scope":"r1", "base_asset":"layout/a", "patch":[{"op":"set_slot", "delete_facts":True}]}
        proposal["proposal_digest"] = proposal_digest(proposal)
        with self.assertRaises(ProposalError):
            validate_task_local_proposal(proposal, run_scope="r1", allowed_assets={"layout/a"})
