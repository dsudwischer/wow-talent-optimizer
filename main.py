from optimizer.algorithms.beam_search import (
    BeamSearchOptimizer,
    BeamSearchConfig,
    LockedTalentTrees,
    TalentBlockList,
    NodeChoicePair,
)
from player import Player
from simc import SimRunner
from talents.converters.icy_veins import convert
from talents.parsers.icy_veins.models import Class


def main() -> None:
    with open("./tree.json", "r") as f:
        class_data = Class.model_validate_json(f.read())

    iv_devourer = class_data.specs["devourer"]
    devourer = convert(iv_devourer)
    optimizer = BeamSearchOptimizer(
        sim_runner=SimRunner(),
        config=BeamSearchConfig(beam_width=10, max_explorations_per_candidate=25),
    )
    result = optimizer.beam_search_optimal_talents(
        devourer,
        Player(
            name="Desevourer",
            level=80,
            race="night_elf",
        ),
        locked_talent_trees=LockedTalentTrees(
            locked_class_tree="vengeful_retreat:1/unrestrained_fury:1/aura_of_pain:1/internal_struggle:1/furious:1/final_breath:1/remorseless:1/soul_splitter:2",
            locked_spec_tree=None,
            locked_hero_tree="demonsurge:1/focused_hatred:1/improved_soul_rending:1/blind_focus:1/violent_transformation:1/enduring_torment:1/undying_embers:1/student_of_suffering:1/monster_rising:1/volatile_instinct:1/demonic_intensity:1",
        ),
        talent_block_list=TalentBlockList(
            blocked_spec_talents=[
                #NodeChoicePair(node_id=node.node_id, choice_index=choice_idx)
                #for node in devourer.spec_tree.nodes
                #for choice_idx, choice in enumerate(node.choices)
                #if choice.talent_name
                #not in "spec_talents=singed_spirit:1/calamitous:1/void_ray:1/sweet_suffering:2/collapsing_star:1/void_metamorphosis:1/impending_apocalypse:1/soulshaper:1/feast_of_souls:1/soul_immolation:1/moment_of_craving:1/predators_thirst:1/focused_ray:1/gift_of_the_void:1/umbral_blade:1/waste_not:1/entropy:1/soul_glutton:1/hungering_slash:1/improved_consume:1/sweet_release:2/duty_eternal:1/spontaneous_immolation:1/the_hunt:1/demonic_instinct:2/devourers_bite:1/singular_strikes:1/voidrush:1/voidpurge:1"
            ]
        ),
    )
    print(
        f"{result.best_dps} dps: {result.best_tree_result.best_spec_tree_result.to_talent_string() if result.best_tree_result else None}"  # type: ignore
    )
    print()


if __name__ == "__main__":
    main()
