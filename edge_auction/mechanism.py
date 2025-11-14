"""Double auction mechanism that adapts to heterogeneous edge computing domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import dist
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class DomainConfig:
    """Domain-specific configuration used to rebalance bids and asks.

    Parameters
    ----------
    name:
        Identifier for the domain (for example, "ar", "vehicular", or "iot").
    distance_weight:
        Weight applied to geographical distance when adjusting utility and cost.
    handoff_weight:
        Weight applied to the handoff penalty for both demand and supply.
    proximity_weight:
        Weight applied to the server proximity preference.
    clearing_discount:
        Optional multiplicative discount used to dampen clearing prices in domains
        where overbidding is common (e.g. low-latency AR/VR workloads).
    """

    name: str
    distance_weight: float = 1.0
    handoff_weight: float = 1.0
    proximity_weight: float = 1.0
    clearing_discount: float = 1.0


@dataclass(frozen=True)
class UserDemand:
    """Represents a buyer in the double auction."""

    id: str
    location: Sequence[float]
    base_value: float
    handoff_cost: float
    distance_sensitivity: float
    domain: str

    def distance_to(self, server: "EdgeServer") -> float:
        return dist(self.location, server.location)


@dataclass
class EdgeServer:
    """Represents a seller (edge server) in the double auction."""

    id: str
    location: Sequence[float]
    capacity: int
    base_cost: float
    distance_rate: float
    handoff_cost_factor: float
    proximity_preference: float = 1.0

    def distance_to(self, user: UserDemand) -> float:
        return dist(self.location, user.location)

    def proximity_penalty(self, distance: float) -> float:
        """Penalty that increases with distance, scaled by proximity preference."""

        return self.proximity_preference * distance


@dataclass
class Allocation:
    """Represents a clearing match between a user and an edge server."""

    user_id: str
    server_id: str
    clearing_price: float
    surplus: float
    distance: float


@dataclass
class MechanismResult:
    """Aggregated result of a double auction run."""

    allocations: List[Allocation] = field(default_factory=list)
    unmatched_users: List[str] = field(default_factory=list)
    total_surplus: float = 0.0
    total_spend: float = 0.0


class DoubleAuctionMechanism:
    """Generalised double auction for multi-domain edge computing deployments.

    The mechanism reweighs the bids of buyers (users) and asks of sellers (edge
    servers) according to the domain configuration. It implements a greedy
    allocation strategy that favours matches with the highest social surplus
    while respecting edge capacity constraints.
    """

    def __init__(self, domain_configs: Iterable[DomainConfig]):
        self._domain_configs: Dict[str, DomainConfig] = {
            config.name: config for config in domain_configs
        }
        if "default" not in self._domain_configs:
            self._domain_configs["default"] = DomainConfig(name="default")

    def _config_for(self, domain: str) -> DomainConfig:
        return self._domain_configs.get(domain, self._domain_configs["default"])

    def _user_value(self, user: UserDemand, server: EdgeServer) -> float:
        config = self._config_for(user.domain)
        distance = user.distance_to(server)
        distance_penalty = config.distance_weight * user.distance_sensitivity * distance
        handoff_penalty = config.handoff_weight * user.handoff_cost
        proximity_bonus = config.proximity_weight * max(0.0, 1.0 - distance)
        return user.base_value - distance_penalty - handoff_penalty + proximity_bonus

    def _server_cost(self, user: UserDemand, server: EdgeServer) -> float:
        config = self._config_for(user.domain)
        distance = server.distance_to(user)
        distance_component = config.distance_weight * server.distance_rate * distance
        handoff_component = config.handoff_weight * server.handoff_cost_factor * user.handoff_cost
        proximity_component = config.proximity_weight * server.proximity_penalty(distance)
        return server.base_cost + distance_component + handoff_component + proximity_component

    def _clearing_price(
        self, user_value: float, server_cost: float, config: DomainConfig
    ) -> float:
        raw_price = (user_value + server_cost) / 2.0
        return raw_price * config.clearing_discount

    def run(
        self, users: Sequence[UserDemand], servers: Sequence[EdgeServer]
    ) -> MechanismResult:
        """Execute the double auction and return a structured result."""

        candidate_matches = []
        for user in users:
            for server in servers:
                if server.capacity <= 0:
                    continue
                user_value = self._user_value(user, server)
                server_cost = self._server_cost(user, server)
                surplus = user_value - server_cost
                if surplus <= 0:
                    continue
                candidate_matches.append(
                    {
                        "user": user,
                        "server": server,
                        "surplus": surplus,
                        "user_value": user_value,
                        "server_cost": server_cost,
                        "distance": user.distance_to(server),
                    }
                )

        # Sort matches from highest to lowest surplus to maximise total surplus.
        candidate_matches.sort(key=lambda item: item["surplus"], reverse=True)

        result = MechanismResult()
        remaining_capacity = {server.id: server.capacity for server in servers}
        matched_users = set()

        for item in candidate_matches:
            user = item["user"]
            server = item["server"]
            if user.id in matched_users:
                continue
            if remaining_capacity[server.id] <= 0:
                continue

            matched_users.add(user.id)
            remaining_capacity[server.id] -= 1
            config = self._config_for(user.domain)
            clearing_price = self._clearing_price(
                item["user_value"], item["server_cost"], config
            )
            allocation = Allocation(
                user_id=user.id,
                server_id=server.id,
                clearing_price=clearing_price,
                surplus=item["surplus"],
                distance=item["distance"],
            )
            result.allocations.append(allocation)
            result.total_surplus += allocation.surplus
            result.total_spend += allocation.clearing_price

        result.unmatched_users = [user.id for user in users if user.id not in matched_users]
        return result


__all__ = [
    "DomainConfig",
    "UserDemand",
    "EdgeServer",
    "DoubleAuctionMechanism",
    "Allocation",
    "MechanismResult",
]
