import unittest

from edge_auction import (
    Allocation,
    DomainConfig,
    DoubleAuctionMechanism,
    EdgeServer,
    MechanismResult,
    UserDemand,
)


class DoubleAuctionMechanismTest(unittest.TestCase):
    def setUp(self) -> None:
        self.domains = [
            DomainConfig(
                name="default",
                distance_weight=0.8,
                handoff_weight=0.5,
                proximity_weight=0.3,
                clearing_discount=0.9,
            ),
            DomainConfig(
                name="vehicular",
                distance_weight=1.2,
                handoff_weight=1.5,
                proximity_weight=0.6,
                clearing_discount=0.8,
            ),
        ]
        self.mechanism = DoubleAuctionMechanism(self.domains)
        self.servers = [
            EdgeServer(
                id="edge-1",
                location=(0.0, 0.0),
                capacity=2,
                base_cost=3.0,
                distance_rate=0.4,
                handoff_cost_factor=0.2,
                proximity_preference=0.5,
            ),
            EdgeServer(
                id="edge-2",
                location=(5.0, 0.0),
                capacity=1,
                base_cost=2.5,
                distance_rate=0.6,
                handoff_cost_factor=0.3,
                proximity_preference=0.8,
            ),
        ]
        self.users = [
            UserDemand(
                id="user-a",
                location=(0.5, 0.5),
                base_value=15.0,
                handoff_cost=1.0,
                distance_sensitivity=0.7,
                domain="default",
            ),
            UserDemand(
                id="user-b",
                location=(4.7, 0.2),
                base_value=14.0,
                handoff_cost=0.5,
                distance_sensitivity=0.6,
                domain="vehicular",
            ),
            UserDemand(
                id="user-c",
                location=(1.0, 0.8),
                base_value=12.0,
                handoff_cost=2.0,
                distance_sensitivity=0.9,
                domain="default",
            ),
        ]

    def test_allocations_are_generated_with_dynamic_pricing(self) -> None:
        result = self.mechanism.run(self.users, self.servers)

        self.assertIsInstance(result, MechanismResult)
        self.assertTrue(result.allocations)
        self.assertLessEqual(len(result.allocations), 3)

        for allocation in result.allocations:
            self.assertIsInstance(allocation, Allocation)
            self.assertGreater(allocation.surplus, 0.0)
            self.assertGreater(allocation.clearing_price, 0.0)

        # Users closest to their respective servers should be prioritised
        assigned_ids = {allocation.user_id for allocation in result.allocations}
        self.assertIn("user-a", assigned_ids)
        self.assertIn("user-b", assigned_ids)

    def test_capacity_limits_create_unmatched_users(self) -> None:
        limited_servers = [
            EdgeServer(
                id="edge-limited",
                location=(0.0, 0.0),
                capacity=1,
                base_cost=4.0,
                distance_rate=0.5,
                handoff_cost_factor=0.2,
                proximity_preference=0.4,
            )
        ]

        result = self.mechanism.run(self.users, limited_servers)
        self.assertGreaterEqual(len(result.unmatched_users), 2)
        self.assertLessEqual(len(result.allocations), 1)


if __name__ == "__main__":
    unittest.main()
