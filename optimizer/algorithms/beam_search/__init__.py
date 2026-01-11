import dataclasses
import random
import uuid
from collections.abc import Iterable
from typing import NamedTuple

from optimizer.talents.player_choice import PlayerTalentTree, ITalentStringProvider
from player import Player
from simc import SimRunner, SimInput, TalentsRecord, SimOutput
from talents.models import ClassTalentForest


@dataclasses.dataclass
class BeamSearchConfig:
    beam_width: int = 10
    max_explorations_per_candidate: int = 10


@dataclasses.dataclass
class BestTalentTreeResult:
    best_class_tree_result: ITalentStringProvider
    best_spec_tree_result: ITalentStringProvider
    best_hero_tree_result: ITalentStringProvider


@dataclasses.dataclass
class BeamSearchOptimizationResult:
    best_tree_result: BestTalentTreeResult | None = None
    best_dps: float = 0.0


@dataclasses.dataclass
class LockedTalentTrees:
    def __init__(
        self,
        locked_class_tree: ITalentStringProvider | None = None,
        locked_spec_tree: ITalentStringProvider | None = None,
        locked_hero_tree: ITalentStringProvider | None = None,
    ):
        self.locked_class_tree = locked_class_tree
        self.locked_spec_tree = locked_spec_tree
        self.locked_hero_tree = locked_hero_tree


class NodeChoicePair(NamedTuple):
    node_id: str
    choice_index: int


class TalentBlockList:
    def __init__(self, blocked_spec_talents: Iterable[NodeChoicePair] | None = None):
        self.blocked_spec_talents: set[NodeChoicePair] = set(blocked_spec_talents or [])


def _make_talents_record(
        locked_talent_trees: LockedTalentTrees,
        class_talents: ITalentStringProvider | None = None,
        spec_talents: ITalentStringProvider | None = None,
        hero_talents: ITalentStringProvider | None = None,
) -> TalentsRecord:
    if spec_talents is None and locked_talent_trees.locked_spec_tree is None:
        raise ValueError("Spec talent tree is required. Consider providing a locked fallback.")
    if class_talents is None and locked_talent_trees.locked_class_tree is None:
        raise ValueError("Class talent tree is required. Consider providing a locked fallback.")
    if hero_talents is None and locked_talent_trees.locked_hero_tree is None:
        raise ValueError("Hero talent tree is required. Consider providing a locked fallback.")
    return TalentsRecord(
        # Pyright has false positives below which are checked by the conditions above
        class_talents=class_talents or locked_talent_trees.locked_class_tree,  # type: ignore
        spec_talents=spec_talents or locked_talent_trees.locked_spec_tree,  # type: ignore
        hero_talents=hero_talents or locked_talent_trees.locked_hero_tree,  # type: ignore
    )


class BeamSearchOptimizer:
    def __init__(self, sim_runner: SimRunner, config: BeamSearchConfig | None = None):
        self._sim_runner = sim_runner
        self._config = config or BeamSearchConfig()

    def _run_sim(
        self, player: Player, talents_record: TalentsRecord
    ) -> SimOutput | None:
        return self._sim_runner.run_simulation(
            SimInput(
                template_str=None,
                talents=talents_record,
                output_name=f"beam_search_{str(uuid.uuid4())}",
                name=player.name,
                level=player.level,
                race=player.race,
            )
        )

    def beam_search_optimal_talents(
        self,
        forest_template: ClassTalentForest,
        player: Player,
        locked_talent_trees: LockedTalentTrees | None = None,
        talent_block_list: TalentBlockList | None = None,
    ) -> BeamSearchOptimizationResult:
        locked_talent_trees = locked_talent_trees or LockedTalentTrees()
        talent_block_list = talent_block_list or TalentBlockList()

        spec_tree = PlayerTalentTree(
            forest_template.spec_tree, player.get_available_spec_talent_points()
        )
        spec_tree.skill_all_nodes(
            {
                (entry.node_id, entry.choice_index)
                for entry in talent_block_list.blocked_spec_talents
            }
        )

        base_output = self._run_sim(
            player,
            _make_talents_record(
                locked_talent_trees, None, spec_tree, None
            ),
        )
        if not base_output:
            raise RuntimeError("Initial sim failed")
        dps_by_talent_str: dict[str, float] = {
            spec_tree.to_talent_string(): base_output.dps
        }

        beam: list[PlayerTalentTree] = [spec_tree]
        best_dps: float = 0.0
        best_tree_so_far: PlayerTalentTree | None = None
        iteration = 0
        while beam:
            print(f"Iteration {iteration + 1}")
            iteration += 1
            candidates: list[tuple[PlayerTalentTree, float]] = []
            has_new_candidates = False
            for tree in beam:
                if tree.get_total_points_spent() <= tree.get_total_points_available():
                    tree_dps = dps_by_talent_str[tree.to_talent_string()]
                    candidates.append(
                        (tree, tree_dps)
                    )
                    if tree_dps > best_dps:
                        best_tree_so_far = tree
                        best_dps = tree_dps
                    continue  # Already evaluated, but valid so keep in candidates
                decrementable_nodes = tree.find_nodes_to_decrement()
                random.shuffle(decrementable_nodes)
                for node_id, choice_index in decrementable_nodes[
                    : self._config.max_explorations_per_candidate
                ]:
                    new_tree = tree.copy()
                    new_tree.decrement_node(node_id, choice_index)
                    spec_talent_str = new_tree.to_talent_string()
                    if spec_talent_str in dps_by_talent_str:
                        print("  Skipping already evaluated talent tree")
                        continue  # Exact tree has already been evaluated
                    sim_result = self._run_sim(
                        player,
                        _make_talents_record(locked_talent_trees, None, new_tree, None),
                    )
                    if sim_result is None:
                        continue  # Simulation failed
                    dps_by_talent_str[spec_talent_str] = sim_result.dps
                    candidates.append((new_tree, sim_result.dps))
                    has_new_candidates = True
                    print(
                        f"  DPS:{sim_result.dps}, Talents ({new_tree.get_total_points_spent()} / {new_tree.get_total_points_available()}): {spec_talent_str[:100]}..."
                    )
                    if (
                        sim_result.dps > best_dps
                        and new_tree.get_total_points_spent()
                        <= new_tree.get_total_points_available()
                    ):
                        best_dps = sim_result.dps
                        best_tree_so_far = new_tree
                        print(f"  New valid best DPS found: {best_dps}")
            if not has_new_candidates:
                print("No new candidates found in this iteration, stopping.")
                break
            # Select top beam_width candidates
            candidates.sort(key=lambda x: x[1], reverse=True)
            print(f"Top candidates this iteration:")
            for i, (tree, dps) in enumerate(candidates[: self._config.beam_width]):
                talent_str = tree.to_talent_string()
                print(
                    f"  Rank {i + 1}: DPS:{dps}, Talents ({tree.get_total_points_spent()} / {tree.get_total_points_available()}): {talent_str}"
                )
            beam = [tree for (tree, dps) in candidates[: self._config.beam_width]]
            if not beam:
                print("No more candidates to explore, stopping.")
                break
        if (
            locked_talent_trees.locked_class_tree is not None
            and best_tree_so_far is not None
            and locked_talent_trees.locked_hero_tree is not None
        ):
            best_tree_result = BestTalentTreeResult(
                best_class_tree_result=locked_talent_trees.locked_class_tree,
                best_spec_tree_result=best_tree_so_far,
                best_hero_tree_result=locked_talent_trees.locked_hero_tree,
            )
        else:
            best_tree_result = None
        return BeamSearchOptimizationResult(
            best_tree_result=best_tree_result,
            best_dps=best_dps,
        )
