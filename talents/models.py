from enum import Enum

from pydantic import BaseModel


class Specialization(str, Enum):
    HAVOC = "havoc"
    DEVOURER = "devourer"
    VENGEANCE = "vengeance"


class ChoiceNodeTalent(BaseModel):
    talent_name: str
    max_points: int


class TalentTreeNode(BaseModel):
    node_id: str
    choices: list[ChoiceNodeTalent]
    gate_id: int
    parent_nodes: list["TalentTreeNode"]
    child_nodes: list["TalentTreeNode"]
    sort_key: str


class Gate(BaseModel):
    gate_id: int
    points_required_below: int


class GateInfo(BaseModel):
    gates: list[Gate]


class TalentTree(BaseModel):
    gate_info: GateInfo
    nodes: list[TalentTreeNode]


class ClassTalentForest(BaseModel):
    spec: Specialization
    spec_tree: TalentTree
