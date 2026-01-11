from unittest import case

from talents.models import (
    ClassTalentForest,
    TalentTree,
    GateInfo,
    Gate,
    TalentTreeNode,
    ChoiceNodeTalent,
    Specialization,
)
from talents.parsers.icy_veins.models import (
    Spec as IVSpec,
    RowCheckpoint as IVRowCheckpoint,
    SpecNode as IVSpecNode,
)


def _convert_spec_id(iv_spec_id: int) -> Specialization:
    match iv_spec_id:
        case 577:
            return Specialization.HAVOC
        case 581:
            return Specialization.VENGEANCE
        case 1480:
            return Specialization.DEVOURER
    raise ValueError(f"IVSpec id {iv_spec_id} not recognized")


def _convert_checkpoints(checkpoints: list[IVRowCheckpoint]) -> GateInfo:
    gates: list[Gate] = [Gate(gate_id=0, points_required_below=0)]
    sorted_checkpoints = sorted(checkpoints, key=lambda c: c.row)
    for checkpoint in sorted_checkpoints:
        gate_id = len(gates)
        gates.append(Gate(gate_id=gate_id, points_required_below=checkpoint.points))
    return GateInfo(gates=gates)


def _convert_talent_name(name: str) -> str:
    sb: list[str] = []
    for char in name:
        if ord("a") <= ord(char) <= ord("z"):
            sb.append(char)
        elif ord("A") <= ord(char) <= ord("Z"):
            sb.append(char.lower())
        elif char.isspace():
            sb.append("_")
        else:
            pass  # Do nothing
    return "".join(sb)


class _RowToGateMapper:
    def __init__(self, checkpoints: list[IVRowCheckpoint]):
        self._row_cutoffs: list[tuple[int, int]] = []  # (Row number, Gate ID)
        sorted_checkpoints = sorted(checkpoints, key=lambda c: c.row)
        for checkpoint in sorted_checkpoints:
            gate_id = len(self._row_cutoffs) + 1
            self._row_cutoffs.append((checkpoint.row, gate_id))
            self.max_gate_id = gate_id

    def map(self, row: int) -> int:
        for cutoff_row, gate_id in self._row_cutoffs:
            if row < cutoff_row:  # IV rows are 0 based
                return gate_id - 1
        return self.max_gate_id


def _iv_node_to_node_id(iv_node_id: int) -> str:
    return str(iv_node_id).strip()


def _convert_spec_nodes(
    spec_nodes: list[IVSpecNode], checkpoints: list[IVRowCheckpoint]
) -> list[TalentTreeNode]:
    node_id_to_node: dict[str, TalentTreeNode] = {}
    row_to_gate_mapper: _RowToGateMapper = _RowToGateMapper(checkpoints)
    for iv_node in spec_nodes:
        node_id = _iv_node_to_node_id(iv_node.id)
        node = TalentTreeNode(
            node_id=node_id,
            choices=[
                ChoiceNodeTalent(
                    talent_name=_convert_talent_name(spell.name),
                    max_points=spell.max_ranks,
                )
                for spell in iv_node.spells
            ],
            gate_id=row_to_gate_mapper.map(iv_node.row),
            parent_nodes=[],  # Fill be filled later
            child_nodes=[],  # Will be filled
            sort_key=str(iv_node.row * 100 + iv_node.column),
        )
        node_id_to_node[node_id] = node
    # Populate parent pointers and children pointers
    for iv_child_node in spec_nodes:
        child_node_id = _iv_node_to_node_id(iv_child_node.id)
        child_node = node_id_to_node[child_node_id]
        for iv_parent_node_id in iv_child_node.previous_node_ids:
            parent_node_id = _iv_node_to_node_id(iv_parent_node_id)
            parent_node = node_id_to_node[parent_node_id]
            parent_node.child_nodes.append(child_node)
            child_node.parent_nodes.append(parent_node)
    return list(node_id_to_node.values())


def convert(spec: IVSpec) -> ClassTalentForest:
    return ClassTalentForest(
        spec=_convert_spec_id(spec.id),
        spec_tree=TalentTree(
            gate_info=_convert_checkpoints(spec.spec_checkpoints),
            nodes=_convert_spec_nodes(
                list(spec.spec_nodes.values()), spec.spec_checkpoints
            ),
        ),
    )
