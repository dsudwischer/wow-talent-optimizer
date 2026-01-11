import abc
import random
from collections import defaultdict
from collections.abc import Container
from dataclasses import dataclass

from talents.models import TalentTreeNode, TalentTree


class DecrementNotPossible(Exception):
    def __init__(
        self,
        current_node: "PlayerTalentNodeSelection",
        choice_index: int,
        player_tree: "PlayerTalentTree",
    ):
        self.current_node = current_node
        self.choice_index = choice_index
        self.player_tree = player_tree


@dataclass
class PlayerTalentNodeSelection:
    node_reference: TalentTreeNode
    points_spent_by_choice_index: list[int]

    def __init__(
        self, node_reference: TalentTreeNode, points_spent_by_choice_index: list[int]
    ):
        if len(points_spent_by_choice_index) != len(node_reference.choices):
            raise ValueError(
                "points_spent_by_choice_index length must match number of choices in node_reference"
            )
        self.node_reference = node_reference
        self.points_spent_by_choice_index = points_spent_by_choice_index

    def has_fully_skilled_choice(self) -> bool:
        return any(
            choice.max_points == points_spent
            for (choice, points_spent) in zip(
                self.node_reference.choices, self.points_spent_by_choice_index
            )
        )

    def holds_talent_points(self) -> bool:
        return any(self.points_spent_by_choice_index)

    def get_choice_indices_with_points(self) -> list[int]:
        return [
            i
            for i, points in enumerate(self.points_spent_by_choice_index)
            if points > 0
        ]

    def to_talent_string(self) -> str:
        return "/".join(
            f"{choice.talent_name}:{points_spent}"
            for (choice, points_spent) in zip(
                self.node_reference.choices, self.points_spent_by_choice_index
            )
            if points_spent > 0
        )

    def violates_single_choice_rule(self) -> bool:
        skilled_choices = sum(
            1 for points in self.points_spent_by_choice_index if points > 0
        )
        return skilled_choices > 1

    def use_point_for_choice(
        self, choice_index: int, bypass_single_choice: bool
    ) -> None:
        if choice_index < 0 or choice_index >= len(self.node_reference.choices):
            raise ValueError("Invalid choice index")
        if (not bypass_single_choice) and self.violates_single_choice_rule():
            raise ValueError("Cannot use point, single choice rule violated")
        if (
            self.points_spent_by_choice_index[choice_index]
            >= self.node_reference.choices[choice_index].max_points
        ):
            raise ValueError("Cannot use point, max points reached for this choice")
        self.points_spent_by_choice_index[choice_index] += 1

    def remove_point_from_choice(self, choice_index: int) -> None:
        if choice_index < 0 or choice_index >= len(self.node_reference.choices):
            raise ValueError("Invalid choice index")
        if self.points_spent_by_choice_index[choice_index] <= 0:
            raise ValueError("Cannot remove point, no points spent for this choice")
        self.points_spent_by_choice_index[choice_index] -= 1

    def reset_points(self) -> None:
        for i in range(len(self.points_spent_by_choice_index)):
            self.points_spent_by_choice_index[i] = 0

    def fully_skill_choice(self, choice_index: int, bypass_single_choice: bool) -> int:
        # Returns number of points added
        if choice_index < 0 or choice_index >= len(self.node_reference.choices):
            raise ValueError("Invalid choice index")
        if (not bypass_single_choice) and self.violates_single_choice_rule():
            raise ValueError("Cannot fully skill choice, single choice rule violated")
        current = self.points_spent_by_choice_index[choice_index]
        max_points = self.node_reference.choices[choice_index].max_points
        self.points_spent_by_choice_index[choice_index] = max_points
        return max_points - current

    def unskill_choice(self, choice_index: int) -> int:
        # Returns number of points removed
        if choice_index < 0 or choice_index >= len(self.node_reference.choices):
            raise ValueError("Invalid choice index")
        current = self.points_spent_by_choice_index[choice_index]
        self.points_spent_by_choice_index[choice_index] = 0
        return current


class ITalentStringProvider(abc.ABC):
    @abc.abstractmethod
    def to_talent_string(self) -> str:
        pass


class FixedTalentStringProvider(ITalentStringProvider):
    def __init__(self, talent_str: str):
        self._talent_str = talent_str

    def to_talent_string(self) -> str:
        return self._talent_str


class PlayerTalentTree(ITalentStringProvider):
    def __init__(self, tree_template: TalentTree, max_points_available: int):
        self._tree_template = tree_template
        self._template_node_by_id: dict[str, TalentTreeNode] = {
            node.node_id: node for node in tree_template.nodes
        }
        self._max_points_available: int = max_points_available
        self._selection_by_node_id: dict[str, PlayerTalentNodeSelection] = (
            self._get_empty_selections_dict()
        )
        self._spent_points_by_gate: defaultdict[int, int] = defaultdict(int)

    def copy(self) -> "PlayerTalentTree":
        new_tree = PlayerTalentTree(self._tree_template, self._max_points_available)
        for node_id, selection in self._selection_by_node_id.items():
            new_selection = PlayerTalentNodeSelection(
                node_reference=selection.node_reference,
                points_spent_by_choice_index=selection.points_spent_by_choice_index.copy(),
            )
            new_tree._selection_by_node_id[node_id] = new_selection
        new_tree._spent_points_by_gate = self._spent_points_by_gate.copy()
        return new_tree

    def _get_empty_selections_dict(self):
        selection_by_node_id: dict[str, PlayerTalentNodeSelection] = {}
        for node in self._tree_template.nodes:
            selection = PlayerTalentNodeSelection(
                node_reference=node,
                points_spent_by_choice_index=[0 for _ in node.choices],
            )
            selection_by_node_id[node.node_id] = selection
        return selection_by_node_id

    def skill_all_nodes(self, except_for: Container[tuple[str, int]]) -> None:
        for selection in self._selection_by_node_id.values():
            for i, choice in enumerate(selection.node_reference.choices):
                if (selection.node_reference.node_id, i) in except_for:
                    print(
                        f"Skipping talent {selection.node_reference.choices[i].talent_name} due to blocklist"
                    )
                    continue
                selection.points_spent_by_choice_index[i] = choice.max_points
                self._spent_points_by_gate[selection.node_reference.gate_id] += (
                    selection.points_spent_by_choice_index[i]
                )

    def to_talent_string(self) -> str:
        talent_strings: list[str] = []
        for node in sorted(
            self._selection_by_node_id.values(),
            key=lambda n: self._template_node_by_id[n.node_reference.node_id].sort_key,
        ):
            node_talent_string = node.to_talent_string()
            if node_talent_string:
                talent_strings.append(node_talent_string)
        return "/".join(talent_strings)

    def can_node_be_decremented(self, node_id: str, choice_index: int) -> bool:
        try:
            if node_id not in self._selection_by_node_id:
                raise ValueError(f"Invalid node ID: {node_id}")
            node_selection = self._selection_by_node_id[node_id]
            # Can only return nodes that are currently skilled
            if not node_selection.holds_talent_points():
                raise DecrementNotPossible(node_selection, choice_index, self)
            choice_indices_with_points = node_selection.get_choice_indices_with_points()
            # Can only decrement if the specified choice index has points
            if choice_index not in choice_indices_with_points:
                raise DecrementNotPossible(node_selection, choice_index, self)
            # Can only decrement if (every child node either has no points or has another valid parent) or (if there is an active single choice violation on this node)
            is_single_choice_rule_violated = (
                node_selection.violates_single_choice_rule()
            )
            child_nodes = self._template_node_by_id[node_id].child_nodes
            for child_node in child_nodes:
                child_node_selection = self._selection_by_node_id[child_node.node_id]
                if child_node_selection.holds_talent_points():
                    has_valid_parent = False
                    for parent_node in child_node_selection.node_reference.parent_nodes:
                        if parent_node.node_id == node_id:
                            continue
                        parent_selection = self._selection_by_node_id[
                            parent_node.node_id
                        ]
                        if parent_selection.has_fully_skilled_choice():
                            has_valid_parent = True
                            break
                    if not (has_valid_parent or is_single_choice_rule_violated):
                        raise DecrementNotPossible(node_selection, choice_index, self)
            # Can only decrement nodes if that does not violate gate requirements, i.e. if there are enough points in lower gates
            running_total_spent = 0
            for gate in sorted(
                self._tree_template.gate_info.gates, key=lambda g: g.gate_id
            ):
                points_needed_below = gate.points_required_below
                points_in_gate = self._spent_points_by_gate.get(gate.gate_id, 0)
                if (
                    gate.gate_id > node_selection.node_reference.gate_id
                    and points_needed_below >= running_total_spent
                ):
                    raise DecrementNotPossible(node_selection, choice_index, self)
                running_total_spent += points_in_gate
        except DecrementNotPossible:
            return False
        return True

    def decrement_node(self, node_id: str, choice_index: int) -> None:
        # Does not check if decrement is valid, use can_node_be_decremented first
        node_selection = self._selection_by_node_id[node_id]
        node_selection.remove_point_from_choice(choice_index)
        gate_id = node_selection.node_reference.gate_id
        self._spent_points_by_gate[gate_id] -= 1

    def find_nodes_to_decrement(self) -> list[tuple[str, int]]:
        # Finds all nodes and choice indices that can be decremented
        candidates: list[tuple[str, int]] = []
        violating_node_ids = self.get_node_ids_with_violated_single_choice()
        candidate_node_ids = list(self._selection_by_node_id.keys())
        random.shuffle(candidate_node_ids)
        # Prioritize fixing violating nodes
        candidate_node_ids = violating_node_ids + [
            nid for nid in candidate_node_ids if nid not in violating_node_ids
        ]
        for node_id in candidate_node_ids:
            node_selection = self._selection_by_node_id[node_id]
            choice_indices_with_points = node_selection.get_choice_indices_with_points()
            choice_indices_copy = choice_indices_with_points.copy()
            random.shuffle(choice_indices_copy)
            for choice_index in choice_indices_copy:
                if self.can_node_be_decremented(node_id, choice_index):
                    candidates.append((node_id, choice_index))
        return candidates

    def get_total_points_spent(self) -> int:
        return sum(
            sum(selection.points_spent_by_choice_index)
            for selection in self._selection_by_node_id.values()
        )

    def get_total_points_available(self) -> int:
        return self._max_points_available

    def get_node_ids_with_violated_single_choice(self) -> list[str]:
        return [
            node_id
            for node_id, selection in self._selection_by_node_id.items()
            if selection.violates_single_choice_rule()
        ]

    def __str__(self):
        return self.to_talent_string()
